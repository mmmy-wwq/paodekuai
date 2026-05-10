"""Server configuration loaded from environment variables.

All settings have sensible defaults so the server runs out of the box.
Tweak via environment variables for production or ngrok deployment.
"""

from __future__ import annotations

import os


# -- Server network ------------------------------------------------------------------

HOST = os.environ.get("HOST", "127.0.0.1")
"""Host address the server binds to.

``127.0.0.1`` (localhost only) by default.
Set to ``0.0.0.0`` when running behind ngrok so the tunnel can reach the server.
"""

PORT = int(os.environ.get("PORT", "8000"))
"""TCP port the server listens on. Default ``8000``."""

# -- CORS ----------------------------------------------------------------------------

CORS_ORIGINS: list[str] = []
"""List of allowed origins for cross-origin requests.

Parsed from the comma-separated ``CORS_ORIGINS`` environment variable.
Defaults to ``["*"]`` (allow all origins) when the variable is not set.
"""

_cors_raw = os.environ.get("CORS_ORIGINS", "*")
CORS_ORIGINS = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

# -- Static files --------------------------------------------------------------------

_CLIENT_DIST = os.environ.get(
    "CLIENT_DIST",
    os.path.join(os.path.dirname(__file__), "..", "client", "dist"),
)
"""Absolute path to the built client SPA directory.

Defaults to ``<project-root>/client/dist/``.
Set this if the client build output lives elsewhere.
"""


def client_dist_exists() -> bool:
    """Return ``True`` when the client distribution directory is present."""
    return os.path.isdir(_CLIENT_DIST)


def client_dist_path() -> str:
    """Return the absolute path to the client distribution directory."""
    return os.path.abspath(_CLIENT_DIST)
