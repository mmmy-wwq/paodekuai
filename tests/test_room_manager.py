"""
Tests for RoomManager: room creation, joining, leaving, and reconnection bugs.

Key bug tested:
- Reconnecting a disconnected player to a full room should succeed
  because the player is already in room.players (is_full was checked first).
"""

from __future__ import annotations

import asyncio
import time

import pytest

from server.network.room_manager import RoomManager, Room


class TestRoomManagerJoin:
    """Tests for RoomManager.join_room reconnection behaviour."""

    @staticmethod
    async def _fill_room(rm: RoomManager, code: str, *names: str) -> list[str]:
        """Add players to a room and return their pids."""
        pids = []
        for name in names:
            pid = f"pid_{name}"
            assert await rm.join_room(code, pid, name)
            pids.append(pid)
        return pids

    @pytest.mark.asyncio
    async def test_reconnect_disconnected_player_in_full_room(self):
        """
        BUG: A player who disconnects stays in room.players (by design for
        reconnection support). When they reconnect, join_room() checks
        is_full FIRST and rejects them with '房间已满'.

        FIX: player_id in room.players should be checked BEFORE is_full.
        """
        rm = RoomManager()
        code = await rm.create_room(max_players=3)
        pids = await self._fill_room(rm, code, "Alice", "Bob", "Charlie")

        room = await rm.get_room(code)
        assert room is not None
        assert room.is_full, "Room should be full with 3 players"

        # p1 (Bob) tries to rejoin even though room is full
        # Since Bob is already in room.players, this should succeed
        result = await rm.join_room(code, pids[1], "Bob-Reconnected")
        assert result is True, (
            "REGRESSION: Reconnection FAILED even though player already in "
            "room.players. Bug: is_full checked before player_id in room.players."
        )

        # Verify the name was updated
        room = await rm.get_room(code)
        assert room.players[pids[1]]["name"] == "Bob-Reconnected"

    @pytest.mark.asyncio
    async def test_cannot_join_full_room_as_new_player(self):
        """A new player (not already in room) should still be rejected when room is full."""
        rm = RoomManager()
        code = await rm.create_room(max_players=3)
        await self._fill_room(rm, code, "Alice", "Bob", "Charlie")

        result = await rm.join_room(code, "pid_David", "David")
        assert result is False, "New player should be rejected from full room"

    @pytest.mark.asyncio
    async def test_reconnect_disconnected_player_updates_connected_at(self):
        """Reconnecting should update connected_at timestamp."""
        rm = RoomManager()
        code = await rm.create_room(max_players=3)
        pids = await self._fill_room(rm, code, "Alice", "Bob")

        room = await rm.get_room(code)
        original_time = room.players[pids[0]]["connected_at"]

        # Wait a tiny bit to ensure timestamp difference
        time.sleep(0.01)

        # p0 reconnects
        result = await rm.join_room(code, pids[0], "Alice")
        assert result is True

        room = await rm.get_room(code)
        assert room.players[pids[0]]["connected_at"] > original_time

    @pytest.mark.asyncio
    async def test_leave_room_frees_slot_for_new_player(self):
        """After leave_room, a new player should be able to join a previously full room."""
        rm = RoomManager()
        code = await rm.create_room(max_players=3)
        pids = await self._fill_room(rm, code, "Alice", "Bob", "Charlie")

        room = await rm.get_room(code)
        assert room.is_full

        # p1 leaves
        left = await rm.leave_room(code, pids[1])
        assert left is True

        # Now new player should be able to join
        result = await rm.join_room(code, "pid_David", "David")
        assert result is True

    @pytest.mark.asyncio
    async def test_leave_nonexistent_player_returns_false(self):
        """Leaving with a player_id not in the room should return False."""
        rm = RoomManager()
        code = await rm.create_room(max_players=3)
        await self._fill_room(rm, code, "Alice")

        result = await rm.leave_room(code, "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_with_diff_name_on_full_room_resets_name(self):
        """
        Simulation: 4 players join, one leaves (client closes), but stays
        in room.players. They reconnect - should succeed and update name.
        This tests the exact scenario: 一家人 room with 爸爸妈妈姐姐弟弟.
        """
        rm = RoomManager()
        code = await rm.create_room(max_players=4)
        pids = await self._fill_room(rm, code, "爸爸", "妈妈", "姐姐", "弟弟")

        room = await rm.get_room(code)
        assert room.is_full
        assert len(room.players) == 4

        # 弟弟 reconnects (simulating disconnect + reconnect)
        result = await rm.join_room(code, pids[3], "弟弟")
        assert result is True, (
            "REGRESSION: 弟弟 reconnection FAILED. Room showed as full "
            "but 弟弟 was already in room.players."
        )


class TestRoom:
    """Tests for Room model."""

    def test_is_full_property(self):
        room = Room(id="TEST", max_players=4)
        assert not room.is_full
        room.players["p0"] = {"name": "A", "connected_at": 0}
        room.players["p1"] = {"name": "B", "connected_at": 0}
        room.players["p2"] = {"name": "C", "connected_at": 0}
        room.players["p3"] = {"name": "D", "connected_at": 0}
        assert room.is_full

    def test_player_count(self):
        room = Room(id="TEST", max_players=3)
        assert room.player_count == 0
        room.players["p0"] = {"name": "A", "connected_at": 0}
        assert room.player_count == 1
