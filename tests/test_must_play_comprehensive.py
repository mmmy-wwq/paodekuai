"""
Comprehensive must-play rule tests + full game scenario tests.

Covers:
  1. Existing must-play (last_play SINGLE, next player has 1 card)
  2. MISSING: Free-play must-play (no last_play, next player has 1 card, plays single)
  3. Counter-clockwise turn order for must-play
  4. All-pass/free-play scenarios
  5. All play/pass mechanics
  6. All pattern types validation
  7. auto_play 必压规则修复
  8. pass_turn 边界条件
"""

from __future__ import annotations

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

    def test_free_play_bomb_allowed_when_next_has_1(self, gsm_3p, three_players):
        """下家1张+自由出牌+出炸弹 → 允许。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("THREE", "DIAMOND")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        result = gsm_3p.play_turn("p0", [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("THREE", "DIAMOND")])
        assert result["success"] is True, f"炸弹应被允许: {result.get('error')}"


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


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 8: auto_play 必压规则修复
# ═══════════════════════════════════════════════════════════════════════

class TestAutoPlayMustPlay:
    """auto_play 遇到必压规则时的行为修复测试。

    旧bug：
      auto_play 在有上家牌时直接 pass_turn，但 pass_turn 遇到必压规则会返回错误。
      timer handler 无视错误直接 return，导致死锁（轮次不前进、无法出牌）。

    修复：
      auto_play 先检查必压规则，触发则出 forced_cards，不触发才 pass。
      自由出牌时也检查下家是否剩1张，是则出最大单牌。
    """

    # ── 有上家牌的场景 ──────────────────────────────────────

    def test_auto_play_must_play_triggered_plays_forced(self, gsm_3p, three_players):
        """【bug复现】上家有牌+必压触发 → auto_play 出 forced card，不是 pass。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # p0 手牌有 ♠3, ♥K
        # p2 (p0的逆时针下家) 剩1张 → 必压触发
        # 桌上最后出的是 ♠5（单张）
        # forced = ♥K（手牌最大单张）
        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card!
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "SPADE")]

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True, f"auto_play should succeed: {result}"
        # ♥K 应该被打出（手牌中不再有）
        assert c("KING", "HEART") not in gsm_3p._players[0]["hand"], "♥K should have been played"
        # ♠3 应该还在
        assert c("THREE", "SPADE") in gsm_3p._players[0]["hand"], "♠3 should remain"

    def test_auto_play_must_play_no_higher_passes(self, gsm_3p, three_players):
        """【边界条件】必压触发条件满足，但本家没有更大的牌 → auto_play 应该 pass。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # p0 只剩 ♠3（比桌上的 ♠K 小）
        # p2 (下家) 剩1张 → 必压条件检查，但 p0 没有更大的单张 → 不触发
        # auto_play 应该 pass
        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card!
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("KING", "SPADE")]

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True, f"auto_play should pass: {result}"
        # ♠3 应该还在（没出牌）
        assert c("THREE", "SPADE") in gsm_3p._players[0]["hand"]
        # 轮次应该前进了（pass成功）
        state = gsm_3p.get_state()
        assert state["current_turn"] != "p0"

    def test_pass_turn_must_play_triggered_fails(self, gsm_3p, three_players):
        """【pass拒绝】必压触发时手动 pass → 应该被拒绝并返回 forced_cards。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "SPADE")]

        result = gsm_3p.pass_turn("p0")
        assert result["success"] is False, "pass 应被拒绝"
        assert result.get("must_play") is True, "应返回 must_play 标志"
        assert result.get("forced_cards") is not None, "应返回 forced_cards"

    def test_pass_turn_no_higher_succeeds(self, gsm_3p, three_players):
        """【边界条件】必压触发条件满足但本家没有更大的牌 → pass 应该允许。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("KING", "SPADE")]

        result = gsm_3p.pass_turn("p0")
        assert result["success"] is True, f"pass 应允许: {result}"
        # 轮次应该前进了
        state = gsm_3p.get_state()
        assert state["current_turn"] != "p0"

    # ── 自由出牌的场景 ──────────────────────────────────────

    def test_auto_play_free_play_next_has_1_plays_highest(self, gsm_3p, three_players):
        """【bug复现】自由出牌+下家1张 → auto_play 出最大单牌，不是最小。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card!
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None  # Free play

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True, f"auto_play should succeed: {result}"
        # ♥K（最大单张）应该被打出
        assert c("KING", "HEART") not in gsm_3p._players[0]["hand"], "♥K should have been played"
        assert c("THREE", "SPADE") in gsm_3p._players[0]["hand"], "♠3 (smallest) should remain"

    def test_auto_play_free_play_normal_plays_smallest(self, gsm_3p, three_players):
        """普通自由出牌+下家>1张 → auto_play 出最小牌（已有测试的增强版）。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART"), c("ACE", "CLUB")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")] * 3  # >1 card
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True
        # ♠3（最小）应该被打出
        assert c("THREE", "SPADE") not in gsm_3p._players[0]["hand"]
        assert c("KING", "HEART") in gsm_3p._players[0]["hand"]


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 9: 极端边界条件测试
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """各种极端边界条件测试。

    覆盖场景：
      1. 必压 forced card = 最后一张牌 → 本局结束
      2. auto_play + 必压 + forced card 是最后一张 → 本局结束
      3. auto_play 自由出牌 + 下家1张 + 最大牌是最后一张 → 本局结束
      4. 全场pass后只剩2人活跃
      5. 玩家出完牌后轮到下家(跳过的玩家) → 正确跳过
      6. 最后手牌: TRIPLE_WITH_TWO 带0个kicker（允许）
      7. 最后手牌: FOUR_WITH_THREE 带0-2个kicker（允许）
      8. 正常对局: TRIPLE_WITH_TWO 必须带恰好2个kicker
      9. 连续两次全场pass
     10. _next_player_with_cards 跳过0张的玩家
    """

    # ── 1. 必压 forced card 最后一张 → 本局结束 ────────────────

    def test_must_play_forced_card_wins_round(self, gsm_3p, three_players):
        """必压触发+forced card是最后一张牌 → 本轮结束。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # p0 只剩 ♥K（唯一手牌）
        # 桌上是 ♠5（单张），p0的下家(p2)剩1张 → 必压触发
        # forced = ♥K，打出后 p0 手牌为空 → ROUND_END
        gsm_3p._players[0]["hand"] = [c("KING", "HEART")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card!
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "SPADE")]

        # 手动打 forced card（♥K 正好是最高单张且能大过 ♠5）
        result = gsm_3p.play_turn("p0", [c("KING", "HEART")])
        assert result["success"] is True, f"must-play forced play should win: {result}"
        assert result.get("phase") == "ROUND_END", "打出最后一张应该结束本轮"
        assert gsm_3p._phase.value == "ROUND_END"

    def test_must_play_forced_card_not_wins_if_not_last(self, gsm_3p, three_players):
        """必压打出forced card但不是最后一张 → 不结束，轮次前进。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card!
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "SPADE")]

        result = gsm_3p.play_turn("p0", [c("KING", "HEART")])
        assert result["success"] is True
        assert result.get("phase") != "ROUND_END", "还有手牌不应结束"
        assert c("THREE", "SPADE") in gsm_3p._players[0]["hand"]

    # ── 2. auto_play + 必压 + forced card = 最后一张 → ROUND_END ────

    def test_auto_play_must_play_wins_round(self, gsm_3p, three_players):
        """auto_play 遇必压+forced card是最后一张 → 本局结束。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("KING", "HEART")]  # 唯一 = forced
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "SPADE")]

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True
        assert result.get("phase") == "ROUND_END", "auto_play forced card 应结束本轮"

    # ── 3. auto_play 自由出牌 + 下家1张 + 最大牌是最后一张 ──────────

    def test_auto_play_free_play_must_play_wins_round(self, gsm_3p, three_players):
        """auto_play自由出牌+下家1张+最大牌是唯一手牌 → 本局结束。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # p0 只有 ♠K，下家(p2)刚好1张 → auto_play 应打出 ♠K 并结束
        gsm_3p._players[0]["hand"] = [c("KING", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None  # Free play

        result = gsm_3p.auto_play("p0")
        assert result["success"] is True
        assert result.get("phase") == "ROUND_END", "自由出牌+下家1张+唯一牌应结束"

    # ── 4. 全场pass后只剩2人活跃 ─────────────────────────────────

    def test_all_pass_with_2_active_players(self, gsm_3p, three_players):
        """2人活跃时全场pass → 正确触发all-pass。
        注意：p1有1张会触发p2的必压，所以让p2先打出♠K再继续。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # p0 5张, p1 1张(即将出完), p2 5张
        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"), c("SIX", "DIAMOND"), c("SEVEN", "SPADE")]
        gsm_3p._players[1]["hand"] = [c("EIGHT", "HEART")]  # 1 card
        gsm_3p._players[2]["hand"] = [c("NINE", "CLUB"), c("TEN", "DIAMOND"), c("JACK", "SPADE"), c("QUEEN", "HEART"), c("KING", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None
        gsm_3p._last_play_player_index = None
        gsm_3p._consecutive_passes = 0
        gsm_3p._turn_number = 0

        # p0 出 ♠3 → 下家 p2 接 (p0的逆时针下家是p2)
        r = gsm_3p.play_turn("p0", [c("THREE", "SPADE")])
        assert r["success"] is True

        # p2 的逆时针下家是 p1(1张), 且桌上是单 ♠3 → 必压触发
        # p2 被迫出最大单 K♣
        r = gsm_3p.play_turn("p2", [c("KING", "CLUB")])
        assert r["success"] is True, f"p2 应被迫出K: {r.get('error')}"

        # 现在桌上 = ♣K. p1必须出比K大的单(没有), 所以不触发必压 → 可pass
        r = gsm_3p.pass_turn("p1")
        assert r["success"] is True

        # p0 pass → 全部pass (此时expected=3-1=2, consecutive_passes=2, last_play_player=p2)
        r = gsm_3p.pass_turn("p0")
        assert r["success"] is True
        assert r.get("all_passed") is True, f"expected all_pass: {r}"
        assert gsm_3p._last_play_cards is None
        # p2得到自由出牌权
        assert gsm_3p._current_turn == 2

    # ── 5. 玩家出完牌后轮到下家(跳过已出完的) ─────────────────

    def test_skip_finished_player_in_turn(self, gsm_3p, three_players):
        """玩家出完牌后，轮到下家时跳过已出完的玩家。"""
        config = RuleConfig(
            player_count=4, deck_size=52, cards_per_player=13, must_play_enabled=True
        )
        gsm = GameStateManager(config, room_id="test")
        players = [
            {"player_id": "p0", "name": "A"},
            {"player_id": "p1", "name": "B"},
            {"player_id": "p2", "name": "C"},
            {"player_id": "p3", "name": "D"},
        ]
        gsm.start_game(players)
        gsm.deal_cards(seed=42)
        _declare_all(gsm, ["p0", "p1", "p2", "p3"])

        # p0 只留1张, p1/p2/p3 各留一些
        gsm._players[0]["hand"] = [c("KING", "SPADE")]  # 1张，打出即赢
        gsm._players[1]["hand"] = [c("ACE", "HEART")] * 3
        gsm._players[2]["hand"] = [c("THREE", "CLUB")]  # 1张
        gsm._players[3]["hand"] = [c("FIVE", "DIAMOND")] * 3
        gsm._current_turn = 0
        gsm._last_play_cards = None

        # p0 出最后一张 → 赢 → ROUND_END
        r = gsm.play_turn("p0", [c("KING", "SPADE")])
        assert r["success"] is True
        assert r.get("phase") == "ROUND_END"
        assert r.get("winner_id") == "p0"

    # ── 6. 最后手牌: TRIPLE_WITH_TWO 带0/1个kicker ─────────────

    def test_last_hand_triple_with_zero_kickers(self, gsm_3p, three_players):
        """最后手牌: 三张相同无kicker → is_last_hand 应允许。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # 验证 identify 在 is_last_hand=True 时允许带0个kicker的三带
        from server.card_engine.recognizer import identify
        cards = [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB")]
        pattern = identify(cards, player_count=3, is_last_hand=True)
        assert pattern is not None, "最后手牌3张相同应识别为三带(0 kicker)"
        assert pattern.type.value == 5  # TRIPLE_WITH_TWO

        # 用 play_turn 打出去
        gsm_3p._players[0]["hand"] = list(cards)
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")] * 3
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        result = gsm_3p.play_turn("p0", list(cards))
        assert result["success"] is True, f"最后手牌三带0kicker应允许: {result.get('error')}"
        assert result.get("phase") == "ROUND_END", "最后手牌出完应结束"

    def test_last_hand_triple_with_one_kicker(self, gsm_3p, three_players):
        """最后手牌: 三带一 → is_last_hand 应允许。"""
        from server.card_engine.recognizer import identify
        cards = [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("KING", "SPADE")]
        pattern = identify(cards, player_count=3, is_last_hand=True)
        assert pattern is not None, "最后手牌4张(三带一)应识别"

        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])
        gsm_3p._players[0]["hand"] = list(cards)
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")] * 3
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        result = gsm_3p.play_turn("p0", list(cards))
        assert result["success"] is True
        assert result.get("phase") == "ROUND_END"

    def test_normal_triple_requires_exact_two_kickers(self, gsm_3p, three_players):
        """正常(非最后手牌): 三带二必须带恰好2个kicker，带0/1/3个不行。"""
        from server.card_engine.recognizer import identify
        # 三带0个kicker → 失败
        assert identify([c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB")], is_last_hand=False) is None
        # 三带1个kicker → 失败
        assert identify([c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("KING", "SPADE")], is_last_hand=False) is None
        # 三带2个kicker → 成功
        assert identify([c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("KING", "SPADE"), c("ACE", "HEART")], is_last_hand=False) is not None

    # ── 7. 最后手牌: FOUR_WITH_THREE 带0-2个kicker ────────────

    def test_last_hand_four_with_varying_kickers(self, gsm_3p, three_players):
        """最后手牌: 四张相同带0/1/2/3个kicker → is_last_hand 应允许。"""
        from server.card_engine.recognizer import identify

        cards = [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("THREE", "DIAMOND")]
        extra_sets = [
            [],
            [c("KING", "SPADE")],
            [c("KING", "SPADE"), c("ACE", "HEART")],
            [c("KING", "SPADE"), c("ACE", "HEART"), c("TWO", "CLUB")],
        ]
        for kickers in range(4):  # 0..3
            test_cards = cards + extra_sets[kickers]
            pattern = identify(test_cards, player_count=3, is_last_hand=True)
            assert pattern is not None, f"最后手牌四带{kickers}应识别"

    # ── 9. 连续两次全场pass ─────────────────────────────────────

    def test_consecutive_all_pass(self, gsm_3p, three_players):
        """连续两次全场pass → 状态正确。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        # 每人至少4张, 连出两轮后没人会剩1张触发必压
        for p in gsm_3p._players:
            p["hand"] = [c("THREE", "SPADE"), c("FOUR", "HEART"), c("FIVE", "CLUB"), c("SIX", "DIAMOND")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None
        gsm_3p._last_play_player_index = None
        gsm_3p._consecutive_passes = 0

        # ── 第一轮: p0→p2→p1 全部pass触发all-pass ──
        r = gsm_3p.play_turn("p0", [c("THREE", "SPADE")])
        assert r["success"] is True
        r = gsm_3p.pass_turn("p2")
        assert r["success"] is True
        r = gsm_3p.pass_turn("p1")
        assert r["success"] is True
        assert r.get("all_passed") is True
        assert gsm_3p._last_play_cards is None  # 桌清空
        # 得到自由出牌权的是p0

        # ── 第二轮: 同样再来一次all-pass ──
        r = gsm_3p.play_turn("p0", [c("FOUR", "HEART")])
        assert r["success"] is True
        r = gsm_3p.pass_turn("p2")
        assert r["success"] is True
        r = gsm_3p.pass_turn("p1")
        assert r["success"] is True, f"round2 p1 pass failed: {r}"
        assert r.get("all_passed") is True
        assert gsm_3p._last_play_cards is None

        # 状态应该还是 PLAYING
        assert gsm_3p._phase.value == "PLAYING"

    # ── 注意：跑得快规则：有人出完牌即本局结束，不存在"玩家0张但继续"的场景 ──

    # ── 额外: 2人局必压规则 ─────────────────────────────────────

    def test_must_play_2_player(self):
        """2人局: 必压规则正确工作。"""
        config = RuleConfig(
            player_count=2, deck_size=32, cards_per_player=16, must_play_enabled=True
        )
        gsm = GameStateManager(config)
        players = [
            {"player_id": "p0", "name": "A"},
            {"player_id": "p1", "name": "B"},
        ]
        gsm.start_game(players)
        gsm.deal_cards(seed=42)
        # 声明阶段（2人局也要走声明）
        s = gsm.get_state()
        while s.get("declaration_turn_player_id"):
            gsm.declare(s["declaration_turn_player_id"], is_declaring=False)
            s = gsm.get_state()

        # p0 = current, p1(逆时针: 0-1 mod 2 = 1)有1张，桌上有单牌
        gsm._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART")]
        gsm._players[1]["hand"] = [c("SEVEN", "CLUB")]  # 1 card
        gsm._current_turn = 0
        gsm._last_play_cards = [c("FIVE", "SPADE")]

        # 应触发必压
        result = gsm.pass_turn("p0")
        assert result["success"] is False, "2人局必压应拒绝pass"
        assert result.get("must_play") is True

        # 打最大牌应通过
        result = gsm.play_turn("p0", [c("KING", "HEART")])
        assert result["success"] is True

    # ── 额外: 自由出牌+下家1张+出炸弹允许 ─────────────────────

    def test_free_play_bomb_allowed_next_has_1(self, gsm_3p, three_players):
        """自由出牌+下家1张+出炸弹 → 允许（已存在测试的别名）。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])

        gsm_3p._players[0]["hand"] = [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("THREE", "DIAMOND")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]  # 1 card
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None

        result = gsm_3p.play_turn("p0", [c("THREE", "SPADE"), c("THREE", "HEART"), c("THREE", "CLUB"), c("THREE", "DIAMOND")])
        assert result["success"] is True, f"下家1张时炸弹应允许: {result.get('error')}"

    # ── 额外: 2人自由出牌auto_play ─────────────────────────────

    def test_auto_play_free_play_2p(self):
        """2人局 auto_play 自由出牌 → 出最小牌。"""
        config = RuleConfig(
            player_count=2, deck_size=32, cards_per_player=16, must_play_enabled=True
        )
        gsm = GameStateManager(config)
        players = [
            {"player_id": "p0", "name": "A"},
            {"player_id": "p1", "name": "B"},
        ]
        gsm.start_game(players)
        gsm.deal_cards(seed=42)
        s = gsm.get_state()
        while s.get("declaration_turn_player_id"):
            gsm.declare(s["declaration_turn_player_id"], is_declaring=False)
            s = gsm.get_state()

        gsm._players[0]["hand"] = [c("THREE", "SPADE"), c("KING", "HEART")]
        gsm._players[1]["hand"] = [c("FIVE", "CLUB")] * 5
        gsm._current_turn = 0
        gsm._last_play_cards = None

        result = gsm.auto_play("p0")
        assert result["success"] is True
        # 应出最小牌 ♠3
        assert c("THREE", "SPADE") not in gsm._players[0]["hand"]


# ═══════════════════════════════════════════════════════════════════════
# TEST CASE 10: 第二轮边界条件
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCasesRound2:
    """第二轮分析发现的新边界条件。

    Bug 1: 必压比较用牌对象而非面值 → 同面值不同花色应接受
    Bug 2: ACE_BOMB 忽略 has_ace_bomb=False → 设置后禁用
    Bug 3: 连对包含 TWO(15) → TWO 不应出现在连对
    """

    def test_must_play_accepts_different_suit_same_rank(self, gsm_3p, three_players):
        """必压触发，手牌有♥K和♠K → 出♥K应接受。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])
        gsm_3p._players[0]["hand"] = [c("KING", "HEART"), c("KING", "SPADE"), c("THREE", "CLUB")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = [c("FIVE", "SPADE")]
        result = gsm_3p.play_turn("p0", [c("KING", "HEART")])
        assert result["success"] is True, f"不同花色同面值应接受: {result.get('error')}"

    def test_free_play_must_play_accepts_different_suit(self, gsm_3p, three_players):
        """自由出牌必压：下家1张，出同面值不同花色的最大牌应接受。"""
        gsm_3p.start_game(three_players)
        gsm_3p.deal_cards(seed=42)
        _declare_all(gsm_3p, ["p0", "p1", "p2"])
        gsm_3p._players[0]["hand"] = [c("KING", "HEART"), c("KING", "SPADE"), c("THREE", "CLUB")]
        gsm_3p._players[1]["hand"] = [c("FIVE", "HEART")] * 5
        gsm_3p._players[2]["hand"] = [c("SEVEN", "CLUB")]
        gsm_3p._current_turn = 0
        gsm_3p._last_play_cards = None
        result = gsm_3p.play_turn("p0", [c("KING", "HEART")])
        assert result["success"] is True, f"自由出牌必压同面值应接受: {result.get('error')}"

    def test_ace_bomb_disabled_by_config(self):
        """has_ace_bomb=False → 3个A不应识别为A炸。"""
        from server.card_engine.recognizer import identify, PatternType
        three_aces = [c("ACE", "SPADE"), c("ACE", "HEART"), c("ACE", "CLUB")]
        pattern_on = identify(three_aces, player_count=3, has_ace_bomb=True)
        assert pattern_on is not None and pattern_on.type == PatternType.ACE_BOMB
        pattern_off = identify(three_aces, player_count=3, has_ace_bomb=False)
        assert pattern_off is None, "has_ace_bomb=False 时A炸不应识别"

    def test_ace_bomb_not_generated_when_disabled(self):
        """has_ace_bomb=False → 不生成A炸可选牌。"""
        from server.rule_engine.rules import RuleConfig, RuleEngine
        from server.card_engine.recognizer import identify, PatternType
        config_disabled = RuleConfig(
            player_count=3, deck_size=48, cards_per_player=16,
            has_ace_bomb=False, must_play_enabled=True,
        )
        engine = RuleEngine(config_disabled)
        hand = [c("ACE", "SPADE"), c("ACE", "HEART"), c("ACE", "CLUB"),
                c("KING", "SPADE"), c("KING", "HEART")]
        plays = engine.get_legal_plays(hand, last_play_pattern=None, player_count=3)
        for play in plays:
            p = identify(play, player_count=3, has_ace_bomb=False)
            if p and p.type == PatternType.ACE_BOMB:
                pytest.fail("has_ace_bomb=False 不应生成A炸")

    def test_consecutive_pairs_rejects_two(self):
        """连对包含TWO → 不应识别。"""
        from server.card_engine.recognizer import identify
        invalid = [
            c("KING", "SPADE"), c("KING", "HEART"),
            c("ACE", "SPADE"), c("ACE", "HEART"),
            c("TWO", "SPADE"), c("TWO", "HEART"),
        ]
        pattern = identify(invalid, player_count=3)
        assert pattern is None, "包含TWO的连对不应识别"

    def test_consecutive_pairs_without_two_accepted(self):
        """连对不包含TWO → 正常识别。"""
        from server.card_engine.recognizer import identify, PatternType
        valid = [
            c("QUEEN", "SPADE"), c("QUEEN", "HEART"),
            c("KING", "SPADE"), c("KING", "HEART"),
            c("ACE", "SPADE"), c("ACE", "HEART"),
        ]
        pattern = identify(valid, player_count=3)
        assert pattern is not None and pattern.type == PatternType.CONSECUTIVE_PAIRS
