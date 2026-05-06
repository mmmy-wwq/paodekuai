/**
 * WebSocket message protocol for 跑得快 (Pao De Kuai).
 *
 * Defines the message contract between client and server.
 * MsgType string values MUST match the Python MsgType enum exactly.
 */

import type { Card } from './card';

// ── MsgType ────────────────────────────────────────────────────────────────

/** WebSocket message types. String values match Python MsgType enum exactly. */
export enum MsgType {
  JOIN = 'JOIN',
  LEAVE = 'LEAVE',
  START_GAME = 'START_GAME',
  DECLARE = 'DECLARE',
  PLAY = 'PLAY',
  PASS = 'PASS',
  STATE_SYNC = 'STATE_SYNC',
  ERROR = 'ERROR',
  GAME_START = 'GAME_START',
  ROUND_END = 'ROUND_END',
  PING = 'PING',
  PONG = 'PONG',
  PLAYER_JOINED = 'PLAYER_JOINED',
  PLAYER_LEFT = 'PLAYER_LEFT',
  READY = 'READY',
}

// ── Message envelope ───────────────────────────────────────────────────────

/** Standard WebSocket message envelope. */
export interface Message<T = any> {
  /** Message type */
  type: MsgType;
  /** Message payload — type depends on MsgType */
  payload: T;
  /** Unix timestamp of message creation */
  timestamp: number;
  /** Optional player identifier */
  playerId?: string;
}

// ── Payload type definitions ──────────────────────────────────────────────

/** Payload for JOIN message. */
export interface JoinPayload {
  name: string;
  roomId: string;
}

/** Payload for PLAY message. */
export interface PlayPayload {
  cards: Card[];
}

/** Payload for DECLARE message. */
export interface DeclarePayload {
  isDeclaring: boolean;
}

/** Payload for ERROR message. */
export interface ErrorPayload {
  code: string;
  message: string;
}

/** Payload for STATE_SYNC message. */
export interface StateSyncPayload {
  gameState: import('./game').GameState;
}

/** Payload for ROUND_END message. */
export interface RoundEndPayload {
  result: import('./game').RoundResult;
}

// ── Serialization helpers ──────────────────────────────────────────────────

/**
 * Serialize a message for WebSocket transmission.
 * Returns a JSON string.
 */
export function serializeMessage(type: MsgType, payload: any): string {
  return JSON.stringify({
    type,
    payload,
    timestamp: Date.now() / 1000,
  });
}

/**
 * Deserialize a raw WebSocket message string into a typed Message.
 * Performs basic type assertion (application code should validate further).
 */
export function deserializeMessage<T = any>(raw: string): Message<T> {
  const parsed = JSON.parse(raw) as Message<T>;

  // Basic structural validation
  if (typeof parsed.type !== 'string' || !Object.values(MsgType).includes(parsed.type)) {
    throw new Error(`Unknown message type: ${parsed.type}`);
  }
  if (typeof parsed.timestamp !== 'number') {
    throw new Error('Message missing required field: timestamp');
  }

  return parsed;
}
