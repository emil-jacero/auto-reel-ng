import { tenthsCell } from '../clock.ts'
import type { ClockCell } from '../clock.ts'
import { ModelError } from './model.ts'
import type { Ms } from './model.ts'

/*
 * A title card's length, as pure rules (D-20, `title-card-duration-drag`): the limits its
 * handle can take, the snap of a dragged edge to tenths and whole seconds, what a key does,
 * and the words. The unit is an integer number of tenths of a second, so 3.9999999 never
 * reaches the draft or the file; seconds are written only at the edges (`tenthsToSeconds`).
 * No DOM, no React, no network, so `npm test` runs it.
 *
 * The engine's bounds are mirrored as two constants; a test reads `reel/card.py` and fails
 * when they differ. The server stays the authority: a value it refuses is a 400 on Save.
 */

/** A length in tenths of a second. */
export type Tenths = number

/** `reel/card.py` `CARD_MIN_DURATION` (0.5 s) and `CARD_MAX_DURATION` (60 s), in tenths. */
export const CARD_MIN_TENTHS: Tenths = 5
export const CARD_MAX_TENTHS: Tenths = 600

/** A press this close (px) to a whole second takes it. */
export const CARD_SNAP_PX = 8

function whole(what: string, value: number): void {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    throw new ModelError(`${what} must be a finite number of zero or more, got ${String(value)}`)
  }
}

/** Seconds (as the document holds them) to whole tenths, or a `ModelError` naming the value. */
export function secondsToTenths(seconds: number): Tenths {
  whole('a card duration in seconds', seconds)
  return Math.round(seconds * 10)
}

/** Tenths to seconds with one decimal exactly (`50 -> 5`, `43 -> 4.3`). */
export function tenthsToSeconds(tenths: Tenths): number {
  whole('a card duration in tenths', tenths)
  return Math.round(tenths) / 10
}

/** `4.3 s`. */
export function tenthsWords(tenths: Tenths): string {
  return `${tenthsToSeconds(tenths).toFixed(1)} s`
}

export type CardRange =
  | { adjustable: true; min: Tenths; max: Tenths }
  | { adjustable: false; reason: string }

/**
 * The lowest and highest length a card's handle can take. A black card runs 0.5 s to 60 s. A
 * card over video adds no time and is held to the first span of the anchor clip that the
 * render keeps (`keptMs`, null when the chapter has no footage), cut down to a tenth. The
 * range always includes `currentTenths`, so a limit never moves a value already set (a card
 * longer than its clip stays and can only be dragged down). A bound below 0.5 s makes the
 * card not adjustable, with the reason: never a value the engine would refuse.
 */
export function cardLimits(card: {
  background: 'black' | 'video'
  currentTenths: Tenths
  keptMs: Ms | null
}): CardRange {
  whole('the card length', card.currentTenths)
  let max = CARD_MAX_TENTHS
  if (card.background === 'video') {
    if (card.keptMs === null) {
      return { adjustable: false, reason: 'The chapter has no footage to put the card over.' }
    }
    whole('the footage length', card.keptMs)
    const footage = Math.floor(card.keptMs / 100)
    if (footage < CARD_MIN_TENTHS) {
      return {
        adjustable: false,
        reason: `The footage under the card is ${(card.keptMs / 1000).toFixed(1)} s, too short for a card of 0.5 s.`,
      }
    }
    max = Math.min(max, footage)
  }
  return {
    adjustable: true,
    min: Math.min(CARD_MIN_TENTHS, card.currentTenths),
    max: Math.max(max, Math.min(card.currentTenths, CARD_MAX_TENTHS)),
  }
}

const within = (tenths: Tenths, min: Tenths, max: Tenths): Tenths => Math.min(max, Math.max(min, tenths))

/**
 * The length for an edge at `ms` from the card's start, at `pps` px per second: the nearest
 * tenth within the limits, or the nearest whole second when it lies within 8 px of the edge
 * and within the limits (of two equally near, the earlier). `snapped` says which.
 */
export function cardTenthsAt(
  ms: number,
  pps: number,
  range: { min: Tenths; max: Tenths },
): { tenths: Tenths; snapped: boolean } {
  whole('the edge position', ms)
  if (typeof pps !== 'number' || !Number.isFinite(pps) || pps <= 0) {
    throw new ModelError(`pixels per second must be a finite number above zero, got ${String(pps)}`)
  }
  const earlier = Math.floor(ms / 1000)
  const nearest = ms - earlier * 1000 <= (earlier + 1) * 1000 - ms ? earlier : earlier + 1
  const secondTenths = nearest * 10
  if (
    secondTenths >= range.min &&
    secondTenths <= range.max &&
    (Math.abs(ms - nearest * 1000) * pps) / 1000 <= CARD_SNAP_PX
  ) {
    return { tenths: secondTenths, snapped: true }
  }
  return { tenths: within(Math.round(ms / 100), range.min, range.max), snapped: false }
}

/**
 * What a key does to the length: Left/Down a tenth shorter, Right/Up a tenth longer, with
 * Shift to the nearest whole second in that direction, Home the lowest, End the highest;
 * held to the range. A key that is not the handle's own is null; at a limit the result is
 * the current value.
 */
export function cardKey(
  key: string,
  shift: boolean,
  now: Tenths,
  range: { min: Tenths; max: Tenths },
): Tenths | null {
  whole('the card length', now)
  switch (key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      return within(shift ? (Math.ceil(now / 10) - 1) * 10 : now - 1, range.min, Math.max(now, range.min))
    case 'ArrowRight':
    case 'ArrowUp':
      return within(shift ? (Math.floor(now / 10) + 1) * 10 : now + 1, Math.min(now, range.max), range.max)
    case 'Home':
      return range.min
    case 'End':
      return range.max
    default:
      return null
  }
}

/** The readout's cell: `4.0` in a cell as wide as `60.0`, so the text keeps its place. */
export function cardCell(tenths: Tenths): ClockCell {
  return tenthsCell(tenths, CARD_MAX_TENTHS)
}

/** `Card 4.0 s`: the handle's value text and the readout's words. */
export function cardValueText(tenths: Tenths): string {
  return `Card ${tenthsWords(tenths)}`
}

/**
 * The live region's words once a drag or a typed value is released:
 * `Title card for Reception now 6.0 s. The movie is 2.0 s longer.` (the second sentence only
 * for a black card whose length changed).
 */
export function releasedWords(
  subject: string,
  now: Tenths,
  was: Tenths,
  background: 'black' | 'video',
): string {
  const head = `Title card for ${subject} now ${tenthsWords(now)}.`
  if (background !== 'black' || now === was) {
    return head
  }
  return `${head} The movie is ${tenthsWords(Math.abs(now - was))} ${now > was ? 'longer' : 'shorter'}.`
}


/** What typing a length means (`parseCardLength`). */
export type LengthParse =
  | { kind: 'set'; tenths: Tenths; seconds: number }
  | { kind: 'unset' }
  | { kind: 'refused'; words: string }

/** `0.5 s and 60.0 s`: the limits of a range, in words. */
function limitWords(range: { min: Tenths; max: Tenths }): string {
  const footage = range.max < CARD_MAX_TENTHS
  return footage
    ? `between ${tenthsWords(range.min)} and ${tenthsWords(range.max)} (the footage under it)`
    : `between ${tenthsWords(range.min)} and ${tenthsWords(range.max)}`
}

/**
 * A length typed in the card dialog, in seconds, against the limits the drag has (`cardLimits`).
 * Whole tenths only; a value outside the limits, not a number or not a whole tenth is refused in
 * words and never rounded or clamped to something the operator did not type; empty means no
 * length of the card's own (Use event style); a card that is not adjustable refuses with its reason.
 */
export function parseCardLength(text: string, range: CardRange): LengthParse {
  const typed = text.trim()
  if (typed === '') {
    return { kind: 'unset' }
  }
  if (!range.adjustable) {
    return { kind: 'refused', words: range.reason }
  }
  if (!/^\d+([.,]\d+)?$/.test(typed)) {
    return { kind: 'refused', words: 'Enter the length in seconds, for example 4 or 4.5.' }
  }
  const seconds = Number(typed.replace(',', '.'))
  const tenths = Math.round(seconds * 10)
  if (Math.abs(seconds * 10 - tenths) > 1e-9) {
    return { kind: 'refused', words: 'Use whole tenths of a second, for example 4.0 or 4.5.' }
  }
  if (tenths < range.min || tenths > range.max) {
    return { kind: 'refused', words: `A title card is ${limitWords(range)} long.` }
  }
  return { kind: 'set', tenths, seconds: tenthsToSeconds(tenths) }
}
