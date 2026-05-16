from __future__ import annotations

"""
Scoring engine for 跑得快 (Pao De Kuai).

Handles normal round scoring (tiered by remaining cards) and declaration/包牌
game scoring. All functions are pure — no side effects, no external state.

Score convention: positive = points gained, negative = points lost.
"""

from typing import Dict, List, Optional


class ScoringEngine:
    """Calculates score changes for a completed round of 跑得快."""

    # ------------------------------------------------------------------
    # Tier lookup
    # ------------------------------------------------------------------

    @staticmethod
    def get_tier(remaining_cards: int, cards_per_player: int) -> int:
        """Return the point tier for a given number of remaining cards.

        Tier mapping (the amount the winner collects from ONE player):

        +-------------------+-------+
        | Remaining Cards   | Tier  |
        +===================+=======+
        | < 5               |   0   |
        +-------------------+-------+
        | = 5               |   1   |
        +-------------------+-------+
        | 6–10              |   2   |
        +-------------------+-------+
        | 11 to < start     |   3   |
        +-------------------+-------+
        | = start (0 played)|   4   |
        +-------------------+-------+

        Tier 4 only when the player played ZERO cards
        (remaining == cards_per_player).
        """
        if remaining_cards < 5:
            return 0
        if remaining_cards == 5:
            return 1
        if remaining_cards <= 10:
            return 2
        if remaining_cards < cards_per_player:
            return 3
        # Played zero cards
        return 4

    # ------------------------------------------------------------------
    # Normal scoring
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_normal_score(
        winner_id: str,
        players: List[dict],
        cards_per_player: int,
    ) -> Dict[str, int]:
        """Calculate score changes after a normal (non-宣言) round.

        Args:
            winner_id: ``player_id`` of the person who emptied their hand.
            players: List of dicts, each with at least::

                {"player_id": str, "remaining_cards": int}

            cards_per_player: Starting hand size.

        Returns:
            Mapping ``player_id → score delta``.
            Positive = points the player *receives*,
            negative = points the player *pays*.

        **Scoring rules**

        * **Standard**: The winner collects from every other player
          according to the tier of that player's remaining cards
          (see :meth:`get_tier`).

        * **Special "everyone close" rule**: If *every* non-winner has
          fewer than 5 remaining cards, then only the player(s) with the
          **most** remaining cards among the losers each pay 1 point to
          the winner.  All other losers pay 0.
        """
        # --- Collect losers --------------------------------------------------
        losers = [p for p in players if p["player_id"] != winner_id]
        if not losers:
            return {winner_id: 0}

        # --- Check for the "all < 5" special case ----------------------------
        all_low = all(p["remaining_cards"] < 5 for p in losers)

        if all_low:
            max_cards = max(p["remaining_cards"] for p in losers)
            tier = 1  # each "worst" loser pays exactly 1

            scores: Dict[str, int] = {winner_id: 0}
            for p in losers:
                if p["remaining_cards"] == max_cards:
                    scores[p["player_id"]] = -tier
                    scores[winner_id] += tier
                else:
                    scores[p["player_id"]] = 0
            # Track winner
            scores[winner_id] = scores.get(winner_id, 0)
            return scores

        # --- Standard scoring ------------------------------------------------
        scores = {winner_id: 0}
        for p in losers:
            tier = ScoringEngine.get_tier(p["remaining_cards"], cards_per_player)
            if tier > 0:
                scores[p["player_id"]] = -tier
                scores[winner_id] += tier
            else:
                scores[p["player_id"]] = 0

        # Ensure winner entry exists (even if no one paid — shouldn't happen)
        scores.setdefault(winner_id, 0)
        return scores

    # ------------------------------------------------------------------
    # Declaration (包牌) scoring
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_declaration_score(
        declarer_id: str,
        breaker_id: Optional[str],
        players: List[dict],
        player_count: int,
    ) -> Dict[str, int]:
        """Calculate score changes after a 包牌 (declaration) round.

        Args:
            declarer_id: ``player_id`` of the player who declared.
            breaker_id: ``player_id`` of the player who broke the spring
                (i.e. managed to play cards against the declarer), or
                ``None`` if the declaration was successful.
            players: List of dicts, each with at least::

                {"player_id": str}

            player_count: Total number of players in the game (for
                calculating the broken-declaration penalty).

        Returns:
            Mapping ``player_id → score delta``.

        **Scoring rules**

        * **Successful declaration** (``breaker_id is None``):
          The declarer collects 5 points from **every** other player.

        * **Broken declaration** (``breaker_id`` is set):
          The breaker collects ``player_count × 5 - 5`` points from the
          declarer **only**.  All other players receive/pay 0.
        """
        scores: Dict[str, int] = {p["player_id"]: 0 for p in players}

        if breaker_id is None:
            # Success — declarer wins 5 from every other
            for p in players:
                if p["player_id"] != declarer_id:
                    scores[p["player_id"]] = -5
                    scores[declarer_id] += 5
        else:
            # Broken — breaker collects from declarer only
            penalty = player_count * 5 - 5
            scores[breaker_id] = penalty
            scores[declarer_id] = -penalty

        return scores
