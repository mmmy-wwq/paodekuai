import { useState, useRef, useCallback, useEffect } from 'react'

export type DealState = 'idle' | 'dealing' | 'done'

export interface DealEvent {
  /** Index of this card in dealing sequence (0-based) */
  index: number
  /** 'me' for the current player, or opponent index (0-based among opponents) */
  target: 'me' | number
}

interface UseDealAnimationOptions {
  /**
   * Total number of cards being dealt.
   * When > 0, hooks auto-starts.
   */
  totalCards: number
  /**
   * Dealing order array — each entry specifies which player
   * gets the corresponding card. 'me' for the current player,
   * or opponent index (0, 1, 2…).
   */
  order: DealEvent[]
  /**
   * Delay in ms between each card deal (default: 80).
   * Increase for a slower, more dramatic deal.
   */
  cardIntervalMs?: number
}

interface UseDealAnimationResult {
  state: DealState
  /** Index of the next card to be dealt (0-based) */
  currentIndex: number
  /** The total number of cards to deal */
  totalCards: number
  /** Currently visible deal events */
  visibleEvents: DealEvent[]
  /** Manually start the deal */
  start: () => void
  /** Reset to idle */
  reset: () => void
}

/**
 * Manages a sequential card-dealing animation timeline.
 * Auto-starts when `totalCards > 0` on initial render.
 */
export function useDealAnimation({
  totalCards,
  order,
  cardIntervalMs = 80,
}: UseDealAnimationOptions): UseDealAnimationResult {
  const [state, setState] = useState<DealState>(totalCards > 0 ? 'dealing' : 'idle')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [visibleEvents, setVisibleEvents] = useState<DealEvent[]>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasStartedRef = useRef(false)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const scheduleNext = useCallback(
    (fromIndex: number) => {
      if (fromIndex >= order.length) {
        setState('done')
        return
      }

      timerRef.current = setTimeout(() => {
        const event = order[fromIndex]
        setCurrentIndex(fromIndex)
        setVisibleEvents((prev) => [...prev, event])
        scheduleNext(fromIndex + 1)
      }, cardIntervalMs)
    },
    [order, cardIntervalMs],
  )

  const start = useCallback(() => {
    if (hasStartedRef.current) return
    hasStartedRef.current = true
    setState('dealing')
    setCurrentIndex(0)
    setVisibleEvents([])
    scheduleNext(0)
  }, [scheduleNext])

  const reset = useCallback(() => {
    clearTimer()
    hasStartedRef.current = false
    setState('idle')
    setCurrentIndex(0)
    setVisibleEvents([])
  }, [clearTimer])

  // Auto-start on mount if totalCards > 0
  useEffect(() => {
    if (totalCards > 0 && !hasStartedRef.current) {
      start()
    }
    return clearTimer
  }, [totalCards, start, clearTimer])

  return {
    state,
    currentIndex,
    totalCards,
    visibleEvents,
    start,
    reset,
  }
}
