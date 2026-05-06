"""
Shared pytest fixtures for 跑得快 (Pao De Kuai) test suite.

Provides card creation helpers, sample hands, and common
game-object fixtures used across all backend test modules.
"""

from __future__ import annotations

import pytest

from server.card_engine.card import Card, Rank, Suit


# ═══════════════════════════════════════════════════════════════════════
# Card creation helper
# ═══════════════════════════════════════════════════════════════════════

def c(rank_str: str, suit_str: str) -> Card:
    """Create a Card from Rank/Suit enum names.

    Examples:
        c("THREE", "SPADE")   → ♠3
        c("ACE", "HEART")     → ♥A
        c("TWO", "CLUB")      → ♣2
    """
    return Card(Suit[suit_str], Rank[rank_str])


# Shorthand for quick card building in test code
S = Suit
R = Rank


# ═══════════════════════════════════════════════════════════════════════
# Single-card fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def s3() -> Card:
    """♠3 — the first-player card."""
    return c("THREE", "SPADE")


@pytest.fixture
def s2() -> Card:
    """♠2 — highest single card (kept in all modes)."""
    return c("TWO", "SPADE")


@pytest.fixture
def d2() -> Card:
    """♦2 — a TWO that gets removed in 2p/3p mode."""
    return c("TWO", "DIAMOND")


@pytest.fixture
def hA() -> Card:
    """♥A — one of the kept Aces."""
    return c("ACE", "HEART")


@pytest.fixture
def dA() -> Card:
    """♦A — the removed Ace in 2p/3p mode."""
    return c("ACE", "DIAMOND")


# ═══════════════════════════════════════════════════════════════════════
# Multi-card fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def pair_threes() -> list[Card]:
    """A PAIR of 3s."""
    return [c("THREE", "SPADE"), c("THREE", "HEART")]


@pytest.fixture
def bomb_threes() -> list[Card]:
    """A BOMB of 3s (4 cards)."""
    return [
        c("THREE", "SPADE"), c("THREE", "HEART"),
        c("THREE", "CLUB"), c("THREE", "DIAMOND"),
    ]


@pytest.fixture
def ace_bomb() -> list[Card]:
    """An ACE_BOMB (3 Aces)."""
    return [
        c("ACE", "SPADE"), c("ACE", "HEART"), c("ACE", "CLUB"),
    ]


@pytest.fixture
def straight_34567() -> list[Card]:
    """A 5-card straight 3-4-5-6-7."""
    return [
        c("THREE", "SPADE"), c("FOUR", "HEART"),
        c("FIVE", "CLUB"), c("SIX", "DIAMOND"),
        c("SEVEN", "SPADE"),
    ]


@pytest.fixture
def straight_10JQKA() -> list[Card]:
    """A 5-card straight 10-J-Q-K-A (ACE at high end)."""
    return [
        c("TEN", "SPADE"), c("JACK", "HEART"),
        c("QUEEN", "CLUB"), c("KING", "DIAMOND"),
        c("ACE", "SPADE"),
    ]


@pytest.fixture
def straight_A2345() -> list[Card]:
    """Invalid straight: ACE at low end (A-2-3-4-5 rejected)."""
    return [
        c("ACE", "SPADE"), c("TWO", "HEART"),
        c("THREE", "CLUB"), c("FOUR", "DIAMOND"),
        c("FIVE", "SPADE"),
    ]


@pytest.fixture
def consecutive_pairs_3344() -> list[Card]:
    """Consecutive pairs 3-3-4-4."""
    return [
        c("THREE", "SPADE"), c("THREE", "HEART"),
        c("FOUR", "CLUB"), c("FOUR", "DIAMOND"),
    ]


@pytest.fixture
def triple_with_two() -> list[Card]:
    """Triple 5s with two kickers (5 cards total)."""
    return [
        c("FIVE", "SPADE"), c("FIVE", "HEART"), c("FIVE", "CLUB"),
        c("THREE", "DIAMOND"), c("FOUR", "SPADE"),
    ]


@pytest.fixture
def four_with_three() -> list[Card]:
    """Four 6s with three kickers (7 cards total)."""
    return [
        c("SIX", "SPADE"), c("SIX", "HEART"), c("SIX", "CLUB"), c("SIX", "DIAMOND"),
        c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"),
    ]


@pytest.fixture
def single_nine() -> list[Card]:
    """A single 9."""
    return [c("NINE", "HEART")]


# ═══════════════════════════════════════════════════════════════════════
# Hand fixtures for rule/state-machine tests
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def hand_16_cards_mixed() -> list[Card]:
    """A realistic 16-card hand with various ranks for 3p testing."""
    return [
        c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"),
        c("FOUR", "SPADE"), c("FOUR", "DIAMOND"),
        c("FIVE", "HEART"), c("FIVE", "CLUB"),
        c("SIX", "SPADE"), c("SIX", "DIAMOND"),
        c("SEVEN", "CLUB"), c("SEVEN", "DIAMOND"),
        c("EIGHT", "SPADE"), c("EIGHT", "HEART"),
        c("NINE", "CLUB"),
        c("TEN", "DIAMOND"),
        c("JACK", "HEART"),
    ]


@pytest.fixture
def hand_with_spade3() -> list[Card]:
    """A hand containing ♠3 for first-player determination."""
    return [
        c("THREE", "SPADE"), c("FIVE", "HEART"),
        c("EIGHT", "CLUB"), c("TEN", "DIAMOND"),
    ]


@pytest.fixture
def hand_5cards_simple() -> list[Card]:
    """A 5-card hand: 3, 4, 5, 6, 7 of mixed suits."""
    return [
        c("THREE", "SPADE"), c("FOUR", "HEART"),
        c("FIVE", "CLUB"), c("SIX", "DIAMOND"),
        c("SEVEN", "SPADE"),
    ]
