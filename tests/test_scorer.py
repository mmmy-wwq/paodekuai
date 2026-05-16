"""
Tests for scoring engine (server.game_engine.scorer).

Covers tier mapping, normal scoring (standard + all<5 special rule),
and declaration scoring (success + broken).
"""

from server.game_engine.scorer import ScoringEngine

# Default cards_per_player for 3p tests (2p/3p both have 16 cards each)
_CPP = 16


# ═══════════════════════════════════════════════════════════════════════
# get_tier
# ═══════════════════════════════════════════════════════════════════════

class TestGetTier:
    """Tests for ScoringEngine.get_tier()."""

    def test_zero_cards_tier_0(self):
        assert ScoringEngine.get_tier(0, _CPP) == 0

    def test_one_card_tier_0(self):
        assert ScoringEngine.get_tier(1, _CPP) == 0

    def test_four_cards_tier_0(self):
        assert ScoringEngine.get_tier(4, _CPP) == 0

    def test_five_cards_tier_1(self):
        assert ScoringEngine.get_tier(5, _CPP) == 1

    def test_six_cards_tier_2(self):
        assert ScoringEngine.get_tier(6, _CPP) == 2

    def test_ten_cards_tier_2(self):
        assert ScoringEngine.get_tier(10, _CPP) == 2

    def test_eleven_cards_tier_3(self):
        assert ScoringEngine.get_tier(11, _CPP) == 3

    def test_fifteen_cards_tier_3(self):
        assert ScoringEngine.get_tier(15, _CPP) == 3

    def test_sixteen_cards_tier_4_3p(self):
        """16 remaining → played 0 cards → tier 4 (3p/2p)."""
        assert ScoringEngine.get_tier(16, 16) == 4

    def test_thirteen_cards_tier_4_4p(self):
        """13 remaining = 0 played in 4p → tier 4."""
        assert ScoringEngine.get_tier(13, 13) == 4

    def test_twelve_cards_tier_3_4p(self):
        """12 remaining = played 1 in 4p → tier 3 (not 0 played)."""
        assert ScoringEngine.get_tier(12, 13) == 3

    def test_fifteen_cards_tier_3_4p(self):
        """15 > starting 13 (shouldn't happen but guards edge)."""
        assert ScoringEngine.get_tier(15, 13) == 4


# ═══════════════════════════════════════════════════════════════════════
# calculate_normal_score — standard
# ═══════════════════════════════════════════════════════════════════════

class TestNormalScoreStandard:
    """Tests for calculate_normal_score with standard tier scoring."""

    def test_winner_scores_zero(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 5},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p0"] > 0

    def test_loser_pays_tier(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 10},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -2
        assert scores["p0"] == 2

    def test_multiple_losers(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 5},
            {"player_id": "p2", "remaining_cards": 10},
            {"player_id": "p3", "remaining_cards": 15},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -1
        assert scores["p2"] == -2
        assert scores["p3"] == -3
        assert scores["p0"] == 6

    def test_net_zero(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 6},
            {"player_id": "p2", "remaining_cards": 12},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert sum(scores.values()) == 0

    def test_loser_with_less_than_5_pays_zero_when_another_has_5plus(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 3},
            {"player_id": "p2", "remaining_cards": 6},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == 0
        assert scores["p2"] == -2

    def test_mixed_tiers(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 3},
            {"player_id": "p2", "remaining_cards": 8},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == 0
        assert scores["p2"] == -2
        assert scores["p0"] == 2

    def test_zero_cards_played_tier_4(self):
        """Player who played 0 cards (remaining = starting 16) pays 4."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 16},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -4
        assert scores["p0"] == 4

    def test_tier_4_4p(self):
        """4p: 13 remaining = 0 played → tier 4."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 13},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, 13)
        assert scores["p1"] == -4

    def test_tier_3_4p_one_played(self):
        """4p: 12 remaining = 1 card played → tier 3."""
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 12},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, 13)
        assert scores["p1"] == -3


# ═══════════════════════════════════════════════════════════════════════
# calculate_normal_score — "all < 5" special rule
# ═══════════════════════════════════════════════════════════════════════

class TestNormalScoreAllLow:
    """Tests for the 'all < 5' special scoring rule."""

    def test_all_low_one_loser(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 4},
            {"player_id": "p2", "remaining_cards": 2},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -1
        assert scores["p2"] == 0
        assert scores["p0"] == 1

    def test_all_low_tie_for_max(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 3},
            {"player_id": "p2", "remaining_cards": 3},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -1
        assert scores["p2"] == -1
        assert scores["p0"] == 2

    def test_all_low_winner_gets_everything(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 4},
            {"player_id": "p2", "remaining_cards": 4},
            {"player_id": "p3", "remaining_cards": 1},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -1
        assert scores["p2"] == -1
        assert scores["p3"] == 0
        assert scores["p0"] == 2

    def test_all_low_not_triggered_when_some_have_5plus(self):
        players = [
            {"player_id": "p0", "remaining_cards": 0},
            {"player_id": "p1", "remaining_cards": 5},
            {"player_id": "p2", "remaining_cards": 2},
        ]
        scores = ScoringEngine.calculate_normal_score("p0", players, _CPP)
        assert scores["p1"] == -1
        assert scores["p2"] == 0


# ═══════════════════════════════════════════════════════════════════════
# calculate_declaration_score
# ═══════════════════════════════════════════════════════════════════════

class TestDeclarationScore:
    """Tests for calculate_declaration_score()."""

    def test_successful_declaration(self):
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
        assert scores["p0"] == 10
        assert scores["p1"] == -5
        assert scores["p2"] == -5

    def test_broken_declaration_3p(self):
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
        assert scores["p2"] == 10
        assert scores["p0"] == -10
        assert scores["p1"] == 0

    def test_broken_declaration_4p(self):
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
        assert scores["p1"] == 15
        assert scores["p0"] == -15
        assert scores["p2"] == 0
        assert scores["p3"] == 0

    def test_successful_declaration_net_zero(self):
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
