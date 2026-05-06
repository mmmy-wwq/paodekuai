"""
Rule Engine for 跑得快 (Pao De Kuai).

Central game logic: validates plays, checks the must-play (必压) rule,
enumerates legal plays, and determines the starting player.

Sits between the card engine (recognition/comparison) and the game
state machine.
"""

from __future__ import annotations

import itertools
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from server.card_engine.card import Card, Rank, Suit
from server.card_engine.comparator import can_beat, compare_max_single
from server.card_engine.recognizer import (
    CardPattern,
    PatternType,
    identify,
)


@dataclass
class RuleConfig:
    """Configuration parameters for the rule engine.

    Allows the same engine to handle 2p, 3p, and 4p modes
    with different deck configurations and rule variants.

    Attributes:
        player_count: Number of players (2, 3, or 4).
        deck_size: Total cards in the deck for this mode.
        cards_per_player: Initial hand size per player.
        has_ace_bomb: Whether ACE_BOMB pattern is available (2-3p only).
        must_play_enabled: Whether the 必压 (must-play) rule is active.
    """
    player_count: int
    deck_size: int
    cards_per_player: int
    has_ace_bomb: bool = True
    must_play_enabled: bool = True


# ─────────────────────────────────────────────────────────────────────
# Internal helper: card‑combination generation
# ─────────────────────────────────────────────────────────────────────

def _is_consecutive(ranks: List[int]) -> bool:
    """Check if sorted ranks form a consecutive sequence with step 1."""
    for i in range(len(ranks) - 1):
        if ranks[i + 1] - ranks[i] != 1:
            return False
    return True


def _generate_straights(
    distinct_ranks: List[int],
    cards_by_rank: Dict[int, List[Card]],
) -> List[List[Card]]:
    """Generate all straight card combinations from distinct ranks."""
    valid_ranks = [r for r in distinct_ranks if r != Rank.TWO.value]
    if len(valid_ranks) < 5:
        return []

    results: List[List[Card]] = []
    for start in range(len(valid_ranks)):
        for end in range(start + 5, len(valid_ranks) + 1):
            segment = valid_ranks[start:end]
            if not _is_consecutive(segment):
                continue
            if Rank.ACE.value in segment and segment[-1] != Rank.ACE.value:
                continue
            cards: List[Card] = []
            for r in segment:
                cards.append(cards_by_rank[r][0])
            results.append(cards)
    return results


def _generate_consecutive_pairs(
    distinct_pairs: List[int],
    cards_by_rank: Dict[int, List[Card]],
) -> List[List[Card]]:
    """Generate all consecutive pair card combinations from the hand."""
    if len(distinct_pairs) < 2:
        return []

    results: List[List[Card]] = []
    for start in range(len(distinct_pairs)):
        for end in range(start + 2, len(distinct_pairs) + 1):
            segment = distinct_pairs[start:end]
            if not _is_consecutive(segment):
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
    """Generate all valid kicker combinations for 三带二 / 四带三."""
    core_set = set(core_cards)
    available_kickers = [c for c in all_cards if c not in core_set]

    if len(available_kickers) < kicker_count:
        return []

    results: List[List[Card]] = []
    for kicker_combo in itertools.combinations(available_kickers, kicker_count):
        results.append(list(core_cards) + list(kicker_combo))
    return results


# ─────────────────────────────────────────────────────────────────────
# RuleEngine
# ─────────────────────────────────────────────────────────────────────

class RuleEngine:
    """Central rule engine for 跑得快.

    All methods are pure — they do not mutate game state or the hand list.
    Return values are plain dicts for easy consumption by callers.
    """

    def __init__(self, config: RuleConfig):
        """Initialise with a rule configuration.

        Args:
            config: RuleConfig specifying player_count, deck_size, etc.
        """
        self.config = config

    # ── is_valid_play ───────────────────────────────────────────────

    def is_valid_play(
        self,
        cards: List[Card],
        hand: List[Card],
        last_play_pattern: Optional[CardPattern],
        player_count: int,
        is_last_hand: bool,
    ) -> Dict[str, Any]:
        """Validate whether `cards` is a legal play given current table state.

        Checks performed:
          1. All played cards must belong to the player's hand.
          2. Cards must form a recognised pattern (via identify()).
          3. If a pattern is on the table, the play must beat it (via can_beat()).
          4. Kicker counts are validated by identify() (relaxed for last_hand).

        Args:
            cards: The cards the player wants to play.
            hand: The player's current hand.
            last_play_pattern: The pattern currently on the table, or None.
            player_count: Number of players in the game.
            is_last_hand: Whether this is the player's last hand (relaxed kickers).

        Returns:
            {
                "valid": bool,
                "error": Optional[str]   — human-readable reason if invalid,
                "must_play": bool        — always False here (see check_must_play),
                "forced_cards": Optional[List[Card]] — always None here,
            }
        """
        result: Dict[str, Any] = {
            "valid": True,
            "error": None,
            "must_play": False,
            "forced_cards": None,
        }

        # ── 1. Card ownership ────────────────────────────────────────
        # Use Counter (multiset) so duplicate cards are caught.
        hand_counter = Counter(hand)
        play_counter = Counter(cards)
        for card, count in play_counter.items():
            if hand_counter.get(card, 0) < count:
                result["valid"] = False
                result["error"] = f"Card {card} is not in your hand"
                return result

        # ── 2. Pattern recognition ───────────────────────────────────
        pattern = identify(cards, player_count=player_count,
                           is_last_hand=is_last_hand)
        if pattern is None:
            result["valid"] = False
            result["error"] = "Cards do not form a valid pattern"
            return result

        # ── 3. Beating the table ─────────────────────────────────────
        if last_play_pattern is not None:
            if not can_beat(pattern, last_play_pattern, player_count):
                result["valid"] = False
                result["error"] = (
                    f"Play cannot beat the current {last_play_pattern.type.name} "
                    f"(main_rank={last_play_pattern.main_rank})"
                )
                return result

        return result

    # ── check_must_play ─────────────────────────────────────────────

    def check_must_play(
        self,
        hand: List[Card],
        last_play_pattern: Optional[CardPattern],
        game_state: Dict[str, Any],
        player_index: int,
    ) -> Dict[str, Any]:
        """Check whether the must-play (必压) rule is triggered for a player.

        Must-play triggers ONLY when ALL of these conditions are met:
          1. last_play_pattern is a SINGLE card.
          2. The player right AFTER the current player has exactly 1 card.
          3. The player being checked IS the current player.
          4. The player's hand contains a single card HIGHER than the last
             played single.

        If triggered, the forced play is the highest-ranked single card
        in the player's hand.

        Args:
            hand: The current player's hand.
            last_play_pattern: The pattern currently on the table.
            game_state: Dictionary with keys:
                "players" — List[dict] with at least "remaining_cards" key.
                "current_turn" — int, index of the acting player.
            player_index: Index of the player to check.

        Returns:
            {
                "triggered": bool,
                "forced_cards": Optional[List[Card]] — [highest_single] if triggered,
            }
        """
        if not self.config.must_play_enabled:
            return {"triggered": False, "forced_cards": None}

        # Condition 1: last play must be a SINGLE
        if last_play_pattern is None:
            return {"triggered": False, "forced_cards": None}
        if last_play_pattern.type != PatternType.SINGLE:
            return {"triggered": False, "forced_cards": None}

        # Condition 3: the player being checked must be the current player
        current_turn = game_state.get("current_turn")
        if current_turn != player_index:
            return {"triggered": False, "forced_cards": None}

        # Condition 2: the next player must have exactly 1 card
        players = game_state.get("players", [])
        if not players:
            return {"triggered": False, "forced_cards": None}

        num_players = len(players)
        next_index = (player_index + 1) % num_players
        next_player = players[next_index]
        if next_player.get("remaining_cards", 0) != 1:
            return {"triggered": False, "forced_cards": None}

        # Condition 4: hand must contain a single higher than last play
        last_rank = last_play_pattern.main_rank
        # Find all singles in hand with rank > last_rank
        higher_singles = [
            c for c in hand if c.rank.value > last_rank
        ]
        if not higher_singles:
            return {"triggered": False, "forced_cards": None}

        # Must play the highest single in hand
        forced = compare_max_single(hand)
        return {"triggered": True, "forced_cards": [forced]}

    # ── get_legal_plays ─────────────────────────────────────────────

    def get_legal_plays(
        self,
        hand: List[Card],
        last_play_pattern: Optional[CardPattern],
        player_count: int,
        is_must_play: bool = False,
    ) -> List[List[Card]]:
        """Enumerate all card combinations from `hand` that can be legally played.

        Behaviour:
          - Free play (last_play_pattern is None): return ALL valid patterns.
          - Table has a pattern: return only patterns that can BEAT it.
          - Must-play rule (is_must_play=True, last_play SINGLE): ONLY
            return single card plays.

        Args:
            hand: The player's current hand.
            last_play_pattern: The pattern currently on the table, or None.
            player_count: Number of players.
            is_must_play: If True and last_play is SINGLE, restrict to singles.

        Returns:
            List of card lists, each a valid playable combination.
        """
        # ── Must-play: only singles ───────────────────────────────────
        if (
            is_must_play
            and last_play_pattern is not None
            and last_play_pattern.type == PatternType.SINGLE
        ):
            singles: List[List[Card]] = []
            seen_ranks: set[int] = set()
            for c in sorted(hand, key=lambda x: x.rank.value, reverse=True):
                if c.rank.value not in seen_ranks:
                    seen_ranks.add(c.rank.value)
                    singles.append([c])
            return singles

        # ── Generate all valid card combinations ─────────────────────
        all_plays = self._generate_all_plays(hand, player_count)

        # ── Free play ────────────────────────────────────────────────
        if last_play_pattern is None:
            # Sort by pattern type priority (highest first), then main_rank
            def _sort_key(play: List[Card]) -> tuple:
                p = identify(play, player_count=player_count)
                if p is None:
                    return (0, 0)
                return (p.type.value, p.main_rank)
            return sorted(all_plays, key=_sort_key, reverse=True)

        # ── Filter: only beats last_play ─────────────────────────────
        beatable: List[List[Card]] = []
        for play in all_plays:
            pattern = identify(play, player_count=player_count)
            if pattern is not None and can_beat(pattern, last_play_pattern, player_count):
                beatable.append(play)

        def _sort_key(p: List[Card]) -> tuple:
            pat = identify(p, player_count=player_count)
            if pat is None:
                return (0, 0)
            return (pat.type.value, pat.main_rank)

        return sorted(beatable, key=_sort_key, reverse=True)

    # ── _generate_all_plays (internal) ──────────────────────────────

    def _generate_all_plays(
        self,
        hand: List[Card],
        player_count: int,
    ) -> List[List[Card]]:
        """Generate all distinct card combinations that form valid patterns.

        Uses the same smart subset-generation logic as the comparator's
        _enumerate_all_patterns, but returns actual card lists instead
        of CardPattern objects.

        Deduplication: one combination per unique (type, main_rank, length,
        kicker_count) to avoid combinatorial explosion for 三带二/四带三.

        Args:
            hand: The player's current hand.
            player_count: Number of players (affects ACE_BOMB).

        Returns:
            List of card lists, each a valid playable combination.
        """
        cards_by_rank: Dict[int, List[Card]] = defaultdict(list)
        for c in hand:
            cards_by_rank[c.rank.value].append(c)

        distinct_ranks = sorted(cards_by_rank.keys())
        results: List[List[Card]] = []
        seen: set[tuple] = set()

        def _add(cards: List[Card]) -> None:
            p = identify(cards, player_count=player_count, is_last_hand=False)
            if p is None:
                return
            key = (p.type, p.main_rank, p.length, p.kicker_count)
            if key in seen:
                return
            seen.add(key)
            results.append(cards)

        # ── SINGLE ──────────────────────────────────────────────────
        for c in hand:
            _add([c])

        # ── PAIR ────────────────────────────────────────────────────
        for rank_val, cards in cards_by_rank.items():
            if len(cards) >= 2:
                _add(list(cards[:2]))

        # ── BOMB ────────────────────────────────────────────────────
        for rank_val, cards in cards_by_rank.items():
            if len(cards) == 4:
                _add(list(cards))

        # ── ACE_BOMB ────────────────────────────────────────────────
        if player_count in (2, 3):
            ace_cards = cards_by_rank.get(Rank.ACE.value, [])
            if len(ace_cards) == 3:
                _add(list(ace_cards))

        # ── STRAIGHT ────────────────────────────────────────────────
        for straight_cards in _generate_straights(distinct_ranks, cards_by_rank):
            _add(straight_cards)

        # ── CONSECUTIVE_PAIRS ───────────────────────────────────────
        pair_ranks = sorted(
            r for r, cards in cards_by_rank.items() if len(cards) >= 2
        )
        for cp_cards in _generate_consecutive_pairs(pair_ranks, cards_by_rank):
            _add(cp_cards)

        # ── TRIPLE_WITH_TWO ──────────────────────────────────────────
        for rank_val, cards in cards_by_rank.items():
            if len(cards) >= 3:
                core = list(cards[:3])
                for combo in _generate_kicker_combos(hand, core, kicker_count=2):
                    _add(combo)

        # ── FOUR_WITH_THREE ─────────────────────────────────────────
        for rank_val, cards in cards_by_rank.items():
            if len(cards) == 4:
                core = list(cards)
                for combo in _generate_kicker_combos(hand, core, kicker_count=3):
                    _add(combo)

        return results

    # ── determine_first_player ──────────────────────────────────────

    def determine_first_player(
        self,
        players: List[Dict[str, Any]],
        round_number: int,
        previous_winner_id: Optional[str] = None,
    ) -> int:
        """Determine which player acts first in a round.

        Rules:
          - First round (round_number == 1):
              - 3 or 4 players: the player holding ♠3 acts first.
              - 2 players: random (0 or 1).
          - Subsequent rounds: the previous winner acts first.

        Args:
            players: List of player dicts, each with keys:
                "player_id" (str) and "hand" (List[Card]).
            round_number: 1-based round number.
            previous_winner_id: The player_id of the previous round's winner.

        Returns:
            0-based index of the first player.
        """
        # ── Subsequent rounds: winner leads ──────────────────────────
        if round_number > 1 and previous_winner_id is not None:
            for idx, p in enumerate(players):
                if p.get("player_id") == previous_winner_id:
                    return idx
            # Fallback if winner not found (shouldn't happen)
            return 0

        # ── First round ──────────────────────────────────────────────
        if self.config.player_count == 2:
            return random.randint(0, 1)

        # 3 or 4 players: find holder of ♠3
        spade_three = Card(Suit.SPADE, Rank.THREE)
        for idx, p in enumerate(players):
            hand = p.get("hand", [])
            if spade_three in hand:
                return idx

        # Fallback (should never happen with a valid deck)
        return 0
