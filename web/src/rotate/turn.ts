/*
 * A clip's editorial turn (`clips.<identity>.rotate` in reel.yaml, D-23): an extra clockwise
 * quarter-turn on top of how the clip plays. Pure functions and the words around them, with
 * no runtime imports so `npm test` covers them. The picture itself is turned in CSS
 * (`rotate.css`); nothing here touches a proxy, a sprite or a thumbnail.
 */

/** A turn shown: a quarter-turn count in degrees, clockwise. 0 is no turn. */
export type Turn = 0 | 90 | 180 | 270

/** Which way a press turns a clip. */
export type Way = 'left' | 'right'

/** The turns, in clockwise order. */
export const TURNS: readonly Turn[] = [0, 90, 180, 270]

/**
 * The quarter-turn a saved value stands for: any multiple of 90 (also -90, 360, 450) mapped
 * into 0, 90, 180 or 270. Anything else (45, 1.5, NaN, a string) is null: shown as no turn,
 * never guessed. `null` and `undefined` (no `rotate`) are 0.
 */
export function normalizeTurn(value: unknown): Turn | null {
  if (value === null || value === undefined) {
    return 0
  }
  if (typeof value !== 'number' || !Number.isInteger(value) || value % 90 !== 0) {
    return null
  }
  return (((value % 360) + 360) % 360) as Turn
}

/** `turn` plus a quarter turn clockwise (`right`) or anticlockwise (`left`); wraps. */
export function stepTurn(turn: Turn, way: Way): Turn {
  return normalizeTurn(turn + (way === 'right' ? 90 : -90)) as Turn
}

/** The tag's words, "Rotated 90 degrees"; empty for no turn. */
export function turnWords(turn: Turn): string {
  return turn === 0 ? '' : `Rotated ${turn} degrees`
}

/**
 * One press, as announced: the way pressed, then the state in the same clockwise words as the
 * tag. "s1.mp4 turned left, now rotated 270 degrees clockwise." / "… no longer rotated."
 */
export function turnAnnouncement(name: string, turn: Turn, way: Way): string {
  return turn === 0
    ? `${name} no longer rotated.`
    : `${name} turned ${way}, now rotated ${turn} degrees clockwise.`
}

/** One group press, as announced: "3 clips rotated right." */
export function groupTurnAnnouncement(count: number, way: Way): string {
  return `${count} ${count === 1 ? 'clip' : 'clips'} rotated ${way}.`
}

/** The save bar's count: "1 clip rotated", "3 clips rotated". */
export function rotatedCount(count: number): string {
  return `${count} ${count === 1 ? 'clip' : 'clips'} rotated`
}

/** The attribute value `rotate.css` styles by; undefined for no turn, so nothing is added. */
export function turnAttr(turn: Turn): string | undefined {
  return turn === 0 ? undefined : String(turn)
}

/**
 * The turns of a reel document's `clips` map: only clips with a turn (a quarter-turn other
 * than 0). A value that is not a multiple of 90 is left out: no turn is shown, none invented.
 */
export function turnsOf(
  clips: Readonly<Record<string, { rotate?: number | null }>>,
): ReadonlyMap<string, Turn> {
  const turns = new Map<string, Turn>()
  for (const [identity, entry] of Object.entries(clips)) {
    const turn = normalizeTurn(entry.rotate)
    if (turn !== null && turn !== 0) {
      turns.set(identity, turn)
    }
  }
  return turns
}
