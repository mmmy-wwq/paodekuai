"""
Room Manager for 跑得快 (Pao De Kuai).

Manages game rooms: create, join, leave, and cleanup.
Thread-safe via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from server.game_engine.state_machine import GameStateManager
from server.rule_engine.rules import RuleConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Characters excluded from room codes to avoid confusion (0/O, I, L).
_EXCLUDED_CHARS: set[str] = {"O", "I", "L"}

#: Valid room code characters: uppercase A-Z minus confusing ones.
_ROOM_CHARS: list[str] = [c for c in "ABCDEFGHJKMNPQRSTUVWXYZ"]

ROOM_CODE_LENGTH: int = 6

#: Deck/card configuration per player count.
#: {player_count: (deck_size, cards_per_player, has_ace_bomb)}
_PLAYER_CONFIG: dict[int, tuple[int, int, bool]] = {
    2: (32, 16, True),
    3: (48, 16, True),
    4: (52, 13, False),
}


def _generate_room_code() -> str:
    """Generate a 6-character uppercase room code with no confusing chars."""
    return "".join(random.choices(_ROOM_CHARS, k=ROOM_CODE_LENGTH))


def _make_rule_config(player_count: int) -> RuleConfig:
    """Build a RuleConfig for the given player count."""
    deck_size, cards_per_player, has_ace_bomb = _PLAYER_CONFIG[player_count]
    return RuleConfig(
        player_count=player_count,
        deck_size=deck_size,
        cards_per_player=cards_per_player,
        has_ace_bomb=has_ace_bomb,
    )


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

@dataclass
class Room:
    """A game room holding players and optional active game state.

    Attributes:
        id: 6-character uppercase room code.
        players: Dict mapping player_id -> {"name": str, "connected_at": float}.
        max_players: Maximum players allowed in this room (2, 3, or 4).
        created_at: Unix timestamp when the room was created.
        game_state_manager: Active game state manager, or None if game not started.
        ready_players: Set of player_ids who have clicked "ready".
    """
    id: str
    max_players: int = 3
    players: Dict[str, Dict] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    game_state_manager: Optional[GameStateManager] = None
    ready_players: set = field(default_factory=set)

    @property
    def player_count(self) -> int:
        """Return the current number of players in the room."""
        return len(self.players)

    @property
    def is_full(self) -> bool:
        """Check if the room has reached its max player capacity."""
        return len(self.players) >= self.max_players

    @property
    def idle_seconds(self) -> float:
        """Return seconds since the room was created or last activity."""
        return time.time() - self.created_at


# ---------------------------------------------------------------------------
# RoomManager
# ---------------------------------------------------------------------------

class RoomManager:
    """Manages all game rooms: creation, joining, leaving, and cleanup.

    Thread-safe: all public methods are protected by asyncio.Lock.
    """

    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def create_room(self, max_players: int = 3) -> str:
        """Create a new room with a unique 6-character uppercase code.

        Args:
            max_players: Maximum players allowed (2, 3, or 4). Default 3.

        Returns:
            The 6-character uppercase room code.

        Raises:
            ValueError: If max_players is not 2, 3, or 4.
        """
        if max_players not in (2, 3, 4):
            raise ValueError(f"max_players must be 2, 3, or 4, got {max_players}")

        async with self._lock:
            # Generate a unique room code (retry on collision)
            for _ in range(100):
                code = _generate_room_code()
                if code not in self._rooms:
                    break
            else:
                # Extremely unlikely: 20^6 ≈ 64M codes; fallback
                code = _generate_room_code()

            room = Room(id=code, max_players=max_players)
            self._rooms[code] = room
            return code

    async def create_room_with_id(
        self, room_id: str, max_players: int = 3
    ) -> str:
        """Create a new room with a specific room ID (e.g., from a URL path).

        Args:
            room_id: The desired room identifier.
            max_players: Maximum players allowed (2, 3, or 4). Default 3.

        Returns:
            The room_id (same as input).

        Raises:
            ValueError: If max_players is invalid or room_id already exists.
        """
        if max_players not in (2, 3, 4):
            raise ValueError(f"max_players must be 2, 3, or 4, got {max_players}")

        async with self._lock:
            if room_id in self._rooms:
                raise ValueError(f"Room {room_id!r} already exists")
            room = Room(id=room_id, max_players=max_players)
            self._rooms[room_id] = room
            return room_id

    async def join_room(self, room_id: str, player_id: str, player_name: str) -> bool:
        """Join a room if it exists and is not full.

        Args:
            room_id: The room code.
            player_id: Unique identifier for the joining player.
            player_name: Display name for the player.

        Returns:
            True if the player joined successfully, False otherwise.
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return False
            if player_id in room.players:
                # Player already in room — treat as rejoin (reconnection)
                room.players[player_id]["name"] = player_name
                room.players[player_id]["connected_at"] = time.time()
                return True
            if room.is_full:
                return False

            room.players[player_id] = {
                "name": player_name,
                "connected_at": time.time(),
            }
            # Update created_at to reflect last activity for cleanup purposes
            room.created_at = time.time()
            return True

    async def leave_room(self, room_id: str, player_id: str) -> bool:
        """Remove a player from a room. Cleans up empty rooms.

        Args:
            room_id: The room code.
            player_id: The player to remove.

        Returns:
            True if the player was in the room (and was removed), False otherwise.
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return False
            if player_id not in room.players:
                return False

            del room.players[player_id]
            room.ready_players.discard(player_id)

            # Clean up empty rooms
            if not room.players:
                del self._rooms[room_id]

            return True

    async def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by its ID, or None if not found."""
        async with self._lock:
            return self._rooms.get(room_id)

    async def get_player_count(self, room_id: str) -> int:
        """Get the current number of players in a room, or 0 if not found."""
        async with self._lock:
            room = self._rooms.get(room_id)
            return room.player_count if room else 0

    async def mark_ready(self, room_id: str, player_id: str) -> bool:
        """Mark a player as ready in the room.

        Args:
            room_id: The room code.
            player_id: The player to mark ready.

        Returns:
            True if the player was marked ready, False if room/player not found.
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None or player_id not in room.players:
                return False
            room.ready_players.add(player_id)
            return True

    async def clear_ready(self, room_id: str) -> None:
        """Clear all ready statuses for a room.

        Args:
            room_id: The room code.
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is not None:
                room.ready_players.clear()

    async def get_ready_info(self, room_id: str) -> dict:
        """Get ready status for all players in a room.

        Args:
            room_id: The room code.

        Returns:
            {"ready_players": [player_id, ...], "all_ready": bool}
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return {"ready_players": [], "all_ready": False}
            ready_list = list(room.ready_players)
            all_ready = (
                len(room.ready_players) >= len(room.players)
                and len(room.players) >= 2
            )
            return {"ready_players": ready_list, "all_ready": all_ready}

    async def cleanup_stale_rooms(self, max_age_minutes: int = 30) -> int:
        """Remove rooms that have been idle longer than max_age_minutes.

        Args:
            max_age_minutes: Maximum idle time in minutes before removal.

        Returns:
            The number of rooms cleaned up.
        """
        max_age_seconds = max_age_minutes * 60
        now = time.time()

        async with self._lock:
            stale_ids = [
                rid
                for rid, room in self._rooms.items()
                if now - room.created_at > max_age_seconds
            ]
            for rid in stale_ids:
                del self._rooms[rid]

        return len(stale_ids)

    async def reset_all(self) -> int:
        """Remove ALL rooms and reset all game state.
        Returns the number of rooms that were active.
        """
        async with self._lock:
            count = len(self._rooms)
            self._rooms.clear()
        return count

    @property
    def room_count(self) -> int:
        """Return the total number of active rooms (non-locking, for diagnostics)."""
        return len(self._rooms)
