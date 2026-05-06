"""
Deck builder and dealer for 跑得快 (Pao De Kuai).

Supports 2, 3, and 4 player modes with different deck configurations:

+------+-----------+------------------------------+-------------+---------------+
| Mode | Base Deck | Removals                     | Final Size  | Cards/Player  |
+------+-----------+------------------------------+-------------+---------------+
| 2p   | 52 cards  | 3x TWO + 1x ACE + 16 random  | 32          | 16            |
| 3p   | 52 cards  | 3x TWO + 1x ACE              | 48          | 16            |
| 4p   | 52 cards  | None                         | 52          | 13            |
+------+-----------+------------------------------+-------------+---------------+

Removal rules:
- 3 of Rank.TWO: Remove the LAST 3 cards by suit enum order
  (DIAMOND, CLUB, HEART), keeping SPADE TWO (♠2).
- 1 of Rank.ACE: Remove the LAST card by suit enum order
  (DIAMOND), keeping SPADE, HEART, CLUB Aces.
- 2p random removal: 16 cards randomly removed from the remaining 48
  after the fixed removals above.
- No jokers in any mode.
"""

from __future__ import annotations

import random
from typing import List, Optional

from server.card_engine.card import Card, Rank, Suit


#: The standard 52-card deck (4 suits × 13 ranks, no jokers).
STANDARD_DECK: List[Card] = [Card(suit, rank) for suit in Suit for rank in Rank]


def build_deck(
    player_count: int,
    seed: Optional[int] = None,
) -> List[Card]:
    """Build and shuffle a deck for the given player count.

    Args:
        player_count: Number of players (2, 3, or 4).
        seed: Optional seed for deterministic shuffling.

    Returns:
        A shuffled list of Cards.

    Raises:
        ValueError: If player_count is not 2, 3, or 4.
    """
    if player_count not in (2, 3, 4):
        raise ValueError(
            f"player_count must be 2, 3, or 4, got {player_count}"
        )

    rng = random.Random(seed)
    deck = list(STANDARD_DECK)

    if player_count in (2, 3):
        # Remove 3 of Rank.TWO: last 3 by suit enum order
        # Suit enum order: SPADE(0) < HEART(1) < CLUB(2) < DIAMOND(3)
        # Remove HEART, CLUB, DIAMOND → keep SPADE TWO (♠2)
        twos = sorted(
            [c for c in deck if c.rank == Rank.TWO],
            key=lambda c: c.suit.value,
        )
        for c in twos[-3:]:  # HEART, CLUB, DIAMOND
            deck.remove(c)

        # Remove 1 of Rank.ACE: last by suit enum order
        # Remove DIAMOND → keep SPADE, HEART, CLUB Aces
        aces = sorted(
            [c for c in deck if c.rank == Rank.ACE],
            key=lambda c: c.suit.value,
        )
        deck.remove(aces[-1])  # DIAMOND ACE

    if player_count == 2:
        # Remove 16 random cards (from the remaining 48)
        to_remove = rng.sample(deck, 16)
        for c in to_remove:
            deck.remove(c)

    # Shuffle the final deck
    rng.shuffle(deck)
    return deck


def deal_cards(deck: List[Card], num_players: int) -> List[List[Card]]:
    """Deal cards evenly to players, sorted by rank.

    Cards are dealt in order from the shuffled deck. Each player's hand
    is then sorted using Card's natural ordering (rank first, then suit
    priority for tiebreaking).

    Args:
        deck: The shuffled deck to deal from.
        num_players: Number of players to deal to.

    Returns:
        A list of lists, where each inner list is one player's hand.
        The number of hands equals num_players, and each hand is sorted.

    Raises:
        ValueError: If the deck size is not divisible by num_players.
    """
    if len(deck) % num_players != 0:
        raise ValueError(
            f"Deck size {len(deck)} is not divisible by {num_players} players"
        )

    cards_per_player = len(deck) // num_players
    hands: List[List[Card]] = []
    for i in range(num_players):
        start = i * cards_per_player
        end = start + cards_per_player
        hand = deck[start:end]
        hands.append(sorted(hand))

    return hands
