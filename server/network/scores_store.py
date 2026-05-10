from __future__ import annotations

"""
Persistent score storage for player historical scores.

Scores are stored in a JSON file (scores.json) keyed by player name.
Each entry tracks the cumulative score across all game sessions.
"""

import json
import os
from typing import Dict

SCORES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "scores.json")


def _load_scores() -> Dict[str, int]:
    """Load all historical scores from disk."""
    if not os.path.isfile(SCORES_FILE):
        return {}
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_scores(scores: Dict[str, int]) -> None:
    """Write all historical scores to disk."""
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


def get_all_scores() -> Dict[str, int]:
    """Return a copy of all historical scores."""
    return dict(_load_scores())


def add_score(player_name: str, delta: int) -> int:
    """Add delta to a player's historical score and return the new total."""
    scores = _load_scores()
    current = scores.get(player_name, 0)
    new_total = current + delta
    scores[player_name] = new_total
    _save_scores(scores)
    return new_total


def reset_scores() -> None:
    """Clear all historical scores (for testing)."""
    _save_scores({})
