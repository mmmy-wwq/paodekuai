import { useMemo, useRef, useCallback } from 'react'
import type { Card as CardType } from '../types/card'
import { compareCards } from '../types/card'
import Card from './Card'
import './HandArea.css'

interface HandAreaProps {
  cards: CardType[]
  selectedIds: Set<number>
  onToggleSelect: (index: number) => void
  disabled?: boolean
}

/** Player's hand area — cards displayed in an overlapping row at screen bottom.
 *  Supports touch-drag to select multiple cards at once. */
function HandArea({ cards, selectedIds, onToggleSelect, disabled = false }: HandAreaProps) {
  const sorted = useMemo(() => [...cards].sort(compareCards), [cards])
  const draggingRef = useRef(false)
  const seenRef = useRef<Set<number>>(new Set())
  const cardsContainerRef = useRef<HTMLDivElement>(null)

  /** Map a touch point to a card index, or -1 if not on any card. */
  const findCardIndex = useCallback((clientX: number, clientY: number): number => {
    const el = document.elementFromPoint(clientX, clientY)
    if (!el) return -1
    const cardEl = (el as HTMLElement).closest('.card')
    if (!cardEl || !cardsContainerRef.current) return -1
    return Array.from(cardsContainerRef.current.children).indexOf(cardEl)
  }, [])

  const handleTouchStart = useCallback(() => {
    draggingRef.current = true
    seenRef.current.clear()
  }, [])

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!draggingRef.current) return
    // Prevent default to avoid scroll / pull-to-refresh while selecting cards
    e.preventDefault()

    const touch = e.touches[0]
    const index = findCardIndex(touch.clientX, touch.clientY)
    if (index < 0 || index >= sorted.length) return
    if (seenRef.current.has(index)) return

    seenRef.current.add(index)
    // Toggle each card encountered during drag — lifts unselected, drops selected
    onToggleSelect(index)
  }, [sorted.length, onToggleSelect, findCardIndex])

  const handleTouchEnd = useCallback(() => {
    draggingRef.current = false
  }, [])

  if (sorted.length === 0) {
    return (
      <div className="hand-area hand-area--empty">
        <p className="hand-area__empty-text">暂无手牌</p>
      </div>
    )
  }

  return (
    <div className="hand-area">
      <div
        className="hand-area__cards"
        ref={cardsContainerRef}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {sorted.map((card, index) => (
          <Card
            key={`${card.suit}-${card.rank}-${index}`}
            card={card}
            selected={selectedIds.has(index)}
            onClick={() => onToggleSelect(index)}
            size="sm"
            disabled={disabled}
          />
        ))}
      </div>
    </div>
  )
}

export default HandArea
