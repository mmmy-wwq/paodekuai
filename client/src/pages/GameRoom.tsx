import { useMemo, useCallback, useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useSearchParams } from 'react-router-dom'
import type { Card as CardType } from '../types/card'
import type { GamePhase, PlayerState } from '../types/game'
import { useGameWebSocket } from '../hooks/useGameWebSocket'
import DealAnimation from '../components/DealAnimation'
import HandArea from '../components/HandArea'
import PlayedCards from '../components/PlayedCards'

// ============================================================================
// Phase Display Labels
// ============================================================================

const PHASE_LABELS: Record<GamePhase, string> = {
  WAITING: '等待中',
  DEALING: '发牌中',
  DECLARATION: '包牌阶段',
  PLAYING: '出牌中',
  ROUND_END: '本局结束',
}

// ============================================================================
// Name Prompt (shown before connecting)
// ============================================================================

function NamePrompt({ onSubmit }: { onSubmit: (name: string) => void }) {
  const [name, setName] = useState('')

  const handleSubmit = () => {
    const trimmed = name.trim()
    if (trimmed) onSubmit(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit()
  }

  return (
    <div className="game-layout">
      <div className="game-layout__play-area">
        <div className="declare-modal">
          <div className="declare-modal__box">
            <h2 className="declare-modal__title">输入昵称</h2>
            <p className="declare-modal__desc">请输入你的玩家昵称以加入游戏</p>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="玩家昵称"
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                border: '2px solid var(--accent-gold)',
                background: 'rgba(255,255,255,0.1)',
                color: 'var(--text-primary)',
                fontSize: '1rem',
                outline: 'none',
                textAlign: 'center',
              }}
            />
            <div className="declare-modal__actions">
              <button
                className="btn-action btn-action--primary"
                onClick={handleSubmit}
                disabled={!name.trim()}
                style={{ flex: 1 }}
              >
                加入
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Component
// ============================================================================

function GameRoom() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const paramName = searchParams.get('name') || ''
  const playerCount = parseInt(searchParams.get('players') || '4', 10)
  const [playerName, setPlayerName] = useState(paramName)
  const [readyClicked, setReadyClicked] = useState(false)
  const [dealAnimDone, setDealAnimDone] = useState(false)

  const {
    gameState,
    selectedCardIds,
    roundResult,
    error,
    sendPlay,
    sendPass,
    sendDeclare,
    sendReady,
    isConnected,
    dispatch,
  } = useGameWebSocket(id || '', playerName, playerCount)

  // ── Reset ready & deal animation state on phase changes ───────────

  useEffect(() => {
    if (gameState?.phase === 'WAITING' || gameState?.phase === 'ROUND_END') {
      const readyPlayers: string[] = gameState?.ready_players || []
      const myId = gameState?.your_player_id || ''
      if (!readyPlayers.includes(myId)) {
        setReadyClicked(false)
      }
    }
    // Reset deal animation for new dealing phase
    if (gameState?.phase === 'DEALING') {
      setDealAnimDone(false)
    }
  }, [gameState?.phase])

  // ── Reset ready state when phase resets (duplicate, kept for safety) ──

  useEffect(() => {
    if (gameState?.phase === 'WAITING' || gameState?.phase === 'ROUND_END') {
      const readyPlayers: string[] = gameState?.ready_players || []
      const myId = gameState?.your_player_id || ''
      if (!readyPlayers.includes(myId)) {
        setReadyClicked(false)
      }
    }
  }, [gameState?.phase])

  // ── Derived data (MUST be before any conditional return — React hooks rule) ─

  const phase: GamePhase = (gameState?.phase as GamePhase) || 'WAITING'
  const myPlayerId = gameState?.your_player_id || ''
  const myHand: CardType[] = gameState?.your_hand || []
  const players: PlayerState[] = gameState?.players || []
  const opponents = players.filter((p) => p.player_id !== myPlayerId)

  // ── Opponent card counts for deal animation ────────────────────────
  const opponentCardCounts = useMemo(
    () => opponents.map((p) => p.remaining_cards ?? p.hand?.length ?? 0),
    [opponents],
  )
  const totalDealCards = myHand.length + opponentCardCounts.reduce((a, b) => a + b, 0)
  const isMyTurn = gameState?.current_turn === myPlayerId
  const isDeclarationMyTurn = gameState?.declaration_turn_player_id === myPlayerId

  console.log('[GameRoom] phase=', phase, 'myPlayerId=', myPlayerId, 'isMyTurn=', isMyTurn, 'handCount=', myHand.length)

  const sortedSelection = useMemo(
    () => [...selectedCardIds].sort((a, b) => a - b),
    [selectedCardIds],
  )
  const currentPlay = useMemo(
    () => sortedSelection.map((i) => myHand[i]).filter(Boolean),
    [sortedSelection, myHand],
  )
  const playerInfoList = useMemo(
    () => players.map((p) => ({ id: p.player_id, name: p.name })),
    [players],
  )

  // ── Handlers ────────────────────────────────────────────────────────

  const handleToggleSelect = useCallback(
    (index: number) => {
      if (phase !== 'PLAYING' || !isMyTurn) return
      if (selectedCardIds.has(index)) {
        dispatch({ type: 'DESELECT_CARD', payload: index })
      } else {
        dispatch({ type: 'SELECT_CARD', payload: index })
      }
    },
    [phase, isMyTurn, selectedCardIds, dispatch],
  )

  const handlePlay = useCallback(() => {
    if (selectedCardIds.size === 0 || !isMyTurn) return
    const cards = [...selectedCardIds]
      .sort((a, b) => a - b)
      .map((i) => myHand[i])
    sendPlay(cards)
    dispatch({ type: 'CLEAR_SELECTION' })
  }, [selectedCardIds, isMyTurn, myHand, sendPlay, dispatch])

  const handlePass = useCallback(() => {
    if (!isMyTurn) return
    sendPass()
    dispatch({ type: 'CLEAR_SELECTION' })
  }, [isMyTurn, sendPass, dispatch])

  const handleHint = useCallback(() => {
    if (phase !== 'PLAYING' || !isMyTurn || myHand.length === 0) return
    dispatch({ type: 'CLEAR_SELECTION' })
    dispatch({ type: 'SELECT_CARD', payload: 0 })
  }, [phase, isMyTurn, myHand, dispatch])

  const handleDeclare = useCallback(
    (isDeclaring: boolean) => {
      console.log('[DECLARE] handleDeclare called, isDeclaring=', isDeclaring)
      sendDeclare(isDeclaring)
    },
    [sendDeclare],
  )

  // ── Find next declarer name ─────────────────────────────────────────

  const declarationTurnPlayer = useMemo(() => {
    if (phase !== 'DECLARATION' || !gameState) return null
    const pid = gameState.declaration_turn_player_id
    if (!pid) return null
    return players.find((p) => p.player_id === pid) || null
  }, [phase, gameState?.declaration_turn_player_id, players])

  const allDeclared = useMemo(
    () => players.every((p) => p.declaration !== undefined && p.declaration !== null),
    [players],
  )

  const canPlay = selectedCardIds.size > 0 && isMyTurn && phase === 'PLAYING'

  // ── Conditional returns (AFTER all hooks — React rule) ──────────────

  if (!playerName) {
    return <NamePrompt onSubmit={(n) => setPlayerName(n)} />
  }

  if (!gameState) {
    return (
      <div className="game-layout">
        <div className="game-layout__top-bar">
          <span className="game-layout__room-code">房间 {id ?? '?'}</span>
        </div>
        <div className="game-layout__play-area">
          <p className="declare-modal__desc" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-primary)', fontSize: '18px' }}>
            {isConnected ? '正在加载游戏状态...' : '正在连接服务器...'}
          </p>
          {error && (
            <p style={{ color: 'var(--suit-red)', textAlign: 'center', padding: '0 2rem' }}>
              {error}
            </p>
          )}
        </div>
      </div>
    )
  }

  // ── Phase-specific rendering ────────────────────────────────────────

  /**
   * The game layout shell wraps all phase views with a consistent structure:
   * top-bar → opponents → play-area → actions → hand-area
   */
  const renderGameShell = (
    playAreaContent: React.ReactNode,
  ) => (
    <><div className="game-layout">
      {/* Top bar */}
      <div className="game-layout__top-bar">
        <span className="game-layout__room-code">房间 {id ?? '?'}</span>
        <span className="game-layout__round">
          第 {gameState.round_number} 局 · {PHASE_LABELS[phase]}
        </span>
        {myPlayerId && (
          <span className="game-layout__round" style={{ color: 'var(--accent-gold)' }}>
            {isMyTurn || isDeclarationMyTurn
              ? '轮到你了'
              : `等待 ${players.find((p) => p.player_id === gameState.current_turn)?.name || '...'} 出牌`}
          </span>
        )}
        <div className="game-layout__scores">
          {players.map((p) => {
            const histScore = (gameState.historical_scores as Record<string, number> | undefined)?.[p.name]
            return (
              <span key={p.player_id}>
                {p.name}: {p.score}
                {histScore !== undefined && <><br /><small style={{ opacity: 0.6 }}>累计 {histScore}</small></>}
              </span>
            )
          })}
        </div>
      </div>

      {/* Opponent areas */}
      <div className="game-layout__opponents">
        {opponents.map((p) => {
          const isActive = gameState.current_turn === p.player_id
          const cardCount = p.remaining_cards ?? p.hand?.length ?? 0
          return (
            <div
              key={p.player_id}
              className={`opponent-slot${isActive ? ' opponent-slot--active' : ''}`}
            >
              <div className="opponent-slot__cards">
                {Array.from({ length: Math.min(cardCount, 10) }, (_, i) => (
                  <div key={i} className="opponent-slot__card-back" />
                ))}
              </div>
              <span className="opponent-slot__name">
                {p.name}
                {cardCount > 0 ? `（${cardCount} 张）` : ''}
                {p.is_declarer ? ' 🏆' : ''}
              </span>
            </div>
          )
        })}
      </div>

      {/* Play area */}
      <div className="game-layout__play-area">
        {playAreaContent}
      </div>

      {/* Hand area — always rendered, disabled when not your turn */}
      <HandArea
        cards={myHand}
        selectedIds={selectedCardIds}
        onToggleSelect={handleToggleSelect}
        disabled={!isMyTurn}
      />
    </div>

    {/* ── Side buttons (portal to body, fixed positioning, text rotates in forced landscape) ── */}
    {((phase === 'DECLARATION' && isDeclarationMyTurn && !allDeclared) || phase === 'PLAYING') && createPortal(
      <>
        {phase === 'DECLARATION' && (
          <>
            <div className="action-side action-side--left action-side--decl">
              <div className="action-side__body">
                <button className="btn-action btn-action--primary" onClick={() => handleDeclare(true)}>
                  是，包牌
                </button>
              </div>
            </div>
            <div className="action-side action-side--right action-side--decl">
              <div className="action-side__body">
                <button className="btn-action btn-action--pass" onClick={() => handleDeclare(false)}>
                  否，不包
                </button>
              </div>
            </div>
          </>
        )}
          {phase === 'PLAYING' && (
            <>
              <div className="action-side action-side--left">
                <div className="action-side__body">
                  <button className="btn-action btn-action--pass" disabled={!isMyTurn} onClick={handlePass}>
                    不要
                  </button>
                </div>
              </div>
              <div className="action-side action-side--right">
                <div className="action-side__body">
                  <button className="btn-action btn-action--primary" disabled={!canPlay} onClick={handlePlay}>
                    出牌
                  </button>
                  <button className="btn-action btn-action--hint" disabled={!isMyTurn} onClick={handleHint}>
                    提示
                  </button>
                </div>
              </div>
            </>
          )}
      </>,
      document.body
    )}
  </>
  )

  // =====================================================================
  // WAITING Phase
  // =====================================================================

  if (phase === 'WAITING') {
    const roomCode = gameState.room_id || gameState.code || id || ''
    const readyPlayers: string[] = gameState.ready_players || []
    const allReady = gameState.all_ready === true
    const maxPlayers = gameState.max_players || gameState.player_count || players.length
    const iAmReady = readyPlayers.includes(myPlayerId)

    const handleReady = () => {
      setReadyClicked(true)
      sendReady()
    }

    // Build seat grid: all maxPlayers positions (filled + empty)
    const seats = Array.from({ length: maxPlayers }, (_, i) => {
      const player = i < players.length ? players[i] : null
      return { index: i, player }
    })

    return renderGameShell(
      <div className="declare-modal">
        <div className="declare-modal__box" style={{ maxWidth: '360px' }}>
          <h2 className="declare-modal__title">
            房间号: {roomCode}
          </h2>
          <p className="declare-modal__desc">
            当前 {players.length}/{maxPlayers} 人 · 等待所有玩家准备
          </p>

          {/* Seat grid */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px',
            justifyContent: 'center',
            width: '100%',
          }}>
            {seats.map((seat) => {
              if (seat.player) {
                const isReady = readyPlayers.includes(seat.player.player_id)
                const isMe = seat.player.player_id === myPlayerId
                return (
                  <div
                    key={seat.player.player_id}
                    style={{
                      flex: '0 0 calc(50% - 4px)',
                      minWidth: '130px',
                      padding: '12px 10px',
                      borderRadius: '8px',
                      background: 'rgba(255,255,255,0.08)',
                      border: `2px solid ${isReady ? 'var(--accent-gold)' : 'rgba(200, 150, 46, 0.2)'}`,
                      textAlign: 'center',
                      fontSize: '14px',
                      color: 'var(--text-primary)',
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: '4px' }}>
                      {seat.player.name} {isMe ? '(你)' : ''}
                    </div>
                    <div style={{
                      color: isReady ? 'var(--accent-gold-light)' : 'var(--text-secondary)',
                      fontWeight: isReady ? 700 : 400,
                      fontSize: '12px',
                    }}>
                      {isReady ? '✓ 已准备' : '未准备'}
                    </div>
                  </div>
                )
              } else {
                return (
                  <div
                    key={`empty-${seat.index}`}
                    style={{
                      flex: '0 0 calc(50% - 4px)',
                      minWidth: '130px',
                      padding: '12px 10px',
                      borderRadius: '8px',
                      background: 'rgba(255,255,255,0.03)',
                      border: '2px dashed rgba(255,255,255,0.15)',
                      textAlign: 'center',
                      fontSize: '13px',
                      color: 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    等待加入...
                  </div>
                )
              }
            })}
          </div>

          {/* Ready button or transition text */}
          {allReady ? (
            <p className="declare-modal__desc" style={{ color: 'var(--accent-gold)', fontWeight: 700 }}>
              游戏开始中...
            </p>
          ) : (
            <>
              {players.length < maxPlayers && (
                <p className="declare-modal__desc">
                  等待更多玩家加入...
                </p>
              )}
              <div className="declare-modal__actions">
                <button
                  className="btn-action btn-action--primary ready-btn"
                  onClick={handleReady}
                  disabled={iAmReady || readyClicked}
                  style={{ flex: 1 }}
                >
                  {iAmReady || readyClicked ? '已准备' : '准备'}
                </button>
              </div>
              {readyClicked && !iAmReady && (
                <p className="declare-modal__desc" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  等待其他玩家准备...
                </p>
              )}
            </>
          )}
        </div>
      </div>,
    )
  }

  // =====================================================================
  // DEALING Phase
  // =====================================================================

  if (phase === 'DEALING') {
    return (
      <div className="game-layout">
        {/* Top bar */}
        <div className="game-layout__top-bar">
          <span className="game-layout__room-code">房间 {id ?? '?'}</span>
          <span className="game-layout__round">
            第 {gameState.round_number} 局 · 发牌中
          </span>
        </div>

        {/* Opponent areas — show current card backs */}
        <div className="game-layout__opponents">
          {opponents.map((p) => {
            const cardCount = p.remaining_cards ?? p.hand?.length ?? 0
            return (
              <div key={p.player_id} className="opponent-slot">
                <div className="opponent-slot__cards">
                  {Array.from({ length: Math.min(cardCount, 10) }, (_, i) => (
                    <div key={i} className="opponent-slot__card-back" />
                  ))}
                </div>
                <span className="opponent-slot__name">{p.name}（{cardCount} 张）</span>
              </div>
            )
          })}
        </div>

        {/* Play area — DealAnimation overlay during dealing */}
        <div className="game-layout__play-area" style={{ pointerEvents: 'none' }}>
          {dealAnimDone ? (
            <div className="declare-modal">
              <div className="declare-modal__box">
                <h2 className="declare-modal__title">发牌完成</h2>
                <p className="declare-modal__desc">等待游戏开始...</p>
              </div>
            </div>
          ) : (
            <DealAnimation
              myCardCount={myHand.length}
              opponentCounts={opponentCardCounts}
              currentIndex={0}
              totalCards={totalDealCards}
              state="dealing"
              onDone={() => setDealAnimDone(true)}
            />
          )}
        </div>

        {/* No hand area during dealing — cards are flying to positions */}
        <div className="hand-area hand-area--empty" style={{ position: 'relative' }}>
          <p className="hand-area__empty-text">发牌中...</p>
        </div>
      </div>
    )
  }

  // =====================================================================
  // DECLARATION Phase
  // =====================================================================

  if (phase === 'DECLARATION') {
    const isMyDeclarationTurn = isDeclarationMyTurn && !allDeclared

    const playAreaContent = isMyDeclarationTurn ? (
      // My turn to declare — show simple prompt (buttons are in side portal)
      <div className="declare-modal">
        <div className="declare-modal__box">
          <h2 className="declare-modal__title">是否包牌？</h2>
          <p className="declare-modal__desc">
            包牌后您必须先出完所有牌，若被他人先出完则包牌失败，计分翻倍。
          </p>
        </div>
      </div>
    ) : (
      // Not my turn — show waiting message
      <div className="declare-modal">
        <div className="declare-modal__box">
          <h2 className="declare-modal__title">包牌阶段</h2>
          <p className="declare-modal__desc">
            {declarationTurnPlayer
              ? `等待 ${declarationTurnPlayer.name} 选择是否包牌...`
              : '等待其他玩家选择...'}
          </p>
          {/* Show each player's declaration status */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
            {players.map((p) => (
              <div
                key={p.player_id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  background: 'rgba(255,255,255,0.06)',
                  borderRadius: '4px',
                  fontSize: '13px',
                }}
              >
                <span style={{ color: 'var(--text-secondary)' }}>
                  {p.name} {p.player_id === myPlayerId ? '(你)' : ''}
                </span>
                <span>
                  {p.declaration === true
                    ? '✅ 包牌'
                    : p.declaration === false
                    ? '❌ 不包'
                    : '⏳ 等待中'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )

    return renderGameShell(playAreaContent)
  }

  // =====================================================================
  // PLAYING Phase
  // =====================================================================

  if (phase === 'PLAYING') {
    const playAreaContent = (
      <PlayedCards
        lastPlay={gameState.last_play ?? null}
        currentPlay={currentPlay.length > 0 ? currentPlay : null}
        players={playerInfoList}
      />
    )

    return renderGameShell(playAreaContent)
  }

  // =====================================================================
  // ROUND_END Phase
  // =====================================================================

  if (phase === 'ROUND_END') {
    const result = roundResult
    const isDeclarationGame = !!gameState.declarer_id
    const readyPlayers: string[] = gameState.ready_players || []
    const allReady = gameState.all_ready === true
    const iAmReady = readyPlayers.includes(myPlayerId)

    const handleReady = () => {
      setReadyClicked(true)
      sendReady()
    }

    const playAreaContent = (
      <div className="result-modal">
        <div className="result-modal__box">
          <h2 className="result-modal__title">本局结束</h2>

          {isDeclarationGame && (
            <p className="result-modal__declare-note">
              {result ? (
                result.breaker_id
                  ? `${players.find((p) => p.player_id === result.breaker_id)?.name ?? '?'} 破牌成功！`
                  : `${players.find((p) => p.player_id === result.declarer_id)?.name ?? '?'} 包牌成功！`
              ) : (
                gameState.declarer_id
                  ? `${players.find((p) => p.player_id === gameState.declarer_id)?.name ?? '?'} 包牌`
                  : ''
              )}
            </p>
          )}

          <div className="result-modal__scores">
            {players.map((p) => {
              const scoreValue = result?.scores?.[p.player_id] ?? p.score
              return (
                <div key={p.player_id} className="result-modal__score-row">
                  <span className="result-modal__player-name">
                    {p.name} {p.player_id === myPlayerId ? '(你)' : ''}
                    {result?.winner_id === p.player_id && ' 🎉'}
                  </span>
                  <span
                    className={`result-modal__score-value ${
                      scoreValue >= 0
                        ? 'result-modal__score-value--positive'
                        : 'result-modal__score-value--negative'
                    }`}
                  >
                    {scoreValue >= 0 ? '+' : ''}{scoreValue}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Ready section */}
          <div className="ready-status" style={{ width: '100%', marginTop: '12px' }}>
            {players.map((p) => {
              const isReady = readyPlayers.includes(p.player_id)
              const isMe = p.player_id === myPlayerId
              return (
                <div
                  key={p.player_id}
                  className={`ready-status__player ${isReady ? 'ready-status__player--ready' : 'ready-status__player--waiting'}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '6px 12px',
                    background: 'rgba(255,255,255,0.06)',
                    borderRadius: '4px',
                    fontSize: '13px',
                    color: 'var(--text-primary)',
                  }}
                >
                  <span>
                    {p.name} {isMe ? '(你)' : ''}
                  </span>
                  <span style={{
                    color: isReady ? 'var(--accent-gold-light)' : 'var(--text-secondary)',
                    fontWeight: isReady ? 700 : 400,
                  }}>
                    {isReady ? '✓ 已准备' : '等待中'}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Ready button or transition text */}
          {allReady ? (
            <p className="declare-modal__desc" style={{ color: 'var(--accent-gold)', fontWeight: 700, marginTop: '12px' }}>
              下一局开始中...
            </p>
          ) : (
            <>
              <button
                className="btn-action btn-action--primary ready-btn result-modal__next-btn"
                onClick={handleReady}
                disabled={iAmReady || readyClicked}
                style={{ marginTop: '12px' }}
              >
                {iAmReady || readyClicked ? '已准备' : '准备'}
              </button>
              {readyClicked && !iAmReady && (
                <p className="declare-modal__desc" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  等待其他玩家准备...
                </p>
              )}
            </>
          )}
        </div>
      </div>
    )

    return renderGameShell(playAreaContent)
  }

  // =====================================================================
  // Fallback (unknown phase)
  // =====================================================================

  return renderGameShell(
    <div className="declare-modal">
      <div className="declare-modal__box">
        <h2 className="declare-modal__title">未知状态</h2>
        <p className="declare-modal__desc">phase: {phase}</p>
      </div>
    </div>,
  )
}

export default GameRoom
