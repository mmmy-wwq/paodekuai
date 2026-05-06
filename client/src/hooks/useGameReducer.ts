import { useReducer } from 'react';
import type { GameState, RoundResult } from '../types/game';

/**
 * Local game state managed by useReducer.
 * selectedCardIds uses Set<number> for O(1) toggle and membership checks.
 */
export interface GameReducerState {
  gameState: GameState | null;
  selectedCardIds: Set<number>;
  roundResult: RoundResult | null;
  error: string | null;
  isConnected: boolean;
}

export type GameReducerAction =
  | { type: 'SET_GAME_STATE'; payload: GameState }
  | { type: 'SELECT_CARD'; payload: number }
  | { type: 'DESELECT_CARD'; payload: number }
  | { type: 'CLEAR_SELECTION' }
  | { type: 'SET_ROUND_RESULT'; payload: RoundResult }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_CONNECTION'; payload: boolean };

function gameReducer(
  state: GameReducerState,
  action: GameReducerAction,
): GameReducerState {
  switch (action.type) {
    case 'SET_GAME_STATE':
      return { ...state, gameState: action.payload, roundResult: null };

    case 'SELECT_CARD': {
      const next = new Set(state.selectedCardIds);
      next.add(action.payload);
      return { ...state, selectedCardIds: next };
    }

    case 'DESELECT_CARD': {
      const next = new Set(state.selectedCardIds);
      next.delete(action.payload);
      return { ...state, selectedCardIds: next };
    }

    case 'CLEAR_SELECTION':
      return { ...state, selectedCardIds: new Set() };

    case 'SET_ROUND_RESULT':
      return { ...state, roundResult: action.payload };

    case 'SET_ERROR':
      return { ...state, error: action.payload };

    case 'CLEAR_ERROR':
      return { ...state, error: null };

    case 'SET_CONNECTION':
      return { ...state, isConnected: action.payload };

    default:
      return state;
  }
}

const initialState: GameReducerState = {
  gameState: null,
  selectedCardIds: new Set(),
  roundResult: null,
  error: null,
  isConnected: false,
};

/**
 * Hook wrapping useReducer for game state management.
 * Returns [state, dispatch] — dispatch accepts GameReducerAction.
 */
export function useGameReducer(): [
  GameReducerState,
  React.Dispatch<GameReducerAction>,
] {
  return useReducer(gameReducer, initialState);
}
