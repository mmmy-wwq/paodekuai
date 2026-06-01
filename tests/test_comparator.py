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

    def test_ace_bomb_beats_bomb(self, ace_bomb):
        """ACE_BOMB beats a regular BOMB (but NOT non-bomb patterns)."""
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

    # ── Bug regression: ACE_BOMB should NOT beat non-bomb patterns ──

    def test_ace_bomb_cannot_beat_straight(self, ace_bomb):
        """ACE_BOMB CANNOT beat a straight (only beats bombs)."""
        play = identify(ace_bomb, player_count=3)
        last = identify([
            c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"),
            c("SIX", "DIAMOND"), c("SEVEN", "SPADE"),
        ])  # a straight
        assert play and last
        assert not can_beat(play, last), "A炸不能压顺子"

    def test_ace_bomb_cannot_beat_single(self, ace_bomb):
        """ACE_BOMB CANNOT beat a single card."""
        play = identify(ace_bomb, player_count=3)
        last = identify([c("THREE", "SPADE")])
        assert play and last
        assert not can_beat(play, last), "A炸不能压单张"

    def test_ace_bomb_cannot_beat_triple_with_two(self, ace_bomb):
        """ACE_BOMB CANNOT beat a triple_with_two."""
        play = identify(ace_bomb, player_count=3)
        last = identify([
            c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"),
            c("FOUR", "DIAMOND"), c("FIVE", "SPADE"),
        ])
        assert play and last
        assert last.type == PatternType.TRIPLE_WITH_TWO
        assert not can_beat(play, last), "A炸不能压三带二"

    def test_ace_bomb_still_beats_bomb(self, ace_bomb):
        """ACE_BOMB still beats regular bombs."""
        play = identify(ace_bomb, player_count=3)
        last = identify([
            c("FIVE", "SPADE"), c("FIVE", "HEART"),
            c("FIVE", "CLUB"), c("FIVE", "DIAMOND"),
        ])
        assert play and last
        assert can_beat(play, last), "A炸应能压炸弹"


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
    def test_airplane_same_length_higher_wins(self):
        """Higher airplane beats lower airplane of same length."""
        c = lambda r, s: Card(Suit[s], Rank[r])
        higher = identify([
            c("FIVE", "SPADE"), c("FIVE", "HEART"), c("FIVE", "CLUB"),
            c("SIX", "SPADE"), c("SIX", "HEART"), c("SIX", "CLUB"),
            c("NINE", "SPADE"), c("NINE", "HEART"),
            c("TEN", "SPADE"), c("TEN", "HEART"),
        ], player_count=3)
        lower = identify([
            c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"),
            c("FOUR", "SPADE"), c("FOUR", "HEART"), c("FOUR", "CLUB"),
            c("SEVEN", "SPADE"), c("SEVEN", "HEART"),
            c("EIGHT", "SPADE"), c("EIGHT", "HEART"),
        ], player_count=3)
        assert higher is not None and lower is not None
        assert higher.type == PatternType.AIRPLANE
        assert lower.type == PatternType.AIRPLANE
        assert can_beat(higher, lower, player_count=3) == True
        assert can_beat(lower, higher, player_count=3) == False

    def test_airplane_different_length_cannot_beat(self):
        """Airplane of different triple count cannot be compared."""
        c = lambda r, s: Card(Suit[s], Rank[r])
        longer = identify([
            c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"),
            c("FOUR", "SPADE"), c("FOUR", "HEART"), c("FOUR", "CLUB"),
            c("FIVE", "SPADE"), c("FIVE", "HEART"), c("FIVE", "CLUB"),
            c("EIGHT", "SPADE"), c("EIGHT", "HEART"),
            c("NINE", "SPADE"), c("NINE", "HEART"),
            c("TEN", "SPADE"), c("TEN", "HEART"),
        ], player_count=3)  # 3 triples + 6 kickers
        shorter = identify([
            c("SIX", "SPADE"), c("SIX", "HEART"), c("SIX", "CLUB"),
            c("SEVEN", "SPADE"), c("SEVEN", "HEART"), c("SEVEN", "CLUB"),
            c("NINE", "SPADE"), c("NINE", "HEART"),
            c("TEN", "SPADE"), c("TEN", "HEART"),
        ], player_count=3)  # 2 triples + 4 kickers
        assert longer is not None and shorter is not None
        assert longer.type == PatternType.AIRPLANE
        assert shorter.type == PatternType.AIRPLANE
        # Different lengths → cross-type → cannot beat
        assert can_beat(longer, shorter, player_count=3) == False

    def test_nothing_beats_airplane_except_bomb(self):
        """Non-bomb patterns cannot beat an airplane."""
        airplane = identify([
            Card(Suit['SPADE'], Rank['THREE']),
            Card(Suit['HEART'], Rank['THREE']),
            Card(Suit['CLUB'], Rank['THREE']),
            Card(Suit['SPADE'], Rank['FOUR']),
            Card(Suit['HEART'], Rank['FOUR']),
            Card(Suit['CLUB'], Rank['FOUR']),
            Card(Suit['SPADE'], Rank['SEVEN']),
            Card(Suit['HEART'], Rank['SEVEN']),
            Card(Suit['SPADE'], Rank['EIGHT']),
            Card(Suit['HEART'], Rank['EIGHT']),
        ], player_count=3)
        single = identify([Card(Suit['SPADE'], Rank['ACE'])])
        pair = identify([Card(Suit['SPADE'], Rank['ACE']), Card(Suit['HEART'], Rank['ACE'])])
        straight = identify([
            Card(Suit['SPADE'], Rank['FIVE']),
            Card(Suit['HEART'], Rank['SIX']),
            Card(Suit['CLUB'], Rank['SEVEN']),
            Card(Suit['DIAMOND'], Rank['EIGHT']),
            Card(Suit['SPADE'], Rank['NINE']),
        ], player_count=3)
        assert airplane is not None
        assert single is not None and pair is not None and straight is not None
        assert can_beat(single, airplane, player_count=3) == False
        assert can_beat(pair, airplane, player_count=3) == False
        assert can_beat(straight, airplane, player_count=3) == False

    def test_free_play_includes_airplane(self, hand_16_cards_mixed):
        """Free play enumeration should include airplane patterns."""
        # Use a hand that can form an airplane
        hand = [
            Card(Suit['SPADE'], Rank['THREE']),
            Card(Suit['HEART'], Rank['THREE']),
            Card(Suit['CLUB'], Rank['THREE']),
            Card(Suit['SPADE'], Rank['FOUR']),
            Card(Suit['HEART'], Rank['FOUR']),
            Card(Suit['CLUB'], Rank['FOUR']),
            Card(Suit['SPADE'], Rank['SEVEN']),
            Card(Suit['HEART'], Rank['SEVEN']),
            Card(Suit['SPADE'], Rank['EIGHT']),
            Card(Suit['HEART'], Rank['EIGHT']),
            Card(Suit['SPADE'], Rank['NINE']),
            Card(Suit['HEART'], Rank['NINE']),
        ]
        patterns = get_all_playable(hand, None, player_count=3)
        airplane_patterns = [p for p in patterns if p.type == PatternType.AIRPLANE]
        assert len(airplane_patterns) >= 1


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

    def test_bomb_beats_airplane(self):
        """BOMB can beat an AIRPLANE."""
        cards = [
            Card(Suit['SPADE'], Rank['THREE']), Card(Suit['HEART'], Rank['THREE']),
            Card(Suit['CLUB'], Rank['THREE']), Card(Suit['DIAMOND'], Rank['THREE']),
        ]
        bomb = identify(cards, player_count=3)
        airplane = identify([
            Card(Suit['SPADE'], Rank['FIVE']), Card(Suit['HEART'], Rank['FIVE']),
            Card(Suit['CLUB'], Rank['FIVE']),
            Card(Suit['SPADE'], Rank['SIX']), Card(Suit['HEART'], Rank['SIX']),
            Card(Suit['CLUB'], Rank['SIX']),
            Card(Suit['SPADE'], Rank['NINE']), Card(Suit['HEART'], Rank['NINE']),
            Card(Suit['SPADE'], Rank['TEN']), Card(Suit['HEART'], Rank['TEN']),
        ], player_count=3)
        assert bomb is not None and airplane is not None
        assert bomb.type == PatternType.BOMB
        assert airplane.type == PatternType.AIRPLANE
        assert can_beat(bomb, airplane, player_count=3) == True

    def test_airplane_cannot_beat_non_airplane(self):
        """Airplane cannot beat non-airplane patterns (cross-type)."""
        airplane = identify([
            Card(Suit['SPADE'], Rank['THREE']), Card(Suit['HEART'], Rank['THREE']),
            Card(Suit['CLUB'], Rank['THREE']),
            Card(Suit['SPADE'], Rank['FOUR']), Card(Suit['HEART'], Rank['FOUR']),
            Card(Suit['CLUB'], Rank['FOUR']),
            Card(Suit['SPADE'], Rank['SEVEN']), Card(Suit['HEART'], Rank['SEVEN']),
            Card(Suit['SPADE'], Rank['EIGHT']), Card(Suit['HEART'], Rank['EIGHT']),
        ], player_count=3)
        single = identify([Card(Suit['SPADE'], Rank['ACE'])])
        assert airplane is not None and single is not None
        # Airplane cannot beat a single (cross-type)
        assert can_beat(airplane, single, player_count=3) == False

    def test_airplane_on_table_filters_correctly(self):
        """With airplane on table, only same-length higher airplane or bombs returned."""
        # Hand has a higher airplane (777+888) and a bomb (3333)
        hand = [
            Card(Suit['SPADE'], Rank['SEVEN']), Card(Suit['HEART'], Rank['SEVEN']),
            Card(Suit['CLUB'], Rank['SEVEN']),
            Card(Suit['SPADE'], Rank['EIGHT']), Card(Suit['HEART'], Rank['EIGHT']),
            Card(Suit['CLUB'], Rank['EIGHT']),
            Card(Suit['SPADE'], Rank['JACK']), Card(Suit['HEART'], Rank['JACK']),
            Card(Suit['SPADE'], Rank['QUEEN']), Card(Suit['HEART'], Rank['QUEEN']),
        ]  # 777+888+J+J+Q+Q = 2 triples + 4 kickers = airplane
        # Last play is a lower airplane (555+666)
        last = identify([
            Card(Suit['SPADE'], Rank['FIVE']), Card(Suit['HEART'], Rank['FIVE']),
            Card(Suit['CLUB'], Rank['FIVE']),
            Card(Suit['SPADE'], Rank['SIX']), Card(Suit['HEART'], Rank['SIX']),
            Card(Suit['CLUB'], Rank['SIX']),
            Card(Suit['SPADE'], Rank['NINE']), Card(Suit['HEART'], Rank['NINE']),
            Card(Suit['SPADE'], Rank['TEN']), Card(Suit['HEART'], Rank['TEN']),
        ], player_count=3)
        assert last is not None and last.type == PatternType.AIRPLANE
        patterns = get_all_playable(hand, last, player_count=3)
        # Should include 777+888 airplane (higher same-length)
        has_higher_airplane = any(
            p.type == PatternType.AIRPLANE and p.main_rank > last.main_rank
            for p in patterns
        )
        assert has_higher_airplane, f"Should find higher airplane in {patterns}"
        # All airplane patterns should be same length
        for p in patterns:
            if p.type == PatternType.AIRPLANE:
                assert p.length == last.length, f"Airplane length {p.length} != {last.length}"


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
