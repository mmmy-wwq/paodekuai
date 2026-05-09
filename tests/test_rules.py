"""
Tests for rule engine (server.rule_engine.rules).

Covers play validation, must-play rule, legal play enumeration,
and first-player determination.
"""

import pytest

from server.card_engine.card import Card, Rank, Suit
from server.card_engine.recognizer import PatternType, identify
from server.rule_engine.rules import RuleConfig, RuleEngine


def c(r: str, s: str) -> Card:
    return Card(Suit[s], Rank[r])


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def engine_3p() -> RuleEngine:
    """RuleEngine configured for 3-player mode."""
    return RuleEngine(RuleConfig(
        player_count=3,
        deck_size=48,
        cards_per_player=16,
        has_ace_bomb=True,
        must_play_enabled=True,
    ))


@pytest.fixture
def engine_4p() -> RuleEngine:
    """RuleEngine configured for 4-player mode."""
    return RuleEngine(RuleConfig(
        player_count=4,
        deck_size=52,
        cards_per_player=13,
        has_ace_bomb=False,
        must_play_enabled=True,
    ))


# ═══════════════════════════════════════════════════════════════════════
# is_valid_play
# ═══════════════════════════════════════════════════════════════════════

class TestIsValidPlay:
    """Tests for RuleEngine.is_valid_play()."""

    def test_valid_single_accepted(self, engine_3p):
        """A valid single card in hand is accepted."""
        hand = [c("FIVE", "SPADE"), c("KING", "HEART")]
        result = engine_3p.is_valid_play(
            cards=[c("FIVE", "SPADE")],
            hand=hand,
            last_play_pattern=None,
            player_count=3,
            is_last_hand=False,
        )
        assert result["valid"] is True
        assert result["error"] is None

    def test_card_not_in_hand_rejected(self, engine_3p):
        """Playing a card not in hand is rejected."""
        hand = [c("FIVE", "SPADE")]
        result = engine_3p.is_valid_play(
            cards=[c("KING", "HEART")],  # not in hand
            hand=hand,
            last_play_pattern=None,
            player_count=3,
            is_last_hand=False,
        )
        assert result["valid"] is False
        assert "not in your hand" in result["error"]

    def test_duplicate_card_usage_rejected(self, engine_3p):
        """Playing more copies than in hand is rejected."""
        hand = [c("FIVE", "SPADE")]  # only one FIVE
        result = engine_3p.is_valid_play(
            cards=[c("FIVE", "SPADE"), c("FIVE", "SPADE")],  # duplicate
            hand=hand,
            last_play_pattern=None,
            player_count=3,
            is_last_hand=False,
        )
        assert result["valid"] is False

    def test_invalid_pattern_rejected(self, engine_3p):
        """Cards that don't form a valid pattern are rejected."""
        hand = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("SEVEN", "CLUB")]
        result = engine_3p.is_valid_play(
            cards=[c("THREE", "SPADE"), c("FOUR", "HEART")],  # not a pair
            hand=hand,
            last_play_pattern=None,
            player_count=3,
            is_last_hand=False,
        )
        assert result["valid"] is False
        assert "not form a valid pattern" in result["error"]

    def test_cannot_beat_rejected(self, engine_3p):
        """A play that can't beat the table's pattern is rejected."""
        hand = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB")]
        last = identify([c("KING", "SPADE")])
        assert last
        result = engine_3p.is_valid_play(
            cards=[c("FIVE", "CLUB")],
            hand=hand,
            last_play_pattern=last,
            player_count=3,
            is_last_hand=False,
        )
        assert result["valid"] is False

    def test_can_beat_accepted(self, engine_3p):
        """A play that correctly beats the table's pattern is accepted."""
        hand = [c("THREE", "SPADE"), c("ACE", "HEART")]
        last = identify([c("KING", "CLUB")])
        assert last
        result = engine_3p.is_valid_play(
            cards=[c("ACE", "HEART")],
            hand=hand,
            last_play_pattern=last,
            player_count=3,
            is_last_hand=False,
        )
        assert result["valid"] is True


# ═══════════════════════════════════════════════════════════════════════
# check_must_play
# ═══════════════════════════════════════════════════════════════════════

class TestCheckMustPlay:
    """Tests for RuleEngine.check_must_play()."""

    def _make_state(self, players_remaining, current_turn):
        return {
            "players": [
                {"player_id": f"p{i}", "remaining_cards": r}
                for i, r in enumerate(players_remaining)
            ],
            "current_turn": current_turn,
        }

    def test_must_play_triggers(self, engine_3p):
        """Must-play triggers: SINGLE on table, next player (counter-clockwise) has 1 card."""
        last = identify([c("FIVE", "SPADE")])
        assert last
        hand = [c("KING", "HEART"), c("THREE", "CLUB")]
        # 3 players counter-clockwise: p0's next is p2 (index 2), p2 has 1 card
        state = self._make_state([5, 10, 1], current_turn=0)
        result = engine_3p.check_must_play(
            hand=hand,
            last_play_pattern=last,
            game_state=state,
            player_index=0,
        )
        assert result["triggered"] is True
        assert result["forced_cards"] is not None
        assert result["forced_cards"][0].rank.value == Rank.KING.value

    def test_must_play_not_triggered_no_higher(self, engine_3p):
        """Must-play not triggered when player has no higher single."""
        last = identify([c("KING", "SPADE")])  # high
        assert last
        hand = [c("THREE", "CLUB"), c("FOUR", "DIAMOND")]
        state = self._make_state([5, 1, 10], current_turn=0)
        result = engine_3p.check_must_play(
            hand=hand,
            last_play_pattern=last,
            game_state=state,
            player_index=0,
        )
        assert result["triggered"] is False

    def test_must_play_not_triggered_wrong_player(self, engine_3p):
        """Must-play NOT triggered when checked player is NOT the current turn."""
        last = identify([c("FIVE", "SPADE")])
        assert last
        hand = [c("ACE", "HEART"), c("TWO", "SPADE")]
        state = self._make_state([5, 1, 10], current_turn=1)  # p1 is current
        result = engine_3p.check_must_play(
            hand=hand,
            last_play_pattern=last,
            game_state=state,
            player_index=0,  # checking p0, but p1 is current
        )
        assert result["triggered"] is False

    def test_must_play_not_triggered_next_not_1card(self, engine_3p):
        """Must-play NOT triggered when next player has >1 card."""
        last = identify([c("FIVE", "SPADE")])
        assert last
        hand = [c("KING", "HEART")]
        state = self._make_state([5, 3, 10], current_turn=0)  # p1 has 3 cards
        result = engine_3p.check_must_play(
            hand=hand,
            last_play_pattern=last,
            game_state=state,
            player_index=0,
        )
        assert result["triggered"] is False

    def test_must_play_disabled(self):
        """Must-play not triggered when the rule is disabled."""
        engine = RuleEngine(RuleConfig(
            player_count=3, deck_size=48, cards_per_player=16,
            must_play_enabled=False,
        ))
        last = identify([c("THREE", "SPADE")])
        assert last
        hand = [c("ACE", "HEART")]
        state = self._make_state([5, 1, 10], current_turn=0)
        result = engine.check_must_play(
            hand=hand,
            last_play_pattern=last,
            game_state=state,
            player_index=0,
        )
        assert result["triggered"] is False

    def test_must_play_no_last_play(self, engine_3p):
        """Must-play not triggered when no last_play on table."""
        hand = [c("ACE", "HEART")]
        state = self._make_state([5, 1, 10], current_turn=0)
        result = engine_3p.check_must_play(
            hand=hand,
            last_play_pattern=None,
            game_state=state,
            player_index=0,
        )
        assert result["triggered"] is False

    def test_must_play_not_single_type(self, engine_3p):
        """Must-play not triggered when last_play is a PAIR, not SINGLE."""
        last = identify([c("FIVE", "SPADE"), c("FIVE", "HEART")])
        assert last
        assert last.type == PatternType.PAIR
        hand = [c("ACE", "HEART")]
        state = self._make_state([5, 1, 10], current_turn=0)
        result = engine_3p.check_must_play(
            hand=hand,
            last_play_pattern=last,
            game_state=state,
            player_index=0,
        )
        assert result["triggered"] is False


# ═══════════════════════════════════════════════════════════════════════
# determine_first_player
# ═══════════════════════════════════════════════════════════════════════

class TestDetermineFirstPlayer:
    """Tests for RuleEngine.determine_first_player()."""

    def test_spade3_holder_goes_first_3p(self, engine_3p):
        """In first round 3p, player holding ♠3 goes first."""
        players = [
            {"player_id": "p0", "hand": [c("FOUR", "SPADE"), c("FIVE", "HEART")]},
            {"player_id": "p1", "hand": [c("THREE", "SPADE"), c("KING", "DIAMOND")]},
            {"player_id": "p2", "hand": [c("ACE", "HEART"), c("TWO", "CLUB")]},
        ]
        idx = engine_3p.determine_first_player(players, round_number=1)
        assert idx == 1  # p1 has ♠3

    def test_spade3_holder_goes_first_4p(self, engine_4p):
        """In first round 4p, player holding ♠3 goes first."""
        players = [
            {"player_id": "p0", "hand": [c("FOUR", "SPADE")]},
            {"player_id": "p1", "hand": [c("SEVEN", "HEART")]},
            {"player_id": "p2", "hand": [c("THREE", "SPADE"), c("ACE", "CLUB")]},
            {"player_id": "p3", "hand": [c("NINE", "DIAMOND")]},
        ]
        idx = engine_4p.determine_first_player(players, round_number=1)
        assert idx == 2  # p2 has ♠3

    def test_winner_leads_subsequent_round(self, engine_3p):
        """In round > 1, the previous winner leads."""
        players = [
            {"player_id": "p0", "hand": [c("THREE", "SPADE")]},
            {"player_id": "p1", "hand": [c("FIVE", "HEART")]},
            {"player_id": "p2", "hand": [c("ACE", "CLUB")]},
        ]
        idx = engine_3p.determine_first_player(
            players, round_number=2, previous_winner_id="p2"
        )
        assert idx == 2

    def test_2p_first_round_random(self, engine_3p):
        """In 2-player first round, result is either 0 or 1 (random)."""
        # Engine is configured for 3p, but we test the logic with 2 players
        engine_2p = RuleEngine(RuleConfig(
            player_count=2, deck_size=32, cards_per_player=16,
        ))
        players = [
            {"player_id": "p0", "hand": [c("FOUR", "SPADE")]},
            {"player_id": "p1", "hand": [c("FIVE", "HEART")]},
        ]
        idx = engine_2p.determine_first_player(players, round_number=1)
        assert idx in (0, 1)
