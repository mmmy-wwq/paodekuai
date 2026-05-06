"""
WebSocket message protocol for 跑得快 (Pao De Kuai).

Defines the message contract between client and server.
MsgType string values MUST match the TypeScript MsgType enum exactly.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from server.card_engine.card import Card


# ── MsgType ────────────────────────────────────────────────────────────────

class MsgType(str, Enum):
    """WebSocket message types.

    String values match TypeScript MsgType enum exactly.
    """
    JOIN = "JOIN"
    LEAVE = "LEAVE"
    START_GAME = "START_GAME"
    DECLARE = "DECLARE"
    PLAY = "PLAY"
    PASS = "PASS"
    STATE_SYNC = "STATE_SYNC"
    ERROR = "ERROR"
    GAME_START = "GAME_START"
    ROUND_END = "ROUND_END"
    PING = "PING"
    PONG = "PONG"
    PLAYER_JOINED = "PLAYER_JOINED"
    PLAYER_LEFT = "PLAYER_LEFT"
    READY = "READY"


# Set of valid message type strings for fast lookup
VALID_MSG_TYPES: set = {t.value for t in MsgType}


# ── Payload type definitions ──────────────────────────────────────────────

# Payload schemas are documented via TypedDict-style comments.
# Specific validation is done in application code based on MsgType.

class JoinPayload(dict):
    """Payload for JOIN message.
    Fields: name (str), room_id (str)
    """


class PlayPayload(dict):
    """Payload for PLAY message.
    Fields: cards (List[dict]) — each dict from card_to_dict()
    """


class DeclarePayload(dict):
    """Payload for DECLARE message.
    Fields: is_declaring (bool)
    """


class StateSyncPayload(dict):
    """Payload for STATE_SYNC message.
    Fields: game_state (dict) — GameState.model_dump()
    """


class ErrorPayload(dict):
    """Payload for ERROR message.
    Fields: code (str), message (str)
    """


class RoundEndPayload(dict):
    """Payload for ROUND_END message.
    Fields: result (dict) — RoundResult.model_dump()
    """


# ── Message model ─────────────────────────────────────────────────────────

@dataclass
class Message:
    """Standard WebSocket message envelope.

    Attributes:
        type: Message type enum
        payload: Message payload as a dict
        timestamp: Unix timestamp of message creation
        player_id: Optional player identifier
    """
    type: MsgType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    player_id: Optional[str] = None


# ── Card serialization helpers ────────────────────────────────────────────

def card_to_dict(card: Card) -> dict:
    """Serialize a Card to a JSON-safe dict.

    Example:
        >>> card_to_dict(Card(Suit.SPADE, Rank.ACE))
        {'suit': 'SPADE', 'rank': 'ACE'}
    """
    return {"suit": card.suit.name, "rank": card.rank.name}


def card_from_dict(data: dict) -> Card:
    """Deserialize a Card from a dict.

    Args:
        data: Dict with 'suit' and 'rank' string keys.

    Returns:
        Card instance.

    Raises:
        KeyError: if required keys are missing.
    """
    from server.card_engine.card import Suit, Rank

    return Card(suit=Suit[data["suit"]], rank=Rank[data["rank"]])


def cards_to_dicts(cards: list) -> list:
    """Convert a list of Cards to a list of dicts."""
    return [card_to_dict(c) for c in cards]


def cards_from_dicts(data: list) -> list:
    """Convert a list of dicts to a list of Cards."""
    return [card_from_dict(d) for d in data]


# ── Message construction ──────────────────────────────────────────────────

def create_message(
    msg_type: MsgType,
    payload: Optional[Dict[str, Any]] = None,
    player_id: Optional[str] = None,
) -> Message:
    """Create a properly formed Message.

    Args:
        msg_type: The message type.
        payload: Message payload dict (defaults to empty dict).
        player_id: Optional player ID.

    Returns:
        A new Message instance with current timestamp.
    """
    return Message(
        type=msg_type,
        payload=payload if payload is not None else {},
        timestamp=time.time(),
        player_id=player_id,
    )


# ── Serialization ─────────────────────────────────────────────────────────

def serialize_message(msg: Message) -> str:
    """Serialize a Message to a JSON string.

    Args:
        msg: Message instance to serialize.

    Returns:
        JSON string representation.
    """
    return json.dumps(_message_to_dict(msg), ensure_ascii=False)


def deserialize_message(raw: str) -> Message:
    """Parse a JSON string into a validated Message.

    Args:
        raw: JSON string to parse.

    Returns:
        Validated Message instance.

    Raises:
        ValueError: if JSON is invalid or validation fails.
    """
    data = json.loads(raw)
    return validate_message(data)


def _message_to_dict(msg: Message) -> dict:
    """Convert a Message to a plain dict for JSON serialization."""
    return {
        "type": msg.type.value,
        "payload": msg.payload,
        "timestamp": msg.timestamp,
        "player_id": msg.player_id,
    }


# ── Validation ────────────────────────────────────────────────────────────

def validate_message(raw: dict) -> Message:
    """Validate and coerce a raw dict into a Message.

    Checks:
        1. `raw` is a dict
        2. `type` field exists and is a valid MsgType string
        3. `timestamp` field exists

    Args:
        raw: Raw dict (typically from JSON.parse or FastAPI receive_json).

    Returns:
        Validated Message instance.

    Raises:
        ValueError: if any validation check fails.
    """
    if not isinstance(raw, dict):
        raise ValueError(
            f"Message must be a dict, got {type(raw).__name__}"
        )

    msg_type_str = raw.get("type")
    if msg_type_str not in VALID_MSG_TYPES:
        raise ValueError(
            f"Unknown message type: {msg_type_str!r}. "
            f"Valid types: {sorted(VALID_MSG_TYPES)}"
        )

    if "timestamp" not in raw:
        raise ValueError("Message missing required field: timestamp")

    return Message(
        type=MsgType(msg_type_str),
        payload=raw.get("payload", {}),
        timestamp=float(raw["timestamp"]),
        player_id=raw.get("player_id"),
    )
