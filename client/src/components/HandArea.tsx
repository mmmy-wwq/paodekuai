import { useMemo } from 'react'
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

/** Player's hand area — cards displayed in an overlapping row at screen bottom. */
function HandArea({ cards, selectedIds, onToggleSelect, disabled = false }: HandAreaProps) {
  const sorted = useMemo(() => [...cards].sort(compareCards), [cards])

  if (sorted.length === 0) {
    return (
      <div className="hand-area hand-area--empty">
        <p className="hand-area__empty-text">暂无手牌</p>
      </div>
    )
  }

  return (
    <div className="hand-area">
      <div className="hand-area__cards">
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
