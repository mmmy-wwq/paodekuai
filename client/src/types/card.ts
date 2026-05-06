/**
 * Card model for 跑得快 (Pao De Kuai).
 *
 * Suit hierarchy: ♠ > ♥ > ♣ > ♦ (used for first-player determination only)
 * Rank hierarchy: 3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2
 */

/** Card suit enum. Priority SPADE > HEART > CLUB > DIAMOND is for starting player only. */
export enum Suit {
  SPADE = 'SPADE',     // ♠
  HEART = 'HEART',     // ♥
  CLUB = 'CLUB',       // ♣
  DIAMOND = 'DIAMOND', // ♦
}

/** Card rank enum. Higher value = bigger card. TWO (15) > ACE (14) > ... > THREE (3). */
export enum Rank {
  THREE = 'THREE',
  FOUR = 'FOUR',
  FIVE = 'FIVE',
  SIX = 'SIX',
  SEVEN = 'SEVEN',
  EIGHT = 'EIGHT',
  NINE = 'NINE',
  TEN = 'TEN',
  JACK = 'JACK',
  QUEEN = 'QUEEN',
  KING = 'KING',
  ACE = 'ACE',
  TWO = 'TWO',
}

/** Maps rank to integer value for comparisons. Higher = stronger. */
export const RANK_VALUE: Record<Rank, number> = {
  [Rank.THREE]: 3,
  [Rank.FOUR]: 4,
  [Rank.FIVE]: 5,
  [Rank.SIX]: 6,
  [Rank.SEVEN]: 7,
  [Rank.EIGHT]: 8,
  [Rank.NINE]: 9,
  [Rank.TEN]: 10,
  [Rank.JACK]: 11,
  [Rank.QUEEN]: 12,
  [Rank.KING]: 13,
  [Rank.ACE]: 14,
  [Rank.TWO]: 15,
};

/** Maps suit to priority for tiebreaking (higher = stronger). */
export const SUIT_PRIORITY: Record<Suit, number> = {
  [Suit.SPADE]: 4,
  [Suit.HEART]: 3,
  [Suit.CLUB]: 2,
  [Suit.DIAMOND]: 1,
};

/** Maps suit to display symbol. */
export const SUIT_DISPLAY: Record<Suit, string> = {
  [Suit.SPADE]: '♠',
  [Suit.HEART]: '♥',
  [Suit.CLUB]: '♣',
  [Suit.DIAMOND]: '♦',
};

/** Maps rank to display string. */
export const RANK_DISPLAY: Record<Rank, string> = {
  [Rank.THREE]: '3',
  [Rank.FOUR]: '4',
  [Rank.FIVE]: '5',
  [Rank.SIX]: '6',
  [Rank.SEVEN]: '7',
  [Rank.EIGHT]: '8',
  [Rank.NINE]: '9',
  [Rank.TEN]: '10',
  [Rank.JACK]: 'J',
  [Rank.QUEEN]: 'Q',
  [Rank.KING]: 'K',
  [Rank.ACE]: 'A',
  [Rank.TWO]: '2',
};

/** Immutable card representation. */
export interface Card {
  readonly suit: Suit;
  readonly rank: Rank;
}

/**
 * Compare two cards for sorting.
 * Primary: rank value (higher = bigger). Secondary: suit priority (for tiebreaking).
 * Returns negative if a < b, positive if a > b, zero if equal.
 */
export function compareCards(a: Card, b: Card): number {
  const rankDiff = RANK_VALUE[a.rank] - RANK_VALUE[b.rank];
  if (rankDiff !== 0) return rankDiff;
  return SUIT_PRIORITY[a.suit] - SUIT_PRIORITY[b.suit];
}

/**
 * Convert a card to its display string, e.g. "♠A", "♥K", "♦3".
 */
export function cardToString(c: Card): string {
  return `${RANK_DISPLAY[c.rank]}${SUIT_DISPLAY[c.suit]}`;
}
