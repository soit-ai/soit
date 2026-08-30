/**
 * The one page tile still carrying a prototype figure.
 *
 * // BACKEND-PENDING: seats needs a licence record — edition, seat cap and
 * // renewal date have no server object. Its numerator is the live member
 * // count; only the cap and the date below are invented. Licensing belongs
 * // to SOIT Cloud (README, "Open source and commercial editions"), so this
 * // is a boundary rather than a gap.
 *
 * Every other tile that used to live here now reads a real measurement.
 */

export interface MockTile {
  value: string
  sub: string
  /** The API that has to ship before this tile can read a real figure. */
  reason: string
}

export const mockTiles = {
  /** Seats keeps the live member count as its numerator; only the licensed
   *  cap and the renewal date below are invented. */
  settingsSeats: {
    value: '25',
    sub: 'renewal 2027-03-01',
    reason: 'no licence record: seat cap, edition and renewal have no server object',
  },
} satisfies Record<string, MockTile>
