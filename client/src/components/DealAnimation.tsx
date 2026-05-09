import { useEffect, useRef, useMemo } from 'react'
import type { DealEvent } from '../hooks/useDealAnimation'
import './DealAnimation.css'

interface DealAnimationProps {
  myCardCount: number
  opponentCounts: number[]
  currentIndex: number
  totalCards: number
  state: 'idle' | 'dealing' | 'done'
  onDone: () => void
}

function getTargetTranslate(target: 'me' | number): { x: string; y: string } {
  if (target === 'me') {
    return { x: '0vw', y: '38vh' }
  }
  const idx = target as number
  const xOffset = (idx - 1) * 28
  return { x: `${xOffset}vw`, y: '-32vh' }
}

function getCardBackGradient(index: number): string {
  const backs = [
    'linear-gradient(135deg, #5a1a1a, #3d1111)',
    'linear-gradient(135deg, #1a3a5c, #0f2440)',
    'linear-gradient(135deg, #2a5a2a, #1a3d1a)',
  ]
  return backs[index % backs.length] || backs[0]
}

function DealAnimation({
  myCardCount,
  opponentCounts,
  currentIndex,
  totalCards,
  state,
  onDone,
}: DealAnimationProps) {
  const doneRef = useRef(false)
  const totalPlayers = 1 + opponentCounts.length

  const order = useMemo(() => {
    const result: DealEvent[] = []
    const maxCards = Math.max(myCardCount, ...opponentCounts)
    for (let round = 0; round < maxCards; round++) {
      for (let p = 0; p < totalPlayers; p++) {
        const count = p === 0 ? myCardCount : opponentCounts[p - 1]
        if (round < count) {
          result.push(p === 0 ? { target: 'me', index: 0 } : { target: (p - 1) as number, index: 0 })
        }
      }
    }
    return result
  }, [myCardCount, opponentCounts, totalPlayers])

  useEffect(() => {
    if (state !== 'dealing' || doneRef.current) return
    if (totalCards === 0) {
      onDone()
      return
    }
    const totalDuration = totalCards * 80 + 600
    const timer = setTimeout(() => {
      if (!doneRef.current) {
        doneRef.current = true
        onDone()
      }
    }, totalDuration)
    return () => clearTimeout(timer)
  }, [state, totalCards, onDone])

  useEffect(() => {
    if (state === 'idle') doneRef.current = false
  }, [state])

  if (state === 'idle') return null

  const remaining = Math.max(0, totalCards - currentIndex)
  const deckCardsToShow = Math.min(remaining, 12)
  const staggerMs = 80

  return (
    <div className={`deal-animation${state === 'done' ? ' deal-animation--done' : ''}`}>
      {/* Center deck pile */}
      <div className="deal-animation__deck">
        {Array.from({ length: Math.min(deckCardsToShow, 6) }, (_, i) => (
          <div
            key={`d-${i}`}
            className="deal-animation__deck-card"
            style={{
              transform: `translateY(${-i * 0.8}px) rotate(${(i - 3) * 0.6}deg)`,
              zIndex: 10 - i,
            }}
          />
        ))}
      </div>

      {/* Flying cards — all rendered upfront with staggered animation delays */}
      {order.map((event, i) => {
        const pos = getTargetTranslate(event.target)
        const delay = i * staggerMs
        const isMe = event.target === 'me'

        return (
          <div
            key={i}
            className="deal-animation__fly-card"
            style={{
              '--end-x': pos.x,
              '--end-y': pos.y,
              '--fly-delay': `${delay}ms`,
            } as React.CSSProperties}
          >
            <div className={`deal-animation__fly-card-inner${isMe ? '' : ' deal-animation__fly-card-inner--back'}`}>
              {isMe ? (
                <>
                  <span className="deal-animation__fly-rank">A</span>
                  <span className="deal-animation__fly-suit">♠</span>
                </>
              ) : (
                <div
                  className="deal-animation__fly-back"
                  style={{ background: getCardBackGradient(event.target as number) }}
                />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default DealAnimation
