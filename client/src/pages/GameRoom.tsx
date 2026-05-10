import { useMemo, useCallback, useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useSearchParams } from 'react-router-dom'
import { compareCards, type Card as CardType } from '../types/card'
import type { GamePhase, PlayerState } from '../types/game'
import { useGameWebSocket } from '../hooks/useGameWebSocket'
import { useSoundEffects } from '../hooks/useSoundEffects'
import { useHintCycle } from '../hooks/useHintEngine'
import DealAnimation from '../components/DealAnimation'
import HandArea from '../components/HandArea'
import Avatar from '../components/Avatar'
import PlayerSlot from '../components/PlayerSlot'

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
// Compoonent
// ============================================================================

function GameRoom() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const paramName = searchParams.get('name') || ''
  const playerCount = parseInt(searchParams.get('players') || '4', 10)
  const [playerName, setPlayerName] = useState(paramName)
  const [readyClicked, setReadyClicked] = useState(false)
  const [dealAnimDone, setDealAnimDone] = useState(false)
  const [showDealAnim, setShowDealAnim] = useState(false)
  const [showEndOverlay, setShowEndOverlay] = useState(false)

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

  // ── Sound effects ──────────────────────────────────────────
  const { playCardSound, playPassSound } = useSoundEffects()
  const prevTurnRef = useRef(0)
  const prevActionsRef = useRef<Record<string, string | null>>({})

  // ── Hint cycle (方案A: frontend local calculation) ─────────
  const { nextHint, resetHint } = useHintCycle()

  // ── Derived data ────────────────────────────────────────────

  // ── Reset ready & deal animation state on phase changes ─────

  useEffect(() => {
    if (gameState?.phase === 'WAITING' || gameState?.phase === 'ROUND_END') {
      const readyPlayers: string[] = gameState?.ready_players || []
      const myId = gameState?.your_player_id || ''
      if (!readyPlayers.includes(myId)) {
        setReadyClicked(false)
      }
    }
    if (gameState?.phase === 'DEALING') {
      setDealAnimDone(false)
      setShowDealAnim(true)
    }
  }, [gameState?.phase])

  useEffect(() => {
    if (gameState?.phase === 'WAITING' || gameState?.phase === 'ROUND_END') {
      const readyPlayers: string[] = gameState?.ready_players || []
      const myId = gameState?.your_player_id || ''
      if (!readyPlayers.includes(myId)) {
        setReadyClicked(false)
      }
    }
  }, [gameState?.phase])

  // ── ROUND_END: 3-second delay before result overlay ─────────
  useEffect(() => {
    if (gameState?.phase === 'ROUND_END') {
      setShowEndOverlay(false)
      const timer = setTimeout(() => setShowEndOverlay(true), 3000)
      return () => clearTimeout(timer)
    } else {
      setShowEndOverlay(false)
    }
  }, [gameState?.phase])

  // ── Sound effect trigger on action changes ─────────────────

  useEffect(() => {
    if (!gameState || gameState.phase !== 'PLAYING') return
    const actions = gameState.player_last_actions || {}
    const turnNum = gameState.turn_number ?? 0

    if (turnNum !== prevTurnRef.current) {
      for (const pid of Object.keys(actions)) {
        const action = actions[pid]
        const prev = prevActionsRef.current[pid]
        if (action !== prev && action === 'play') {
          playCardSound()
          break
        } else if (action !== prev && action === 'pass') {
          playPassSound()
          break
        }
      }
      prevActionsRef.current = JSON.parse(JSON.stringify(actions))
      prevTurnRef.current = turnNum
    }
  }, [gameState, playCardSound, playPassSound])

  // ── Local countdown timer (after phase declared below) ──
  const [localCountdown, setLocalCountdown] = useState(0)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Derived data ────────────────────────────────────────────

  const phase: GamePhase = (gameState?.phase as GamePhase) || 'WAITING'
  const myPlayerId = gameState?.your_player_id || ''
  const myHand: CardType[] = gameState?.your_hand || []
  const players: PlayerState[] = gameState?.players || []
  const opponents = players.filter((p) => p.player_id !== myPlayerId)

  const opponentCardCounts = useMemo(
    () => opponents.map((p) => p.remaining_cards ?? p.hand?.length ?? 0),
    [opponents],
  )
  const totalDealCards = myHand.length + opponentCardCounts.reduce((a, b) => a + b, 0)
  const isMyTurn = gameState?.current_turn === myPlayerId
  const isDeclarationMyTurn = gameState?.declaration_turn_player_id === myPlayerId

  // ── Local countdown: decrement every second ─────────────────
  useEffect(() => {
    if (phase !== 'PLAYING') {
      setLocalCountdown(0)
      return
    }
    const serverTime = gameState?.remaining_time ?? 0
    if (serverTime > 0) {
      if (countdownRef.current) clearInterval(countdownRef.current)
      setLocalCountdown(serverTime)
      countdownRef.current = setInterval(() => {
        setLocalCountdown((prev) => {
          const next = prev - 1
          if (next <= 0) {
            if (countdownRef.current) clearInterval(countdownRef.current)
            countdownRef.current = null
            return 0
          }
          return next
        })
      }, 1000)
    } else if (serverTime === 0) {
      setLocalCountdown(0)
    }
    return () => {
      if (countdownRef.current) {
        clearInterval(countdownRef.current)
        countdownRef.current = null
      }
    }
  }, [gameState?.remaining_time, gameState?.current_turn, phase])

  // ── Position mapping for PLAYING / ROUND_END phase ──────────
  // Counter-clockwise from me: me → right → top → left (4p)
  const playerPositions = useMemo(() => {
    if (!gameState || (phase !== 'PLAYING' && phase !== 'ROUND_END')) return {}
    const myIdx = players.findIndex((p) => p.player_id === myPlayerId)
    if (myIdx < 0) return {}
    const total = players.length
    const posMap: Record<string, string> = {}
    posMap[players[myIdx].player_id] = 'me'

    if (total === 2) {
      const other = (myIdx - 1 + 2) % 2
      posMap[players[other].player_id] = 'top'
    } else if (total === 3) {
      const r = (myIdx - 1 + 3) % 3
      const l = (myIdx - 2 + 3) % 3
      posMap[players[r].player_id] = 'top-right'
      posMap[players[l].player_id] = 'top-left'
    } else {
      // 4 players
      const right = (myIdx - 1 + 4) % 4
      const top = (myIdx - 2 + 4) % 4
      const left = (myIdx - 3 + 4) % 4
      posMap[players[right].player_id] = 'right'
      posMap[players[top].player_id] = 'top'
      posMap[players[left].player_id] = 'left'
    }
    return posMap
  }, [gameState, phase, players, myPlayerId])

  // ── Handlers ────────────────────────────────────────────────

  // Sorted hand for consistent index mapping with HandArea
  const sortedHand = useMemo(() => [...myHand].sort(compareCards), [myHand])

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
      .map((i) => sortedHand[i])
    sendPlay(cards)
    dispatch({ type: 'CLEAR_SELECTION' })
    resetHint()
  }, [selectedCardIds, isMyTurn, sortedHand, sendPlay, dispatch, resetHint])

  const handlePass = useCallback(() => {
    if (!isMyTurn) return
    sendPass()
    dispatch({ type: 'CLEAR_SELECTION' })
    resetHint()
  }, [isMyTurn, sendPass, dispatch, resetHint])

  const handleHint = useCallback(() => {
    if (phase !== 'PLAYING' || !isMyTurn || myHand.length === 0) return
    const lastPlay = gameState?.last_play ?? null
    // nextHint returns indices into the SORTED hand (matching sortedHand order)
    const indices = nextHint(sortedHand, lastPlay)
    dispatch({ type: 'CLEAR_SELECTION' })
    for (const idx of indices) {
      dispatch({ type: 'SELECT_CARD', payload: idx })
    }
  }, [phase, isMyTurn, myHand.length, sortedHand, gameState?.last_play, nextHint, dispatch])

  const handleDeclare = useCallback(
    (isDeclaring: boolean) => {
      sendDeclare(isDeclaring)
    },
    [sendDeclare],
  )

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

  // =====================================================================
  // Overlays (shared across all phases)
  // =====================================================================

  const renderOverlays = () => (
    <>
      {/* Deal animation overlay */}
      {showDealAnim && !dealAnimDone && createPortal(
        <DealAnimation
          myCardCount={myHand.length}
          opponentCounts={opponentCardCounts}
          currentIndex={0}
          totalCards={totalDealCards}
          state="dealing"
          onDone={() => {
            setDealAnimDone(true)
            setTimeout(() => setShowDealAnim(false), 300)
          }}
        />,
        document.body
      )}

      {/* Win confetti overlay */}
      {phase === 'ROUND_END' && gameState && createPortal(
        <div className="win-confetti" key={gameState.round_number}>
          {Array.from({ length: 40 }, (_, i) => (
            <div
              key={i}
              className="win-confetti__piece"
              style={{
                left: `${Math.random() * 100}%`,
                background: ['#c8962e', '#e8c56d', '#c44536', '#f5f0e8', '#d4a017'][i % 5],
                animationDelay: `${Math.random() * 2}s`,
                animationDuration: `${1.5 + Math.random() * 1.5}s`,
              }}
            />
          ))}
        </div>,
        document.body
      )}
    </>
  )

  // ── Conditional returns ──────────────────────────────────────

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

  // =====================================================================
  // PLAYING Phase — Game Table Layout (players around table)
  // =====================================================================

  if (phase === 'PLAYING') {
    const lastPlays = gameState.player_last_plays || {}
    const lastActions = gameState.player_last_actions || {}
    const playerCount = players.length

    const turnPlayerName = players.find((p) => p.player_id === gameState.current_turn)?.name || '...'

    // Side buttons portal
    const buttonsPortal = createPortal(
      <>
        {/* Left: 出牌 + 不要 */}
        <div className="action-side action-side--left">
          <div className="action-side__body">
            <button className="btn-action btn-action--primary" disabled={!canPlay} onClick={handlePlay}>
              出牌
            </button>
            <button className="btn-action btn-action--pass" disabled={!isMyTurn} onClick={handlePass}>
              不要
            </button>
          </div>
        </div>
        {/* Right: 提示 */}
        <div className="action-side action-side--right">
          <div className="action-side__body">
            <button className="btn-action btn-action--hint" disabled={!isMyTurn} onClick={handleHint}>
              提示
            </button>
          </div>
        </div>
      </>,
      document.body
    )

    return (
      <>
        <div className={`game-table game-table--${playerCount}p`}>
          {/* Player slots around the table */}
          {players.map((p) => {
            const pos = playerPositions[p.player_id] || 'top'
            const cardCount = p.remaining_cards ?? p.hand?.length ?? 0
            const histScore = (gameState.historical_scores as Record<string, number> | undefined)?.[p.name]
            return (
              <PlayerSlot
                key={p.player_id}
                name={p.name}
                cardCount={cardCount}
                isActive={gameState.current_turn === p.player_id}
                isDeclarer={p.is_declarer}
                position={pos}
                lastPlay={lastPlays[p.player_id] ?? null}
                lastAction={lastActions[p.player_id] ?? null}
                isMyTurn={p.player_id === myPlayerId && isMyTurn}
                countdown={gameState.current_turn === p.player_id ? localCountdown : undefined}
                sessionScore={p.score}
                historicalScore={histScore}
              />
            )
          })}

          {/* Center area — cards/countdown are in each player's slot */}

          {/* Center top info bar */}
          <div className="game-table__info">
            <span>🏠 {id ?? '?'}</span>
            <span>第 {gameState.round_number} 局</span>
            <span className="game-table__turn">
              {isMyTurn ? '🔔 轮到你了' : `⏳ ${turnPlayerName} 出牌`}
            </span>
          </div>

          {/* Hand area at bottom */}
          <HandArea
            cards={myHand}
            selectedIds={selectedCardIds}
            onToggleSelect={handleToggleSelect}
            disabled={!isMyTurn}
          />
        </div>

        {buttonsPortal}
        {renderOverlays()}
      </>
    )
  }

  // =====================================================================
  // Phase-specific rendering (columns: top-bar → opponents → play-area → hand)
  // =====================================================================

  const renderGameShell = (playAreaContent: React.ReactNode) => (
    <>
      <div className="game-layout">
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

        <div className="game-layout__opponents">
          {opponents.map((p) => {
            const isActive = gameState.current_turn === p.player_id
            const cardCount = p.remaining_cards ?? p.hand?.length ?? 0
            const histScore = (gameState.historical_scores as Record<string, number> | undefined)?.[p.name]
            return (
              <div
                key={p.player_id}
                className={`opponent-slot${isActive ? ' opponent-slot--active' : ''}`}
              >
                <Avatar name={p.name} size={36} />
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
                <div className="opponent-slot__scores">
                  <span className="os-score-item">
                    <span className="os-score-label">本轮</span>
                    <span className={`os-score-value ${p.score >= 0 ? 'os-score-value--pos' : 'os-score-value--neg'}`}>
                      {p.score}
                    </span>
                  </span>
                  {histScore !== undefined && (
                    <span className="os-score-item">
                      <span className="os-score-label">累计</span>
                      <span className={`os-score-value ${histScore >= 0 ? 'os-score-value--pos' : 'os-score-value--neg'}`}>
                        {histScore}
                      </span>
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="game-layout__play-area">
          {playAreaContent}
        </div>

        <HandArea
          cards={myHand}
          selectedIds={selectedCardIds}
          onToggleSelect={handleToggleSelect}
          disabled={!isMyTurn}
        />
      </div>

      {/* Side buttons for DECLARATION phase */}
      {phase === 'DECLARATION' && isDeclarationMyTurn && !allDeclared && createPortal(
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
        </>,
        document.body
      )}

      {renderOverlays()}
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

    const seats = Array.from({ length: maxPlayers }, (_, i) => {
      const player = i < players.length ? players[i] : null
      return { index: i, player }
    })

    return renderGameShell(
      <div className="declare-modal">
        <div className="declare-modal__box" style={{ maxWidth: '360px' }}>
          <h2 className="declare-modal__title">房间号: {roomCode}</h2>
          <p className="declare-modal__desc">当前 {players.length}/{maxPlayers} 人 · 等待所有玩家准备</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', width: '100%' }}>
            {seats.map((seat) => {
              if (seat.player) {
                const isReady = readyPlayers.includes(seat.player.player_id)
                const isMe = seat.player.player_id === myPlayerId
                return (
                  <div key={seat.player.player_id} style={{
                    flex: '0 0 calc(50% - 4px)', minWidth: '130px', padding: '12px 10px',
                    borderRadius: '8px', background: 'rgba(255,255,255,0.08)',
                    border: `2px solid ${isReady ? 'var(--accent-gold)' : 'rgba(200, 150, 46, 0.2)'}`,
                    textAlign: 'center', fontSize: '14px', color: 'var(--text-primary)',
                  }}>
                    <div style={{ fontWeight: 700, marginBottom: '4px' }}>
                      {seat.player.name} {isMe ? '(你)' : ''}
                    </div>
                    <div style={{ color: isReady ? 'var(--accent-gold-light)' : 'var(--text-secondary)', fontWeight: isReady ? 700 : 400, fontSize: '12px' }}>
                      {isReady ? '✓ 已准备' : '未准备'}
                    </div>
                  </div>
                )
              } else {
                return (
                  <div key={`empty-${seat.index}`} style={{
                    flex: '0 0 calc(50% - 4px)', minWidth: '130px', padding: '12px 10px',
                    borderRadius: '8px', background: 'rgba(255,255,255,0.03)',
                    border: '2px dashed rgba(255,255,255,0.15)', textAlign: 'center', fontSize: '13px',
                    color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    等待加入...
                  </div>
                )
              }
            })}
          </div>
          {allReady ? (
            <p className="declare-modal__desc" style={{ color: 'var(--accent-gold)', fontWeight: 700 }}>游戏开始中...</p>
          ) : (
            <>
              {players.length < maxPlayers && <p className="declare-modal__desc">等待更多玩家加入...</p>}
              <div className="declare-modal__actions">
                <button className="btn-action btn-action--primary ready-btn" onClick={handleReady} disabled={iAmReady || readyClicked} style={{ flex: 1 }}>
                  {iAmReady || readyClicked ? '已准备' : '准备'}
                </button>
              </div>
              {readyClicked && !iAmReady && (
                <p className="declare-modal__desc" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>等待其他玩家准备...</p>
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
    return renderGameShell(
      <div className="declare-modal">
        <div className="declare-modal__box">
          <h2 className="declare-modal__title">发牌中...</h2>
          <p className="declare-modal__desc">请稍候，正在发牌</p>
        </div>
      </div>,
    )
  }

  // =====================================================================
  // DECLARATION Phase
  // =====================================================================

  if (phase === 'DECLARATION') {
    const isMyDeclarationTurn = isDeclarationMyTurn && !allDeclared

    const playAreaContent = isMyDeclarationTurn ? (
      <div className="declare-modal">
        <div className="declare-modal__box">
          <h2 className="declare-modal__title">是否包牌？</h2>
          <p className="declare-modal__desc">包牌后您必须先出完所有牌，若被他人先出完则包牌失败，计分翻倍。</p>
        </div>
      </div>
    ) : (
      <div className="declare-modal">
        <div className="declare-modal__box">
          <h2 className="declare-modal__title">包牌阶段</h2>
          <p className="declare-modal__desc">
            {declarationTurnPlayer ? `等待 ${declarationTurnPlayer.name} 选择是否包牌...` : '等待其他玩家选择...'}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
            {players.map((p) => (
              <div key={p.player_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', fontSize: '13px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{p.name} {p.player_id === myPlayerId ? '(你)' : ''}</span>
                <span>{p.declaration === true ? '✅ 包牌' : p.declaration === false ? '❌ 不包' : '⏳ 等待中'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )

    return renderGameShell(playAreaContent)
  }

  // =====================================================================
  // ROUND_END Phase — game table background + result overlay
  // =====================================================================

  if (phase === 'ROUND_END') {
    const result = roundResult
    const scoreDeltas = result?.score_deltas || {}
    const isDeclarationGame = !!gameState.declarer_id
    const readyPlayers: string[] = gameState.ready_players || []
    const allReady = gameState.all_ready === true
    const iAmReady = readyPlayers.includes(myPlayerId)
    const playerCount = players.length

    const handleReady = () => {
      setReadyClicked(true)
      sendReady()
    }

    // Reuse PLAYING phase positions for the frozen background
    const lastPlays = gameState.player_last_plays || {}
    const lastActions = gameState.player_last_actions || {}

    const resultOverlay = createPortal(
      <div className="round-end-overlay">
        <div className="round-end-overlay__box">
          <h2 className="round-end-overlay__title">本局结束</h2>

          {isDeclarationGame && (
            <p className="round-end-overlay__declare-note">
              {result ? (
                result.breaker_id
                  ? `${players.find((p) => p.player_id === result.breaker_id)?.name ?? '?'} 破牌成功！`
                  : `${players.find((p) => p.player_id === result.declarer_id)?.name ?? '?'} 包牌成功！`
              ) : (
                gameState.declarer_id ? `${players.find((p) => p.player_id === gameState.declarer_id)?.name ?? '?'} 包牌` : ''
              )}
            </p>
          )}

          {/* Scores: 本局得分 + 本轮累计 + 历史累计 — with inline ready status */}
          <div className="round-end-overlay__scores">
            {players.map((p) => {
              const delta = scoreDeltas[p.player_id] ?? 0
              const histScore = (gameState.historical_scores as Record<string, number> | undefined)?.[p.name]
              const isReady = readyPlayers.includes(p.player_id)
              return (
                <div key={p.player_id} className="round-end-overlay__score-row">
                  <div className="round-end-overlay__row-top">
                    <div className="round-end-overlay__player-info">
                      <span className="round-end-overlay__player-name">
                        {p.name}
                        {p.player_id === myPlayerId ? ' (你)' : ''}
                        {result?.winner_id === p.player_id && ' 🎉'}
                      </span>
                      <span className={`round-end-overlay__ready-status ${isReady ? 'round-end-overlay__ready-status--ready' : ''}`}>
                        {isReady ? '✓ 已准备' : '等待准备'}
                      </span>
                    </div>
                    <span className={`round-end-overlay__score-value ${delta >= 0 ? 'round-end-overlay__score-value--pos' : 'round-end-overlay__score-value--neg'}`}>
                      {delta >= 0 ? '+' : ''}{delta}
                    </span>
                  </div>
                  <div className="round-end-overlay__row-bottom">
                    <span>本轮 <b>{p.score}</b></span>
                    {histScore !== undefined && <span>累计 <b>{histScore}</b></span>}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Compact ready button */}
          <div className="round-end-overlay__actions">
            {allReady ? (
              <span className="round-end-overlay__all-ready">下一局开始中...</span>
            ) : (
              <>
                <button className="btn-action btn-action--primary" onClick={handleReady}
                  disabled={iAmReady || readyClicked}
                  style={{ flex: 1, padding: '8px 20px', fontSize: '14px' }}>
                  {iAmReady || readyClicked ? '已准备' : '准备'}
                </button>
                {readyClicked && !iAmReady && (
                  <span className="round-end-overlay__waiting">等待其他玩家准备...</span>
                )}
              </>
            )}
          </div>
        </div>
      </div>,
      document.body
    )

    return (
      <>
        <div className={`game-table game-table--${playerCount}p`}>
          {players.map((p) => {
            const pos = playerPositions[p.player_id] || 'top'
            const cardCount = p.remaining_cards ?? p.hand?.length ?? 0
            const histScore = (gameState.historical_scores as Record<string, number> | undefined)?.[p.name]
            return (
              <PlayerSlot
                key={p.player_id}
                name={p.name}
                cardCount={cardCount}
                isActive={false}
                isDeclarer={p.is_declarer}
                position={pos}
                lastPlay={lastPlays[p.player_id] ?? null}
                lastAction={lastActions[p.player_id] ?? null}
                sessionScore={p.score}
                historicalScore={histScore}
                remainingCards={p.hand}
              />
            )
          })}

          {/* Info bar */}
          <div className="game-table__info">
            <span>🏠 {id ?? '?'}</span>
            <span>第 {gameState.round_number} 局 · 本局结束</span>
          </div>

          {/* Hand area — remaining cards, disabled */}
          <HandArea
            cards={myHand}
            selectedIds={selectedCardIds}
            onToggleSelect={() => {}}
            disabled={true}
          />
        </div>

        {showEndOverlay && resultOverlay}
        {!showEndOverlay && (
          <div className="round-end-preview-label">本局结束 · 结算中...</div>
        )}
        {renderOverlays()}
      </>
    )
  }

  // =====================================================================
  // Fallback
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
