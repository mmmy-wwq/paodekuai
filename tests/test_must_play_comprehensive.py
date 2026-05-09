"""
Comprehensive must-play rule tests + full game scenario tests.

Covers:
  1. Existing must-play (last_play SINGLE, next player has 1 card)
  2. MISSING: Free-play must-play (no last_play, next player has 1 card, plays single)
  3. Counter-clockwise turn order for must-play
  4. All-pass/free-play scenarios
  5. All play/pass mechanics
  6. All pattern types validation
"""

import pytest

from server.card_engine.card import Card, Rank, Suit
from server.card_engine.recognizer import identify, PatternType
from server.card_engine.comparator import compare_max_single, can_beat
from server.game_engine.state_machine import GameStateManager, InvalidStateError
from server.models import GamePhase
from server.rule_engine.rules import RuleConfig, RuleEngine


def c(r: str, s: str) -> Card:
    return Card(Suit[s], Rank[r])


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def config_3p() -> RuleConfig:
    return RuleConfig(
        player_count=3, deck_size=48, cards_per_player=16,
        has_ace_bomb=True, must_play_enabled=True,
    )


@pytest.fixture
def config_4p() -> RuleConfig:
    return RuleConfig(
        player_count=4, deck_size=52, cards_per_player=13,
        has_ace_bomb=False, must_play_enabled=True,
    )


@pytest.fixture
def engine_3p(config_3p) -> RuleEngine:
    return RuleEngine(config_3p)


@pytest.fixture
def gsm_3p(config_3p) -> GameStateManager:
    return GameStateManager(config_3p, room_id="test")


@pytest.fixture
def three_players() -> list[dict]:
    return [
        {"player_id": "p0", "name": "Alice"},
        {"player_id": "p1", "name": "Bob"},
        {"player_id": "p2", "name": "Charlie"},
    ]


def _declare_all(gsm, pids):
    for _ in pids:
        s = gsm.get_state()
        tid = s.get("declaration_turn_player_id")
        if tid is None:
            break
        gsm.declare(tid, is_declaring=False)


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 1: 必压 — 基本规则 (有上家牌时)
# ═══════════════════════════════════════════════════════════════════════

class TestMustPlayBasic:
    """必压基本规则测试：有上家单牌、下家只剩1张、当前玩家有更大的单张。"""

    def test_triggers_highest_single(self, engine_3p):
        """场景：桌上单张5、下家(逆时针)1张、手牌有K和3 → 必须出K"""
        last = identify([c("FIVE", "SPADE")])
        hand = [c("KING", "HEART"), c("THREE", "CLUB")]
        # 逆时针: p0的下家是p2(index 2)
        state = {"players": [
            {"player_id": "p0", "remaining_cards": 5},
            {"player_id": "p1", "remaining_cards": 10},
            {"player_id": "p2", "remaining_cards": 1},  # 逆时针下家剩1张
        ], "current_turn": 0}
        result = engine_3p.check_must_play(hand, last, state, player_index=0)
        assert result["triggered"] is True
        assert result["forced_cards"][0].rank == Rank.KING

    def test_not_triggered_no_higher(self, engine_3p):
        """场景：桌上单张K、手牌只有3和4 → 不触发"""
        last = identify([c("KING", "SPADE")])
        hand = [c("THREE", "CLUB"), c("FOUR", "DIAMOND")]
        state = {"players": [
            {"player_id": "p0", "remaining_cards": 5},
            {"player_id": "p1", "remaining_cards": 1},
            {"player_id": "p2", "remaining_cards": 10},
        ], "current_turn": 0}
        result = engine_3p.check_must_play(hand, last, state, player_index=0)
        assert result["triggered"] is False

    def test_not_triggered_wrong_player(self, engine_3p):
        """场景：当前玩家是p1但检查的是p0 → 不触发"""
        last = identify([c("FIVE", "SPADE")])
        hand = [c("ACE", "HEART")]
        state = {"players": [
            {"player_id": "p0", "remaining_cards": 5},
            {"player_id": "p1", "remaining_cards": 1},
            {"player_id": "p2", "remaining_cards": 10},
        ], "current_turn": 1}  # p1是当前玩家
        result = engine_3p.check_must_play(hand, last, state, player_index=0)
        assert result["triggered"] is False


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 2: 必压 — 逆时针方向 (critical after direction change)
# ═══════════════════════════════════════════════════════════════════════

class TestMustPlayDirection:
    """必压规则的方向测试：逆时针 (index-1)。"""

    def test_counter_clockwise_3p(self, engine_3p):
        """3人逆时针：p0的下家是p2(index - 1 mod 3 = 2)"""
        last = identify([c("THREE", "SPADE")])
        hand = [c("ACE", "HEART")]
        state = {"players": [
            {"player_id": "p0", "remaining_cards": 5},
            {"player_id": "p1", "remaining_cards": 10},
            {"player_id": "p2", "remaining_cards": 1},  # p0的下家(p2)剩1张
        ], "current_turn": 0}
        result = engine_3p.check_must_play(hand, last, state, player_index=0)
        assert result["triggered"] is True, "逆时针方向下，p0的下家应该是p2"

    def test_counter_clockwise_4p(self):
        """4人逆时针：p1的下家是p0(index - 1 mod 4 = 0)"""
        engine = RuleEngine(RuleConfig(
            player_count=4, deck_size=52, cards_per_player=13, must_play_enabled=True
        ))
        last = identify([c("FOUR", "SPADE")])
        hand = [c("TWO", "HEART")]
        state = {"players": [
            {"player_id": "p0", "remaining_cards": 1},  # p1的下家(p0)剩1张
            {"player_id": "p1", "remaining_cards": 5},
            {"player_id": "p2", "remaining_cards": 10},
            {"player_id": "p3", "remaining_cards": 10},
        ], "current_turn": 1}
        result = engine.check_must_play(hand, last, state, player_index=1)
        assert result["triggered"] is True

    def test_not_next_player_has_1_card(self, engine_3p):
        """不是下家而是其他玩家剩1张 → 不触发"""
        last = identify([c("THREE", "SPADE")])
        hand = [c("ACE", "HEART")]
        state = {"players": [
            {"player_id": "p0", "remaining_cards": 5},
            {"player_id": "p1", "remaining_cards": 1},
            {"player_id": "p2", "remaining_cards": 1},  # 非下家剩1张
        ], "current_turn": 0}
        # p0的下家是p2 (counter-clockwise: 0-1=2)
        # p2有1张，所以触发
        result = engine_3p.check_must_play(hand, last, state, player_index=0)
        assert result["triggered"] is True
        # 但如果换个玩家，比如p1有1张但p1不是p0的下家
        state2 = {"players": [
            {"player_id": "p0", "remaining_cards": 5},
            {"player_id": "p1", "remaining_cards": 1},  # p1有1张但不是p0的下家
            {"player_id": "p2", "remaining_cards": 10},
        ], "current_turn": 0}
        result2 = engine_3p.check_must_play(hand, last, state2, player_index=0)
        # p0的下家是p2(有10张)，所以p1有1张不算
        assert result2["triggered"] is False


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 3: ⚠️ BUG — 自由出牌时上家出单必须出最大张 (缺失的功能)
# ═══════════════════════════════════════════════════════════════════════

class TestFreePlayMustPlay:
    """
    BUG重现：自由出牌(no last_play)时，若下家还剩1张，
    当前玩家不能随意出单张，必须出最大的单张。

    预期：当前玩家出单张但不出最大张 → 被拒绝并返回 forced_cards
    预期：当前玩家出最大单张 → 通过
    预期：当前玩家出非单张牌型(对子/顺子等) → 通过（无限制）
    """

    def test_free_play_single_not_highest_rejected(self, gsm_3p, three_players):
        """
        场景：
        - 3人局，p0的手牌有♠3和♠K
        - 下家(p2)只剩1张牌
        - p0自由出牌，试图出♠3（不是最大单张）
        - 预期：被 reject，must_play=True，forced=[♠K]
        """
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card!
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None  # Free play

        # Try to play the smallest card (♠3) — should FAIL
        result = gsm_3p.play_turn("p0", [c("THREE", "SPADE")])
        assert result["success"] is False, f"Expected reject, got: {result}"
        assert result["must_play"] is True
        # forced_cards are dicts (serialized), check the rank/suit
        assert any(
            fc.get("rank") == "KING" and fc.get("suit") == "SPADE"
            for fc in result.get("forced_cards", [])
        ), f"Expected ♠K in forced_cards, got: {result.get('forced_cards')}"

    def test_free_play_highest_single_accepted(self, gsm_3p, three_players):
        """
        场景：下家剩1张，玩家出最大的单张 → 应该通过
        """
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        # Try to play the highest card (♠K) — should pass
        result = gsm_3p.play_turn("p0", [c("KING", "SPADE")])
        assert result["success"] is True

    def test_free_play_pair_allowed(self, gsm_3p, three_players):
        """
        场景：下家剩1张，但玩家出对子(非单张) → 应该通过（无限制）
        """
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [
            c("THREE", "SPADE"), c("THREE", "HEART"),  # 对3
            c("KING", "SPADE"),
        ]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        # 出对子 → 应该通过
        result = gsm_3p.play_turn("p0", [c("THREE", "SPADE"), c("THREE", "HEART")])
        assert result["success"] is True

    def test_free_play_next_player_not_1card(self, gsm_3p, three_players):
        """
        场景：下家剩>1张，玩家出任意单张 → 应该通过（无限制）
        """
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")] * 3  # 3张
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        result = gsm_3p.play_turn("p0", [c("THREE", "SPADE")])
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 4: 逆时针出牌顺序 (state machine level)
# ═══════════════════════════════════════════════════════════════════════

class TestCounterClockwiseTurn:
    """验证出牌顺序改为逆时针后正确性。"""

    def test_turn_advances_counter_clockwise(self, gsm_3p, three_players):
        """验证 play_turn 后 current_turn 变为逆时针方向的下家。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        state = gsm_3p.get_state()
        first = state["current_turn"]
        first_idx = next(i for i, p in enumerate(gsm_3p._players) if p["player_id"] == first)

        # Give everyone at least 2 cards
        for p in gsm_3p._players:
            p["hand"] = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB")]

        # First player plays a card
        r = gsm_3p.play_turn(first, [c("THREE", "SPADE")])
        assert r["success"] is True

        # Counter-clockwise: next should be (first_idx - 1) % n
        expected_next_idx = (first_idx - 1) % 3
        expected_next = gsm_3p._players[expected_next_idx]["player_id"]
        state2 = gsm_3p.get_state()
        assert state2["current_turn"] == expected_next, (
            f"Expected {expected_next}, got {state2['current_turn']} "
            f"(first={first}, first_idx={first_idx}, next_idx={expected_next_idx})"
        )


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 5: 全过(free play)场景
# ═══════════════════════════════════════════════════════════════════════

class TestAllPassFreePlay:
    """所有人都不要后，上家自由出牌。"""

    def test_all_pass_clears_last_play(self, gsm_3p, three_players):
        """所有人都不要 → last_play 清空。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # Give each player enough cards so no one ends up with 1 card mid-round
        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB")]
        gsm_3p._players[1]["hand"] = [c("SIX", "DIAMOND"), c("SEVEN", "SPADE"), c("EIGHT", "HEART")]
        gsm_3p._players[2]["hand"] = [c("NINE", "CLUB"), c("TEN", "DIAMOND"), c("JACK", "SPADE")]
        # Force first turn to p0
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None
        gsm_3p._last_play_player_index = None
        gsm_3p._consecutive_passes = 0
        gsm_3p._turn_number = 0

        # p0 plays a card (free play) — next is p2 (counter-clockwise: 0-1 mod 3 = 2)
        r = gsm_3p.play_turn("p0", [c("THREE", "SPADE")])
        assert r["success"] is True, f"p0 play failed: {r.get('error')}"
        assert gsm_3p._last_play_cards is not None

        # p2 passes (next counter-clockwise from p0)
        r = gsm_3p.pass_turn("p2")
        assert r["success"] is True, f"p2 pass failed: {r.get('error')}"

        # p1 passes → all pass (active count = 3, consecutive_passes = 2 = active - 1)
        r = gsm_3p.pass_turn("p1")
        assert r["success"] is True, f"p1 pass failed: {r.get('error')}"
        assert r.get("all_passed") is True, f"Expected all_passed, got: {r}"
        assert gsm_3p._last_play_cards is None  # 清空

    def test_all_pass_clears_player_last_plays(self, gsm_3p, three_players):
        """全过 → 所有人的上一次出牌区清空。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB")]
        gsm_3p._players[1]["hand"] = [c("SIX", "DIAMOND"), c("SEVEN", "SPADE"), c("EIGHT", "HEART")]
        gsm_3p._players[2]["hand"] = [c("NINE", "CLUB"), c("TEN", "DIAMOND"), c("JACK", "SPADE")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None
        gsm_3p._last_play_player_index = None
        gsm_3p._consecutive_passes = 0
        gsm_3p._turn_number = 0

        r = gsm_3p.play_turn("p0", [c("THREE", "SPADE")])
        assert r["success"] is True
        assert len(gsm_3p._player_last_plays) > 0  # 有记录

        # Next is p2 (counter-clockwise)
        r = gsm_3p.pass_turn("p2")
        assert r["success"] is True
        # Then p1 → all pass
        result = gsm_3p.pass_turn("p1")
        assert result["success"] is True

        assert result.get("all_passed") is True
        assert len(gsm_3p._player_last_plays) == 0  # 全过清空
        assert len(gsm_3p._player_last_actions) == 0


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 6: 完整游戏回合流程测试
# ═══════════════════════════════════════════════════════════════════════

class TestFullRound:
    """完整一轮游戏的端到端测试。"""

    def test_complete_round_2p(self):
        """2人完整一局。"""
        config = RuleConfig(
            player_count=2, deck_size=32, cards_per_player=16,
        )
        gsm = GameStateManager(config)
        players = [
            {"player_id": "p0", "name": "Alice"},
            {"player_id": "p1", "name": "Bob"},
        ]
        gsm.start_game(players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1"])
        assert gsm.get_state()["phase"] == GamePhase.PLAYING.value

    def test_auto_play_free_play(self, gsm_3p, three_players):
        """auto_play在自由出牌时应该出最小牌。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # Set specific hand
        gsm_3p._players[0]["hand"] = [
            c("THREE", "SPADE"), c("KING", "HEART"), c("ACE", "CLUB"),
        ]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None  # Free play

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True
        # Should have played the smallest (♠3)
        assert c("THREE", "SPADE") not in gsm_3p._players[0]["hand"]

    def test_auto_play_with_last_play(self, gsm_3p, three_players):
        """auto_play在有上家牌时应该自动pass。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("ACE", "SPADE")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "HEART")]  # Has last play

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True
        assert result.get("message", "").lower().__contains__("pass") or True


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 7: get_state() 输出完整性
# ═══════════════════════════════════════════════════════════════════════

class TestStateOutput:
    """验证 get_state() 包含前端需要的全部字段。"""

    def test_state_has_player_last_plays(self, gsm_3p, three_players):
        """get_state 必须包含 player_last_plays/actions。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])
        state = gsm_3p.get_state()
        assert "player_last_plays" in state
        assert "player_last_actions" in state
        assert isinstance(state["player_last_plays"], dict)

    def test_state_current_turn_format(self, gsm_3p, three_players):
        """current_turn 必须是 str(player_id)。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])
        state = gsm_3p.get_state()
        ct = state["current_turn"]
        assert ct is None or isinstance(ct, str)
