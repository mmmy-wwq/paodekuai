import type { CardPlay } from '../types/game'
import type { Card as CardType } from '../types/card'
import { RANK_DISPLAY, SUIT_DISPLAY, Suit } from '../types/card'
import Avatar from './Avatar'
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
  /** Single-session (单轮) cumulative score */
  sessionScore?: number
  /** Historical (累计) score from persistent storage */
  historicalScore?: number
  /** Remaining hand cards to reveal (ROUND_END) */
  remainingCards?: CardType[]
  /** Declaration phase: player's choice (true=包牌, false=不包, null=未选) */
  declaration?: boolean | null
  /** Declaration phase: this player is currently choosing */
  isDeclarationTurn?: boolean
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

/** Avatar size per position. */
function avatarSizeFor(position: string): number {
  switch (position) {
    case 'me': return 48
    case 'left': case 'right': return 40
    default: return 36 // top, top-left, top-right
  }
}

/** Renders a single player's slot: avatar, name, scores, play area. */
function PlayerSlot({ name, cardCount, isActive, isDeclarer, position, lastPlay, lastAction, isMyTurn = false, countdown, sessionScore, historicalScore, remainingCards, declaration, isDeclarationTurn }: PlayerSlotProps) {
  const avatarSize = avatarSizeFor(position)
  // Layout direction: play area should face the table center
  const layoutClass = 
    position === 'me' ? 'ps-layout--col-rev' :
    position === 'left' ? 'ps-layout--row' :
    position === 'right' ? 'ps-layout--row-rev' :
    'ps-layout--col' // top, top-left, top-right

  const isMe = position === 'me'

  // Determine play area content (normal game or declaration phase)
  let playContent: React.ReactNode = null

  // ── Declaration phase ──────────────────────────────────────
  if (declaration !== undefined) {
    let declText = '⏳ 选择中'
    if (declaration === true) declText = '✅ 包牌'
    else if (declaration === false) declText = '❌ 不包'
    const isDeclTurn = isDeclarationTurn && declaration === null
    playContent = (
      <div className={`ps-decl-status${isDeclTurn ? ' ps-decl-status--turn' : ''}${declaration === true ? ' ps-decl-status--yes' : ''}${declaration === false ? ' ps-decl-status--no' : ''}`}>
        <span className="ps-decl-text">{declText}</span>
      </div>
    )
  } else if (lastAction === 'pass') {
    playContent = <span className="ps-play-pass">过</span>
  } else if (!isActive && lastPlay && lastAction === 'play') {
    playContent = (
      <div className="ps-play-cards">
        {lastPlay.cards.map((card, i) => (
          <MiniCard key={i} card={card} />
        ))}
      </div>
    )
  } else if (isMe && isMyTurn) {
    playContent = <span className="ps-play-prompt">请出牌</span>
  }


  // Helper to render remaining hand cards
  const renderRemainingCards = (className: string) => {
    if (!remainingCards || remainingCards.length === 0) return null
    return (
      <div className={`ps-remaining-cards ${className}`}>
        {remainingCards.slice(0, 12).map((card, i) => (
          <MiniCard key={i} card={card} />
        ))}
        {remainingCards.length > 12 && (
          <span className="ps-remaining-more">+{remainingCards.length - 12}</span>
        )}
      </div>
    )
  }

  const isTop = position === 'top' || position === 'top-left' || position === 'top-right'
  const isSide = position === 'left' || position === 'right'

  return (
    <div className={`player-slot player-slot--${position} ${layoutClass}${isActive ? ' player-slot--active' : ''}`}>
      {/* Header: avatar + name + scores */}
      <div className="ps-header">
        <div className="ps-name-col">
          <Avatar name={name} size={avatarSize} />
          <span className="ps-name">
            {name}
            {isDeclarer && <span className="ps-declarer"> 🏆</span>}
          </span>
          {/* Scores: 单轮 (session) + 累计 (historical) */}
          {(sessionScore !== undefined || historicalScore !== undefined) && (
            <div className="ps-scores">
              {sessionScore !== undefined && (
                <span className="ps-score-item">
                  <span className="ps-score-label">本轮</span>
                  <span className={`ps-score-value ${sessionScore >= 0 ? 'ps-score-value--pos' : 'ps-score-value--neg'}`}>
                    {sessionScore}
                  </span>
                </span>
              )}
              {historicalScore !== undefined && (
                <span className="ps-score-item">
                  <span className="ps-score-label">累计</span>
                  <span className={`ps-score-value ${historicalScore >= 0 ? 'ps-score-value--pos' : 'ps-score-value--neg'}`}>
                    {historicalScore}
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
        {/* Card count: card back with number */}
        {!isMe && cardCount > 0 && (
          <span className="ps-card-count">
            <span className="ps-card-back-icon">
              <span className="ps-card-back-num">{cardCount}</span>
            </span>
          </span>
        )}
        {!isMe && cardCount === 0 && (
          <span className="ps-card-count ps-card-count--empty">出完</span>
        )}
        {/* Top player: remaining cards at right end of header row */}
        {!isMe && isTop && renderRemainingCards('ps-remaining-cards--inline')}
      </div>

      {/* Left/Right: remaining cards floated above the slot */}
      {!isMe && isSide && renderRemainingCards('ps-remaining-cards--above')}

      {/* Per-player play area */}
      <div className="ps-play-area">
        {playContent}
        {/* Countdown timer for active player (top-right of play area) */}
        {isActive && countdown !== undefined && countdown > 0 && (
          <span className="ps-countdown">{countdown}s</span>
        )}
      </div>
    </div>
  )
}

export { MiniCard }
export default PlayerSlot
