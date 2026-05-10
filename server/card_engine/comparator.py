"""
Card pattern comparator for 跑得快 (Pao De Kuai).

Determines whether one card pattern can beat another on the table,
enumerates all playable patterns from a hand, and finds the highest card.

Comparison Hierarchy (strongest to weakest):
  1. ACE_BOMB — beats everything (only in 2-3 player modes)
  2. BOMB — beats all non-bomb patterns; vs another bomb: higher main_rank wins
  3. Non-bomb patterns — only comparable within the same type

Cross-type comparison is NOT allowed except for bombs.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from typing import List, Optional

from server.card_engine.card import Card, Rank
from server.card_engine.recognizer import (
    CardPattern,
    PatternType,
    identify,
)


def can_beat(
    play: CardPattern,
    last_play: CardPattern,
    player_count: int = 3,
) -> bool:
    """Determine whether `play` can beat `last_play` on the table.

    Comparison rules (in priority order):
      1. ACE_BOMB beats everything — any pattern, including regular BOMB.
      2. Nothing beats ACE_BOMB.
      3. BOMB beats any non-bomb pattern, regardless of rank.
      4. Non-bomb CANNOT beat BOMB.
      5. Cross-type comparison NOT allowed (e.g., triple cannot beat a straight).
      6. Same-type comparison: higher main_rank wins.
         - For STRAIGHT: must also have the SAME length.
         - For CONSECUTIVE_PAIRS: compare main_rank only.
         - For all other same-type pairs: compare main_rank.

    Args:
        play: The card pattern being played.
        last_play: The card pattern currently on the table.
        player_count: Number of players (affects ACE_BOMB; unused but kept
                      for API consistency).

    Returns:
        True if `play` beats `last_play`, False otherwise.
    """
    # ── Rule 1: ACE_BOMB beats everything ──────────────────────────
    if play.type == PatternType.ACE_BOMB:
        return True

    # ── Rule 2: Nothing beats ACE_BOMB ─────────────────────────────
    if last_play.type == PatternType.ACE_BOMB:
        return False

    # ── Rule 3: BOMB vs non-bomb ───────────────────────────────────
    if play.type == PatternType.BOMB and last_play.type != PatternType.BOMB:
        return True

    # ── Rule 4: Non-bomb vs BOMB ───────────────────────────────────
    if last_play.type == PatternType.BOMB and play.type != PatternType.BOMB:
        return False

    # ── Rule 5: Cross-type comparison NOT allowed ──────────────────
    if play.type != last_play.type:
        return False

    # ── Rule 6: Same-type comparison ───────────────────────────────
    if play.type in (PatternType.STRAIGHT, PatternType.AIRPLANE, PatternType.CONSECUTIVE_PAIRS):
        # These patterns must have the same "length" (cards for straights,
        # triple count for airplanes, pair count for consecutive pairs).
        if play.length != last_play.length:
            return False

    # All other same-type comparisons: higher main_rank wins
    return play.main_rank > last_play.main_rank


def _generate_straights(
    distinct_ranks: List[int],
    cards_by_rank: dict[int, List[Card]],
) -> List[List[Card]]:
    """Generate all straight combinations from distinct ranks.

    A straight is a consecutive sequence of ≥5 distinct ranks.
    Only the highest-rank card from each rank is used (suit doesn't matter).

    Args:
        distinct_ranks: Sorted list of rank values that appear in the hand.
        cards_by_rank: Map from rank value to list of cards of that rank.

    Returns:
        List of card lists, each representing a valid straight candidate.
    """
    # Filter: no TWO (15) allowed in straights
    valid_ranks = [r for r in distinct_ranks if r != Rank.TWO.value]
    if len(valid_ranks) < 5:
        return []

    results: List[List[Card]] = []
    # Try all start indices
    for start in range(len(valid_ranks)):
        # Try all lengths ≥5
        for end in range(start + 5, len(valid_ranks) + 1):
            segment = valid_ranks[start:end]
            # Must be consecutive
            if any(segment[i + 1] - segment[i] != 1 for i in range(len(segment) - 1)):
                continue
            # ACE (14) only at the high end — if ACE is present, it must be
            # the last element. Since we check consecutiveness above, ACE
            # could only appear at position -1 or not at all.
            if Rank.ACE.value in segment and segment[-1] != Rank.ACE.value:
                continue
            # Build card list (one card per rank, pick any)
            cards: List[Card] = []
            for r in segment:
                cards.append(cards_by_rank[r][0])
            results.append(cards)

    return results


def _generate_consecutive_pairs(
    distinct_pairs: List[int],
    cards_by_rank: dict[int, List[Card]],
) -> List[List[Card]]:
    """Generate all consecutive pair combinations from the hand.

    A consecutive pair set is ≥2 pairs with consecutive ranks.
    Only the first 2 cards of each rank are used.

    Args:
        distinct_pairs: Sorted list of rank values that have ≥2 occurrences.
        cards_by_rank: Map from rank value to list of cards of that rank.

    Returns:
        List of card lists, each representing a valid consecutive pair candidate.
    """
    if len(distinct_pairs) < 2:
        return []

    results: List[List[Card]] = []
    for start in range(len(distinct_pairs)):
        for end in range(start + 2, len(distinct_pairs) + 1):
            segment = distinct_pairs[start:end]
            # Must be consecutive
            if any(segment[i + 1] - segment[i] != 1 for i in range(len(segment) - 1)):
                continue
            cards: List[Card] = []
            for r in segment:
                cards.extend(cards_by_rank[r][:2])
            results.append(cards)

    return results


def _generate_kicker_combos(
    all_cards: List[Card],
    core_cards: List[Card],
    kicker_count: int,
) -> List[List[Card]]:
    """Generate all valid kicker combinations for 三带二 / 四带三.

    Args:
        all_cards: All cards in the hand.
        core_cards: The core cards (the 3 or 4 of same rank).
        kicker_count: Number of kicker cards needed.

    Returns:
        List of card lists (core + kickers) forming valid patterns.
    """
    # Kickers must be cards NOT in the core set
    core_set = set(core_cards)
    available_kickers = [c for c in all_cards if c not in core_set]

    if len(available_kickers) < kicker_count:
        return []

    results: List[List[Card]] = []
    for kicker_combo in itertools.combinations(available_kickers, kicker_count):
        candidate = list(core_cards) + list(kicker_combo)
        results.append(candidate)
    return results


def _enumerate_all_patterns(
    hand: List[Card],
    player_count: int,
    has_ace_bomb: bool = True,
) -> List[CardPattern]:
    """Enumerate all valid card patterns that can be formed from a hand.

    Uses identify() to validate each candidate card combination.

    Args:
        hand: The player's current hand.
        player_count: Number of players (affects ACE_BOMB availability).

    Returns:
        List of all valid CardPattern instances that can be formed.
    """
    # Group cards by rank for efficient lookup
    cards_by_rank: dict[int, List[Card]] = defaultdict(list)
    for c in hand:
        cards_by_rank[c.rank.value].append(c)

    distinct_ranks = sorted(cards_by_rank.keys())
    patterns: List[CardPattern] = []
    seen: set[tuple] = set()  # deduplication key

    def _add(cards: List[Card]) -> None:
        """Validate a card list and add its pattern if valid and new."""
        p = identify(cards, player_count=player_count)
        if p is None:
            return
        # Deduplicate: same pattern can come from different card combinations
        key = (p.type, p.main_rank, p.length, p.kicker_count)
        if key in seen:
            return
        seen.add(key)
        patterns.append(p)

    # ── SINGLE (单张) ─────────────────────────────────────────────
    for c in hand:
        _add([c])

    # ── PAIR (对子) ──────────────────────────────────────────────
    for rank_val, cards in cards_by_rank.items():
        if len(cards) >= 2:
            _add(list(cards[:2]))

    # ── BOMB (炸弹) ──────────────────────────────────────────────
    for rank_val, cards in cards_by_rank.items():
        if len(cards) == 4:
            _add(list(cards))

    # ── ACE_BOMB (A炸) ──────────────────────────────────────────
    if has_ace_bomb and player_count in (2, 3):
        ace_cards = cards_by_rank.get(Rank.ACE.value, [])
        if len(ace_cards) == 3:
            _add(list(ace_cards))

    # ── STRAIGHT (顺子) ──────────────────────────────────────────
    for straight_cards in _generate_straights(distinct_ranks, cards_by_rank):
        _add(straight_cards)

    # ── CONSECUTIVE_PAIRS (连对) ─────────────────────────────────
    pair_ranks = sorted(
        r for r, cards in cards_by_rank.items() if len(cards) >= 2
    )
    for cp_cards in _generate_consecutive_pairs(pair_ranks, cards_by_rank):
        _add(cp_cards)

    # ── TRIPLE_WITH_TWO (三带二) ──────────────────────────────────
    for rank_val, cards in cards_by_rank.items():
        if len(cards) >= 3:
            core = list(cards[:3])
            for combo in _generate_kicker_combos(hand, core, kicker_count=2):
                _add(combo)

    # ── AIRPLANE (飞机带翅膀) ──────────────────────────────────
    # Find consecutive triple ranks (2+ triples, no TWO)
    triple_ranks = sorted(
        r for r, cards in cards_by_rank.items()
        if len(cards) >= 3 and r != Rank.TWO.value
    )
    for start in range(len(triple_ranks)):
        for end in range(start + 1, len(triple_ranks)):
            segment = triple_ranks[start:end + 1]
            if any(segment[i + 1] - segment[i] != 1 for i in range(len(segment) - 1)):
                continue
            triple_count = len(segment)
            # Build core cards: 3 per triple rank
            core: List[Card] = []
            for r in segment:
                core.extend(cards_by_rank[r][:3])
            # Generate kicker combos
            for combo in _generate_kicker_combos(hand, core, kicker_count=triple_count * 2):
                _add(combo)

    # ── FOUR_WITH_THREE (四带三) ─────────────────────────────────
    for rank_val, cards in cards_by_rank.items():
        if len(cards) == 4:
            core = list(cards)
            for combo in _generate_kicker_combos(hand, core, kicker_count=3):
                _add(combo)

    return patterns


def get_all_playable(
    hand: List[Card],
    last_play: Optional[CardPattern],
    player_count: int,
    is_must_play: bool = False,
    has_ace_bomb: bool = True,
) -> List[CardPattern]:
    """Enumerate all patterns from `hand` that can be legally played.

    Behavior depends on the table state:
      - If `last_play` is None (free play / new round):
          Enumerate ALL valid patterns from the hand.
      - If `last_play` has a pattern:
          Enumerate only patterns that CAN_BEAT the current play.
      - If `is_must_play` is True AND `last_play.type` is SINGLE:
          ONLY return SINGLE patterns (must-play rule: follow suit with singles).

    Uses the PatternRecognizer from recognizer.py to identify patterns.

    Args:
        hand: The player's current hand.
        last_play: The pattern currently on the table, or None for free play.
        player_count: Number of players in the game.
        is_must_play: If True and last_play is SINGLE, restrict to SINGLE only.

    Returns:
        List of CardPattern instances that can be legally played,
        sorted by pattern type priority (highest first).
    """
    # ── Must-play rule: only SINGLE ────────────────────────────────
    if (
        is_must_play
        and last_play is not None
        and last_play.type == PatternType.SINGLE
    ):
        patterns: List[CardPattern] = []
        seen: set[int] = set()
        for card in hand:
            p = identify([card], player_count=player_count)
            if p is not None and p.main_rank not in seen:
                seen.add(p.main_rank)
                patterns.append(p)
        return sorted(patterns, key=lambda p: p.main_rank, reverse=True)

    # ── Enumerate all valid patterns from hand ─────────────────────
    all_patterns = _enumerate_all_patterns(hand, player_count, has_ace_bomb)

    # ── Free play: return all ──────────────────────────────────────
    if last_play is None:
        return sorted(
            all_patterns,
            key=lambda p: (p.type.value, p.main_rank),
            reverse=True,
        )

    # ── Filter to only patterns that can beat last_play ────────────
    beatable: List[CardPattern] = []
    for p in all_patterns:
        if can_beat(p, last_play, player_count):
            beatable.append(p)

    return sorted(
        beatable,
        key=lambda p: (p.type.value, p.main_rank),
        reverse=True,
    )


def compare_max_single(hand: List[Card]) -> Card:
    """Return the card with the highest rank value in the hand.

    Comparison is by rank only (not suit). TWO (15) > ACE (14) > ... > THREE (3).
    If multiple cards share the highest rank, any one of them is returned.

    Args:
        hand: The player's current hand. Must be non-empty.

    Returns:
        The Card with the highest rank value.

    Raises:
        ValueError: If `hand` is empty.
    """
    if not hand:
        raise ValueError("Cannot find max single: hand is empty")

    return max(hand, key=lambda c: c.rank.value)
