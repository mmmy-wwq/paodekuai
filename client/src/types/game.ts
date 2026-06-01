/**
 * Game state type definitions for 跑得快 (Pao De Kuai).
 *
 * Mirrors server/models.py Pydantic models AND server/game_engine/state_machine.py
 * get_state() output exactly. All field names use snake_case to match the JSON
 * payload sent by the server — NO camelCase mapping layer.
 */

import type { Card } from './card';

// ---------------------------------------------------------------------------
// Game Phase
// ---------------------------------------------------------------------------

/** Explicit game state-machine phases. */
export type GamePhase =
  | 'WAITING'
  | 'DEALING'
  | 'DECLARATION'
  | 'PLAYING'
  | 'ROUND_END';

// ---------------------------------------------------------------------------
// Player
// ---------------------------------------------------------------------------

/** Snapshot of a single player's state (as sent by server). */
export interface PlayerState {
  player_id: string;
  name: string;
  hand: Card[];
  score: number;
  remaining_cards: number;
  is_declarer: boolean;
  /** Only present during DECLARATION phase: player's choice (null = not yet chosen). */
  declaration?: boolean | null;
}

// ---------------------------------------------------------------------------
// Game
// ---------------------------------------------------------------------------

/** Full game state broadcast to all clients (STATE_SYNC payload).
 *
 *  All keys match the server's get_state() dict exactly.
 */
export interface GameState {
  room_id: string;
  players: PlayerState[];
  phase: GamePhase;
  /** The player_id whose turn it is (string, NOT index). Only set in PLAYING. */
  current_turn: string | null;
  /** The index of the current-turn player. Only set in PLAYING. */
  current_turn_index: number | null;
  /** The last valid play on the table, or null for free play. */
  last_play?: CardPlay | null;
  consecutive_passes: number;
  turn_number: number;
  round_number: number;
  deck_size: number;
  player_count: number;
  /** The declarer (包牌) player_id, or null if no one declared. */
  declarer_id?: string | null;
  /** During DECLARATION: the player_id whose turn it is to choose. */
  declaration_turn_player_id: string | null;

  /** Historical scores keyed by player name (persisted across sessions). */
  historical_scores?: Record<string, number>;

  // ── Personal fields (only in per-player STATE_SYNC) ──────────────
  /** Your own hand cards (only sent to you via _broadcast_individual_hands). */
  your_hand?: Card[];
  /** Your assigned player_id. */
  your_player_id?: string;

  /** Ready system: list of player_ids who have clicked ready. */
  ready_players?: string[];
  /** Ready system: true when all players are ready. */
  all_ready?: boolean;

  /** Pre-game: max players for the room. */
  max_players?: number;
  /** Room code (pre-game lobby). */
  code?: string;

  /** Legacy support: some messages include success flag. */
  success?: boolean;

  /** Per-player last play: player_id -> last valid CardPlay they made, or null */
  player_last_plays?: Record<string, CardPlay | null>;
  /** Per-player last action: player_id -> 'play' | 'pass' | null */
  player_last_actions?: Record<string, string | null>;

  /** Turn countdown remaining seconds (server-side timer). */
  remaining_time?: number;

  /** When all players pass, this is set to the last passer's player_id
   *  so the client can still announce "过" even though player_last_actions
   *  is cleared for UI cleanliness. */
  all_pass_last_player?: string | null;

  /** Server-driven announcement sound path.
   *  e.g. "dad/single_KING", "mom/pass", "sister/declare_yes"
   *  Client plays this directly — no pattern detection needed. */
  announcement_sound?: string;

  /** Reconnection token. Store in localStorage, pass as ?token= on reconnect. */
  reconnect_token?: string;

  /** Player IDs currently in auto-play (托管) mode. */
  auto_play_players?: string[];
}

// ---------------------------------------------------------------------------
// Play
// ---------------------------------------------------------------------------

/** A validated play — what cards, what pattern, by whom. */
export interface CardPlay {
  cards: Card[];
  pattern_type: string;
  pattern_display: string;
  player_id: string;
}

/** Incoming play request from a client. */
export interface PlayRequest {
  player_id: string;
  cards: Card[];
}

/** Server response to a play request. */
export interface PlayResponse {
  valid: boolean;
  error?: string;
  must_play?: boolean;
  forced_cards?: Card[];
}

// ---------------------------------------------------------------------------
// Round Result
// ---------------------------------------------------------------------------

/** Result of a completed round. */
export interface RoundResult {
  winner_id: string;
  scores: Record<string, number>;
  /** Per-player score changes this round (delta). */
  score_deltas?: Record<string, number>;
  is_declaration_game: boolean;
  declarer_id?: string | null;
  breaker_id?: string | null;
}

// ---------------------------------------------------------------------------
// Room
// ---------------------------------------------------------------------------

/** Room info displayed before game starts. */
export interface RoomInfo {
  room_id: string;
  player_count: number;
  max_players: number;
  players: { id: string; name: string }[];
}
