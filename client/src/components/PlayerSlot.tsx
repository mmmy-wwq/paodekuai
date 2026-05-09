import type { CardPlay } from '../types/game'
import type { Card as CardType } from '../types/card'
import { RANK_DISPLAY, SUIT_DISPLAY, Suit } from '../types/card'
import './PlayerSlot.css'

interface PlayerSlotProps {
  name: string
  cardCount: number
  isActive: boolean
  isDeclarer: boolean
  position: string // 'me' | 'top' | 'right' | 'left' | 'top-left' | 'top-right'
  lastPlay?: CardPlay | null
  lastAction?: string | null // 'play' | 'pass'
  isMyTurn?: boolean
  countdown?: number
}

/** Mini-card used inside opponent last-play display. */
function MiniCard({ card }: { card: CardType }) {
  const isRed = card.suit === Suit.HEART || card.suit === Suit.DIAMOND
  return (
    <div className={`ps-mini-card${isRed ? ' ps-mini-card--red' : ''}`}>
      <span className="ps-mini-card__rank">{RANK_DISPLAY[card.rank]}</span>
      <span className="ps-mini-card__suit">{SUIT_DISPLAY[card.suit]}</span>
    </div>
  )
}

/** Renders a single player's slot: name, card count (1 back + number), play area. */
function PlayerSlot({ name, cardCount, isActive, isDeclarer, position, lastPlay, lastAction, isMyTurn = false, countdown }: PlayerSlotProps) {
  // Layout direction: play area should face the table center
  const layoutClass = 
    position === 'me' ? 'ps-layout--col-rev' :
    position === 'left' ? 'ps-layout--row' :
    position === 'right' ? 'ps-layout--row-rev' :
    'ps-layout--col' // top, top-left, top-right

  // Determine play area content
  let playContent: React.ReactNode = null
  if (lastPlay && lastAction === 'play') {
    playContent = (
      <div className="ps-play-cards">
        {lastPlay.cards.map((card, i) => (
          <MiniCard key={i} card={card} />
        ))}
      </div>
    )
  } else if (lastAction === 'pass') {
    playContent = <span className="ps-play-pass">过</span>
  } else if (position === 'me' && isMyTurn) {
    playContent = <span className="ps-play-prompt">请出牌</span>
  }

  return (
    <div className={`player-slot player-slot--${position} ${layoutClass}${isActive ? ' player-slot--active' : ''}`}>
      {/* Header: name + card count badges */}
      <div className="ps-header">
        <span className="ps-name">
          {name}
          {isDeclarer && <span className="ps-declarer"> 🏆</span>}
        </span>
        {/* Card count: card back with number */}
        {position !== 'me' && cardCount > 0 && (
          <span className="ps-card-count">
            <span className="ps-card-back-icon">
              <span className="ps-card-back-num">{cardCount}</span>
            </span>
          </span>
        )}
        {position !== 'me' && cardCount === 0 && (
          <span className="ps-card-count ps-card-count--empty">出完</span>
        )}
      </div>

      {/* Per-player play area */}
      <div className="ps-play-area">
        {playContent}
        {/* Countdown timer for active player */}
        {isActive && countdown !== undefined && countdown > 0 && (
          <span className="ps-countdown">{countdown}s</span>
        )}
      </div>
    </div>
  )
}

export { MiniCard }
export default PlayerSlot
