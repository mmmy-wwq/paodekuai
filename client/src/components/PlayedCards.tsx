import type { Card as CardType } from '../types/card'
import type { CardPlay } from '../types/game'
import CardComponent from './Card'
import './PlayedCards.css'

interface PlayedCardsProps {
  lastPlay: CardPlay | null
  currentPlay: CardType[] | null
  players: { id: string; name: string }[]
}

/** Displays cards played on the table — last valid play and current pending play. */
function PlayedCards({ lastPlay, currentPlay, players }: PlayedCardsProps) {
  const getPlayerName = (playerId: string): string => {
    const player = players.find((p) => p.id === playerId)
    return player?.name ?? playerId
  }

  return (
    <div className="played-cards">
      {/* Last valid play */}
      {lastPlay ? (
        <div className="played-cards__last">
          <div className="played-cards__label">
            <span className="played-cards__player">
              {getPlayerName(lastPlay.player_id)}
            </span>
            <span className="played-cards__pattern">{lastPlay.pattern_display}</span>
          </div>
          <div className="played-cards__cards">
            {lastPlay.cards.map((card, i) => (
              <CardComponent key={`last-${i}`} card={card} size="md" disabled />
            ))}
          </div>
        </div>
      ) : (
        <div className="played-cards__last played-cards__last--empty">
          <p className="played-cards__hint">等待出牌</p>
        </div>
      )}

      {/* Current pending play */}
      {currentPlay && currentPlay.length > 0 && (
        <div className="played-cards__current">
          <span className="played-cards__current-label">当前选择</span>
          <div className="played-cards__cards">
            {currentPlay.map((card, i) => (
              <CardComponent key={`current-${i}`} card={card} size="lg" disabled />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default PlayedCards
