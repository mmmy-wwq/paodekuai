"""
Card model for 跑得快 (Pao De Kuai).

Suit hierarchy: ♠ > ♥ > ♣ > ♦ (used for first-player determination only)
Rank hierarchy: 3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Suit(Enum):
    """Card suit with priority for tiebreaking.

    Suit priority SPADE > HEART > CLUB > DIAMOND is used ONLY for
    determining the starting player, NOT for card value comparison.
    """
    SPADE = 0    # ♠
    HEART = 1    # ♥
    CLUB = 2     # ♣
    DIAMOND = 3  # ♦


class Rank(Enum):
    """Card rank with integer values for comparison.

    Higher value = bigger card.
    2 (15) > A (14) > K (13) > ... > 3 (3)
    """
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14
    TWO = 15


# Priority values for suit-based tiebreaking (higher = stronger)
SUIT_PRIORITY: dict[Suit, int] = {
    Suit.SPADE: 4,
    Suit.HEART: 3,
    Suit.CLUB: 2,
    Suit.DIAMOND: 1,
}

# Display mappings for UI rendering
SUIT_DISPLAY: dict[Suit, str] = {
    Suit.SPADE: "♠",
    Suit.HEART: "♥",
    Suit.CLUB: "♣",
    Suit.DIAMOND: "♦",
}

RANK_DISPLAY: dict[Rank, str] = {
    Rank.THREE: "3",
    Rank.FOUR: "4",
    Rank.FIVE: "5",
    Rank.SIX: "6",
    Rank.SEVEN: "7",
    Rank.EIGHT: "8",
    Rank.NINE: "9",
    Rank.TEN: "10",
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
    Rank.TWO: "2",
}


@dataclass(frozen=True)
class Card:
    """An immutable playing card.

    Comparison is by rank first, then suit priority (for tiebreaking).
    """
    suit: Suit
    rank: Rank

    def __lt__(self, other: "Card") -> bool:
        if self.rank.value != other.rank.value:
            return self.rank.value < other.rank.value
        return SUIT_PRIORITY[self.suit] < SUIT_PRIORITY[other.suit]

    def __le__(self, other: "Card") -> bool:
        if self.rank.value != other.rank.value:
            return self.rank.value <= other.rank.value
        return SUIT_PRIORITY[self.suit] <= SUIT_PRIORITY[other.suit]

    def __gt__(self, other: "Card") -> bool:
        if self.rank.value != other.rank.value:
            return self.rank.value > other.rank.value
        return SUIT_PRIORITY[self.suit] > SUIT_PRIORITY[other.suit]

    def __ge__(self, other: "Card") -> bool:
        if self.rank.value != other.rank.value:
            return self.rank.value >= other.rank.value
        return SUIT_PRIORITY[self.suit] >= SUIT_PRIORITY[other.suit]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    def __str__(self) -> str:
        return f"{SUIT_DISPLAY[self.suit]}{RANK_DISPLAY[self.rank]}"

    def __repr__(self) -> str:
        return f"Card(suit={self.suit.name}, rank={self.rank.name})"
