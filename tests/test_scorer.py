"""
Tests for scoring engine (server.game_engine.scorer).

Covers tier mapping, normal scoring (standard + all<5 special rule),
and declaration scoring (success + broken).
"""

from server.game_engine.scorer import ScoringEngine


# ═══════════════════════════════════════════════════════════════════════
# get_tier
# ═══════════════════════════════════════════════════════════════════════

class TestGetTier:
    """Tests for ScoringEngine.get_tier()."""

    def test_zero_cards_tier_0(self):
        """0 remaining cards → tier 0."""
        assert ScoringEngine.get_tier(0) == 0

    def test_one_card_tier_0(self):
        """1 remaining card → tier 0."""
        assert ScoringEngine.get_tier(1) == 0

    def test_four_cards_tier_0(self):
        """4 remaining cards → tier 0 (boundary: <5)."""
        assert ScoringEngine.get_tier(4) == 0

    def test_five_cards_tier_1(self):
        """5 remaining cards → tier 1."""
        assert ScoringEngine.get_tier(5) == 1

    def test_six_cards_tier_2(self):
        """6 remaining cards → tier 2 (lower bound of 6-10)."""
        assert ScoringEngine.get_tier(6) == 2

    def test_ten_cards_tier_2(self):
        """10 remaining cards → tier 2 (upper bound of 6-10)."""
        assert ScoringEngine.get_tier(10) == 2

    def test_eleven_cards_tier_3(self):
        """11 remaining cards → tier 3 (lower bound of 11-15)."""
        assert ScoringEngine.get_tier(11) == 3

    def test_fifteen_cards_tier_3(self):
        """15 remaining cards → tier 3 (upper bound of 11-15)."""
        assert ScoringEngine.get_tier(15) == 3

    def test_sixteen_cards_tier_4(self):
        """16 remaining cards → tier 4 (≥16)."""
        assert ScoringEngine.get_tier(16) == 4

    def test_twenty_cards_tier_4(self):
        """20 remaining cards → tier 4 (beyond normal range)."""
        assert ScoringEngine.get_tier(20) == 4


# ═══════════════════════════════════════════════════════════════════════
# calculate_normal_score — standard
# ═══════════════════════════════════════════════════════════════════════

class TestNormalScoreStandard:
    """Tests for calculate_normal_score with standard tier scoring."""

    def test_winner_scores_zero(self):
        """Winner's score delta is always non-negative."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 5},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p0"] > 0

    def test_loser_pays_tier(self):
        """Loser pays their tier amount; winner receives it."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 10},  # tier 2
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == -2
        assert scores["p0"] == 2

    def test_multiple_losers(self):
        """Winner collects from all losers according to their tiers."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 5},   # tier 1 → pays 1
            {"player_id": "p2", "remaining_cards": 10},  # tier 2 → pays 2
            {"player_id": "p3", "remaining_cards": 15},  # tier 3 → pays 3
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == -1
        assert scores["p2"] == -2
        assert scores["p3"] == -3
        assert scores["p0"] == 6  # 1 + 2 + 3

    def test_net_zero(self):
        """Score deltas sum to zero."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 6},
            {"player_id": "p2", "remaining_cards": 12},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert sum(scores.values()) == 0

    def test_loser_with_less_than_5_pays_zero_when_another_has_5plus(self):
        """Loser with <5 cards pays 0 when another loser has ≥5 (standard scoring, not all<5 rule)."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 3},  # tier 0
            {"player_id": "p2", "remaining_cards": 6},  # tier 2 → triggers standard mode
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == 0
        assert scores["p2"] == -2

    def test_mixed_tiers(self):
        """Some losers pay, some don't, depending on tier."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 3},  # tier 0
            {"player_id": "p2", "remaining_cards": 8},  # tier 2
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == 0
        assert scores["p2"] == -2
        assert scores["p0"] == 2


# ═══════════════════════════════════════════════════════════════════════
# calculate_normal_score — "all < 5" special rule
# ═══════════════════════════════════════════════════════════════════════

class TestNormalScoreAllLow:
    """Tests for the 'all < 5' special scoring rule."""

    def test_all_low_one_loser(self):
        """When all losers have <5 cards and only 1 has the max, only they pay 1."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 4},
            {"player_id": "p2", "remaining_cards": 2},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == -1  # p1 has 4, p2 has 2 → p1 has most
        assert scores["p2"] == 0
        assert scores["p0"] == 1

    def test_all_low_tie_for_max(self):
        """When all losers <5 and tied for max, each tied player pays 1."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 3},
            {"player_id": "p2", "remaining_cards": 3},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == -1
        assert scores["p2"] == -1
        assert scores["p0"] == 2  # 1 + 1

    def test_all_low_winner_gets_everything(self):
        """All <5: only max-card loser(s) pay, winner receives sum."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 4},
            {"player_id": "p2", "remaining_cards": 4},
            {"player_id": "p3", "remaining_cards": 1},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        assert scores["p1"] == -1
        assert scores["p2"] == -1
        assert scores["p3"] == 0
        assert scores["p0"] == 2

    def test_all_low_not_triggered_when_some_have_5plus(self):
        """All <5 rule NOT triggered if ANY loser has ≥5 cards."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 5},  # ≥5 breaks the rule
            {"player_id": "p2", "remaining_cards": 2},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players)
        # Standard scoring applies
        assert scores["p1"] == -1  # tier 1
        assert scores["p2"] == 0   # tier 0


# ═══════════════════════════════════════════════════════════════════════
# calculate_declaration_score
# ═══════════════════════════════════════════════════════════════════════

class TestDeclarationScore:
    """Tests for calculate_declaration_score()."""

    def test_successful_declaration(self):
        """Successful declaration: declarer gets 5 from each other player."""
        players = [
            {"player_id": "p0"},
            {"player_id": "p1"},
            {"player_id": "p2"},
        ]
        scores = ScoringEngine.calculate_declaration_score(
            declarer_id="p0",
            breaker_id=None,
            players=players,
            player_count=3,
        )
        assert scores["p0"] == 10   # +5 from p1, +5 from p2
        assert scores["p1"] == -5
        assert scores["p2"] == -5

    def test_broken_declaration_3p(self):
        """Broken declaration 3p: breaker gets 3*5-5=10 from declarer."""
        players = [
            {"player_id": "p0"},
            {"player_id": "p1"},
            {"player_id": "p2"},
        ]
        scores = ScoringEngine.calculate_declaration_score(
            declarer_id="p0",
            breaker_id="p2",
            players=players,
            player_count=3,
        )
        # Penalty: player_count * 5 - 5 = 3*5-5 = 10
        assert scores["p2"] == 10
        assert scores["p0"] == -10
        assert scores["p1"] == 0

    def test_broken_declaration_4p(self):
        """Broken declaration 4p: breaker gets 4*5-5=15 from declarer."""
        players = [
            {"player_id": "p0"},
            {"player_id": "p1"},
            {"player_id": "p2"},
            {"player_id": "p3"},
        ]
        scores = ScoringEngine.calculate_declaration_score(
            declarer_id="p0",
            breaker_id="p1",
            players=players,
            player_count=4,
        )
        # Penalty: 4*5-5 = 15
        assert scores["p1"] == 15
        assert scores["p0"] == -15
        assert scores["p2"] == 0
        assert scores["p3"] == 0

    def test_successful_declaration_net_zero(self):
        """Successful declaration scores sum to zero."""
        players = [
            {"player_id": "p0"},
            {"player_id": "p1"},
            {"player_id": "p2"},
            {"player_id": "p3"},
        ]
        scores = ScoringEngine.calculate_declaration_score(
            declarer_id="p0",
            breaker_id=None,
            players=players,
            player_count=4,
        )
        assert sum(scores.values()) == 0

    def test_broken_declaration_net_zero(self):
        """Broken declaration scores sum to zero."""
        players = [
            {"player_id": "p0"},
            {"player_id": "p1"},
            {"player_id": "p2"},
        ]
        scores = ScoringEngine.calculate_declaration_score(
            declarer_id="p1",
            breaker_id="p0",
            players=players,
            player_count=3,
        )
        assert sum(scores.values()) == 0

    def test_broken_2p_penalty(self):
        """Broken declaration 2p: breaker gets 2*5-5=5 from declarer."""
        players = [
            {"player_id": "p0"},
            {"player_id": "p1"},
        ]
        scores = ScoringEngine.calculate_declaration_score(
            declarer_id="p0",
            breaker_id="p1",
            players=players,
            player_count=2,
        )
        assert scores["p1"] == 5
        assert scores["p0"] == -5
