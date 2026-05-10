import { useRef, useCallback } from 'react'
import type { Card } from '../types/card'
import { RANK_VALUE, Rank } from '../types/card'

/**
 * Chinese rank names for card game announcements.
 */
const RANK_NAME: Record<string, string> = {
  'THREE': '三', 'FOUR': '四', 'FIVE': '五', 'SIX': '六',
  'SEVEN': '七', 'EIGHT': '八', 'NINE': '九', 'TEN': '十',
  'JACK': '勾', 'QUEEN': '圈', 'KING': '克',
  'ACE': '尖', 'TWO': '二',
}

/** Build Chinese text for a played card pattern. */
function buildPatternText(cards: Card[]): string {
  if (cards.length === 0) return ''

  // Count ranks
  const rankCounts = new Map<Rank, number>()
  for (const c of cards) {
    rankCounts.set(c.rank, (rankCounts.get(c.rank) || 0) + 1)
  }
  const grouped = Array.from(rankCounts.entries()).sort((a, b) => RANK_VALUE[a[0]] - RANK_VALUE[b[0]])

  // Single
  if (cards.length === 1) return RANK_NAME[cards[0].rank] || ''

  // Pair
  if (cards.length === 2 && grouped.length === 1) {
    return '对' + (RANK_NAME[grouped[0][0]] || '')
  }

  // Triple / Triple with two
  if (grouped.some(([, c]) => c >= 3)) {
    const triple = grouped.find(([, c]) => c >= 3)!
    const othersCount = cards.length - 3
    if (othersCount === 0 || othersCount === 2) {
      return '三个' + (RANK_NAME[triple[0]] || '')
    }
  }

  // Four with three
  if (grouped.some(([, c]) => c >= 4)) {
    const four = grouped.find(([, c]) => c >= 4)!
    return '四个' + (RANK_NAME[four[0]] || '')
  }

  // Check for consecutive patterns
  const vals = grouped.map(([r]) => RANK_VALUE[r])
  const isConsecutive = vals.every((v, i) => i === 0 || v - vals[i - 1] === 1)
  const noTwo = !grouped.some(([r]) => r === Rank.TWO)

  // Airplane: 2+ consecutive triples
  const tripleRanks = grouped.filter(([, c]) => c >= 3 && c !== 4)
  if (tripleRanks.length >= 2) {
    const tripleVals = tripleRanks.map(([r]) => RANK_VALUE[r])
    const tripleConsecutive = tripleVals.every((v, i) => i === 0 || v - tripleVals[i - 1] === 1)
    if (tripleConsecutive) return '飞机带翅膀'
  }

  // Straight
  if (cards.length >= 5 && noTwo && isConsecutive && grouped.every(([, c]) => c === 1)) {
    return '顺子'
  }

  // Consecutive pairs
  if (cards.length >= 4 && noTwo && isConsecutive && grouped.every(([, c]) => c === 2)) {
    return '连对'
  }

  // Bomb (4 same rank)
  if (cards.length === 4 && grouped.length === 1) {
    const r = grouped[0][0]
    if (r === Rank.TWO) return 'A炸'
    return '炸弹'
  }

  // Ace bomb (3 aces)
  if (cards.length === 3 && grouped.length === 1 && grouped[0][0] === Rank.ACE) {
    return 'A炸'
  }

  return ''
}

/**
 * Hook providing simple Web Audio API sound effects for the card game.
 * Sounds are synthesized programmatically — no external audio files needed.
 */
export function useSoundEffects() {
  const ctxRef = useRef<AudioContext | null>(null)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  const getCtx = useCallback((): AudioContext => {
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext()
    }
    if (ctxRef.current.state === 'suspended') {
      ctxRef.current.resume()
    }
    return ctxRef.current
  }, [])

  /** Play card sound — short crisp "snap" like cards hitting a table. */
  const playCardSound = useCallback(() => {
    try {
      const ctx = getCtx()
      const now = ctx.currentTime

      // White noise burst → crisp snap
      const bufferSize = ctx.sampleRate * 0.08
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
      const data = buffer.getChannelData(0)
      for (let i = 0; i < bufferSize; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.015))
      }

      const noise = ctx.createBufferSource()
      noise.buffer = buffer

      const filter = ctx.createBiquadFilter()
      filter.type = 'highpass'
      filter.frequency.setValueAtTime(3000, ctx.currentTime)
      filter.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.06)

      const gain = ctx.createGain()
      gain.gain.setValueAtTime(0.25, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08)

      noise.connect(filter)
      filter.connect(gain)
      gain.connect(ctx.destination)
      noise.start(now)
      noise.stop(now + 0.08)
    } catch {
      // Audio not available — silently ignore
    }
  }, [getCtx])

  /** Play pass sound — short low "thud". */
  const playPassSound = useCallback(() => {
    try {
      const ctx = getCtx()
      const now = ctx.currentTime

      const osc = ctx.createOscillator()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(220, now)
      osc.frequency.exponentialRampToValueAtTime(110, now + 0.12)

      const gain = ctx.createGain()
      gain.gain.setValueAtTime(0.15, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12)

      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(now)
      osc.stop(now + 0.12)
    } catch {
      // Audio not available
    }
  }, [getCtx])

  /** Speak a card pattern using Speech Synthesis (Chinese voice). */
  const speakPattern = useCallback((cards: Card[]) => {
    try {
      const text = buildPatternText(cards)
      if (!text) return

      // Cancel previous utterance to avoid overlapping
      if (utteranceRef.current) {
        window.speechSynthesis.cancel()
      }

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'zh-CN'
      utterance.rate = 1.0
      utterance.pitch = 1.0
      utterance.volume = 0.8
      utteranceRef.current = utterance
      window.speechSynthesis.speak(utterance)
    } catch {
      // Speech synthesis not available
    }
  }, [])

  return { playCardSound, playPassSound, speakPattern }
}
