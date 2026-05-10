"""
Card pattern recognizer for 跑得快 (Pao De Kuai).

Given a list of cards, identifies the valid card pattern (if any) based on
the game's type hierarchy. Recognition is exclusive: each set of cards
matches exactly one pattern type, checked from highest to lowest priority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from server.card_engine.card import Card, Rank


class PatternType(Enum):
    """Card pattern types in priority order (highest first).

    Used by identify() to determine which pattern a set of cards forms.
    Actual recognition priority is determined by the check order in identify(),
    not by enum member order.
    """
    SINGLE = 1             # 单张
    PAIR = 2               # 对子
    CONSECUTIVE_PAIRS = 3  # 连对
    STRAIGHT = 4           # 顺子
    TRIPLE_WITH_TWO = 5    # 三带二
    BOMB = 6               # 炸弹
    FOUR_WITH_THREE = 7    # 四带三
    ACE_BOMB = 8           # A炸


# Friendly Chinese display names for pattern types
_PATTERN_DISPLAY: dict[PatternType, str] = {
    PatternType.SINGLE: "单张",
    PatternType.PAIR: "对子",
    PatternType.CONSECUTIVE_PAIRS: "连对",
    PatternType.STRAIGHT: "顺子",
    PatternType.TRIPLE_WITH_TWO: "三带二",
    PatternType.BOMB: "炸弹",
    PatternType.FOUR_WITH_THREE: "四带三",
    PatternType.ACE_BOMB: "A炸",
}


@dataclass(frozen=True)
class CardPattern:
    """Result of card pattern recognition.

    Attributes:
        type: The recognized pattern type.
        main_rank: The integer rank value of the primary card group.
                   For BOMB/ACE_BOMB: the rank of the repeated cards.
                   For FOUR_WITH_THREE: the rank that appears 4 times.
                   For TRIPLE_WITH_TWO: the rank that appears 3 times.
                   For STRAIGHT: the highest rank in the straight.
                   For CONSECUTIVE_PAIRS: the highest pair rank.
                   For PAIR/SINGLE: the rank of the card(s).
        length: Number of "units" in the pattern.
                For STRAIGHT: number of cards.
                For CONSECUTIVE_PAIRS: number of pairs.
                For BOMB: always 4.
                For ACE_BOMB: always 3.
                For PAIR/SINGLE: always 1.
        kicker_count: Number of kicker (non-core-group) cards.
                       Only meaningful for FOUR_WITH_THREE and TRIPLE_WITH_TWO.
                       Always 0 for other pattern types.
    """
    type: PatternType
    main_rank: int
    length: int
    kicker_count: int = 0


def get_pattern_display_name(pattern: CardPattern) -> str:
    """Return the Chinese display name for a card pattern.

    Args:
        pattern: A recognized CardPattern instance.

    Returns:
        String like "单张", "对子", "顺子", "三带二", etc.
    """
    return _PATTERN_DISPLAY.get(pattern.type, "未知")


# Valid rank values for straights. TWO (15) is excluded.
# ACE (14) is allowed but only at the high end.
_STRAIGHT_RANKS = frozenset(
    r.value for r in Rank if r != Rank.TWO
)


def _is_consecutive(ranks: List[int]) -> bool:
    """Check if sorted ranks form a consecutive sequence with step 1."""
    for i in range(len(ranks) - 1):
        if ranks[i + 1] - ranks[i] != 1:
            return False
    return True


def identify(
    cards: List[Card],
    player_count: int = 3,
    is_last_hand: bool = False,
    has_ace_bomb: bool = True,
) -> Optional[CardPattern]:
    """Identify the card pattern formed by a list of cards.

    Recognition proceeds from highest to lowest priority pattern type.
    The first match is returned. Returns None if no valid pattern is found.

    Args:
        cards: The list of cards to identify.
        player_count: Number of players in the game (2, 3, or 4).
                      Affects ACE_BOMB availability (only in 2-3 player mode).
        is_last_hand: If True, relaxed kicker rules apply for TRIPLE_WITH_TWO
                      and FOUR_WITH_THREE (fewer kickers allowed).

    Returns:
        A CardPattern if a valid pattern is identified, None otherwise.
    """
    if not cards:
        return None

    total = len(cards)

    # Build frequency dict: {rank_value: count}
    rank_freq: dict[int, int] = Counter(card.rank.value for card in cards)
    rank_values = sorted(rank_freq.keys())

    # ── Highest priority: BOMB (炸弹) ────────────────────────────
    # Exactly 4 cards, all same rank.
    if total == 4 and len(rank_freq) == 1:
        rank_val = rank_values[0]
        return CardPattern(
            type=PatternType.BOMB,
            main_rank=rank_val,
            length=4,
        )

    # ── ACE_BOMB (A炸) ──────────────────────────────────────────
    # Exactly 3 Aces, only in 2 or 3 player mode.
    if has_ace_bomb and player_count in (2, 3) and total == 3 and len(rank_freq) == 1:
        rank_val = rank_values[0]
        if rank_val == Rank.ACE.value:
            return CardPattern(
                type=PatternType.ACE_BOMB,
                main_rank=rank_val,
                length=3,
            )

    # ── Helper: find rank with a specific count ─────────────────
    def _find_group(count: int) -> Optional[int]:
        """Return the rank that appears exactly `count` times, or None."""
        groups = [r for r, c in rank_freq.items() if c == count]
        if len(groups) == 1:
            return groups[0]
        return None

    # ── FOUR_WITH_THREE (四带三) ─────────────────────────────────
    group_rank = _find_group(4)
    if group_rank is not None:
        kicker_count = total - 4
        if is_last_hand:
            if kicker_count <= 3:
                return CardPattern(
                    type=PatternType.FOUR_WITH_THREE,
                    main_rank=group_rank,
                    length=4,
                    kicker_count=kicker_count,
                )
        else:
            if kicker_count == 3:
                return CardPattern(
                    type=PatternType.FOUR_WITH_THREE,
                    main_rank=group_rank,
                    length=4,
                    kicker_count=3,
                )

    # ── TRIPLE_WITH_TWO (三带二) ─────────────────────────────────
    group_rank = _find_group(3)
    if group_rank is not None:
        kicker_count = total - 3
        if is_last_hand:
            if kicker_count <= 2:
                return CardPattern(
                    type=PatternType.TRIPLE_WITH_TWO,
                    main_rank=group_rank,
                    length=3,
                    kicker_count=kicker_count,
                )
        else:
            if kicker_count == 2:
                return CardPattern(
                    type=PatternType.TRIPLE_WITH_TWO,
                    main_rank=group_rank,
                    length=3,
                    kicker_count=2,
                )

    # ── STRAIGHT (顺子) ─────────────────────────────────────────
    # Requirements:
    #   - ≥5 cards
    #   - All ranks unique (each rank appears exactly once)
    #   - No TWO (15)
    #   - ACE (14) only at high end
    #   - Ranks must be consecutive
    if (
        total >= 5
        and len(rank_freq) == total  # all ranks unique
        and Rank.TWO.value not in rank_freq
        and _is_consecutive(rank_values)
    ):
        # ACE is only valid at the high end.
        # Since ranks are consecutive and TWO is banned, ACE (14) can only
        # appear as the last element of a consecutive sequence ending at 14.
        if Rank.ACE.value in rank_freq:
            if rank_values[-1] != Rank.ACE.value:
                return None  # ACE not at high end
        return CardPattern(
            type=PatternType.STRAIGHT,
            main_rank=rank_values[-1],
            length=total,
        )

    # ── CONSECUTIVE_PAIRS (连对) ─────────────────────────────────
    # Requirements:
    #   - ≥2 pairs (each rank appears exactly 2 times)
    #   - All cards accounted for (total == 2 * unique_ranks)
    #   - Pair ranks must be consecutive
    #   - No TWO (15) allowed
    if total >= 4 and total % 2 == 0:
        unique_count = len(rank_freq)
        if (
            unique_count >= 2
            and total == unique_count * 2
            and all(c == 2 for c in rank_freq.values())
            and Rank.TWO.value not in rank_freq
            and _is_consecutive(rank_values)
        ):
            return CardPattern(
                type=PatternType.CONSECUTIVE_PAIRS,
                main_rank=rank_values[-1],
                length=unique_count,
            )

    # ── PAIR (对子) ─────────────────────────────────────────────
    if total == 2 and len(rank_freq) == 1:
        return CardPattern(
            type=PatternType.PAIR,
            main_rank=rank_values[0],
            length=1,
        )

    # ── SINGLE (单张) ───────────────────────────────────────────
    if total == 1:
        return CardPattern(
            type=PatternType.SINGLE,
            main_rank=rank_values[0],
            length=1,
        )

    # ── No valid pattern ────────────────────────────────────────
    return None
