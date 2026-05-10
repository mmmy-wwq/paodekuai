"""
Tests for card pattern recognizer (server.card_engine.recognizer).

Covers all 8 pattern types, edge cases, last-hand kicker rules,
and ACE_BOMB player-count restrictions.
"""

import pytest

from server.card_engine.card import Card, Rank, Suit
from server.card_engine.recognizer import (
    CardPattern,
    PatternType,
    get_pattern_display_name,
    identify,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def c(r: str, s: str) -> Card:
    return Card(Suit[s], Rank[r])


# ═══════════════════════════════════════════════════════════════════════
# SINGLE (单张)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifySingle:
    """Tests for SINGLE pattern recognition."""

    def test_single_recognized(self):
        """A single card is recognized as SINGLE."""
        result = identify([c("FIVE", "HEART")])
        assert result is not None
        assert result.type == PatternType.SINGLE
        assert result.main_rank == Rank.FIVE.value
        assert result.length == 1

    def test_single_main_rank_is_correct(self):
        """The main_rank of a SINGLE equals the card's rank value."""
        result = identify([c("KING", "CLUB")])
        assert result.main_rank == Rank.KING.value

    def test_single_kicker_count_zero(self):
        """SINGLE always has kicker_count 0."""
        result = identify([c("THREE", "SPADE")])
        assert result.kicker_count == 0


# ═══════════════════════════════════════════════════════════════════════
# PAIR (对子)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyPair:
    """Tests for PAIR pattern recognition."""

    def test_pair_recognized(self):
        """Two cards of same rank form a PAIR."""
        result = identify([c("QUEEN", "SPADE"), c("QUEEN", "HEART")])
        assert result is not None
        assert result.type == PatternType.PAIR
        assert result.main_rank == Rank.QUEEN.value

    def test_pair_length_is_one(self):
        """A PAIR has length=1 (one pair unit)."""
        result = identify([c("JACK", "CLUB"), c("JACK", "DIAMOND")])
        assert result.length == 1

    def test_two_different_ranks_not_pair(self):
        """Two cards of different ranks do NOT form a PAIR."""
        result = identify([c("THREE", "SPADE"), c("FOUR", "HEART")])
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# STRAIGHT (顺子)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyStraight:
    """Tests for STRAIGHT pattern recognition."""

    def test_5card_straight(self, straight_34567):
        """A 5-card consecutive sequence is a valid STRAIGHT."""
        result = identify(straight_34567)
        assert result is not None
        assert result.type == PatternType.STRAIGHT
        assert result.main_rank == Rank.SEVEN.value  # highest rank
        assert result.length == 5

    def test_ace_high_straight(self, straight_10JQKA):
        """10-J-Q-K-A is valid (ACE at high end only)."""
        result = identify(straight_10JQKA)
        assert result is not None
        assert result.type == PatternType.STRAIGHT
        assert result.main_rank == Rank.ACE.value

    def test_ace_low_straight_rejected(self, straight_A2345):
        """A-2-3-4-5 is rejected (TWO banned + ACE not at high end)."""
        # Note: straight_A2345 has TWO which is banned, and ACE at low end
        result = identify(straight_A2345)
        assert result is None

    def test_A2345_without_two_also_rejected(self):
        """A-3-4-5-6 with ACE at low end is rejected."""
        cards = [
            c("ACE", "SPADE"), c("THREE", "HEART"),
            c("FOUR", "CLUB"), c("FIVE", "DIAMOND"),
            c("SIX", "SPADE"),
        ]
        result = identify(cards)
        assert result is None

    def test_straight_with_two_rejected(self):
        """A straight containing TWO is rejected."""
        cards = [
            c("TEN", "SPADE"), c("JACK", "HEART"),
            c("QUEEN", "CLUB"), c("KING", "DIAMOND"),
            c("TWO", "SPADE"),  # TWO invalid in straights
        ]
        result = identify(cards)
        assert result is None

    def test_straight_must_be_5plus(self):
        """A straight requires at least 5 cards."""
        result = identify([
            c("THREE", "SPADE"), c("FOUR", "HEART"),
            c("FIVE", "CLUB"), c("SIX", "DIAMOND"),
        ])
        # 4 cards - not enough for straight
        assert result is None

    def test_straight_8card(self):
        """An 8-card straight is valid."""
        cards = [
            c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"),
            c("SIX", "DIAMOND"), c("SEVEN", "SPADE"), c("EIGHT", "HEART"),
            c("NINE", "CLUB"), c("TEN", "DIAMOND"),
        ]
        result = identify(cards)
        assert result is not None
        assert result.type == PatternType.STRAIGHT
        assert result.length == 8


# ═══════════════════════════════════════════════════════════════════════
# CONSECUTIVE_PAIRS (连对)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyConsecutivePairs:
    """Tests for CONSECUTIVE_PAIRS pattern recognition."""

    def test_2pairs_recognized(self, consecutive_pairs_3344):
        """Two consecutive pairs (3-3-4-4) form a valid 连对."""
        result = identify(consecutive_pairs_3344)
        assert result is not None
        assert result.type == PatternType.CONSECUTIVE_PAIRS
        assert result.main_rank == Rank.FOUR.value
        assert result.length == 2  # 2 pairs

    def test_3pairs_recognized(self):
        """Three consecutive pairs are valid."""
        cards = [
            c("SIX", "SPADE"), c("SIX", "HEART"),
            c("SEVEN", "CLUB"), c("SEVEN", "DIAMOND"),
            c("EIGHT", "SPADE"), c("EIGHT", "HEART"),
        ]
        result = identify(cards)
        assert result is not None
        assert result.type == PatternType.CONSECUTIVE_PAIRS
        assert result.length == 3

    def test_non_consecutive_pairs_rejected(self):
        """Pairs with a gap are rejected."""
        cards = [
            c("THREE", "SPADE"), c("THREE", "HEART"),
            c("FIVE", "CLUB"), c("FIVE", "DIAMOND"),  # gap: no FOUR
        ]
        result = identify(cards)
        assert result is None

    def test_consecutive_pairs_with_two(self):
        """Consecutive pairs CANNOT include TWO (跑得快规则)."""
        cards = [
            c("ACE", "SPADE"), c("ACE", "HEART"),
            c("TWO", "CLUB"), c("TWO", "DIAMOND"),
        ]
        result = identify(cards)
        assert result is None, "连对不应包含TWO"

    def test_single_pair_not_consecutive_pairs(self):
        """A single pair of cards is recognized as PAIR, not CONSECUTIVE_PAIRS."""
        result = identify([c("KING", "SPADE"), c("KING", "HEART")])
        assert result is not None
        assert result.type == PatternType.PAIR


# ═══════════════════════════════════════════════════════════════════════
# TRIPLE_WITH_TWO (三带二)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyTripleWithTwo:
    """Tests for TRIPLE_WITH_TWO pattern recognition."""

    def test_triple_with_two_recognized(self, triple_with_two):
        """3 of same rank + 2 kickers = TRIPLE_WITH_TWO."""
        result = identify(triple_with_two)
        assert result is not None
        assert result.type == PatternType.TRIPLE_WITH_TWO
        assert result.main_rank == Rank.FIVE.value
        assert result.kicker_count == 2

    def test_triple_without_kickers_rejected(self):
        """3 cards alone (no kickers) does NOT form 三带二 in normal mode."""
        cards = [
            c("KING", "SPADE"), c("KING", "HEART"), c("KING", "CLUB"),
        ]
        result = identify(cards, is_last_hand=False)
        assert result is None

    def test_triple_without_kickers_last_hand(self):
        """3 cards alone IS valid as 三带二 on last hand (relaxed kickers)."""
        cards = [
            c("KING", "SPADE"), c("KING", "HEART"), c("KING", "CLUB"),
        ]
        result = identify(cards, is_last_hand=True)
        assert result is not None
        assert result.type == PatternType.TRIPLE_WITH_TWO
        assert result.kicker_count == 0

    def test_triple_with_one_kicker_last_hand(self):
        """3 + 1 kicker valid on last hand."""
        cards = [
            c("QUEEN", "SPADE"), c("QUEEN", "HEART"), c("QUEEN", "CLUB"),
            c("THREE", "DIAMOND"),
        ]
        result = identify(cards, is_last_hand=True)
        assert result is not None
        assert result.type == PatternType.TRIPLE_WITH_TWO
        assert result.kicker_count == 1


# ═══════════════════════════════════════════════════════════════════════
# FOUR_WITH_THREE (四带三)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyFourWithThree:
    """Tests for FOUR_WITH_THREE pattern recognition."""

    def test_four_with_three_recognized(self, four_with_three):
        """4 of same rank + 3 kickers = FOUR_WITH_THREE."""
        result = identify(four_with_three)
        assert result is not None
        assert result.type == PatternType.FOUR_WITH_THREE
        assert result.main_rank == Rank.SIX.value
        assert result.kicker_count == 3

    def test_four_alone_rejected(self, bomb_threes):
        """4 cards alone = BOMB, not FOUR_WITH_THREE."""
        result = identify(bomb_threes)
        assert result is not None
        assert result.type == PatternType.BOMB

    def test_four_with_two_kickers_rejected_normal(self):
        """4 + 2 kickers rejected in normal mode (need exactly 3 kickers)."""
        cards = [
            c("SEVEN", "SPADE"), c("SEVEN", "HEART"),
            c("SEVEN", "CLUB"), c("SEVEN", "DIAMOND"),
            c("THREE", "SPADE"), c("FOUR", "HEART"),
        ]
        result = identify(cards, is_last_hand=False)
        assert result is None

    def test_four_with_two_kickers_last_hand(self):
        """4 + 2 kickers valid on last hand."""
        cards = [
            c("SEVEN", "SPADE"), c("SEVEN", "HEART"),
            c("SEVEN", "CLUB"), c("SEVEN", "DIAMOND"),
            c("THREE", "SPADE"), c("FOUR", "HEART"),
        ]
        result = identify(cards, is_last_hand=True)
        assert result is not None
        assert result.type == PatternType.FOUR_WITH_THREE
        assert result.kicker_count == 2


# ═══════════════════════════════════════════════════════════════════════
# BOMB (炸弹)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyBomb:
    """Tests for BOMB pattern recognition."""

    def test_bomb_recognized(self, bomb_threes):
        """4 cards of same rank = BOMB."""
        result = identify(bomb_threes)
        assert result is not None
        assert result.type == PatternType.BOMB
        assert result.main_rank == Rank.THREE.value
        assert result.length == 4

    def test_bomb_kicker_count_zero(self, bomb_threes):
        """BOMB has kicker_count 0."""
        result = identify(bomb_threes)
        assert result.kicker_count == 0

    def test_3cards_not_bomb(self):
        """3 cards of same rank are NOT a BOMB."""
        cards = [
            c("ACE", "SPADE"), c("ACE", "HEART"), c("ACE", "CLUB"),
        ]
        result = identify(cards, player_count=4)
        assert result is None  # Not a bomb (need 4), and ACE_BOMB only in 2-3p


# ═══════════════════════════════════════════════════════════════════════
# ACE_BOMB (A炸)
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyAceBomb:
    """Tests for ACE_BOMB pattern recognition."""

    def test_ace_bomb_3players(self, ace_bomb):
        """3 Aces in 3-player mode = ACE_BOMB."""
        result = identify(ace_bomb, player_count=3)
        assert result is not None
        assert result.type == PatternType.ACE_BOMB
        assert result.main_rank == Rank.ACE.value

    def test_ace_bomb_2players(self, ace_bomb):
        """3 Aces in 2-player mode = ACE_BOMB."""
        result = identify(ace_bomb, player_count=2)
        assert result is not None
        assert result.type == PatternType.ACE_BOMB

    def test_ace_bomb_not_in_4players(self, ace_bomb):
        """3 Aces in 4-player mode does NOT form ACE_BOMB."""
        result = identify(ace_bomb, player_count=4)
        assert result is None

    def test_ace_bomb_length_is_3(self, ace_bomb):
        """ACE_BOMB length is always 3."""
        result = identify(ace_bomb, player_count=3)
        assert result.length == 3


# ═══════════════════════════════════════════════════════════════════════
# Edge cases & misc
# ═══════════════════════════════════════════════════════════════════════

class TestIdentifyEdgeCases:
    """Edge case tests for identify()."""

    def test_empty_cards_returns_none(self):
        """An empty list returns None."""
        result = identify([])
        assert result is None

    def test_bomb_priority_over_four_with_three(self, bomb_threes):
        """4 cards alone = BOMB, not FOUR_WITH_THREE with 0 kickers."""
        result = identify(bomb_threes)
        assert result.type == PatternType.BOMB

    def test_frozen_card_pattern(self):
        """CardPattern is frozen/immutable."""
        pattern = identify([c("NINE", "HEART")])
        assert pattern is not None
        with pytest.raises(Exception):
            pattern.main_rank = 99  # type: ignore


# ═══════════════════════════════════════════════════════════════════════
# get_pattern_display_name
# ═══════════════════════════════════════════════════════════════════════

class TestGetPatternDisplayName:
    """Tests for get_pattern_display_name()."""

    def test_known_pattern_returns_chinese(self):
        """Known patterns return their Chinese display name."""
        p = identify([c("KING", "SPADE")])
        assert p is not None
        name = get_pattern_display_name(p)
        assert name == "单张"

    def test_all_pattern_types_have_display(self):
        """Every PatternType has a non-empty display name."""
        for pt in PatternType:
            pattern = CardPattern(type=pt, main_rank=3, length=1)
            name = get_pattern_display_name(pattern)
            assert name, f"PatternType {pt} has no display name"
            assert name != "未知", f"PatternType {pt} returned '未知'"
