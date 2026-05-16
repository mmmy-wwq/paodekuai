"""
Game server for 跑得快 (Pao De Kuai).

Bridges the WebSocket transport layer to the game state machine.
Coordinates game logic through GameStateManager and room management
through RoomManager. All game decisions are server-authoritative.

Message routing by MsgType:
    JOIN        → register player, broadcast STATE_SYNC
    PLAY        → gsm.play_turn(), broadcast result
    PASS        → gsm.pass_turn(), broadcast result
    DECLARE     → gsm.declare(), broadcast result
    PING        → respond PONG
    START_GAME  → init game, deal cards, broadcast GAME_START
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from server.game_engine.state_machine import GameStateManager, InvalidStateError
from server.game_engine.turn_timer import TurnTimer
from server.network.protocol import (
    MsgType,
    Message,
    cards_from_dicts,
    create_message,
    serialize_message,
    validate_message,
)
from server.network.room_manager import RoomManager, _make_rule_config
from server.network.scores_store import get_all_scores, add_score


class GameServer:
    """WebSocket game server — authoritatively routes messages to game logic.

    Maintains per-room WebSocket registries and coordinates between
    RoomManager (lobby/room management) and GameStateManager (game rules).
    """

    def __init__(self, room_manager: Optional[RoomManager] = None) -> None:
        """Initialize the game server.

        Args:
            room_manager: Existing RoomManager instance, or creates a new one.
        """
        self._rm: RoomManager = room_manager or RoomManager()
        # room_id → {player_id: WebSocket}
        self._room_sockets: Dict[str, Dict[str, WebSocket]] = {}
        # Player-id to room-id reverse lookup for disconnect handling
        self._player_room: Dict[str, str] = {}
        # room_id → TurnTimer for turn timeout
        self._turn_timers: Dict[str, TurnTimer] = {}
        # Reconnection tokens: pid → token (persists across disconnects)
        self._reconnect_tokens: Dict[str, str] = {}
        # Disconnected players: pid → asyncio.TimerHandle for watchdog
        self._disconnect_watchdogs: Dict[str, asyncio.TimerHandle] = {}

    # ── Connection lifecycle ─────────────────────────────────────────────────

    async def handle_connection(
        self, websocket: WebSocket, room_id: str, player_name: str,
        player_count: int = 4, reconnect_id: str = "",
        reconnect_token: str = "",
    ) -> Optional[str]:
        """Accept WebSocket, register player in room, send STATE_SYNC.

        Behaviour by room_id value:
        - ``"lobby"``: Accept without auto-creating a room — client can
          send CREATE_ROOM / JOIN_ROOM messages to manage rooms.
        - Existing room:
            - If ``reconnect_id`` + ``reconnect_token`` match a known
              disconnected player → restore their connection.
            - Otherwise → register as a new player.
        - Non-existent room: Auto-create with the URL room_id as code
          (first player = host).

        Args:
            websocket: The accepted WebSocket connection.
            room_id: Room identifier from the URL path.
            player_name: Display name from query param ``?name=XXX``.
            reconnect_id: Player ID from ``?pid=XXX`` (stored in localStorage).
            reconnect_token: Reconnection token from ``?token=XXX``.

        Returns:
            The generated player_id on success, or None on failure.
        """
        await websocket.accept()

        # ── Lobby: accept without room creation ────────────────────────
        if room_id == "lobby":
            player_id = str(uuid.uuid4())[:8]
            # Track the lobby connection for message handling
            if "lobby" not in self._room_sockets:
                self._room_sockets["lobby"] = {}
            self._room_sockets["lobby"][player_id] = websocket
            self._player_room[player_id] = "lobby"

            connected_msg = create_message(
                MsgType.STATE_SYNC,
                payload={
                    "phase": "LOBBY",
                    "message": "Connected to lobby. Create or join a room.",
                    "player_id": player_id,
                },
            )
            await websocket.send_text(serialize_message(connected_msg))
            return player_id

        # ── Ensure room exists (auto-create if first connection) ────────
        room = await self._rm.get_room(room_id)
        if room is None:
            try:
                room_id = await self._rm.create_room_with_id(
                    room_id=room_id, max_players=player_count
                )
                room = await self._rm.get_room(room_id)
            except Exception:
                await self._send_error(
                    websocket, "ROOM_CREATE_FAILED", "Failed to create room"
                )
                await websocket.close()
                return None

        # ── Role-based reconnection: same name = same role slot ─────────
        # For the family room (or any room), if a player with the same
        # name already exists in the room, the new connection takes over
        # that role: kick the old socket and reclaim the pid.
        existing_pid: Optional[str] = None
        for pid, info in room.players.items():
            if info.get("name") == player_name:
                existing_pid = pid
                break

        if existing_pid:
            # Kick old connection if still active
            old_ws = self._room_sockets.get(room_id, {}).get(existing_pid)
            if old_ws is not None and old_ws is not websocket:
                try:
                    await old_ws.close(code=1000, reason="Role taken over")
                except Exception:
                    pass
            # Remove old tracking
            self._room_sockets.get(room_id, {}).pop(existing_pid, None)
            self._player_room.pop(existing_pid, None)

            # Cancel old watchdog if any
            wd = self._disconnect_watchdogs.pop(existing_pid, None)
            if wd:
                wd.cancel()

            # Leave room first (so join_room can re-add)
            await self._rm.leave_room(room_id, existing_pid)

            # Reclaim the pid
            reconnect_id = existing_pid
            print(f"[CONN] Role takeover: {player_name} reclaims pid={existing_pid[:8]}")

        # ── Reconnection: validate token ─────────────────────────────────
        if reconnect_id:
            stored_token = self._reconnect_tokens.get(reconnect_id)
            if stored_token and stored_token == reconnect_token:
                # Valid reconnection — restore player
                player_id = reconnect_id
                # Cancel disconnect watchdog
                wd = self._disconnect_watchdogs.pop(player_id, None)
                if wd:
                    wd.cancel()
                print(f"[CONN] Reconnected player {player_id[:8]} ({player_name})")
            else:
                # Token invalid or expired — but still let them back in
                # if their pid exists in the room (remove old entry first)
                if room and reconnect_id in room.players:
                    await self._rm.leave_room(room_id, reconnect_id)
                    player_id = reconnect_id
                    print(f"[CONN] Reclaimed player slot {player_id[:8]} ({player_name})")
                else:
                    print(f"[CONN] Reconnect failed for pid={reconnect_id[:8]} — unknown, will create new")
                    reconnect_id = ""
                    player_id = str(uuid.uuid4())[:8]
        else:
            player_id = str(uuid.uuid4())[:8]

        # ── Register player in room ─────────────────────────────────────
        joined = await self._rm.join_room(room_id, player_id, player_name)
        print(f"[CONN] player={player_id[:8]} name={player_name} room={room_id} joined={joined}")
        if not joined:
            await self._send_error(
                websocket, "ROOM_FULL", f"Room {room_id} is full or unavailable"
            )
            await websocket.close()
            return None

        # ── Generate/refresh reconnect token ────────────────────────────
        new_token = str(uuid.uuid4())[:12]
        self._reconnect_tokens[player_id] = new_token

        # ── Track WebSocket ─────────────────────────────────────────────
        if room_id not in self._room_sockets:
            self._room_sockets[room_id] = {}
        self._room_sockets[room_id][player_id] = websocket
        self._player_room[player_id] = room_id

        # ── Disable托管 on reconnection (player is back) ────────────────
        room_after = await self._rm.get_room(room_id)
        if room_after and room_after.game_state_manager:
            gsm = room_after.game_state_manager
            if player_id in gsm._auto_play_players:
                gsm.toggle_auto_play(player_id)
                print(f"[CONN] Disabled auto-play for reconnected player {player_id[:8]}")

        # ── Send STATE_SYNC (includes reconnect_token for the player) ──
        await self.broadcast_state(room_id)

        return player_id

    async def handle_disconnect(self, websocket: WebSocket) -> None:
        """Handle a WebSocket disconnection.

        Removes the player's socket from tracking, marks them disconnected
        in the room, and broadcasts the updated state.

        Args:
            websocket: The disconnected WebSocket.
        """
        player_id: Optional[str] = None
        room_id: Optional[str] = None

        # ── Find the disconnected player ──────────────────────────────
        for rid, players in self._room_sockets.items():
            for pid, ws in list(players.items()):
                if ws is websocket:
                    player_id = pid
                    room_id = rid
                    break
            if player_id:
                break

        if player_id is None or room_id is None:
            return

        # ── Clean up socket tracking ───────────────────────────────────
        if room_id in self._room_sockets:
            self._room_sockets[room_id].pop(player_id, None)
        self._player_room.pop(player_id, None)
        # Keep player in room + reconnect token so they can reconnect

        # ── Auto-enable托管 for disconnected player if in PLAYING ────
        room = await self._rm.get_room(room_id)
        if room and room.game_state_manager:
            gsm = room.game_state_manager
            if gsm._phase.value == "PLAYING" and player_id not in gsm._auto_play_players:
                gsm.toggle_auto_play(player_id)

        # ── Start watchdog: auto-play / remove after 60s ──────────────
        async def _watchdog():
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                return  # reconnected — cancelled
            # Player didn't reconnect — remove from room
            self._disconnect_watchdogs.pop(player_id, None)
            self._reconnect_tokens.pop(player_id, None)
            room = await self._rm.get_room(room_id)
            if room and room.game_state_manager:
                gsm = room.game_state_manager
                state = gsm.get_state()
                if state.get("current_turn") == player_id:
                    gsm.auto_play(player_id)
            await self._rm.leave_room(room_id, player_id)
            await self.broadcast_state(room_id)
            print(f"[WATCHDOG] Player {player_id[:8]} timed out, removed from room {room_id}")

        task = asyncio.create_task(_watchdog())
        self._disconnect_watchdogs[player_id] = task

        # ── If no one left connected, clean up room immediately ────────
        remaining_sockets = self._room_sockets.get(room_id, {})
        if not remaining_sockets:
            # Cancel all watchdogs for this room
            for pid in list(self._disconnect_watchdogs.keys()):
                p_room = self._player_room.get(pid)
                if p_room == room_id:
                    wd = self._disconnect_watchdogs.pop(pid, None)
                    if wd:
                        wd.cancel()
                    self._reconnect_tokens.pop(pid, None)
            # Remove all players from room
            room = await self._rm.get_room(room_id)
            if room:
                for pid in list(room.players.keys()):
                    await self._rm.leave_room(room_id, pid)
            # Cancel turn timer
            self._cancel_turn_timer(room_id)
            print(f"[DISCONNECT] All players gone, room {room_id} cleaned up")

        # ── Broadcast updated state (other players see "暂离") ─────────
        await self.broadcast_state(room_id)

    # ── Message routing ─────────────────────────────────────────────────────

    async def handle_message(
        self, websocket: WebSocket, player_id: str, raw_data: dict
    ) -> None:
        """Parse, validate, and route an incoming WebSocket message.

        All messages are validated via protocol.validate_message() before
        processing. Invalid messages receive an ERROR response.

        Args:
            websocket: The sending WebSocket.
            player_id: The sender's player ID.
            raw_data: Raw dict from ``websocket.receive_json()``.
        """
        # ── Validate message ────────────────────────────────────────────
        try:
            msg = validate_message(raw_data)
        except ValueError as exc:
            await self._send_error(websocket, "INVALID_MESSAGE", str(exc))
            return

        # ── Route by type ───────────────────────────────────────────────
        try:
            msg_type = msg.type

            if msg_type == MsgType.PING:
                await self._handle_ping(websocket)

            elif msg_type == MsgType.JOIN:
                await self._handle_join(websocket, player_id, msg)

            elif msg_type == MsgType.START_GAME:
                await self._handle_start_game(websocket, player_id)

            elif msg_type == MsgType.PLAY:
                await self._handle_play(websocket, player_id, msg)

            elif msg_type == MsgType.PASS:
                await self._handle_pass(websocket, player_id)

            elif msg_type == MsgType.DECLARE:
                await self._handle_declare(websocket, player_id, msg)

            elif msg_type == MsgType.LEAVE:
                await self._handle_leave(websocket, player_id)

            elif msg_type == MsgType.READY:
                await self._handle_ready(websocket, player_id)

            elif msg_type == MsgType.AUTO_PLAY:
                await self._handle_auto_play(websocket, player_id)

            else:
                await self._send_error(
                    websocket, "UNHANDLED_TYPE", f"Unhandled message type: {msg_type.value}"
                )

        except Exception as exc:
            await self._send_error(websocket, "SERVER_ERROR", str(exc))

    # ── Broadcast helpers ────────────────────────────────────────────────────

    async def broadcast_state(self, room_id: str) -> None:
        """Send current game state (STATE_SYNC) to each player individually.

        Each player receives a personalized STATE_SYNC with their own
        ``your_hand`` and ``your_player_id`` fields. This is critical
        because the client needs these to show cards and identify self.
        """
        room = await self._rm.get_room(room_id)
        if room is None:
            return

        ready_info = await self._rm.get_ready_info(room_id)
        gsm = room.game_state_manager

        if gsm is not None:
            # Game has started — send personalized game state to each player
            state = gsm.get_state()
            state_players = state.get("players", [])
            print(f"[BCAST] Game state phase={gsm._phase.value}, sending to {len(state_players)} players")

            for p in state_players:
                pid = p.get("player_id")
                if not pid:
                    continue
                ws = self._room_sockets.get(room_id, {}).get(pid)
                if ws is None:
                    continue

                personal_payload: Dict[str, Any] = dict(state)
                personal_payload["ready_players"] = ready_info["ready_players"]
                personal_payload["all_ready"] = ready_info["all_ready"]
                personal_payload["your_hand"] = p.get("hand", [])
                personal_payload["your_player_id"] = pid
                personal_payload["historical_scores"] = get_all_scores()

                # Turn timer remaining seconds
                timer = self._turn_timers.get(room_id)
                if timer and timer.is_running:
                    personal_payload["remaining_time"] = timer.remaining_seconds()

                # Include reconnect token for this player (reconnection support)
                token = self._reconnect_tokens.get(pid, "")
                personal_payload["reconnect_token"] = token

                msg = create_message(MsgType.STATE_SYNC, payload=personal_payload)
                try:
                    await ws.send_text(serialize_message(msg))
                except Exception:
                    pass
        else:
            # Pre-game lobby — send per-player room status
            print(f"[BCAST] Pre-game lobby for room {room_id}, players={list(room.players.keys())}, ready={ready_info}")
            for pid, info in room.players.items():
                ws = self._room_sockets.get(room_id, {}).get(pid)
                if ws is None:
                    continue

                payload = {
                    "room_id": room_id,
                    "code": room.id,
                    "players": [
                        {"player_id": p, "name": d["name"]}
                        for p, d in room.players.items()
                    ],
                    "max_players": room.max_players,
                    "phase": "WAITING",
                    "ready_players": ready_info["ready_players"],
                    "all_ready": ready_info["all_ready"],
                    "your_player_id": pid,
                    "your_hand": [],
                    "historical_scores": get_all_scores(),
                    "reconnect_token": self._reconnect_tokens.get(pid, ""),
                }

                msg = create_message(MsgType.STATE_SYNC, payload=payload)
                try:
                    await ws.send_text(serialize_message(msg))
                except Exception:
                    pass

    async def broadcast_error(
        self, websocket: WebSocket, code: str, message: str
    ) -> None:
        """Send an ERROR message to a specific client.

        Args:
            websocket: Target WebSocket.
            code: Error code string.
            message: Human-readable error message.
        """
        await self._send_error(websocket, code, message)

    async def _broadcast_raw(self, room_id: str, raw: str) -> None:
        """Send a raw JSON string to every connected socket in a room.

        Disconnected sockets are silently skipped.

        Args:
            room_id: Target room.
            raw: JSON string to send.
        """
        sockets = self._room_sockets.get(room_id, {})
        for ws in list(sockets.values()):
            try:
                await ws.send_text(raw)
            except Exception:
                # Socket may have disconnected between checks — skip
                pass

    async def _send_error(
        self, websocket: WebSocket, code: str, message: str
    ) -> None:
        """Send an ERROR message to a specific WebSocket."""
        msg = create_message(
            MsgType.ERROR,
            payload={"code": code, "message": message},
        )
        try:
            await websocket.send_text(serialize_message(msg))
        except Exception:
            pass

    # ── Message handlers ──────────────────────────────────────────────────────

    async def _handle_ping(self, websocket: WebSocket) -> None:
        """Respond to PING with PONG."""
        pong = create_message(MsgType.PONG)
        await websocket.send_text(serialize_message(pong))

    async def _handle_join(
        self, websocket: WebSocket, player_id: str, msg: Message
    ) -> None:
        """Handle JOIN: register a player in a room and broadcast STATE_SYNC.

        Payload may contain ``room_id`` and ``name`` for explicit joining.
        """
        name = msg.payload.get("name", "Unknown")
        target_room = msg.payload.get("room_id", "")

        if target_room:
            # Join a specific room
            joined = await self._rm.join_room(target_room, player_id, name)
            if not joined:
                await self._send_error(
                    websocket, "JOIN_FAILED", f"Unable to join room {target_room}"
                )
                return
            if target_room not in self._room_sockets:
                self._room_sockets[target_room] = {}
            self._room_sockets[target_room][player_id] = websocket
            self._player_room[player_id] = target_room

        # Find the player's room
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(
                websocket, "NOT_IN_ROOM", "You are not in any room"
            )
            return

        await self.broadcast_state(room_id)

    async def _handle_start_game(
        self, websocket: WebSocket, player_id: str
    ) -> None:
        """Handle START_GAME: initialize game state and deal cards.

        Creates a GameStateManager for the room, starts the game,
        deals cards, and broadcasts GAME_START + STATE_SYNC.
        """
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(
                websocket, "NOT_IN_ROOM", "You are not in any room"
            )
            return

        room = await self._rm.get_room(room_id)
        if room is None:
            await self._send_error(websocket, "ROOM_NOT_FOUND", "Room not found")
            return

        # ── Build player list ───────────────────────────────────────────
        player_list = []
        for pid in room.players:
            info = room.players[pid]
            player_list.append({
                "player_id": pid,
                "name": info["name"],
                "score": 0,
            })

        actual_count = len(player_list)
        if actual_count < 2:
            await self._send_error(
                websocket,
                "NOT_ENOUGH_PLAYERS",
                f"Need at least 2 players, have {actual_count}",
            )
            return

        # ── Create GSM with actual player count (not max_players) ────────
        if room.game_state_manager is None:
            config = _make_rule_config(actual_count)
            room.game_state_manager = GameStateManager(config, room_id=room_id)

        gsm = room.game_state_manager

        # ── Start game flow ─────────────────────────────────────────────
        result = gsm.start_game(player_list)
        if not result["success"]:
            await self._send_error(websocket, "START_FAILED", result.get("error", "Unknown error"))
            return

        # Deal cards
        deal_result = gsm.deal_cards()
        if not deal_result["success"]:
            await self._send_error(websocket, "DEAL_FAILED", deal_result.get("error", "Unknown error"))
            return

        # ── Broadcast GAME_START ────────────────────────────────────────
        start_msg = create_message(
            MsgType.GAME_START,
            payload={
                "phase": gsm._phase.value,
                "message": "Game started! Cards dealt.",
            },
        )
        await self._broadcast_raw(room_id, serialize_message(start_msg))

        # ── Broadcast individual hands (STATE_SYNC shows masked info) ──
        await self._broadcast_individual_hands(room_id, gsm)

        # ── Broadcast full state ────────────────────────────────────────
        await self.broadcast_state(room_id)

    async def _handle_play(
        self, websocket: WebSocket, player_id: str, msg: Message
    ) -> None:
        """Handle PLAY: validate and process a card play.

        Payload must contain ``cards`` (list of card dicts).
        """
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        room = await self._rm.get_room(room_id)
        if room is None or room.game_state_manager is None:
            await self._send_error(websocket, "NO_GAME", "No active game")
            return

        gsm = room.game_state_manager

        # ── Parse cards ─────────────────────────────────────────────────
        cards_raw = msg.payload.get("cards", [])
        if not cards_raw:
            await self._send_error(websocket, "NO_CARDS", "No cards provided")
            return

        try:
            cards = cards_from_dicts(cards_raw)
        except (KeyError, ValueError) as exc:
            await self._send_error(websocket, "INVALID_CARDS", str(exc))
            return

        # ── Execute play ────────────────────────────────────────────────
        print(f"[PLAY] player={player_id[:8]} room={room_id} cards={[str(c) for c in cards]}")
        try:
            result = gsm.play_turn(player_id, cards)
        except InvalidStateError as exc:
            await self._send_error(websocket, "INVALID_STATE", str(exc))
            return

        if not result["success"]:
            print(f"[PLAY] FAILED player={player_id[:8]} error={result.get('error')}")
            # Send error back to the player who made the invalid play
            error_payload = {
                "code": result.get("error", "Invalid play"),
                "message": result.get("error", "Invalid play"),
            }
            if result.get("must_play"):
                error_payload["must_play"] = True
                error_payload["forced_cards"] = result.get("forced_cards")

            error_msg = create_message(MsgType.ERROR, payload=error_payload)
            await websocket.send_text(serialize_message(error_msg))
            return

        # ── Success: broadcast new state ────────────────────────────────
        # Start turn timer BEFORE broadcasting so remaining_time appears
        if result.get("phase") != "ROUND_END":
            await self._start_turn_timer(room_id)
        await self.broadcast_state(room_id)

        # If the next player is in auto-play, trigger immediately.
        # _check_and_trigger_auto_play handles chain + timer + broadcast.
        if result.get("phase") != "ROUND_END":
            await self._check_and_trigger_auto_play(room_id)

        # ── If round ended, broadcast ROUND_END and persist scores ─────
        if result.get("phase") == "ROUND_END":
            score_deltas = result.get("score_deltas", {})

            # Persist historical scores BEFORE re-broadcasting state
            if room and score_deltas:
                for pid, delta in score_deltas.items():
                    p_info = room.players.get(pid)
                    if p_info:
                        p_name = p_info.get("name", pid)
                        add_score(p_name, delta)
                        print(f"[SCORE] {p_name} delta={delta:+d}")

            # Re-broadcast state with updated historical_scores
            await self.broadcast_state(room_id)

            # Broadcast ROUND_END message
            round_end_msg = create_message(
                MsgType.ROUND_END,
                payload={
                    "winner_id": result.get("winner_id"),
                    "scores": result.get("scores"),
                    "score_deltas": score_deltas,
                    "is_declaration_game": result.get("is_declaration_game"),
                    "declarer_id": result.get("declarer_id"),
                    "breaker_id": result.get("breaker_id"),
                },
            )
            await self._broadcast_raw(room_id, serialize_message(round_end_msg))

            # Cancel turn timer (round is over)
            self._cancel_turn_timer(room_id)

    async def _handle_pass(
        self, websocket: WebSocket, player_id: str
    ) -> None:
        """Handle PASS: process a pass attempt."""
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        room = await self._rm.get_room(room_id)
        if room is None or room.game_state_manager is None:
            await self._send_error(websocket, "NO_GAME", "No active game")
            return

        gsm = room.game_state_manager

        try:
            result = gsm.pass_turn(player_id)
        except InvalidStateError as exc:
            await self._send_error(websocket, "INVALID_STATE", str(exc))
            return

        if not result["success"]:
            print(f"[PASS] FAILED player={player_id[:8]} error={result.get('error')}")
            error_payload = {
                "code": "PASS_REJECTED",
                "message": result.get("error", "Cannot pass"),
            }
            if result.get("must_play"):
                error_payload["must_play"] = True
                error_payload["forced_cards"] = result.get("forced_cards")

            error_msg = create_message(MsgType.ERROR, payload=error_payload)
            await websocket.send_text(serialize_message(error_msg))
            return

        # ── Broadcast new state ─────────────────────────────────────────
        # Start turn timer BEFORE broadcasting so remaining_time appears
        await self._start_turn_timer(room_id)
        await self.broadcast_state(room_id)

        # If the next player is in auto-play, trigger immediately.
        # _check_and_trigger_auto_play handles chain + timer + broadcast.
        await self._check_and_trigger_auto_play(room_id)

    async def _handle_declare(
        self, websocket: WebSocket, player_id: str, msg: Message
    ) -> None:
        """Handle DECLARE: record a player's 包牌 (declaration) choice."""
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        room = await self._rm.get_room(room_id)
        if room is None or room.game_state_manager is None:
            await self._send_error(websocket, "NO_GAME", "No active game")
            return

        gsm = room.game_state_manager
        # Accept both camelCase and snake_case
        is_declaring = bool(msg.payload.get("isDeclaring", msg.payload.get("is_declaring", False)))
        print(f"[DECLARE] player={player_id[:8]} room={room_id} is_declaring={is_declaring}")

        try:
            result = gsm.declare(player_id, is_declaring)
        except InvalidStateError as exc:
            await self._send_error(websocket, "INVALID_STATE", str(exc))
            return

        if not result["success"]:
            await self._send_error(
                websocket, "DECLARE_FAILED", result.get("error", "Declaration failed")
            )
            return

        # ── Broadcast new state ─────────────────────────────────────────
        print(f"[DECLARE] Broadcasting state after declaration, gsm._phase={gsm._phase.value}")
        await self.broadcast_state(room_id)

        # ── Start turn timer if game entered PLAYING phase ───────────
        if gsm._phase.value == "PLAYING":
            await self._start_turn_timer(room_id)
            # Trigger auto-play if the first player is in auto-play.
            # _check_and_trigger_auto_play handles chain + timer + broadcast.
            await self._check_and_trigger_auto_play(room_id)

    async def _handle_auto_play(
        self, websocket: WebSocket, player_id: str
    ) -> None:
        """Handle AUTO_PLAY: toggle auto-play mode for the player."""
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        room = await self._rm.get_room(room_id)
        if room is None or room.game_state_manager is None:
            await self._send_error(websocket, "NO_GAME", "No active game")
            return

        gsm = room.game_state_manager
        result = gsm.toggle_auto_play(player_id)

        if result.get("success"):
            await self.broadcast_state(room_id)
            # If enabled and it's this player's turn, trigger immediately
            if result.get("auto_play_enabled"):
                state = gsm.get_state()
                if state.get("current_turn") == player_id and gsm._phase.value == "PLAYING":
                    gsm.auto_play(player_id)
                    await self.broadcast_state(room_id)
                    # Chain through consecutive托管 players.
                    # _check_and_trigger_auto_play handles chain + timer + broadcast.
                    await self._check_and_trigger_auto_play(room_id)

    async def _check_and_trigger_auto_play(self, room_id: str) -> None:
        """After an action, chain-trigger auto-play for ALL consecutive
        auto-play players until a non-auto-play player or round end.
        Also manages the turn timer: starts a fresh timer for the
        final player and broadcasts with correct remaining_time."""
        room = await self._rm.get_room(room_id)
        if room is None or room.game_state_manager is None:
            return
        gsm = room.game_state_manager
        if gsm._phase.value != "PLAYING":
            return
        for _ in range(10):  # safety limit
            state = gsm.get_state()
            current = state.get("current_turn")
            if not current or current not in gsm._auto_play_players:
                break
            gsm.auto_play(current)
            await self.broadcast_state(room_id)
            if gsm._phase.value != "PLAYING":
                break
            # Delay between托管 moves so players can see the action
            await asyncio.sleep(1.5)
        # Start fresh timer for whoever ended up as current after the chain,
        # then broadcast so clients see the correct remaining_time.
        if gsm._phase.value == "PLAYING":
            await self._start_turn_timer(room_id)
        await self.broadcast_state(room_id)

    async def _handle_leave(
        self, websocket: WebSocket, player_id: str
    ) -> None:
        """Handle LEAVE: explicitly leave the current room."""
        room_id = self._player_room.get(player_id)
        if room_id is None:
            return

        # Clean up tracking
        if room_id in self._room_sockets:
            self._room_sockets[room_id].pop(player_id, None)
        self._player_room.pop(player_id, None)

        await self._rm.leave_room(room_id, player_id)
        await self.broadcast_state(room_id)

        leave_msg = create_message(
            MsgType.PLAYER_LEFT,
            payload={"player_id": player_id},
        )
        try:
            await websocket.send_text(serialize_message(leave_msg))
        except Exception:
            pass

    async def _handle_ready(
        self, websocket: WebSocket, player_id: str
    ) -> None:
        """Handle READY: mark player as ready; start/advance game if all ready."""
        room_id = self._player_room.get(player_id)
        if room_id is None:
            await self._send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        room = await self._rm.get_room(room_id)
        if room is None:
            await self._send_error(websocket, "ROOM_NOT_FOUND", "Room not found")
            return

        # Mark this player as ready
        ok = await self._rm.mark_ready(room_id, player_id)
        print(f"[READY] player={player_id[:8]} room={room_id} mark_ready={ok}")

        # Check if all players are ready
        ready_info = await self._rm.get_ready_info(room_id)
        print(f"[READY] ready_info: {ready_info}")
        await self.broadcast_state(room_id)

        if not ready_info["all_ready"]:
            return

        # Clear ready status for next round
        await self._rm.clear_ready(room_id)

        # Cancel any running turn timer (new game / new round)
        self._cancel_turn_timer(room_id)

        gsm = room.game_state_manager

        if gsm is None:
            # Game hasn't started yet — start it
            print(f"[START] First game, players={len(room.players)} mode={'2p' if len(room.players)==2 else '3p' if len(room.players)==3 else '4p'}")
            player_list = []
            for pid in room.players:
                info = room.players[pid]
                player_list.append({
                    "player_id": pid,
                    "name": info["name"],
                    "score": 0,
                })

            if len(player_list) < 2:
                await self._send_error(
                    websocket,
                    "NOT_ENOUGH_PLAYERS",
                    f"Need at least 2 players, have {len(player_list)}",
                )
                return

            # Create GSM with actual player count
            config = _make_rule_config(len(player_list))
            room.game_state_manager = GameStateManager(config, room_id=room_id)
            gsm = room.game_state_manager

            # Start game
            result = gsm.start_game(player_list)
            if not result["success"]:
                await self._send_error(websocket, "START_FAILED", result.get("error", "Unknown error"))
                return
            print(f"[START] game started, phase={gsm._phase.value}")

            # Deal cards
            deal_result = gsm.deal_cards()
            if not deal_result["success"]:
                await self._send_error(websocket, "DEAL_FAILED", deal_result.get("error", "Unknown error"))
                return
            print(f"[START] cards dealt, hands={[len(h) for h in deal_result.get('hands', [])]}")

            # Broadcast GAME_START
            start_msg = create_message(
                MsgType.GAME_START,
                payload={
                    "phase": gsm._phase.value,
                    "message": "Game started! Cards dealt.",
                },
            )
            await self._broadcast_raw(room_id, serialize_message(start_msg))

            # Broadcast individual hands
            await self._broadcast_individual_hands(room_id, gsm)

            # Broadcast full state
            await self.broadcast_state(room_id)

        else:
            # Game is ongoing — advance to next round
            print(f"[NEXT_ROUND] advancing to next round")
            next_round = gsm.start_next_round()
            if not next_round["success"]:
                await self._send_error(websocket, "NEXT_ROUND_FAILED", next_round.get("error", "Unknown error"))
                return
            print(f"[NEXT_ROUND] round={gsm._round_number} phase={gsm._phase.value}")

            # Broadcast GAME_START for new round
            start_msg = create_message(
                MsgType.GAME_START,
                payload={
                    "phase": gsm._phase.value,
                    "message": "Next round started! Cards dealt.",
                },
            )
            await self._broadcast_raw(room_id, serialize_message(start_msg))

            # Broadcast individual hands
            await self._broadcast_individual_hands(room_id, gsm)

            # Broadcast full state
            await self.broadcast_state(room_id)

    # ── Individual hand broadcast ─────────────────────────────────────────────

    async def _broadcast_individual_hands(
        self, room_id: str, gsm: GameStateManager
    ) -> None:
        """Send each player their own hand via STATE_SYNC with full card info.

        Only the owning player receives their complete hand. Other players
        receive masked info (remaining_cards count) via broadcast_state.

        Args:
            room_id: The room to send hands to.
            gsm: The game state manager.
        """
        state = gsm.get_state()
        players = state.get("players", [])

        for p in players:
            pid = p.get("player_id")
            if pid is None:
                continue

            ws = self._room_sockets.get(room_id, {}).get(pid)
            if ws is None:
                continue

            # Build a player-specific state with their full hand visible
            personal_payload: Dict[str, Any] = dict(state)
            personal_payload["your_hand"] = p.get("hand", [])
            personal_payload["your_player_id"] = pid
            personal_payload["reconnect_token"] = self._reconnect_tokens.get(pid, "")

            msg = create_message(MsgType.STATE_SYNC, payload=personal_payload)
            try:
                await ws.send_text(serialize_message(msg))
            except Exception:
                pass

    # ── Turn timer management ────────────────────────────────────────────────

    async def _start_turn_timer(self, room_id: str) -> None:
        """Cancel old timer and start a new 30s turn timer for the current player.
        
        On timeout: auto-pass or auto-play the smallest card.
        """
        # Cancel existing
        if room_id in self._turn_timers:
            self._turn_timers[room_id].cancel()

        room = await self._rm.get_room(room_id)
        if room is None or room.game_state_manager is None:
            return
        gsm = room.game_state_manager
        if gsm._phase.value != "PLAYING":
            return

        timer = TurnTimer()
        room_id_captured = room_id

        async def on_timeout():
            """Auto-play or auto-pass on timeout. Chains through托管 players."""
            room2 = await self._rm.get_room(room_id_captured)
            if room2 is None or room2.game_state_manager is None:
                return
            gsm2 = room2.game_state_manager
            state = gsm2.get_state()
            pid = state.get("current_turn")
            if not pid:
                return

            result = gsm2.auto_play(pid)

            if result.get("phase") == "ROUND_END":
                # Persist scores
                sd = result.get("score_deltas", {})
                if sd:
                    for pid2, delta in sd.items():
                        p_info = room2.players.get(pid2)
                        if p_info:
                            add_score(p_info.get("name", pid2), delta)
                await self.broadcast_state(room_id_captured)
                return

            if result.get("success"):
                # Chain through consecutive托管 players.
                # _check_and_trigger_auto_play handles chain + timer + broadcast.
                await self._check_and_trigger_auto_play(room_id_captured)

        timer.start(duration_sec=30, on_timeout=on_timeout)
        self._turn_timers[room_id] = timer

    # ── Turn timer helpers for handlers ────────────────────────────────────

    def _cancel_turn_timer(self, room_id: str) -> None:
        """Cancel the turn timer for a room."""
        if room_id in self._turn_timers:
            self._turn_timers[room_id].cancel()

    # ── Reset ───────────────────────────────────────────────────────────────────

    async def reset_all(self) -> dict:
        """End all games, kick all players, clear all rooms.
        Returns a summary dict.
        """
        room_count = len(self._room_sockets)
        conn_count = sum(len(s) for s in self._room_sockets.values())

        # Cancel all turn timers
        for tid in list(self._turn_timers.keys()):
            self._turn_timers[tid].cancel()
        self._turn_timers.clear()

        # Cancel all disconnect watchdogs
        for task in self._disconnect_watchdogs.values():
            task.cancel()
        self._disconnect_watchdogs.clear()

        # Close all WebSocket connections
        for room_sockets in self._room_sockets.values():
            for ws in room_sockets.values():
                try:
                    await ws.close(code=1001, reason="Server reset")
                except Exception:
                    pass

        # Clear all tracking
        self._room_sockets.clear()
        self._player_room.clear()
        self._reconnect_tokens.clear()
        await self._rm.reset_all()

        return {
            "rooms_cleared": room_count,
            "connections_closed": conn_count,
        }

    # ── Diagnostic ────────────────────────────────────────────────────────────

    @property
    def active_rooms(self) -> int:
        """Number of rooms with active WebSocket connections."""
        return len(self._room_sockets)

    @property
    def active_connections(self) -> int:
        """Total number of active WebSocket connections."""
        return sum(len(sockets) for sockets in self._room_sockets.values())


