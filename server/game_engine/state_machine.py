"""
Game state machine for 跑得快 (Pao De Kuai).

Manages the game lifecycle through explicit phases:
WAITING → DEALING → DECLARATION → PLAYING → ROUND_END

Coordinates the card engine (recognizer, comparator, deck), rule engine,
and scoring engine into a cohesive game flow. All methods return plain dicts
for easy consumption by network/serialization layers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.card_engine.card import Card
from server.card_engine.deck import build_deck, deal_cards as deal
from server.card_engine.recognizer import identify, get_pattern_display_name
from server.game_engine.scorer import ScoringEngine
from server.models import GamePhase
from server.rule_engine.rules import RuleConfig, RuleEngine


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class InvalidStateError(Exception):
    """Raised when an operation is attempted in the wrong game phase."""
    pass


# ---------------------------------------------------------------------------
# Serialization helpers (mirror models.py to avoid circular imports)
# ---------------------------------------------------------------------------

def _card_to_dict(card: Card) -> dict:
    """Serialize a Card to a plain dict for JSON."""
    return {"suit": card.suit.name, "rank": card.rank.name}


def _cards_to_dicts(cards: List[Card]) -> list:
    return [_card_to_dict(c) for c in cards]


# ---------------------------------------------------------------------------
# GameStateManager
# ---------------------------------------------------------------------------

class GameStateManager:
    """Manages the complete lifecycle of a 跑得快 game round.

    Coordinates:
    - RuleEngine: for all validation (is_valid_play, check_must_play, determine_first_player)
    - ScoringEngine: for end-of-round score calculation
    - Deck: for building and dealing

    Phase transitions:
        WAITING → DEALING → DECLARATION → PLAYING → ROUND_END
    """

    def __init__(self, config: RuleConfig, room_id: str = ""):
        """Initialize the state machine with a rule configuration.

        Args:
            config: RuleConfig specifying player_count, deck_size, etc.
            room_id: Optional room identifier.
        """
        self._config = config
        self._room_id = room_id
        self._rule_engine = RuleEngine(config)
        self._scorer = ScoringEngine()

        # ── Mutable state ──────────────────────────────────────────
        self._phase: GamePhase = GamePhase.WAITING
        self._players: List[Dict[str, Any]] = []
        self._current_turn: int = 0
        self._last_play_cards: Optional[List[Card]] = None
        self._last_play_player_index: Optional[int] = None
        self._last_play_pattern_type: str = ""
        self._last_play_pattern_display: str = ""
        self._consecutive_passes: int = 0
        self._turn_number: int = 0
        self._round_number: int = 1
        self._deck: List[Card] = []
        self._deck_size: int = 0
        self._previous_winner_id: Optional[str] = None
        self._round_history: List[Dict[str, Any]] = []
        self._declarer_id: Optional[str] = None
        self._declaration_turn: int = 0  # whose turn to declare
        # Per-player last play/action tracking for frontend display
        self._player_last_plays: Dict[int, Optional[Dict[str, Any]]] = {}
        self._player_last_actions: Dict[int, Optional[str]] = {}  # 'play' | 'pass'

    # ── Phase helpers ──────────────────────────────────────────────

    def _require_phase(self, *allowed: GamePhase) -> None:
        """Raise InvalidStateError if current phase is not in `allowed`."""
        if self._phase not in allowed:
            raise InvalidStateError(
                f"Expected phase in {[p.value for p in allowed]}, "
                f"got {self._phase.value}"
            )

    def _next_player_with_cards(self, start_index: int) -> int:
        """Find the next player index (wrapping) who still has cards.

        Args:
            start_index: The index of the current player.

        Returns:
            The index of the next player with a non-empty hand.
            If no one has cards (shouldn't happen during PLAYING), returns start_index.
        """
        n = len(self._players)
        for offset in range(1, n + 1):
            candidate = (start_index - offset) % n  # counter-clockwise
            if self._players[candidate]["hand"]:
                return candidate
        return start_index  # fallback

    def _count_active_players(self) -> int:
        """Return the number of players who still have cards."""
        return sum(1 for p in self._players if p["hand"])

    # ── Build must-play game_state dict ────────────────────────────

    def _build_must_play_state(self) -> Dict[str, Any]:
        """Build the game_state dict expected by RuleEngine.check_must_play."""
        return {
            "players": [
                {"player_id": p["player_id"], "remaining_cards": len(p["hand"])}
                for p in self._players
            ],
            "current_turn": self._current_turn,
        }

    # ── Serialize last play ────────────────────────────────────────

    def _serialize_last_play(self) -> Optional[Dict[str, Any]]:
        """Return a serialized dict of the current last play, or None."""
        if self._last_play_cards is None or self._last_play_player_index is None:
            return None
        return {
            "cards": _cards_to_dicts(self._last_play_cards),
            "pattern_type": self._last_play_pattern_type,
            "pattern_display": self._last_play_pattern_display,
            "player_id": self._players[self._last_play_player_index]["player_id"],
        }

    # ── Public API ─────────────────────────────────────────────────

    def start_game(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Initialize a new game with the given players.

        Transitions phase from WAITING to DEALING.

        Args:
            players: List of dicts, each with at least:
                {"player_id": str, "name": str}
                Optional: "score": int (default 0)

        Returns:
            {"success": bool, "phase": str, "message": str, ...}
        """
        self._require_phase(GamePhase.WAITING)

        if len(players) != self._config.player_count:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": (
                    f"Expected {self._config.player_count} players, "
                    f"got {len(players)}"
                ),
            }

        self._players = [
            {
                "player_id": p["player_id"],
                "name": p.get("name", p["player_id"]),
                "hand": [],
                "score": p.get("score", 0),
                "is_declarer": False,
                "declaration": None,  # None = not yet chosen
            }
            for p in players
        ]

        self._phase = GamePhase.DEALING
        return {
            "success": True,
            "phase": self._phase.value,
            "message": f"Game started with {len(players)} players",
        }

    def deal_cards(self, seed: Optional[int] = None) -> Dict[str, Any]:
        """Build the deck and deal cards to all players.

        Transitions phase from DEALING to DECLARATION.

        Args:
            seed: Optional seed for deterministic shuffling.

        Returns:
            {"success": bool, "phase": str, ...}
        """
        self._require_phase(GamePhase.DEALING)

        self._deck = build_deck(self._config.player_count, seed=seed)
        self._deck_size = len(self._deck)
        hands = deal(self._deck, self._config.player_count)

        for i, hand in enumerate(hands):
            self._players[i]["hand"] = hand

        # Reset per-round state
        self._current_turn = 0
        self._last_play_cards = None
        self._last_play_player_index = None
        self._last_play_pattern_type = ""
        self._last_play_pattern_display = ""
        self._consecutive_passes = 0
        self._turn_number = 0
        self._player_last_plays = {}
        self._player_last_actions = {}
        self._declarer_id = None
        self._declaration_turn = self._rule_engine.determine_first_player(
            players=[
                {"player_id": p["player_id"], "hand": p["hand"]}
                for p in self._players
            ],
            round_number=self._round_number,
            previous_winner_id=self._previous_winner_id,
        )
        for p in self._players:
            p["is_declarer"] = False
            p["declaration"] = None

        self._phase = GamePhase.DECLARATION
        return {
            "success": True,
            "phase": self._phase.value,
            "deck_size": self._deck_size,
            "cards_per_player": self._config.cards_per_player,
            "message": f"Dealt {self._deck_size} cards to {len(self._players)} players",
        }

    def declare(self, player_id: str, is_declaring: bool) -> Dict[str, Any]:
        """Record a player's declaration (包牌) choice.

        Once all players have chosen, transitions from DECLARATION to PLAYING.

        Args:
            player_id: The declaring player's ID.
            is_declaring: True if the player wants to 包牌 (spring).

        Returns:
            {"success": bool, "phase": str, ...}
        """
        self._require_phase(GamePhase.DECLARATION)

        # Find the player
        target_index: Optional[int] = None
        for i, p in enumerate(self._players):
            if p["player_id"] == player_id:
                target_index = i
                break

        if target_index is None:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": f"Player {player_id} not found",
            }

        # ── Enforce declaration turn order ─────────────────────────
        if target_index != self._declaration_turn:
            current_declarer = self._players[self._declaration_turn]
            return {
                "success": False,
                "phase": self._phase.value,
                "error": (
                    f"Not your turn to declare. "
                    f"Waiting for {current_declarer['name']}."
                ),
            }

        if self._players[target_index]["declaration"] is not None:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": f"Player {player_id} already declared",
            }

        self._players[target_index]["declaration"] = is_declaring
        print(f"[DECLARE_STATE] player={player_id[:8]} chose is_declaring={is_declaring}")

        if is_declaring:
            if self._declarer_id is None:
                self._declarer_id = player_id
                self._players[target_index]["is_declarer"] = True
                print(f"[DECLARE_STATE] Set declarer_id={player_id[:8]}")
            # 包牌: auto-fill remaining players, transition to PLAYING immediately
            for p in self._players:
                if p["declaration"] is None:
                    p["declaration"] = False
            print(f"[DECLARE_STATE] Auto-filled remaining players as False")

        # ── Advance to next player ─────────────────────────────────
        n = len(self._players)
        for _ in range(n):
            self._declaration_turn = (self._declaration_turn + 1) % n
            if self._players[self._declaration_turn]["declaration"] is None:
                break

        # Check if all players have chosen
        all_chosen = all(p["declaration"] is not None for p in self._players)
        print(f"[DECLARE_STATE] all_chosen={all_chosen} declarer_id={self._declarer_id}")

        if not all_chosen:
            next_player = self._players[self._declaration_turn]
            return {
                "success": True,
                "phase": self._phase.value,
                "next_declarer_id": next_player["player_id"],
                "next_declarer_name": next_player["name"],
                "message": (
                    f"Player {player_id} chose "
                    f"{'包牌' if is_declaring else '不包牌'}. "
                    f"Now {next_player['name']}'s turn."
                ),
            }

        # ── All declarations collected: transition to PLAYING ───────
        self._phase = GamePhase.PLAYING
        print(f"[DECLARE_STATE] Transitioned to PLAYING phase")

        # Determine first player
        if self._declarer_id is not None:
            # Declarer goes first
            for i, p in enumerate(self._players):
                if p["player_id"] == self._declarer_id:
                    self._current_turn = i
                    break
        else:
            # No declarer: use determine_first_player
            player_dicts = [
                {"player_id": p["player_id"], "hand": p["hand"]}
                for p in self._players
            ]
            self._current_turn = self._rule_engine.determine_first_player(
                players=player_dicts,
                round_number=self._round_number,
                previous_winner_id=self._previous_winner_id,
            )

        return {
            "success": True,
            "phase": self._phase.value,
            "current_turn": self._players[self._current_turn]["player_id"],
            "declarer_id": self._declarer_id,
            "message": (
                f"All players declared. "
                f"{'Declarer' if self._declarer_id else 'Player'} "
                f"{self._players[self._current_turn]['name']} goes first."
            ),
        }

    def play_turn(self, player_id: str, cards: List[Card]) -> Dict[str, Any]:
        """Process a play attempt from a player.

        Validates the play via RuleEngine, updates game state on success,
        and checks for round-end conditions (player emptied hand).

        Args:
            player_id: The ID of the player making the play.
            cards: The cards the player wants to play.

        Returns:
            {"success": bool, "phase": str, ...}
        """
        self._require_phase(GamePhase.PLAYING)

        current_player = self._players[self._current_turn]

        # ── 1. Verify it's this player's turn ───────────────────────
        if current_player["player_id"] != player_id:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": (
                    f"Not your turn. Current player: "
                    f"{current_player['name']}"
                ),
            }

        hand = current_player["hand"]
        is_last_hand = (len(cards) == len(hand))

        # ── 2. Identify last play pattern (if any) ──────────────────
        last_play_pattern = None
        if self._last_play_cards is not None:
            last_play_pattern = identify(
                self._last_play_cards,
                player_count=self._config.player_count,
            )

        # ── 3. Check must-play rule ─────────────────────────────────
        must_play_state = self._build_must_play_state()
        must_result = self._rule_engine.check_must_play(
            hand=hand,
            last_play_pattern=last_play_pattern,
            game_state=must_play_state,
            player_index=self._current_turn,
        )

        if must_result["triggered"]:
            forced = must_result["forced_cards"]
            # The player MUST play the forced card(s)
            if set(cards) != set(forced or []):
                forced_desc = ", ".join(str(c) for c in (forced or []))
                return {
                    "success": False,
                    "phase": self._phase.value,
                    "error": f"必压规则触发，必须出 {forced_desc}",
                    "must_play": True,
                    "forced_cards": _cards_to_dicts(forced or []),
                }

        # ── 3b. Free-play must-play: next player has 1 card, must play highest single ──
        if self._last_play_cards is None:
            n_players = len(self._players)
            next_idx = (self._current_turn - 1) % n_players  # counter-clockwise
            if self._players[next_idx]["hand"] and len(self._players[next_idx]["hand"]) == 1:
                # Check if current play is a single
                from server.card_engine.recognizer import PatternType
                play_pattern = identify(
                    cards,
                    player_count=self._config.player_count,
                )
                if play_pattern is not None and play_pattern.type == PatternType.SINGLE:
                    # Find the highest single in hand
                    forced_single = max(hand, key=lambda c: (c.rank.value, c.suit.value))
                    if len(cards) != 1 or cards[0] != forced_single:
                        return {
                            "success": False,
                            "phase": self._phase.value,
                            "error": f"必压规则触发，上家出单时必须出最大单牌 ({forced_single})",
                            "must_play": True,
                            "forced_cards": _cards_to_dicts([forced_single]),
                        }

        # ── 4. Validate the play via RuleEngine ─────────────────────
        validation = self._rule_engine.is_valid_play(
            cards=cards,
            hand=hand,
            last_play_pattern=last_play_pattern,
            player_count=self._config.player_count,
            is_last_hand=is_last_hand,
        )

        if not validation["valid"]:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": validation.get("error", "Invalid play"),
            }

        # ── 5. Apply the play: remove cards from hand ───────────────
        for c in cards:
            hand.remove(c)

        # ── 6. Update table state ───────────────────────────────────
        identified = identify(
            cards,
            player_count=self._config.player_count,
            is_last_hand=is_last_hand,
        )

        self._last_play_cards = list(cards)
        self._last_play_player_index = self._current_turn
        if identified is not None:
            self._last_play_pattern_type = identified.type.name
            self._last_play_pattern_display = get_pattern_display_name(identified)
        self._consecutive_passes = 0
        self._turn_number += 1

        # Record per-player last play for frontend display
        self._player_last_plays[self._current_turn] = self._serialize_last_play()
        self._player_last_actions[self._current_turn] = 'play'

        # ── 7. Declaration break check ─────────────────────────────
        # In declaration (包牌) mode: a non-declarer playing ANY card
        # immediately ends the round — they "break" the declaration.
        if self._declarer_id is not None and player_id != self._declarer_id:
            return self._end_round_internal(player_id)

        # ── 8. Check for round end (player emptied hand) ────────────
        if not hand:
            # This player wins the round
            winner_id = player_id
            return self._end_round_internal(winner_id)

        # ── 9. Advance to next player with cards ────────────────────
        self._current_turn = self._next_player_with_cards(self._current_turn)

        return {
            "success": True,
            "phase": self._phase.value,
            "current_turn": self._players[self._current_turn]["player_id"],
            "last_play": self._serialize_last_play(),
            "remaining_cards": len(hand),
            "message": f"Play accepted. {len(hand)} cards remaining.",
        }

    def pass_turn(self, player_id: str) -> Dict[str, Any]:
        """Process a pass from the current player.

        Validates the pass (must-play check), handles all-passed detection,
        and advances the turn.

        Args:
            player_id: The ID of the player passing.

        Returns:
            {"success": bool, "phase": str, ...}
        """
        self._require_phase(GamePhase.PLAYING)

        current_player = self._players[self._current_turn]

        # ── 1. Verify it's this player's turn ───────────────────────
        if current_player["player_id"] != player_id:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": (
                    f"Not your turn. Current player: "
                    f"{current_player['name']}"
                ),
            }

        # ── 2. Cannot pass on free play (no last_play on table) ─────
        if self._last_play_cards is None:
            return {
                "success": False,
                "phase": self._phase.value,
                "error": "Cannot pass on a free play. You must play cards.",
            }

        # ── 3. Check must-play rule ─────────────────────────────────
        last_play_pattern = identify(
            self._last_play_cards,
            player_count=self._config.player_count,
        )

        must_play_state = self._build_must_play_state()
        must_result = self._rule_engine.check_must_play(
            hand=current_player["hand"],
            last_play_pattern=last_play_pattern,
            game_state=must_play_state,
            player_index=self._current_turn,
        )

        if must_result["triggered"]:
            forced = must_result["forced_cards"]
            forced_desc = ", ".join(str(c) for c in (forced or []))
            return {
                "success": False,
                "phase": self._phase.value,
                "error": f"必压规则触发，不能Pass，必须出 {forced_desc}",
                "must_play": True,
                "forced_cards": _cards_to_dicts(forced or []),
            }

        # ── 4. Record pass and advance ──────────────────────────────
        self._consecutive_passes += 1
        self._turn_number += 1
        # Record per-player pass action
        self._player_last_actions[self._current_turn] = 'pass'

        active_count = self._count_active_players()
        expected_passes = active_count - 1  # all except last_play player

        if self._consecutive_passes >= expected_passes and self._last_play_player_index is not None:
            # ── All-passed: last player who played gets free turn ──
            # Clear all per-player last play records (table reset)
            self._player_last_plays = {}
            self._player_last_actions = {}
            free_turn_player = self._last_play_player_index
            self._last_play_cards = None
            self._last_play_player_index = None
            self._last_play_pattern_type = ""
            self._last_play_pattern_display = ""
            self._consecutive_passes = 0
            self._current_turn = free_turn_player

            # Ensure that player still has cards (they always should since
            # they didn't win the round yet)
            if not self._players[self._current_turn]["hand"]:
                # Edge case: shouldn't happen, but handle gracefully
                self._current_turn = self._next_player_with_cards(
                    self._current_turn
                )

            return {
                "success": True,
                "phase": self._phase.value,
                "current_turn": self._players[self._current_turn]["player_id"],
                "last_play": None,
                "message": "All passed. New round: free play.",
                "all_passed": True,
            }

        # ── 5. Normal pass: advance to next player ─────────────────
        self._current_turn = self._next_player_with_cards(self._current_turn)

        return {
            "success": True,
            "phase": self._phase.value,
            "current_turn": self._players[self._current_turn]["player_id"],
            "consecutive_passes": self._consecutive_passes,
            "message": "Pass accepted.",
        }

    def auto_play(self, player_id: str) -> Dict[str, Any]:
        """Auto-play on timeout: pass if possible, else play the smallest card.

        Called by the turn timer when a player runs out of time.

        Args:
            player_id: The ID of the player whose turn it is.

        Returns:
            Same shape as play_turn / pass_turn.
        """
        self._require_phase(GamePhase.PLAYING)

        current_player = self._players[self._current_turn]

        if current_player["player_id"] != player_id:
            return {"success": False, "error": "Not your turn"}

        if self._last_play_cards is not None:
            # Can pass → auto-pass
            return self.pass_turn(player_id)
        else:
            # Free play → play the smallest single card
            hand = current_player["hand"]
            if not hand:
                return {"success": False, "error": "No cards remaining"}
            # hand is sorted, first card is smallest
            return self.play_turn(player_id, [hand[0]])

    def end_round(self) -> Dict[str, Any]:
        """End the current round explicitly (e.g., on forfeit).

        Normally, end_round is triggered automatically when a player
        empties their hand via play_turn. This method provides manual
        round termination for exceptional cases.

        Returns:
            {"success": bool, "phase": str, ...}
        """
        self._require_phase(GamePhase.PLAYING, GamePhase.ROUND_END)

        if self._phase == GamePhase.ROUND_END:
            return self._build_round_end_result()

        # Find the winner (player who emptied hand first, or forfeit)
        # For explicit end_round, use last player who played as winner
        winner_id: Optional[str] = None
        for p in self._players:
            if not p["hand"]:
                winner_id = p["player_id"]
                break

        if winner_id is None:
            # Determine winner by finding player with fewest cards
            winner_id = min(
                self._players, key=lambda p: len(p["hand"])
            )["player_id"]

        return self._end_round_internal(winner_id)

    # ── Internal round-end logic ───────────────────────────────────

    def _end_round_internal(self, winner_id: str) -> Dict[str, Any]:
        """Handle round-end scoring and state transition.

        Args:
            winner_id: The player_id of the round winner.

        Returns:
            Round result dict.
        """
        # Build player dicts for the scorer
        scorer_players = [
            {
                "player_id": p["player_id"],
                "remaining_cards": len(p["hand"]),
            }
            for p in self._players
        ]

        # Calculate scores
        if self._declarer_id is not None:
            # Declaration round
            if winner_id == self._declarer_id:
                # Declarer won
                breaker_id = None
            else:
                # Declarer was broken
                breaker_id = winner_id

            score_deltas = self._scorer.calculate_declaration_score(
                declarer_id=self._declarer_id,
                breaker_id=breaker_id,
                players=scorer_players,
                player_count=self._config.player_count,
            )
            is_declaration_game = True
        else:
            # Normal round
            score_deltas = self._scorer.calculate_normal_score(
                winner_id=winner_id,
                players=scorer_players,
            )
            is_declaration_game = False

        # Apply score changes
        for p in self._players:
            pid = p["player_id"]
            if pid in score_deltas:
                p["score"] += score_deltas[pid]

        self._phase = GamePhase.ROUND_END
        self._previous_winner_id = winner_id

        # Clear per-player last play records for next round
        self._player_last_plays = {}
        self._player_last_actions = {}

        result = {
            "success": True,
            "phase": self._phase.value,
            "winner_id": winner_id,
            "scores": {p["player_id"]: p["score"] for p in self._players},
            "score_deltas": score_deltas,
            "is_declaration_game": is_declaration_game,
            "declarer_id": self._declarer_id,
            "breaker_id": (
                None
                if (not is_declaration_game or winner_id == self._declarer_id)
                else winner_id
            ),
            "final_hands": {
                p["player_id"]: _cards_to_dicts(p["hand"])
                for p in self._players
            },
        }

        self._round_history.append({
            "round_number": self._round_number,
            "winner_id": winner_id,
            "score_deltas": dict(score_deltas),
            "is_declaration_game": is_declaration_game,
            "declarer_id": self._declarer_id,
        })

        return result

    def _build_round_end_result(self) -> Dict[str, Any]:
        """Return the most recent round's result if already in ROUND_END."""
        if self._round_history:
            last = self._round_history[-1]
            return {
                "success": True,
                "phase": self._phase.value,
                "winner_id": last["winner_id"],
                "scores": {p["player_id"]: p["score"] for p in self._players},
                "is_declaration_game": last["is_declaration_game"],
                "declarer_id": last.get("declarer_id"),
            }
        return {"success": True, "phase": self._phase.value}

    def start_next_round(self) -> Dict[str, Any]:
        """Advance to the next round: deal new cards, reset round state.

        Transitions from ROUND_END to DEALING, then deals cards into
        DECLARATION phase.

        Returns:
            {"success": bool, "phase": str, ...}
        """
        self._require_phase(GamePhase.ROUND_END)

        self._round_number += 1
        self._phase = GamePhase.DEALING
        return self.deal_cards()

    def get_state(self) -> Dict[str, Any]:
        """Return the current game state as a plain dict.

        Returns:
            Dict with at least: {"success": bool, "phase": str, ...}
        """
        # Build serialized player list
        serialized_players = []
        for p in self._players:
            sp = {
                "player_id": p["player_id"],
                "name": p["name"],
                "hand": _cards_to_dicts(p["hand"]),
                "score": p["score"],
                "remaining_cards": len(p["hand"]),
            }
            if self._phase in (GamePhase.DECLARATION, GamePhase.PLAYING,
                               GamePhase.ROUND_END):
                sp["is_declarer"] = p.get("is_declarer", False)
                if self._phase == GamePhase.DECLARATION:
                    sp["declaration"] = p.get("declaration")
            serialized_players.append(sp)

        state: Dict[str, Any] = {
            "success": True,
            "phase": self._phase.value,
            "room_id": self._room_id,
            "players": serialized_players,
            "current_turn": (
                self._players[self._current_turn]["player_id"]
                if self._players and self._phase == GamePhase.PLAYING
                else None
            ),
            "current_turn_index": (
                self._current_turn
                if self._players and self._phase == GamePhase.PLAYING
                else None
            ),
            "last_play": self._serialize_last_play(),
            "consecutive_passes": self._consecutive_passes,
            "turn_number": self._turn_number,
            "round_number": self._round_number,
            "deck_size": self._deck_size,
            "player_count": self._config.player_count,
            "declarer_id": self._declarer_id,
            "declaration_turn_player_id": (
                self._players[self._declaration_turn]["player_id"]
                if self._phase == GamePhase.DECLARATION and self._players
                else None
            ),
            "player_last_plays": {
                self._players[i]["player_id"]: self._player_last_plays.get(i)
                for i in range(len(self._players))
            },
            "player_last_actions": {
                self._players[i]["player_id"]: self._player_last_actions.get(i)
                for i in range(len(self._players))
            },
        }

        return state
