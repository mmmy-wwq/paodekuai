import { useCallback, useRef } from 'react'
import type { Card } from '../types/card'
import { RANK_VALUE, Rank, compareCards } from '../types/card'
import type { CardPlay } from '../types/game'

// ====================================================================
// Types
// ====================================================================

type PatternType =
  | 'single' | 'pair' | 'triple'
  | 'triple_with_two' | 'straight' | 'consecutive_pairs'
  | 'airplane'
  | 'bomb' | 'ace_bomb' | 'four_with_three'

interface PatternInfo {
  type: PatternType
  mainRank: Rank
  mainValue: number    // numeric rank for comparison
  length: number       // card count (except airplane = number of triples)
}

// ====================================================================
// Group cards by rank
// ====================================================================

function groupByRank(cards: Card[]): Array<[Rank, Card[]]> {
  const map = new Map<Rank, Card[]>()
  for (const c of cards) {
    const arr = map.get(c.rank)
    if (arr) arr.push(c)
    else map.set(c.rank, [c])
  }
  return Array.from(map.entries()).sort(
    (a, b) => RANK_VALUE[a[0]] - RANK_VALUE[b[0]],
  )
}

// ====================================================================
// Full pattern recognition
// ====================================================================

function identify(cards: Card[]): PatternInfo | null {
  const n = cards.length
  if (n === 0) return null

  const groups = groupByRank(cards)
  const rankCounts = groups.map(([r, cs]) => ({ rank: r, value: RANK_VALUE[r], count: cs.length }))
  rankCounts.sort((a, b) => a.value - b.value)

  // All same rank → single(1) / pair(2) / triple(3) / bomb(4)
  if (rankCounts.length === 1) {
    const r = rankCounts[0]
    if (n === 1) return { type: 'single', mainRank: r.rank, mainValue: r.value, length: 1 }
    if (n === 2) return { type: 'pair', mainRank: r.rank, mainValue: r.value, length: 2 }
    if (n === 3) return { type: 'triple', mainRank: r.rank, mainValue: r.value, length: 3 }
    // 4 same rank = BOMB (always, including TWO). ACE_BOMB handled below.
    if (n === 4) return { type: 'bomb', mainRank: r.rank, mainValue: r.value, length: 4 }
  }

  // ── ACE_BOMB (A炸) ──────────────────────────────────────────────
  // 3 Aces, only in 2 or 3 player mode (checked by caller context)
  if (n === 3 && rankCounts.length === 1) {
    const r = rankCounts[0]
    if (r.rank === Rank.ACE) {
      return { type: 'ace_bomb', mainRank: r.rank, mainValue: r.value, length: 3 }
    }
  }

  // ── TRIPLE_WITH_TWO (三带二) ─────────────────────────────────────
  // 5 cards, one rank appears exactly 3 times, kickers can be any 2 cards
  if (n === 5) {
    const tripleRank = rankCounts.find((r) => r.count === 3)
    if (tripleRank) {
      return { type: 'triple_with_two', mainRank: tripleRank.rank, mainValue: tripleRank.value, length: 5 }
    }
  }

  // ── FOUR_WITH_THREE (四带三) ─────────────────────────────────────
  // 7 cards, one rank appears exactly 4 times, kickers can be any 3 cards
  if (n === 7) {
    const fourRank = rankCounts.find((r) => r.count === 4)
    if (fourRank) {
      return { type: 'four_with_three', mainRank: fourRank.rank, mainValue: fourRank.value, length: 7 }
    }
  }

  // ── AIRPLANE (飞机带翅膀) ──────────────────────────────────────
  // 2+ consecutive triples, no TWO.
  // Normal play: exactly 2 kickers per triple.
  // Last hand: 0 to 2 kickers per triple (server already validated).
  // Client is permissive since it doesn't know is_last_hand.
  if (n >= 6) {  // minimum: 2 triples = 6 cards (last hand, no kickers)
    const tripRanks = rankCounts
      .filter((r) => r.count >= 3 && r.value !== RANK_VALUE[Rank.TWO])
      .map((r) => r.value)
    if (tripRanks.length >= 2) {
      for (let s = 0; s < tripRanks.length; s++) {
        for (let e = s + 1; e < tripRanks.length; e++) {
          const seg = tripRanks.slice(s, e + 1)
          if (seg[seg.length - 1] - seg[0] !== seg.length - 1) continue
          const tripleCount = seg.length
          const coreCards = tripleCount * 3
          const kickers = n - coreCards
          if (kickers >= 0 && kickers <= tripleCount * 2) {
            return { type: 'airplane', mainRank: rankCounts.find((r) => r.value === seg[seg.length - 1])!.rank, mainValue: seg[seg.length - 1], length: tripleCount }
          }
        }
      }
    }
  }

  // 3+ distinct ranks → straight or consecutive_pairs
  const vals = rankCounts.map((r) => r.value)
  const isConsecutive = () => {
    for (let i = 1; i < vals.length; i++) {
      if (vals[i] - vals[i - 1] !== 1) return false
    }
    return true
  }

  // ── Consecutive pairs (连对): n ≥ 4 (2+ pairs), all counts = 2, consecutive, no 2 ──
  // NOTE: separate from straight check because consecutive pairs work with n=4 (2 pairs)
  if (n >= 4 && n % 2 === 0 && !vals.includes(RANK_VALUE[Rank.TWO]) && rankCounts.every((r) => r.count === 2) && isConsecutive()) {
    return { type: 'consecutive_pairs', mainRank: rankCounts[0].rank, mainValue: vals[0], length: n }
  }

  // ── Straight (顺子): n ≥ 5, all counts = 1, consecutive, no 2 ──
  if (n >= 5 && !vals.includes(RANK_VALUE[Rank.TWO]) && rankCounts.every((r) => r.count === 1) && isConsecutive()) {
    return { type: 'straight', mainRank: rankCounts[0].rank, mainValue: vals[0], length: n }
  }

  return null
}

// ====================================================================
// Helpers
// ====================================================================

/** Find indices of all cards of a given rank. Returns indices into `sorted`. */
function indicesOfRank(sorted: Card[], rank: Rank): number[] {
  return sorted.reduce<number[]>((acc, c, i) => {
    if (c.rank === rank) acc.push(i)
    return acc
  }, [])
}

/** Pick `count` cards of given rank from sorted hand, return indices. */
function pickRank(sorted: Card[], rank: Rank, count: number): number[] {
  const idxs = indicesOfRank(sorted, rank)
  return idxs.slice(0, count)
}

// ====================================================================
// Free play generation: all possible plays sorted smallest → largest
// ====================================================================

function genFreePlays(sorted: Card[]): number[][] {
  const plays: number[][] = []
  const groups = groupByRank(sorted)

  // Singles
  for (let i = 0; i < sorted.length; i++) {
    plays.push([i])
  }

  // Pairs
  for (const [, cards] of groups) {
    if (cards.length >= 2) {
      plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 2))
    }
  }

  // Triples
  for (const [, cards] of groups) {
    if (cards.length >= 3) {
      plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 3))
    }
  }

  // Triple + Two (kickers = smallest 2 remaining)
  for (const [rank, cards] of groups) {
    if (cards.length >= 3) {
      const triple = cards.map((c) => sorted.indexOf(c)).slice(0, 3)
      const kickers = sorted
        .map((c, i) => ({ card: c, idx: i }))
        .filter((x) => x.card.rank !== rank)
        .slice(0, 2)
        .map((x) => x.idx)
      if (kickers.length >= 2) {
        plays.push([...triple, ...kickers])
      }
    }
  }

  // Airplane (2+ consecutive triples, each needs 2 kickers)
  const tripleRanks = groups
    .filter(([r, cards]) => cards.length >= 3 && r !== Rank.TWO)
    .map(([r]) => RANK_VALUE[r])
    .sort((a, b) => a - b)
  for (let start = 0; start < tripleRanks.length; start++) {
    for (let end = start + 1; end < tripleRanks.length; end++) {
      const seg = tripleRanks.slice(start, end + 1)
      if (seg[seg.length - 1] - seg[0] !== seg.length - 1) continue
      const tripleCount = seg.length
      const requiredKickers = tripleCount * 2
      // Build core indices
      const rankMap: Record<number, Rank> = {}
      for (const c of sorted) rankMap[RANK_VALUE[c.rank]] = c.rank
      const core: number[] = []
      const usedRanks: Rank[] = []
      for (const v of seg) {
        const r = rankMap[v]
        const idxs = indicesOfRank(sorted, r)
        core.push(...idxs.slice(0, 3))
        usedRanks.push(r)
      }
      // Find kickers (any cards not in core ranks)
      const kickers: number[] = []
      for (let i = 0; i < sorted.length && kickers.length < requiredKickers; i++) {
        if (!usedRanks.includes(sorted[i].rank)) kickers.push(i)
      }
      if (kickers.length >= requiredKickers) {
        plays.push([...core, ...kickers.slice(0, requiredKickers)])
      }
    }
  }

  // Four + Three (四带三)
  for (const [rank, cards] of groups) {
    if (cards.length === 4) {
      const four = cards.map((c) => sorted.indexOf(c)).slice(0, 4)
      const kickers: number[] = []
      for (let i = 0; i < sorted.length && kickers.length < 3; i++) {
        if (sorted[i].rank !== rank) kickers.push(i)
      }
      if (kickers.length >= 3) {
        plays.push([...four, ...kickers.slice(0, 3)])
      }
    }
  }

  // Straights (5+ consecutive, no 2)
  const vals = [...new Set(sorted.filter((c) => c.rank !== Rank.TWO).map((c) => RANK_VALUE[c.rank]))].sort((a, b) => a - b)
  for (let len = 5; len <= vals.length; len++) {
    for (let start = 0; start + len <= vals.length; start++) {
      const seg = vals.slice(start, start + len)
      if (seg[seg.length - 1] - seg[0] !== len - 1) continue
      // Valid straight of length len starting at seg[0]
      const rankMap: Record<number, Rank> = {}
      for (const c of sorted) rankMap[RANK_VALUE[c.rank]] = c.rank
      const play: number[] = []
      for (const v of seg) {
        const r = rankMap[v]
        const idx = sorted.findIndex((c) => c.rank === r && !play.includes(sorted.indexOf(c)))
        if (idx >= 0) play.push(idx)
      }
      if (play.length === len) plays.push(play)
    }
  }

  // Consecutive pairs (2+ consecutive pairs, no 2)
  const pairVals: number[] = []
  for (const [rank, cards] of groups) {
    if (cards.length >= 2 && rank !== Rank.TWO) {
      pairVals.push(RANK_VALUE[rank])
    }
  }
  pairVals.sort((a, b) => a - b)
  for (let len = 2; len <= pairVals.length; len++) {
    for (let start = 0; start + len <= pairVals.length; start++) {
      const seg = pairVals.slice(start, start + len)
      if (seg[seg.length - 1] - seg[0] !== len - 1) continue
      const rankMap: Record<number, Rank> = {}
      for (const c of sorted) rankMap[RANK_VALUE[c.rank]] = c.rank
      const play: number[] = []
      for (const v of seg) {
        const r = rankMap[v]
        play.push(...pickRank(sorted, r, 2))
      }
      if (play.length === len * 2) plays.push(play)
    }
  }

  // Bombs (4 same rank, any rank including TWO)
  for (const [, cards] of groups) {
    if (cards.length >= 4) {
      plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 4))
    }
  }
  // Ace bomb (3 Aces)
  const aceBombGroup = groups.find(([r]) => r === Rank.ACE)
  if (aceBombGroup && aceBombGroup[1].length >= 3) {
    plays.push(aceBombGroup[1].map((c) => sorted.indexOf(c)).slice(0, 3))
  }

  return plays
}

// ====================================================================
// Beating plays: find plays that beat the target pattern
// ====================================================================

function genBeating(sorted: Card[], target: PatternInfo): number[][] {
  const plays: number[][] = []
  const groups = groupByRank(sorted)

  // Helper: add bombs (always beats non-bomb) and ace_bomb
  const addBombs = () => {
    for (const [, cards] of groups) {
      if (cards.length >= 4) {
        plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 4))
      }
    }
    // Ace bomb (3 Aces)
    const aceG = groups.find(([r]) => r === Rank.ACE)
    if (aceG && aceG[1].length >= 3) {
      plays.push(aceG[1].map((c) => sorted.indexOf(c)).slice(0, 3))
    }
  }

  // If target is ace_bomb → nothing beats it
  if (target.type === 'ace_bomb') return []

  // If target is bomb → only higher bomb or ace_bomb
  if (target.type === 'bomb') {
    for (const [rank, cards] of groups) {
      if (cards.length >= 4 && RANK_VALUE[rank] > target.mainValue) {
        plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 4))
      }
    }
    // Ace bomb (3 Aces) beats everything, including bombs
    const aceG = groups.find(([r]) => r === Rank.ACE)
    if (aceG && aceG[1].length >= 3) {
      plays.push(aceG[1].map((c) => sorted.indexOf(c)).slice(0, 3))
    }
    return plays
  }

  switch (target.type) {
    case 'single': {
      for (let i = 0; i < sorted.length; i++) {
        if (RANK_VALUE[sorted[i].rank] > target.mainValue) plays.push([i])
      }
      break
    }
    case 'pair': {
      for (const [rank, cards] of groups) {
        if (cards.length >= 2 && RANK_VALUE[rank] > target.mainValue) {
          plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 2))
        }
      }
      break
    }
    case 'triple': {
      for (const [rank, cards] of groups) {
        if (cards.length >= 3 && RANK_VALUE[rank] > target.mainValue) {
          plays.push(cards.map((c) => sorted.indexOf(c)).slice(0, 3))
        }
      }
      break
    }
    case 'triple_with_two': {
      for (const [rank, cards] of groups) {
        if (cards.length >= 3 && RANK_VALUE[rank] > target.mainValue) {
          const triple = cards.map((c) => sorted.indexOf(c)).slice(0, 3)
          // Find available kickers (any cards of different rank)
          const kickers: number[] = []
          for (let i = 0; i < sorted.length && kickers.length < 2; i++) {
            if (sorted[i].rank !== rank) kickers.push(i)
          }
          // Only 5-card plays (三带二) can beat another 三带二.
          // Plain triple (3 cards) would be identified as 'triple', not 'triple_with_two',
          // and the server would reject it (cross-type can't beat).
          if (kickers.length >= 2) {
            plays.push([...triple, ...kickers.slice(0, 2)])
          }
        }
      }
      break
    }
    case 'four_with_three': {
      for (const [rank, cards] of groups) {
        if (cards.length >= 4 && RANK_VALUE[rank] > target.mainValue) {
          const four = cards.map((c) => sorted.indexOf(c)).slice(0, 4)
          const kickers: number[] = []
          for (let i = 0; i < sorted.length && kickers.length < 3; i++) {
            if (sorted[i].rank !== rank) kickers.push(i)
          }
          // Only 7-card plays (四带三) can beat another 四带三.
          if (kickers.length >= 3) {
            plays.push([...four, ...kickers.slice(0, 3)])
          }
        }
      }
      break
    }
    case 'airplane': {
      const neededTriples = target.length
      // Find consecutive triple sequences of same length
      const tripleRanks = groups
        .filter(([r, cards]) => cards.length >= 3 && r !== Rank.TWO)
        .map(([r]) => RANK_VALUE[r])
        .sort((a, b) => a - b)
      for (let s = 0; s + neededTriples <= tripleRanks.length; s++) {
        const seg = tripleRanks.slice(s, s + neededTriples)
        if (seg[seg.length - 1] - seg[0] !== neededTriples - 1) continue
        if (seg[0] <= target.mainValue) continue // not higher
        // Build core indices
        const rankMap: Record<number, Rank> = {}
        for (const c of sorted) rankMap[RANK_VALUE[c.rank]] = c.rank
        const core: number[] = []
        const usedRanks: Rank[] = []
        for (const v of seg) {
          const r = rankMap[v]
          core.push(...pickRank(sorted, r, 3))
          usedRanks.push(r)
        }
        const requiredKickers = neededTriples * 2
        const kickers: number[] = []
        for (let i = 0; i < sorted.length && kickers.length < requiredKickers; i++) {
          if (!usedRanks.includes(sorted[i].rank)) kickers.push(i)
        }
        if (kickers.length >= requiredKickers) {
          plays.push([...core, ...kickers.slice(0, requiredKickers)])
        }
      }
      break
    }
    case 'straight': {
      const neededLen = target.length
      // Find straights of same length in hand
      const vals = [...new Set(sorted.filter((c) => c.rank !== Rank.TWO).map((c) => RANK_VALUE[c.rank]))].sort((a, b) => a - b)
      for (let start = 0; start + neededLen <= vals.length; start++) {
        const seg = vals.slice(start, start + neededLen)
        if (seg[seg.length - 1] - seg[0] !== neededLen - 1) continue
        if (seg[0] <= target.mainValue) continue // not higher
        const rankMap: Record<number, Rank> = {}
        for (const c of sorted) rankMap[RANK_VALUE[c.rank]] = c.rank
        const play: number[] = []
        for (const v of seg) {
          const r = rankMap[v]
          const idx = sorted.findIndex((c) => c.rank === r && !play.includes(sorted.indexOf(c)))
          if (idx >= 0) play.push(idx)
        }
        if (play.length === neededLen) plays.push(play)
      }
      break
    }
    case 'consecutive_pairs': {
      const neededPairs = target.length / 2
      const pairVals: number[] = []
      for (const [rank, cards] of groups) {
        if (cards.length >= 2 && rank !== Rank.TWO) {
          pairVals.push(RANK_VALUE[rank])
        }
      }
      pairVals.sort((a, b) => a - b)
      for (let start = 0; start + neededPairs <= pairVals.length; start++) {
        const seg = pairVals.slice(start, start + neededPairs)
        if (seg[seg.length - 1] - seg[0] !== neededPairs - 1) continue
        if (seg[0] <= target.mainValue) continue
        const rankMap: Record<number, Rank> = {}
        for (const c of sorted) rankMap[RANK_VALUE[c.rank]] = c.rank
        const play: number[] = []
        for (const v of seg) {
          const r = rankMap[v]
          play.push(...pickRank(sorted, r, 2))
        }
        if (play.length === neededPairs * 2) plays.push(play)
      }
      break
    }
  }

  // Add bombs (always beats non-ace-bomb patterns)
  addBombs()
  return plays
}

// ====================================================================
// Public API
// ====================================================================

export function getHintPlays(hand: Card[], lastPlay: CardPlay | null): number[][] {
  if (hand.length === 0) return []
  const sorted = [...hand].sort(compareCards)

  if (!lastPlay || lastPlay.cards.length === 0) {
    return genFreePlays(sorted)
  }

  const target = identify(lastPlay.cards)
  if (!target) return []
  return genBeating(sorted, target)
}

// ====================================================================
// Hook with cycle state
// ====================================================================

export function useHintCycle() {
  const hintPlaysRef = useRef<number[][]>([])
  const hintIndexRef = useRef(-1)
  const contextRef = useRef('')

  const nextHint = useCallback((hand: Card[], lastPlay: CardPlay | null): number[] => {
    const ctx = `${hand.length}-${lastPlay?.player_id ?? 'free'}-${lastPlay?.cards?.length ?? 0}`

    if (ctx !== contextRef.current) {
      hintPlaysRef.current = getHintPlays(hand, lastPlay)
      hintIndexRef.current = -1
      contextRef.current = ctx
    }

    hintIndexRef.current += 1
    if (hintIndexRef.current >= hintPlaysRef.current.length) {
      hintIndexRef.current = 0
    }

    return hintPlaysRef.current.length > 0
      ? hintPlaysRef.current[hintIndexRef.current]
      : []
  }, [])

  const resetHint = useCallback(() => {
    hintPlaysRef.current = []
    hintIndexRef.current = -1
    contextRef.current = ''
  }, [])

  return { nextHint, resetHint }
}
