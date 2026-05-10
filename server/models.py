from __future__ import annotations

"""
Pydantic data models for 跑得快 (Pao De Kuai) game state.

Pure data structures — no game logic.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, field_serializer

from server.card_engine.card import Card, Suit, Rank


# ---------------------------------------------------------------------------
# Helpers: Card serialization (Card is a frozen dataclass, not Pydantic)
# ---------------------------------------------------------------------------

def _card_to_dict(card: Card) -> dict:
    """Serialize a Card to a plain dict for JSON."""
    return {"suit": card.suit.name, "rank": card.rank.name}


def _dict_to_card(d: dict) -> Card:
    """Deserialize a dict back to a Card."""
    return Card(suit=Suit[d["suit"]], rank=Rank[d["rank"]])


def _cards_to_dicts(cards: list[Card]) -> list[dict]:
    return [_card_to_dict(c) for c in cards]


def _dicts_to_cards(dicts: list[dict]) -> list[Card]:
    return [_dict_to_card(d) for d in dicts]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GamePhase(str, Enum):
    """Explicit game state-machine phases."""
    WAITING = "WAITING"
    DEALING = "DEALING"
    DECLARATION = "DECLARATION"
    PLAYING = "PLAYING"
    ROUND_END = "ROUND_END"


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class PlayerState(BaseModel):
    """Snapshot of a single player's state."""
    player_id: str
    name: str
    hand: list[Card]
    score: int = 0
    is_declarer: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_serializer("hand")
    def _serialize_hand(self, cards: list[Card]) -> list[dict]:
        return _cards_to_dicts(cards)

    @field_validator("hand", mode="before")
    @classmethod
    def _deserialize_hand(cls, v):
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return _dicts_to_cards(v)
        return v


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class GameState(BaseModel):
    """Full game state broadcast to all clients."""
    room_id: str
    players: list[PlayerState]
    phase: GamePhase
    current_turn: int = 0
    last_play: Optional["CardPlay"] = None
    last_play_player_id: Optional[str] = None
    turn_number: int = 0
    round_number: int = 1
    player_count: int
    deck_size: int
    consecutive_passes: int = 0
    player_last_plays: dict[str, Optional["CardPlay"]] = {}
    player_last_actions: dict[str, Optional[str]] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ---------------------------------------------------------------------------
# Play
# ---------------------------------------------------------------------------

class CardPlay(BaseModel):
    """A validated play — what cards, what pattern, by whom."""
    cards: list[Card]
    pattern_type: str
    pattern_display: str
    player_id: str

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_serializer("cards")
    def _serialize_cards(self, cards: list[Card]) -> list[dict]:
        return _cards_to_dicts(cards)

    @field_validator("cards", mode="before")
    @classmethod
    def _deserialize_cards(cls, v):
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return _dicts_to_cards(v)
        return v


class PlayRequest(BaseModel):
    """Incoming play request from a client."""
    player_id: str
    cards: list[Card]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_serializer("cards")
    def _serialize_cards(self, cards: list[Card]) -> list[dict]:
        return _cards_to_dicts(cards)

    @field_validator("cards", mode="before")
    @classmethod
    def _deserialize_cards(cls, v):
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return _dicts_to_cards(v)
        return v


class PlayResponse(BaseModel):
    """Server response to a play request."""
    valid: bool
    error: Optional[str] = None
    must_play: bool = False
    forced_cards: Optional[list[Card]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_serializer("forced_cards")
    def _serialize_forced(self, cards: list[Card] | None) -> list[dict] | None:
        if cards is None:
            return None
        return _cards_to_dicts(cards)

    @field_validator("forced_cards", mode="before")
    @classmethod
    def _deserialize_forced(cls, v):
        if v is None:
            return None
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return _dicts_to_cards(v)
        return v


# ---------------------------------------------------------------------------
# Round Result
# ---------------------------------------------------------------------------

class RoundResult(BaseModel):
    """Result of a completed round."""
    winner_id: str
    scores: dict[str, int]
    is_declaration_game: bool
    declarer_id: Optional[str] = None
    breaker_id: Optional[str] = None
