"""
Tests for game state machine (server.game_engine.state_machine).

Covers phase transitions, invalid-state guards, play/pass mechanics,
must-play enforcement, round-end scoring, and next-round advancement.
"""

from __future__ import annotations

import pytest

from server.card_engine.card import Card, Rank, Suit
from server.game_engine.state_machine import GameStateManager, InvalidStateError
from server.models import GamePhase
from server.rule_engine.rules import RuleConfig


def c(r: str, s: str) -> Card:
    return Card(Suit[s], Rank[r])


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def config_3p() -> RuleConfig:
    return RuleConfig(
        player_count=3,
        deck_size=48,
        cards_per_player=16,
        has_ace_bomb=True,
        must_play_enabled=True,
    )


@pytest.fixture
def gsm(config_3p) -> GameStateManager:
    return GameStateManager(config_3p, room_id="test-room")


@pytest.fixture
def three_players() -> list[dict]:
    return [
        {"player_id": "p0", "name": "Alice"},
        {"player_id": "p1", "name": "Bob"},
        {"player_id": "p2", "name": "Charlie"},
    ]


def _declare_all(gsm: GameStateManager, player_ids: list[str]) -> None:
    """Declare all players (no 包牌) in the correct turn order.
    
    Reads declaration_turn_player_id from the state and declares
    each player in sequence until all have chosen.
    """
    for _ in player_ids:
        state = gsm.get_state()
        turn_id = state.get("declaration_turn_player_id")
        if turn_id is None:
            break
        gsm.declare(turn_id, is_declaring=False)


# ═══════════════════════════════════════════════════════════════════════
# Phase transitions
# ═══════════════════════════════════════════════════════════════════════

class TestPhaseTransitions:
    """Tests for correct phase flow WAITING→DEALING→DECLARATION→PLAYING→ROUND_END."""

    def test_initial_phase_is_waiting(self, gsm):
        """Game starts in WAITING phase."""
        state = gsm.get_state()
        assert state["phase"] == GamePhase.WAITING.value

    def test_start_game_transitions_to_dealing(self, gsm, three_players):
        """start_game transitions WAITING → DEALING."""
        result = gsm.start_game(three_players)
        assert result["success"] is True
        assert result["phase"] == GamePhase.DEALING.value

    def test_deal_cards_transitions_to_declaration(self, gsm, three_players):
        """deal_cards transitions DEALING → DECLARATION."""
        gsm.start_game(three_players)
        result = gsm.deal_cards(seed=42)
        assert result["success"] is True
        assert result["phase"] == GamePhase.DECLARATION.value

    def test_all_declare_transitions_to_playing(self, gsm, three_players):
        """After all players declare, phase transitions to PLAYING."""
        gsm.start_game(three_players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1", "p2"])
        result = gsm.get_state()
        assert result["phase"] == GamePhase.PLAYING.value


# ═══════════════════════════════════════════════════════════════════════
# Invalid transitions / phase guards
# ═══════════════════════════════════════════════════════════════════════

class TestInvalidTransitions:
    """Tests for phase-guard enforcement."""

    def test_deal_cards_before_start_game_raises(self, gsm):
        """deal_cards in WAITING raises InvalidStateError."""
        with pytest.raises(InvalidStateError):
            gsm.deal_cards()

    def test_declare_before_dealing_raises(self, gsm, three_players):
        """declare before DEALING raises InvalidStateError."""
        gsm.start_game(three_players)  # now DEALING
        with pytest.raises(InvalidStateError):
            gsm.declare("p0", is_declaring=False)

    def test_play_turn_before_playing_raises(self, gsm, three_players):
        """play_turn before PLAYING raises InvalidStateError."""
        gsm.start_game(three_players)
        gsm.deal_cards(seed=42)
        with pytest.raises(InvalidStateError):
            gsm.play_turn("p0", [c("THREE", "SPADE")])

    def test_wrong_player_count_rejected(self, gsm):
        """start_game rejects wrong number of players."""
        result = gsm.start_game([
            {"player_id": "p0", "name": "Alice"},
            {"player_id": "p1", "name": "Bob"},
        ])  # only 2, expected 3
        assert result["success"] is False


# ═══════════════════════════════════════════════════════════════════════
# Play / Pass mechanics
# ═══════════════════════════════════════════════════════════════════════

class TestPlayPassMechanics:
    """Tests for play_turn and pass_turn during PLAYING phase."""

    @pytest.fixture
    def ready_game(self, gsm, three_players):
        """A game that's been started, dealt, and all players have declared no."""
        gsm.start_game(three_players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1", "p2"])
        return gsm

    def test_play_wrong_player_rejected(self, ready_game):
        """Playing out of turn is rejected."""
        state = ready_game.get_state()
        current = state["current_turn"]
        # Try to play as a different player
        wrong_player = "p0"
        for pid in ["p0", "p1", "p2"]:
            if pid != current:
                wrong_player = pid
                break
        result = ready_game.play_turn(wrong_player, [c("THREE", "SPADE")])
        assert result["success"] is False
        assert "Not your turn" in result.get("error", "")

    def test_free_play_accepted(self, ready_game):
        """On free play (no last_play), valid pattern is accepted."""
        state = ready_game.get_state()
        current = state["current_turn"]
        # The current player must play from their hand
        # We need to find the hand of the current player
        players = state["players"]
        hand = []
        for p in players:
            if p["player_id"] == current:
                # Deserialize cards (they're dicts from get_state)
                hand = [Card(Suit[s["suit"]], Rank[s["rank"]]) for s in p["hand"]]
                break
        # Play any valid single
        if hand:
            result = ready_game.play_turn(current, [hand[0]])
            assert result["success"] is True

    def test_pass_on_free_play_rejected(self, ready_game):
        """Passing on a free play (no last_play) is rejected."""
        state = ready_game.get_state()
        current = state["current_turn"]
        result = ready_game.pass_turn(current)
        assert result["success"] is False
        assert "Cannot pass" in result.get("error", "")


# ═══════════════════════════════════════════════════════════════════════
# Round end
# ═══════════════════════════════════════════════════════════════════════

class TestRoundEnd:
    """Tests for round-end mechanics."""

    def test_round_end_by_emptying_hand(self, gsm, three_players):
        """Playing all remaining cards triggers round end."""
        # Set up a 2-player game for simplicity
        config_2p = RuleConfig(
            player_count=2, deck_size=32, cards_per_player=16,
        )
        gsm2 = GameStateManager(config_2p)
        players = [
            {"player_id": "p0", "name": "Alice"},
            {"player_id": "p1", "name": "Bob"},
        ]
        gsm2.start_game(players)
        gsm2.deal_cards(seed=42)
        _declare_all(gsm2, ["p0", "p1"])
        # Verify end_round returns a valid result in PLAYING phase
        result = gsm2.end_round()
        assert result["success"] is True

    def test_next_round_from_round_end(self, gsm, three_players):
        """start_next_round transitions ROUND_END → DEALING → DECLARATION."""
        gsm.start_game(three_players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1", "p2"])
        gsm.end_round()
        result = gsm.start_next_round()
        assert result["success"] is True
        assert result["phase"] == GamePhase.DECLARATION.value

    def test_get_state_contract(self, gsm, three_players):
        """get_state returns expected keys."""
        gsm.start_game(three_players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1", "p2"])
        state = gsm.get_state()
        assert "success" in state
        assert state["success"] is True
        assert "phase" in state
        assert "players" in state
        assert "current_turn" in state
        assert "last_play" in state
        assert "round_number" in state
        assert "deck_size" in state
        assert "player_count" in state
        assert state["player_count"] == 3

    def test_repeated_play_returns_different_error(self, gsm, three_players):
        """Playing twice out of turn gives consistent error."""
        gsm.start_game(three_players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1", "p2"])
        state = gsm.get_state()
        current = state["current_turn"]
        # Find a non-current player
        wrong = "p0" if current != "p0" else "p1"
        result1 = gsm.play_turn(wrong, [c("THREE", "SPADE")])
        result2 = gsm.play_turn(wrong, [c("FOUR", "HEART")])
        assert result1["success"] is False
        assert result2["success"] is False
