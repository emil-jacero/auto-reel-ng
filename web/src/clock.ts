/*
 * The clock: how the client writes a running time (a time that changes while something
 * plays, is scrubbed or is dragged), D-20. A readout is written to a scale taken from the
 * longest value it can show, then every value is written to that scale, so the text has
 * the same number of characters whatever the position: minutes padded to the longest
 * value's digits, seconds two digits, a fixed fraction with its trailing zeros kept.
 *
 * It is not `cuts/times.ts` `formatTime`, which writes a cut's time (typed back, parsed,
 * trailing zeros dropped: `1:02.4`) and is spoken. A running time is read, never typed.
 *
 * No imports, so it runs under `node --experimental-strip-types` as it is.
 */

/** The digits a readout reserves, and the longest value it can show (whole ms). */
export type ClockScale = {
  /** 0 unless the longest value is an hour or more; then the digits of its hours. */
  hourDigits: number
  /** 2 when there are hours, else the digits of the longest value's minutes (at least 1). */
  minuteDigits: number
  /** The fraction's digits: 2 (centiseconds) for playback, 3 (milliseconds) for a trim. */
  decimals: 2 | 3
  /** The longest value, cut to the fraction's unit: a larger value is shown as this. */
  longestMs: number
}

const MS_PER_MINUTE = 60_000
const MS_PER_HOUR = 3_600_000

function digitsOf(n: number): number {
  return String(Math.floor(n)).length
}

function unitOf(decimals: 2 | 3): number {
  return decimals === 2 ? 10 : 1
}

function readable(what: string, ms: number): void {
  if (typeof ms !== 'number' || !Number.isFinite(ms) || ms < 0) {
    throw new RangeError(`${what} must be a time of zero or more, not ${String(ms)}`)
  }
}

/**
 * The scale of a readout whose longest value is `longestMs`. It depends on the set of
 * values the readout can show and on nothing that changes while it plays.
 */
export function clockScale(longestMs: number, decimals: 2 | 3 = 2): ClockScale {
  readable('the longest time of a clock', longestMs)
  const unit = unitOf(decimals)
  const longest = Math.floor(longestMs / unit) * unit
  const hours = Math.floor(longest / MS_PER_HOUR)
  return {
    hourDigits: hours > 0 ? digitsOf(hours) : 0,
    minuteDigits: hours > 0 ? 2 : digitsOf(longest / MS_PER_MINUTE),
    decimals,
    longestMs: longest,
  }
}

/** The width of any text the scale writes, in characters (so in `ch` of a mono face). */
export function clockChars(scale: ClockScale): number {
  const hours = scale.hourDigits > 0 ? scale.hourDigits + 1 : 0
  return hours + scale.minuteDigits + 1 + 2 + 1 + scale.decimals
}

const pad = (n: number, digits: number) => String(n).padStart(digits, '0')

/**
 * `ms` written to `scale`: `0:09.50`, `09:59.99`, `1:00:00.00`. Cut down to the fraction's
 * unit, never rounded up, so a position never reads later than its total; a value above
 * the scale's longest is the longest. `null` (a time not known yet) is dashes in the same
 * places, never `0:00`. A value that is negative or not a number is not written: it throws
 * a `RangeError`, never a made-up time.
 */
export function formatClock(ms: number | null, scale: ClockScale): string {
  if (ms === null) {
    const hours = scale.hourDigits > 0 ? `${'-'.repeat(scale.hourDigits)}:` : ''
    return `${hours}${'-'.repeat(scale.minuteDigits)}:--.${'-'.repeat(scale.decimals)}`
  }
  readable('a time on a clock', ms)
  const unit = unitOf(scale.decimals)
  const whole = Math.floor(Math.min(ms, scale.longestMs) / unit) * unit
  const hours = Math.floor(whole / MS_PER_HOUR)
  const minutes = Math.floor(whole / MS_PER_MINUTE) % 60
  const seconds = Math.floor(whole / 1000) % 60
  const fraction = Math.floor((whole % 1000) / unit)
  const head =
    scale.hourDigits > 0
      ? `${pad(hours, scale.hourDigits)}:${pad(minutes, 2)}`
      : String(Math.floor(whole / MS_PER_MINUTE)).padStart(scale.minuteDigits, '0')
  return `${head}:${pad(seconds, 2)}.${pad(fraction, scale.decimals)}`
}

/** A time ready to draw: its text and the width of its cell in `ch` (digits of a mono face). */
export type ClockCell = { text: string; ch: number }

/** `formatClock` with the width of its cell, for the screens that reserve it. */
export function clockCell(ms: number | null, scale: ClockScale): ClockCell {
  return { text: formatClock(ms, scale), ch: clockChars(scale) }
}
