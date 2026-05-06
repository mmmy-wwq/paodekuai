import type { Card as CardType } from '../types/card'
import { Suit, cardToString } from '../types/card'
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
      <span className="card__content">{cardToString(card)}</span>
    </div>
  )
}

export default Card
