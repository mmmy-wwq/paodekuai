"""
Tests for card pattern comparator (server.card_engine.comparator).

Covers same-type comparison, cross-type enforcement, bomb hierarchy,
ACE_BOMB supremacy, straight length checks, playable enumeration,
and max-single lookups.
"""

import pytest

from server.card_engine.card import Card, Rank, Suit
from server.card_engine.recognizer import (
    PatternType,
    identify,
)
from server.card_engine.comparator import (
    can_beat,
    compare_max_single,
    get_all_playable,
)


def c(r: str, s: str) -> Card:
    return Card(Suit[s], Rank[r])


# ═══════════════════════════════════════════════════════════════════════
# can_beat — same-type comparison
# ═══════════════════════════════════════════════════════════════════════

class TestCanBeatSameType:
    """Tests for can_beat with same-type patterns."""

    def test_higher_single_beats_lower(self):
        """A higher-ranked SINGLE beats a lower one."""
        play = identify([c("KING", "SPADE")])
        last = identify([c("QUEEN", "HEART")])
        assert play and last
        assert can_beat(play, last)

    def test_lower_single_cannot_beat_higher(self):
        """A lower-ranked SINGLE cannot beat a higher one."""
        play = identify([c("FOUR", "CLUB")])
        last = identify([c("NINE", "SPADE")])
        assert play and last
        assert not can_beat(play, last)

    def test_higher_pair_beats_lower(self):
        """A higher-ranked PAIR beats a lower one."""
        play = identify([c("TEN", "SPADE"), c("TEN", "HEART")])
        last = identify([c("FIVE", "CLUB"), c("FIVE", "DIAMOND")])
        assert play and last
        assert can_beat(play, last)

    def test_same_rank_single_no_beat(self):
        """Same-rank SINGLEs cannot beat each other (rank must be HIGHER)."""
        play = identify([c("JACK", "SPADE")])
        last = identify([c("JACK", "HEART")])
        assert play and last
        assert not can_beat(play, last)

    def test_higher_consecutive_pairs_beat_lower(self):
        """Higher-ranked consecutive pairs beat lower ones."""
        play_cards = [
            c("SEVEN", "SPADE"), c("SEVEN", "HEART"),
            c("EIGHT", "CLUB"), c("EIGHT", "DIAMOND"),
        ]
        last_cards = [
            c("FIVE", "SPADE"), c("FIVE", "HEART"),
            c("SIX", "CLUB"), c("SIX", "DIAMOND"),
        ]
        play = identify(play_cards)
        last = identify(last_cards)
        assert play and last
        assert can_beat(play, last)

    def test_higher_triple_with_two_beats_lower(self):
        """Higher-ranked 三带二 beats lower one."""
        play_cards = [
            c("KING", "SPADE"), c("KING", "HEART"), c("KING", "CLUB"),
            c("THREE", "DIAMOND"), c("FOUR", "SPADE"),
        ]
        last_cards = [
            c("TEN", "SPADE"), c("TEN", "HEART"), c("TEN", "CLUB"),
            c("FIVE", "DIAMOND"), c("SIX", "SPADE"),
        ]
        play = identify(play_cards)
        last = identify(last_cards)
        assert play and last
        assert can_beat(play, last)


# ═══════════════════════════════════════════════════════════════════════
# can_beat — cross-type enforcement
# ═══════════════════════════════════════════════════════════════════════

class TestCanBeatCrossType:
    """Tests for can_beat with cross-type patterns."""

    def test_pair_cannot_beat_single(self, pair_threes):
        """A PAIR cannot beat a SINGLE (cross-type not allowed)."""
        play = identify(pair_threes)
        last = identify([c("THREE", "DIAMOND")])
        assert play and last
        assert not can_beat(play, last)

    def test_straight_cannot_beat_pair(self, straight_34567):
        """A STRAIGHT cannot beat a PAIR."""
        play = identify(straight_34567)
        last = identify([c("QUEEN", "SPADE"), c("QUEEN", "HEART")])
        assert play and last
        assert not can_beat(play, last)

    def test_triple_with_two_cannot_beat_straight(self, triple_with_two):
        """三带二 cannot beat a STRAIGHT."""
        play = identify(triple_with_two)
        last = identify([
            c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"),
            c("SIX", "DIAMOND"), c("SEVEN", "SPADE"),
        ])
        assert play and last
        assert not can_beat(play, last)


# ═══════════════════════════════════════════════════════════════════════
# can_beat — bomb hierarchy
# ═══════════════════════════════════════════════════════════════════════

class TestCanBeatBomb:
    """Tests for BOMB and ACE_BOMB comparison rules."""

    def test_bomb_beats_any_non_bomb(self, bomb_threes):
        """A BOMB beats any non-bomb pattern regardless of rank."""
        play = identify(bomb_threes)  # 3s bomb
        # A high Straight (10-J-Q-K-A) should lose to any bomb
        last = identify([
            c("TEN", "SPADE"), c("JACK", "HEART"), c("QUEEN", "CLUB"),
            c("KING", "DIAMOND"), c("ACE", "SPADE"),
        ])
        assert play and last
        assert can_beat(play, last)

    def test_higher_bomb_beats_lower_bomb(self):
        """A higher-ranked BOMB beats a lower-ranked BOMB."""
        play = identify([
            c("KING", "SPADE"), c("KING", "HEART"),
            c("KING", "CLUB"), c("KING", "DIAMOND"),
        ])
        last = identify([
            c("THREE", "SPADE"), c("THREE", "HEART"),
            c("THREE", "CLUB"), c("THREE", "DIAMOND"),
        ])
        assert play and last
        assert can_beat(play, last)

    def test_lower_bomb_cannot_beat_higher_bomb(self):
        """A lower-ranked BOMB cannot beat a higher-ranked BOMB."""
        play = identify([
            c("FIVE", "SPADE"), c("FIVE", "HEART"),
            c("FIVE", "CLUB"), c("FIVE", "DIAMOND"),
        ])
        last = identify([
            c("TWO", "SPADE"), c("TWO", "HEART"),
            c("TWO", "CLUB"), c("TWO", "DIAMOND"),
        ])
        assert play and last
        assert not can_beat(play, last)

    def test_non_bomb_cannot_beat_bomb(self):
        """A non-bomb pattern cannot beat a BOMB."""
        play = identify([c("TWO", "SPADE")])  # highest single
        last = identify([
            c("THREE", "SPADE"), c("THREE", "HEART"),
            c("THREE", "CLUB"), c("THREE", "DIAMOND"),
        ])  # lowest bomb
        assert play and last
        assert not can_beat(play, last)


# ═══════════════════════════════════════════════════════════════════════
# can_beat — ACE_BOMB supremacy
# ═══════════════════════════════════════════════════════════════════════

class TestCanBeatAceBomb:
    """Tests for ACE_BOMB supremacy rules."""

    def test_ace_bomb_beats_everything(self, ace_bomb):
        """ACE_BOMB beats any pattern, including regular BOMB."""
        play = identify(ace_bomb, player_count=3)
        last = identify([
            c("TWO", "SPADE"), c("TWO", "HEART"),
            c("TWO", "CLUB"), c("TWO", "DIAMOND"),
        ])  # highest possible bomb
        assert play and last
        assert play.type == PatternType.ACE_BOMB
        assert can_beat(play, last)

    def test_nothing_beats_ace_bomb(self, ace_bomb):
        """No pattern can beat an ACE_BOMB."""
        last = identify(ace_bomb, player_count=3)
        play = identify([
            c("TWO", "SPADE"), c("TWO", "HEART"),
            c("TWO", "CLUB"), c("TWO", "DIAMOND"),
        ])
        assert play and last
        assert not can_beat(play, last)


# ═══════════════════════════════════════════════════════════════════════
# can_beat — straight length check
# ═══════════════════════════════════════════════════════════════════════

class TestCanBeatStraightLength:
    """Tests for STRAIGHT length-matching requirement."""

    def test_straight_must_match_length(self):
        """A 6-card straight cannot beat a 5-card straight even if rank is higher."""
        play = identify([
            c("FOUR", "SPADE"), c("FIVE", "HEART"), c("SIX", "CLUB"),
            c("SEVEN", "DIAMOND"), c("EIGHT", "SPADE"), c("NINE", "HEART"),
        ])
        last = identify([
            c("TEN", "SPADE"), c("JACK", "HEART"), c("QUEEN", "CLUB"),
            c("KING", "DIAMOND"), c("ACE", "SPADE"),
        ])
        assert play and last
        assert not can_beat(play, last)

    def test_same_length_higher_straight_beats(self):
        """A longer straight with higher main rank CAN beat a shorter one? No — same length required."""
        play = identify([
            c("EIGHT", "SPADE"), c("NINE", "HEART"), c("TEN", "CLUB"),
            c("JACK", "DIAMOND"), c("QUEEN", "SPADE"),
        ])
        last = identify([
            c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"),
            c("SIX", "DIAMOND"), c("SEVEN", "SPADE"),
        ])
        assert play and last
        assert can_beat(play, last)


# ═══════════════════════════════════════════════════════════════════════
# get_all_playable
# ═══════════════════════════════════════════════════════════════════════

class TestGetAllPlayable:
    """Tests for get_all_playable enumeration."""

    def test_free_play_returns_all_patterns(self, hand_16_cards_mixed):
        """With no last_play, free play returns all valid patterns."""
        patterns = get_all_playable(hand_16_cards_mixed, None, player_count=3)
        assert len(patterns) > 0
        # Should include SINGLEs for each distinct rank
        types_found = {p.type for p in patterns}
        assert PatternType.SINGLE in types_found

    def test_filter_to_beatable(self, hand_16_cards_mixed):
        """When last_play exists on table, only beatable patterns returned."""
        last = identify([c("THREE", "SPADE")])
        assert last
        patterns = get_all_playable(hand_16_cards_mixed, last, player_count=3)
        # All returned patterns should have main_rank > 3 or be bombs
        for p in patterns:
            assert can_beat(p, last, player_count=3)

    def test_bomb_on_table_only_bombs_beatable(self):
        """When a BOMB is on the table, only higher bombs or ACE_BOMB can beat it."""
        hand = [
            c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("THREE", "DIAMOND"),
            c("FIVE", "SPADE"), c("FIVE", "HEART"), c("FIVE", "CLUB"), c("FIVE", "DIAMOND"),
            c("TWO", "SPADE"), c("KING", "HEART"),
        ]
        last = identify([
            c("SEVEN", "SPADE"), c("SEVEN", "HEART"),
            c("SEVEN", "CLUB"), c("SEVEN", "DIAMOND"),
        ])
        assert last
        patterns = get_all_playable(hand, last, player_count=4)
        for p in patterns:
            assert p.type in (PatternType.BOMB, PatternType.ACE_BOMB)

    def test_must_play_returns_only_singles(self, hand_16_cards_mixed):
        """Must-play mode with SINGLE on table returns only SINGLE patterns."""
        last = identify([c("FOUR", "SPADE")])
        assert last
        patterns = get_all_playable(
            hand_16_cards_mixed, last, player_count=3, is_must_play=True
        )
        for p in patterns:
            assert p.type == PatternType.SINGLE

    def test_must_play_singles_descending(self, hand_16_cards_mixed):
        """Must-play SINGLEs are returned in descending rank order."""
        last = identify([c("THREE", "SPADE")])
        assert last
        patterns = get_all_playable(
            hand_16_cards_mixed, last, player_count=3, is_must_play=True
        )
        # Verify descending order
        for i in range(len(patterns) - 1):
            assert patterns[i].main_rank >= patterns[i + 1].main_rank


# ═══════════════════════════════════════════════════════════════════════
# compare_max_single
# ═══════════════════════════════════════════════════════════════════════

class TestCompareMaxSingle:
    """Tests for compare_max_single()."""

    def test_returns_highest_rank(self):
        """Returns the card with the highest rank value."""
        hand = [
            c("THREE", "SPADE"), c("KING", "HEART"), c("TWO", "CLUB"),
        ]
        result = compare_max_single(hand)
        assert result.rank == Rank.TWO

    def test_empty_hand_raises(self):
        """Empty hand raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            compare_max_single([])

    def test_multiple_same_rank_returns_any(self):
        """When multiple cards share the highest rank, any one is returned."""
        hand = [
            c("ACE", "SPADE"), c("ACE", "HEART"), c("THREE", "CLUB"),
        ]
        result = compare_max_single(hand)
        assert result.rank == Rank.ACE
