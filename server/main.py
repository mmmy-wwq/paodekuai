from __future__ import annotations

"""Pao De Kuai card game server.
 
FastAPI application serving the SPA client and WebSocket game endpoint.
All game logic is delegated to the GameServer which coordinates
RoomManager and GameStateManager.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, Response

from server.config import CORS_ORIGINS, client_dist_exists, client_dist_path
from server.network.game_server import GameServer
from server.network.scores_store import get_all_scores, add_score

CLIENT_DIST = client_dist_path()

_MIME_MAP = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".txt": "text/plain",
    ".webmanifest": "application/manifest+json",
    ".woff2": "font/woff2",
}


# ── Lifespan: per-process singleton ─────────────────────────────────────────

game_server: GameServer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the game server on startup."""
    global game_server
    game_server = GameServer()
    yield
    # Cleanup on shutdown (connections close automatically)


app = FastAPI(title="跑得快", lifespan=lifespan)

# ── CORS middleware (required for ngrok / cross-origin access) ──────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Scores API (preset player historical scores) ──────────────────────────


@app.get("/api/scores")
async def api_get_scores():
    """Return all historical scores keyed by player name."""
    return get_all_scores()


@app.post("/api/scores/{player_name}")
async def api_add_score(player_name: str, delta: int = 0):
    """Add delta to a player's historical score. Used when game round ends."""
    new_total = add_score(player_name, delta)
    return {"player_name": player_name, "delta": delta, "total": new_total}


# ── WebSocket endpoint (must be before catch-all route) ─────────────────────


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    name: str = Query(default="Player"),
    players: int = Query(default=4, ge=2, le=4),
    pid: str = Query(default=""),
):
    """WebSocket game endpoint."""
    player_id = await game_server.handle_connection(websocket, room_id, name, player_count=players, reconnect_id=pid)
    if player_id is None:
        return
    try:
        while True:
            raw_data = await websocket.receive_json()
            await game_server.handle_message(websocket, player_id, raw_data)
    except WebSocketDisconnect:
        await game_server.handle_disconnect(websocket)


# ── Debug endpoint ───────────────────────────────────────────────────────────

@app.get("/debug/room/{room_id}")
async def debug_room(room_id: str):
    """Return raw room state for debugging."""
    room = await game_server._rm.get_room(room_id)
    if room is None:
        return {"error": "Room not found"}
    return {
        "id": room.id,
        "max_players": room.max_players,
        "players": {pid: {"name": d["name"]} for pid, d in room.players.items()},
        "ready_players": list(room.ready_players),
        "gsm_exists": room.game_state_manager is not None,
        "sockets": list(game_server._room_sockets.get(room_id, {}).keys()),
    }

# ── Catch-all static file serve (with explicit MIME types for Windows) ──────


@app.get("/{file_path:path}")
async def serve_static(file_path: str, request: Request):
    """Serve any file from the client dist directory with correct MIME type."""
    # Root or SPA fallback → index.html
    if not file_path or file_path.endswith("/"):
        file_path = "index.html"

    safe_path = os.path.normpath(os.path.join(CLIENT_DIST, file_path))
    # Prevent directory traversal
    if not safe_path.startswith(os.path.abspath(CLIENT_DIST)):
        return Response("Not found", status_code=404)

    if not os.path.isfile(safe_path):
        # SPA fallback: only for routes without a file extension
        # Asset requests (js/css/png etc.) get 404 to avoid MIME mismatch
        if "." in os.path.basename(file_path):
            return Response("Not found", status_code=404)
        safe_path = os.path.normpath(os.path.join(CLIENT_DIST, "index.html"))

    _, ext = os.path.splitext(safe_path)
    media_type = _MIME_MAP.get(ext, "application/octet-stream")
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    return FileResponse(safe_path, media_type=media_type, headers=headers)
