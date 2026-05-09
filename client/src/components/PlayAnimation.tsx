import { useEffect, useState, useRef } from 'react'
import type { Card as CardType } from '../types/card'
import { RANK_DISPLAY, SUIT_DISPLAY, Suit } from '../types/card'
import './PlayAnimation.css'

interface PlayAnimationProps {
  /** The cards being played */
  cards: CardType[]
  /** Player name who played */
  playerName: string
  /** Target position class for shrink animation */
  targetPosition: string // 'me' | 'top' | 'right' | 'left' | 'top-left' | 'top-right'
  /** Callback when entire animation finishes */
  onDone: () => void
}

/** Map position name to CSS transform for shrink phase */
function getShrinkTarget(pos: string): { x: string; y: string } {
  switch (pos) {
    case 'me': return { x: '0vw', y: '20vh' }
    case 'top': return { x: '0vw', y: '-32vh' }
    case 'right': return { x: '20vw', y: '0vh' }
    case 'left': return { x: '-20vw', y: '0vh' }
    case 'top-right': return { x: '12vw', y: '-28vh' }
    case 'top-left': return { x: '-12vw', y: '-28vh' }
    default: return { x: '0vw', y: '-32vh' }
  }
}

/**
 * Two-phase play animation:
 *   Phase 1: Cards fly to center, display 3s with player name
 *   Phase 2: Cards shrink and move to player's position area
 */
function PlayAnimation({ cards, playerName, targetPosition, onDone }: PlayAnimationProps) {
  const [phase, setPhase] = useState<'fly-in' | 'hold' | 'shrink'>('fly-in')
  const doneRef = useRef(false)
  const target = getShrinkTarget(targetPosition)

  useEffect(() => {
    // Phase 1: fly-in (0.4s) → hold (3s) → Phase 2: shrink (0.5s)
    const t1 = setTimeout(() => setPhase('hold'), 400)
    const t2 = setTimeout(() => setPhase('shrink'), 3400)
    const t3 = setTimeout(() => {
      if (!doneRef.current) {
        doneRef.current = true
        onDone()
      }
    }, 4000)

    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(t3)
    }
  }, [onDone])

  return (
    <div className={`play-anim ${phase === 'shrink' ? 'play-anim--shrinking' : ''}`}>
      {/* Center display area */}
      <div className={`play-anim__center ${phase === 'fly-in' ? 'play-anim__center--entering' : ''} ${phase === 'shrink' ? 'play-anim__center--shrinking' : ''}`}
        style={phase === 'shrink' ? {
          '--shrink-x': target.x,
          '--shrink-y': target.y,
          '--shrink-scale': '0.35',
        } as React.CSSProperties : undefined}
      >
        <div className="play-anim__label">{playerName} 出牌</div>
        <div className="play-anim__cards">
          {cards.map((card, i) => {
            const isRed = card.suit === Suit.HEART || card.suit === Suit.DIAMOND
            return (
              <div
                key={i}
                className={`play-anim__card${isRed ? ' play-anim__card--red' : ''}`}
                style={{
                  transform: `rotate(${(i - (cards.length - 1) / 2) * 3}deg)`,
                  animationDelay: `${phase === 'fly-in' ? i * 60 : 0}ms`,
                }}
              >
                <span className="play-anim__card-rank">{RANK_DISPLAY[card.rank]}</span>
                <span className="play-anim__card-suit">{SUIT_DISPLAY[card.suit]}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default PlayAnimation
