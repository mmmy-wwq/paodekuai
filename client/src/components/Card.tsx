import type { Card as CardType } from '../types/card'
import { Suit, RANK_DISPLAY, SUIT_DISPLAY, cardToString } from '../types/card'
import './Card.css'

interface CardProps {
  card: CardType
  selected?: boolean
  onClick?: () => void
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}

/** Single playing card component. */
function Card({ card, selected = false, onClick, size = 'sm', disabled = false }: CardProps) {
  const suitColor = card.suit === Suit.HEART || card.suit === Suit.DIAMOND ? 'red' : 'black'

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!disabled && onClick) {
      onClick()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      e.stopPropagation()
      if (!disabled && onClick) {
        onClick()
      }
    }
  }

  return (
    <div
      className={`card card--${size} card--${suitColor}${selected ? ' card--selected' : ''}${disabled ? ' card--disabled' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={cardToString(card)}
      aria-selected={selected}
      aria-disabled={disabled}
    >
      {/* Four-corner cloud motifs (四角云纹) */}
      <span className="card__corner card__corner--tl" aria-hidden="true" />
      <span className="card__corner card__corner--tr" aria-hidden="true" />
      <span className="card__corner card__corner--bl" aria-hidden="true" />
      <span className="card__corner card__corner--br" aria-hidden="true" />

      <div className="card__content">
        <span className="card__rank">{RANK_DISPLAY[card.rank]}</span>
        <span className="card__suit">{SUIT_DISPLAY[card.suit]}</span>
      </div>
    </div>
  )
}

export default Card
