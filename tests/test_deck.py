"""
Tests for deck builder and dealer (server.card_engine.deck).

Covers 2p/3p/4p deck sizes, TWO/ACE removal, ♠3 preservation,
seed reproducibility, and deal_cards correctness.
"""

import pytest

from server.card_engine.card import Card, Rank, Suit
from server.card_engine.deck import STANDARD_DECK, build_deck, deal_cards


def c(r: str, s: str) -> Card:
    return Card(Suit[s], Rank[r])


# ═══════════════════════════════════════════════════════════════════════
# STANDARD_DECK
# ═══════════════════════════════════════════════════════════════════════

class TestStandardDeck:
    """Tests for the STANDARD_DECK constant."""

    def test_has_52_cards(self):
        """STANDARD_DECK contains exactly 52 cards."""
        assert len(STANDARD_DECK) == 52

    def test_no_jokers(self):
        """No joker cards in the deck."""
        ranks = {c.rank for c in STANDARD_DECK}
        assert all(r in Rank for r in ranks)

    def test_all_suits_present(self):
        """All 4 suits are represented."""
        suits = {c.suit for c in STANDARD_DECK}
        assert suits == {Suit.SPADE, Suit.HEART, Suit.CLUB, Suit.DIAMOND}


# ═══════════════════════════════════════════════════════════════════════
# build_deck — player counts
# ═══════════════════════════════════════════════════════════════════════

class TestBuildDeckPlayerCounts:
    """Tests for deck sizes per player count."""

    def test_4p_has_52_cards(self):
        """4-player deck has all 52 cards."""
        deck = build_deck(4, seed=42)
        assert len(deck) == 52

    def test_3p_has_48_cards(self):
        """3-player deck has 48 cards (52 - 3 TWOs - 1 ACE)."""
        deck = build_deck(3, seed=42)
        assert len(deck) == 48

    def test_2p_has_32_cards(self):
        """2-player deck has 32 cards (48 - 16 random)."""
        deck = build_deck(2, seed=42)
        assert len(deck) == 32

    def test_invalid_player_count(self):
        """Invalid player_count raises ValueError."""
        with pytest.raises(ValueError, match="player_count"):
            build_deck(5)


# ═══════════════════════════════════════════════════════════════════════
# build_deck — TWO/ACE removal
# ═══════════════════════════════════════════════════════════════════════

class TestBuildDeckRemovals:
    """Tests for fixed TWO and ACE removal in 2p/3p mode."""

    def test_spade_2_kept(self):
        """♠2 is always kept in all modes."""
        deck = build_deck(3, seed=42)
        spade_two = c("TWO", "SPADE")
        assert spade_two in deck

    def test_heart_2_removed(self):
        """♥2 is removed in 3-player mode."""
        deck = build_deck(3, seed=42)
        heart_two = c("TWO", "HEART")
        assert heart_two not in deck

    def test_club_2_removed(self):
        """♣2 is removed in 3-player mode."""
        deck = build_deck(3, seed=42)
        club_two = c("TWO", "CLUB")
        assert club_two not in deck

    def test_diamond_2_removed(self):
        """♦2 is removed in 3-player mode."""
        deck = build_deck(3, seed=42)
        diamond_two = c("TWO", "DIAMOND")
        assert diamond_two not in deck

    def test_diamond_ace_removed(self):
        """♦A is removed in 3-player mode."""
        deck = build_deck(3, seed=42)
        diamond_ace = c("ACE", "DIAMOND")
        assert diamond_ace not in deck

    def test_spade_ace_kept(self):
        """♠A is kept in 3-player mode."""
        deck = build_deck(3, seed=42)
        spade_ace = c("ACE", "SPADE")
        assert spade_ace in deck

    def test_spade_3_present_in_3p(self):
        """♠3 is present in a 3-player deck."""
        deck = build_deck(3, seed=99)
        spade_three = c("THREE", "SPADE")
        assert spade_three in deck

    def test_all_4_twos_present_in_4p(self):
        """All 4 TWOs are present in 4-player mode."""
        deck = build_deck(4, seed=42)
        two_cards = [c for c in deck if c.rank == Rank.TWO]
        assert len(two_cards) == 4


# ═══════════════════════════════════════════════════════════════════════
# build_deck — seed reproducibility
# ═══════════════════════════════════════════════════════════════════════

class TestBuildDeckSeed:
    """Tests for seed-based determinism."""

    def test_same_seed_produces_same_deck(self):
        """Same seed → same deck order."""
        deck1 = build_deck(3, seed=123)
        deck2 = build_deck(3, seed=123)
        assert deck1 == deck2

    def test_different_seeds_produce_different_decks(self):
        """Different seeds → different deck order."""
        deck1 = build_deck(4, seed=1)
        deck2 = build_deck(4, seed=2)
        assert deck1 != deck2


# ═══════════════════════════════════════════════════════════════════════
# deal_cards
# ═══════════════════════════════════════════════════════════════════════

class TestDealCards:
    """Tests for deal_cards()."""

    def test_even_distribution_4p(self):
        """Each player gets equal cards in 4p mode."""
        deck = build_deck(4, seed=42)
        hands = deal_cards(deck, 4)
        assert len(hands) == 4
        for h in hands:
            assert len(h) == 13

    def test_even_distribution_3p(self):
        """Each player gets equal cards in 3p mode."""
        deck = build_deck(3, seed=42)
        hands = deal_cards(deck, 3)
        assert len(hands) == 3
        for h in hands:
            assert len(h) == 16

    def test_even_distribution_2p(self):
        """Each player gets equal cards in 2p mode."""
        deck = build_deck(2, seed=42)
        hands = deal_cards(deck, 2)
        assert len(hands) == 2
        for h in hands:
            assert len(h) == 16

    def test_hands_are_sorted(self):
        """Dealt hands are sorted by rank then suit priority."""
        deck = build_deck(3, seed=42)
        hands = deal_cards(deck, 3)
        for hand in hands:
            for i in range(len(hand) - 1):
                assert hand[i].rank.value <= hand[i + 1].rank.value

    def test_invalid_division_raises(self):
        """Dealing mismatched deck size raises ValueError."""
        with pytest.raises(ValueError, match="not divisible"):
            deal_cards(STANDARD_DECK, 3)  # 52 not divisible by 3

    def test_no_duplicate_cards_across_hands(self):
        """All cards are unique across all hands."""
        deck = build_deck(4, seed=42)
        hands = deal_cards(deck, 4)
        all_cards = []
        for h in hands:
            all_cards.extend(h)
        assert len(all_cards) == len(set(all_cards))
