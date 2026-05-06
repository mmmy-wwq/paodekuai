import { useEffect, useRef, useCallback } from 'react';
import type { Card } from '../types/card';
import {
  MsgType,
  serializeMessage,
  deserializeMessage,
} from '../types/protocol';
import type {
  Message,
  ErrorPayload,
} from '../types/protocol';
import type { GameState, RoundResult } from '../types/game';
import { useGameReducer } from './useGameReducer';

/** Get WebSocket base URL from env or auto-detect from page origin. */
function getWsBase(): string {
  const envUrl = import.meta.env.VITE_WS_URL as string | undefined;
  if (typeof envUrl === 'string' && envUrl.length > 0) return envUrl;
  if (typeof window !== 'undefined') {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}`;
  }
  return 'ws://localhost:8000';
}

const WS_BASE = getWsBase();

/** Reconnect timing constants. */
const INITIAL_RECONNECT_DELAY = 1_000;
const MAX_RECONNECT_DELAY = 30_000;
const RECONNECT_MULTIPLIER = 2;

/**
 * WebSocket hook for 跑得快 game communication.
 *
 * Manages WebSocket lifecycle: connect, JOIN, message dispatch,
 * PING→PONG heartbeat, and exponential-backoff reconnection.
 *
 * @param roomId  Room identifier for WebSocket path
 * @param playerName  Display name sent in JOIN payload
 * @param playerCount  Maximum players for the room (2-4), sent as query param
 * @returns  { gameState, sendPlay, sendPass, sendDeclare, isConnected, dispatch }
 */
export function useGameWebSocket(roomId: string, playerName: string, playerCount: number = 4) {
  const [state, dispatch] = useGameReducer();

  // ── Refs for mutable values outside React lifecycle ──
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);
  const reconnectTimerRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  // ── Send helpers ────────────────────────────────────────────────────

  /** Send a typed message over the current WebSocket (if open). */
  const sendMessage = useCallback(
    (type: MsgType, payload: unknown) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(serializeMessage(type, payload));
      }
    },
    [],
  );

  /** Send PLAY with selected cards. */
  const sendPlay = useCallback(
    (cards: Card[]) => {
      sendMessage(MsgType.PLAY, { cards });
    },
    [sendMessage],
  );

  /** Send PASS (no cards played this turn). */
  const sendPass = useCallback(() => {
    sendMessage(MsgType.PASS, {});
  }, [sendMessage]);

  /** Send DECLARE (declaration phase choice). */
  const sendDeclare = useCallback(
    (isDeclaring: boolean) => {
      console.log('[WS] sendDeclare isDeclaring=', isDeclaring, 'payload=', { isDeclaring })
      sendMessage(MsgType.DECLARE, { isDeclaring });
    },
    [sendMessage],
  );

  /** Send READY to confirm readiness. */
  const sendReady = useCallback(() => {
    sendMessage(MsgType.READY, {});
  }, [sendMessage]);

  // ── Connection management ───────────────────────────────────────────

  /** Retrieve stored PID for this player name, if any. */
  function getStoredPid(name: string): string {
    try {
      return localStorage.getItem(`pdq_pid_${name}`) || ''
    } catch { return '' }
  }

  /** Save PID for this player name so they can reconnect. */
  function saveStoredPid(name: string, pid: string): void {
    try {
      localStorage.setItem(`pdq_pid_${name}`, pid)
    } catch { /* ignore quota errors */ }
  }

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Don't connect without a player name
    if (!playerName || !roomId) return;

    // Close any stale connection
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }

    const storedPid = getStoredPid(playerName)
    const params = new URLSearchParams({ name: playerName, players: String(playerCount) })
    if (storedPid) params.append('pid', storedPid)
    const ws = new WebSocket(`${WS_BASE}/ws/${roomId}?${params}`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      dispatch({ type: 'SET_CONNECTION', payload: true });
      // Reset backoff on successful connection
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
      // Send JOIN
      sendMessage(MsgType.JOIN, { name: playerName, roomId });
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const msg = deserializeMessage(event.data) as Message;

        switch (msg.type) {
          case MsgType.STATE_SYNC: {
            const gs = msg.payload as GameState;
            console.log('[WS] STATE_SYNC received, phase=', gs.phase, 'your_player_id=', gs.your_player_id)
            // Store player PID for reconnection
            if (gs.your_player_id) {
              saveStoredPid(playerName, gs.your_player_id)
            }
            dispatch({ type: 'SET_GAME_STATE', payload: gs });
            break;
          }

          case MsgType.ERROR: {
            const payload = msg.payload as ErrorPayload;
            dispatch({ type: 'SET_ERROR', payload: payload.message });
            break;
          }

          case MsgType.ROUND_END: {
            // Store round result for display; server also follows up with STATE_SYNC
            dispatch({ type: 'SET_ROUND_RESULT', payload: msg.payload as RoundResult });
            break;
          }

          case MsgType.PING:
            sendMessage(MsgType.PONG, {});
            break;
        }
      } catch {
        // Ignore malformed messages (server will re-sync on next STATE_SYNC)
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;

      dispatch({ type: 'SET_CONNECTION', payload: false });

      // Exponential backoff: 1s → 2s → 4s → 8s → ... → max 30s
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(
        delay * RECONNECT_MULTIPLIER,
        MAX_RECONNECT_DELAY,
      );

      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, delay);
    };

    // onerror triggers onclose — no separate handler needed
  }, [roomId, playerName, playerCount, sendMessage, dispatch]);

  // ── Mount / unmount lifecycle ───────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;

      // Clear pending reconnect
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      // Close WebSocket without triggering reconnect
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // ── Public API ──────────────────────────────────────────────────────

  return {
    gameState: state.gameState,
    selectedCardIds: state.selectedCardIds,
    roundResult: state.roundResult,
    error: state.error,
    sendPlay,
    sendPass,
    sendDeclare,
    sendReady,
    isConnected: state.isConnected,
    dispatch,
  } as const;
}
