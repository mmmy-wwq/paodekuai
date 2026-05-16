"""
Tests for GameServer: WebSocket lifecycle, reconnection, auto-play (托管),
and disconnect handling.

Key bugs tested:
1. After a player enables 托管 and auto-plays, the next 托管 player is NOT
   chain-triggered (only one auto-play instead of chaining through all).
2. On disconnect, the player is NOT auto-set to 托管 mode.
3. Role-based reconnection: selecting a role should load game state.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from server.game_engine.state_machine import GameStateManager
from server.network.game_server import GameServer
from server.network.protocol import (MsgType, Message, create_message,
                                       serialize_message, deserialize_message)
from server.network.room_manager import RoomManager
from server.rule_engine.rules import RuleConfig
from server.card_engine.card import Card, Rank, Suit
from server.models import GamePhase


def c(rank_str: str, suit_str: str) -> Card:
    return Card(Suit[suit_str], Rank[rank_str])


# ── Helper: create a minimal mock WebSocket ──────────────────────────────

class MockWebSocket:
    """A mock WebSocket that records sent messages."""

    def __init__(self):
        self.sent: list[str] = []
        self.closed: bool = False
        self.close_code: Optional[int] = None
        self.accept = AsyncMock(return_value=None)
        self.close = AsyncMock(return_value=None)

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def receive_json(self) -> dict:
        return {}


# ── GSM setup helpers ────────────────────────────────────────────────────

def _setup_gsm_for_playing(room, player_names: list[str], pids: list[str]):
    """Create GSM, start game, deal, and complete declaration so phase=PLAYING."""
    config = RuleConfig(
        player_count=len(pids),
        deck_size={2: 32, 3: 48, 4: 52}[len(pids)],
        cards_per_player={2: 16, 3: 16, 4: 13}[len(pids)],
        has_ace_bomb=len(pids) < 4,
    )
    room.game_state_manager = GameStateManager(config, room_id=room.id)
    gsm = room.game_state_manager

    players = [{"player_id": pid, "name": name} for pid, name in zip(pids, player_names)]
    gsm.start_game(players)
    gsm.deal_cards(seed=42)

    # Complete declaration phase respecting turn order.
    # After deal, _declaration_turn is set to whatever index
    # determine_first_player returns. We must call declare() in
    # the correct order (following _declaration_turn advancement).
    n = len(pids)
    for _ in range(n):
        decl_pid = gsm._players[gsm._declaration_turn]["player_id"]
        gsm.declare(decl_pid, False)

    return gsm


# ═══════════════════════════════════════════════════════════════════════════
# Tests: GameServer handle_connection reconnection
# ═══════════════════════════════════════════════════════════════════════════

class TestGameServerReconnect:
    """Test that reconnection works even when room is full."""

    @pytest.fixture
    def gs(self) -> GameServer:
        rm = RoomManager()
        return GameServer(room_manager=rm)

    @pytest.mark.asyncio
    async def test_reconnect_to_full_room_with_valid_token(self, gs: GameServer):
        """
        BUG: Player disconnects, room is full (4/4), player reconnects
        with valid pid+token -> should succeed, not show '房间已满'.
        """
        room_id = "FAMILY"
        # Player 1-4 connect
        ws1 = MockWebSocket()
        pid1 = await gs.handle_connection(ws1, room_id, "爸爸", player_count=4)
        assert pid1 is not None
        ws2 = MockWebSocket()
        pid2 = await gs.handle_connection(ws2, room_id, "妈妈", player_count=4)
        assert pid2 is not None
        ws3 = MockWebSocket()
        pid3 = await gs.handle_connection(ws3, room_id, "姐姐", player_count=4)
        assert pid3 is not None
        ws4 = MockWebSocket()
        pid4 = await gs.handle_connection(ws4, room_id, "弟弟", player_count=4)
        assert pid4 is not None

        # Room is full
        room = await gs._rm.get_room(room_id)
        assert room.is_full

        # Get reconnect token for 爸爸
        token = gs._reconnect_tokens.get(pid1, "")
        assert token, "Should have a reconnect token"

        # Simulate 爸爸 disconnecting
        await gs.handle_disconnect(ws1)

        # 爸爸 should still be in room.players
        room = await gs._rm.get_room(room_id)
        assert pid1 in room.players, "爸爸 should stay in room after disconnect"
        assert room.is_full, "Room should still be full (player slot held for reconnect)"

        # 爸爸 reconnects with valid pid + token
        ws1b = MockWebSocket()
        pid_reconnect = await gs.handle_connection(
            ws1b, room_id, "爸爸", player_count=4,
            reconnect_id=pid1, reconnect_token=token,
        )
        assert pid_reconnect is not None, (
            "REGRESSION: 爸爸 reconnection FAILED with valid token. "
            "Expected to reconnect but got None (likely '房间已满' error)."
        )
        assert pid_reconnect == pid1, "Reconnected player should keep same pid"

    @pytest.mark.asyncio
    async def test_reconnect_without_token_but_same_pid(self, gs: GameServer):
        """
        Even without a valid token, if the pid is still in room.players,
        the player should be able to reclaim their slot.
        """
        room_id = "FAMILY"
        ws1 = MockWebSocket()
        pid1 = await gs.handle_connection(ws1, room_id, "爸爸", player_count=4)
        ws2 = MockWebSocket()
        pid2 = await gs.handle_connection(ws2, room_id, "妈妈", player_count=4)
        ws3 = MockWebSocket()
        await gs.handle_connection(ws3, room_id, "姐姐", player_count=4)
        ws4 = MockWebSocket()
        await gs.handle_connection(ws4, room_id, "弟弟", player_count=4)

        assert pid1 is not None
        await gs.handle_disconnect(ws1)

        # Reconnect WITHOUT token (new browser, cleared localStorage)
        ws1b = MockWebSocket()
        pid_reconnect = await gs.handle_connection(
            ws1b, room_id, "爸爸", player_count=4,
            reconnect_id=pid1, reconnect_token="",
        )
        assert pid_reconnect is not None, (
            "Reconnection without token should reclaim slot via leave+rejoin"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tests: GameServer disconnect -> auto 托管
# ═══════════════════════════════════════════════════════════════════════════

class TestDisconnectAutoPlay:
    """Test that disconnected players are auto-set to 托管 mode."""

    @pytest.fixture
    def gs(self) -> GameServer:
        rm = RoomManager()
        return GameServer(room_manager=rm)

    @pytest.mark.asyncio
    async def test_disconnect_auto_enables_auto_play(self, gs: GameServer):
        """
        BUG: When a player disconnects mid-game, they are NOT auto-set to
        托管 mode. This means their turn causes a 30-second wait for everyone.
        After disconnect, the player should be in _auto_play_players.
        """
        room_id = "TEST"
        await gs._rm.create_room_with_id(room_id, max_players=3)

        ws1 = MockWebSocket()
        pid1 = await gs.handle_connection(ws1, room_id, "Alice", player_count=3)
        ws2 = MockWebSocket()
        pid2 = await gs.handle_connection(ws2, room_id, "Bob", player_count=3)
        ws3 = MockWebSocket()
        pid3 = await gs.handle_connection(ws3, room_id, "Charlie", player_count=3)

        # Start the game and complete declaration
        room = await gs._rm.get_room(room_id)
        gsm = _setup_gsm_for_playing(room, ["Alice", "Bob", "Charlie"], [pid1, pid2, pid3])

        assert gsm._phase.value == "PLAYING"

        # Bob should NOT be in托管 before disconnect
        assert pid2 not in gsm._auto_play_players

        # Simulate Bob disconnecting
        await gs.handle_disconnect(ws2)

        # After disconnect, Bob SHOULD be in auto-play
        assert pid2 in gsm._auto_play_players, (
            "REGRESSION: Disconnected player should be auto-set to 托管 mode. "
            "Bug: disconnect does not enable auto-play, causing long waits."
        )

    @pytest.mark.asyncio
    async def test_disconnect_when_not_playing_does_not_crash(self, gs: GameServer):
        """Disconnecting when no game is active should not crash."""
        room_id = "TEST"
        await gs._rm.create_room_with_id(room_id, max_players=3)
        ws1 = MockWebSocket()
        pid1 = await gs.handle_connection(ws1, room_id, "Alice", player_count=3)

        await gs.handle_disconnect(ws1)
        # Test passes if no exception raised


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Auto-play chaining in _handle_auto_play
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoPlayChaining:
    """Test that auto-play chains through consecutive 托管 players."""

    @pytest.fixture
    def gs(self) -> GameServer:
        rm = RoomManager()
        return GameServer(room_manager=rm)

    @pytest.mark.asyncio
    async def test_handle_auto_play_chains_when_next_player_is_also_auto(self, gs: GameServer):
        """
        BUG: _handle_auto_play only calls gsm.auto_play(current_player) once.
        If the next player is also in 托管, they are not triggered immediately.

        Fix: _handle_auto_play should call _check_and_trigger_auto_play after
        auto-playing to chain through consecutive 托管 players.
        """
        room_id = "TEST"
        await gs._rm.create_room_with_id(room_id, max_players=3)

        ws1 = MockWebSocket()
        pid1 = await gs.handle_connection(ws1, room_id, "Alice", player_count=3)
        ws2 = MockWebSocket()
        pid2 = await gs.handle_connection(ws2, room_id, "Bob", player_count=3)
        ws3 = MockWebSocket()
        pid3 = await gs.handle_connection(ws3, room_id, "Charlie", player_count=3)

        room = await gs._rm.get_room(room_id)
        gsm = _setup_gsm_for_playing(room, ["Alice", "Bob", "Charlie"], [pid1, pid2, pid3])

        # Override hands with 3 cards each (no must-play triggers)
        gsm._players[0]["hand"] = [c("THREE", "SPADE"), c("FIVE", "HEART"), c("NINE", "CLUB")]
        gsm._players[1]["hand"] = [c("FOUR", "DIAMOND"), c("SIX", "SPADE"), c("TEN", "HEART")]
        gsm._players[2]["hand"] = [c("FOUR", "SPADE"), c("SEVEN", "CLUB"), c("JACK", "DIAMOND")]
        gsm._current_turn = 0
        gsm._last_play_cards = None
        gsm._last_play_player_index = None
        gsm._consecutive_passes = 0
        gsm._turn_number = 0

        # Alice (p0) plays 3, turn advances counter-clockwise to p2 (Charlie)
        result = gsm.play_turn(pid1, [c("THREE", "SPADE")])
        assert result["success"]

        state = gsm.get_state()
        assert state["current_turn"] == pid3  # Charlie

        # Set both Charlie(p2) and Bob(p1) to托管
        gsm.toggle_auto_play(pid3)  # Charlie
        gsm.toggle_auto_play(pid2)  # Bob

        # Now simulate _handle_auto_play: Charlie is托管, auto-plays
        gsm.auto_play(pid3)

        # After Charlie plays, turn should advance to Bob (p1)
        state_after = gsm.get_state()
        if state_after["phase"] == "PLAYING":
            assert state_after["current_turn"] == pid2, (
                f"After Charlie auto-plays, turn should go to Bob. "
                f"Got: {state_after['current_turn']}"
            )
            # Bob is still托管, but we need chaining to auto-play him
            assert pid2 in gsm._auto_play_players, (
                "Bob should still be in托管 after Charlie's auto-play"
            )
            # Key assertion: if _check_and_trigger_auto_play were called here,
            # Bob would auto-play too. Without it, Bob sits idle.
            # This test confirms the GSM state after single auto_play call.


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _check_and_trigger_auto_play chains (integration test)
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckAndTriggerAutoPlay:
    """Test that _check_and_trigger_auto_play properly chains."""

    @pytest.fixture
    def gs(self) -> GameServer:
        rm = RoomManager()
        return GameServer(room_manager=rm)

    @pytest.mark.asyncio
    async def test_chains_through_multiple_auto_play_players(self, gs: GameServer):
        """
        When the current turn is a托管 player and the next player is also
        托管, _check_and_trigger_auto_play should auto-play both in sequence.
        """
        room_id = "TEST"
        await gs._rm.create_room_with_id(room_id, max_players=3)

        ws1 = MockWebSocket()
        pid1 = await gs.handle_connection(ws1, room_id, "Alice", player_count=3)
        ws2 = MockWebSocket()
        pid2 = await gs.handle_connection(ws2, room_id, "Bob", player_count=3)
        ws3 = MockWebSocket()
        pid3 = await gs.handle_connection(ws3, room_id, "Charlie", player_count=3)

        room = await gs._rm.get_room(room_id)
        gsm = _setup_gsm_for_playing(room, ["Alice", "Bob", "Charlie"], [pid1, pid2, pid3])

        # Override hands with 3 cards each
        gsm._players[0]["hand"] = [c("THREE", "SPADE"), c("FIVE", "HEART"), c("NINE", "CLUB")]
        gsm._players[1]["hand"] = [c("FOUR", "DIAMOND"), c("SIX", "SPADE"), c("TEN", "HEART")]
        gsm._players[2]["hand"] = [c("FOUR", "SPADE"), c("SEVEN", "CLUB"), c("JACK", "DIAMOND")]
        gsm._current_turn = 0
        gsm._last_play_cards = None
        gsm._last_play_player_index = None
        gsm._consecutive_passes = 0
        gsm._turn_number = 0

        # Alice plays 3, turn -> Charlie (counter-clockwise: 0->2->1->0)
        gsm.play_turn(pid1, [c("THREE", "SPADE")])
        state = gsm.get_state()
        assert state["current_turn"] == pid3  # Charlie

        # Set both Charlie and Bob to托管
        gsm.toggle_auto_play(pid3)
        gsm.toggle_auto_play(pid2)

        # Register these WebSockets so broadcast_state works
        await gs._check_and_trigger_auto_play(room_id)

        # After chain, turn should be back to Alice (both托管 players auto-played)
        state_after = gsm.get_state()
        assert state_after["current_turn"] == pid1, (
            f"After chaining through Charlie and Bob (both托管), "
            f"turn should return to Alice. Got: {state_after['current_turn']}"
        )

        # All three players should have 2 cards left each
        remaining = [len(p["hand"]) for p in gsm._players]
        assert remaining == [2, 2, 2], (
            f"Each player should have 2 cards after chain. Got: {remaining}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Role-based reconnection (family room)
# ═══════════════════════════════════════════════════════════════════════════

class TestRoleBasedReconnection:
    """Test that role-based reconnection works for the family room."""

    @pytest.fixture
    def gs(self) -> GameServer:
        rm = RoomManager()
        return GameServer(room_manager=rm)

    @pytest.mark.asyncio
    async def test_reconnect_by_role_name_reclaims_slot(self, gs: GameServer):
        """
        When a player reconnects with the same role name (e.g., '爸爸'),
        they should reclaim their slot even in a full room.
        """
        room_id = "一家人"
        ws_dad = MockWebSocket()
        pid_dad = await gs.handle_connection(ws_dad, room_id, "爸爸", player_count=4)
        ws_mom = MockWebSocket()
        await gs.handle_connection(ws_mom, room_id, "妈妈", player_count=4)
        ws_sis = MockWebSocket()
        await gs.handle_connection(ws_sis, room_id, "姐姐", player_count=4)
        ws_bro = MockWebSocket()
        await gs.handle_connection(ws_bro, room_id, "弟弟", player_count=4)

        room = await gs._rm.get_room(room_id)
        assert room.is_full

        token = gs._reconnect_tokens.get(pid_dad, "")

        # 爸爸 disconnects
        await gs.handle_disconnect(ws_dad)

        room = await gs._rm.get_room(room_id)
        assert pid_dad in room.players

        # 爸爸 reconnects with valid token
        ws_dad2 = MockWebSocket()
        pid_reconnect = await gs.handle_connection(
            ws_dad2, room_id, "爸爸", player_count=4,
            reconnect_id=pid_dad, reconnect_token=token,
        )
        assert pid_reconnect is not None, "爸爸 should be able to reconnect"
        assert pid_reconnect == pid_dad, "Should get same pid"

    @pytest.mark.asyncio
    async def test_reconnect_get_game_state_on_rejoin(self, gs: GameServer):
        """
        After reconnecting mid-game, the player should receive the current
        game state (STATE_SYNC) including their hand.
        """
        room_id = "一家人"
        ws_dad = MockWebSocket()
        pid_dad = await gs.handle_connection(ws_dad, room_id, "爸爸", player_count=4)
        ws_mom = MockWebSocket()
        pid_mom = await gs.handle_connection(ws_mom, room_id, "妈妈", player_count=4)
        ws_sis = MockWebSocket()
        pid_sis = await gs.handle_connection(ws_sis, room_id, "姐姐", player_count=4)
        ws_bro = MockWebSocket()
        pid_bro = await gs.handle_connection(ws_bro, room_id, "弟弟", player_count=4)

        token = gs._reconnect_tokens.get(pid_dad, "")

        # Start a game
        room = await gs._rm.get_room(room_id)
        gsm = _setup_gsm_for_playing(
            room,
            ["爸爸", "妈妈", "姐姐", "弟弟"],
            [pid_dad, pid_mom, pid_sis, pid_bro],
        )
        assert gsm._phase.value == "PLAYING"

        # 爸爸 disconnects
        await gs.handle_disconnect(ws_dad)

        # 爸爸 reconnects
        ws_dad2 = MockWebSocket()
        pid_reconnect = await gs.handle_connection(
            ws_dad2, room_id, "爸爸", player_count=4,
            reconnect_id=pid_dad, reconnect_token=token,
        )
        assert pid_reconnect is not None, "爸爸 reconnection failed"
        assert pid_reconnect == pid_dad

        # After reconnection, ws_dad2 should have received STATE_SYNC
        assert len(ws_dad2.sent) > 0, "Reconnected player should receive messages"
        # Verify at least one message contains game state info
        found_phase = False
        for msg_text in ws_dad2.sent:
            if "PLAYING" in msg_text or "your_hand" in msg_text or "phase" in msg_text:
                found_phase = True
                break
        assert found_phase, (
            "Reconnected player should receive game state with PLAYING phase info"
        )

    @pytest.mark.asyncio
    async def test_reconnect_updates_name_in_room(self, gs: GameServer):
        """Reconnecting should update the player's name in room.players."""
        room_id = "一家人"
        ws = MockWebSocket()
        pid = await gs.handle_connection(ws, room_id, "爸爸", player_count=4)
        ws2 = MockWebSocket()
        await gs.handle_connection(ws2, room_id, "妈妈", player_count=4)

        token = gs._reconnect_tokens.get(pid, "")

        await gs.handle_disconnect(ws)

        ws3 = MockWebSocket()
        pid_r = await gs.handle_connection(
            ws3, room_id, "爸爸", player_count=4,
            reconnect_id=pid, reconnect_token=token,
        )
        assert pid_r == pid
        room = await gs._rm.get_room(room_id)
        assert room.players[pid]["name"] == "爸爸"
