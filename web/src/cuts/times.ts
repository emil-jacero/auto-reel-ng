import type { components } from '../api/schema'

/*
 * A clip's cuts in words and numbers: reading a typed time, writing one, the
 * checks a new cut must pass, and the words the panel and the read view use.
 *
 * Pure, with type-only imports (erased by type stripping), so a scratch script
 * can run it under Node as it is. A cut's times are places in its clip, in
 * seconds from the clip's start, not moments in a day: `format.ts` does not
 * apply to them.
 */

/** One cut as `reel.yaml` holds it: the span the movie leaves out (D-D). */
export type Trim = components['schemas']['TrimBody']

/** What a typed time can be refused for. */
export type TimeRefusal = 'empty' | 'unreadable' | 'too-precise'

/** A cut as a list shows it: removed ones stay listed, struck through, until the save. */
export type ListedCut = { in: number; out: number; removed?: boolean }

// `h:mm:ss`, `m:ss` or seconds, then an optional fraction after `.` or `,`.
const TIME = /^(?:(\d+):([0-5]\d):([0-5]\d)|(\d+):([0-5]\d)|(\d+))(?:[.,](\d+))?$/

/**
 * A typed time, in whole milliseconds. Kept whole so that `ms / 1000` is the
 * nearest double to what was typed (`0:58.1` is 58.1, never 58.099999999999994).
 */
export function parseTime(
  typed: string,
): { ok: true; ms: number } | { ok: false; refusal: TimeRefusal } {
  const text = typed.trim()
  if (text === '') {
    return { ok: false, refusal: 'empty' }
  }
  const match = TIME.exec(text)
  if (match === null) {
    return { ok: false, refusal: 'unreadable' }
  }
  const [, hours, minutes, seconds, shortMinutes, shortSeconds, plain, fraction] = match
  if (fraction !== undefined && fraction.length > 3) {
    return { ok: false, refusal: 'too-precise' }
  }
  const whole =
    plain !== undefined
      ? Number(plain)
      : shortMinutes !== undefined
        ? Number(shortMinutes) * 60 + Number(shortSeconds)
        : (Number(hours) * 60 + Number(minutes)) * 60 + Number(seconds)
  const ms = Number((fraction ?? '').padEnd(3, '0'))
  return { ok: true, ms: whole * 1000 + ms }
}

/** A time cut into hours, minutes, seconds and its fraction's digits (no trailing zero). */
function parts(seconds: number): { h: number; m: number; s: number; fraction: string } {
  const ms = Math.round(seconds * 1000)
  const whole = Math.floor(ms / 1000)
  return {
    h: Math.floor(whole / 3600),
    m: Math.floor(whole / 60) % 60,
    s: whole % 60,
    fraction: String(ms % 1000)
      .padStart(3, '0')
      .replace(/0+$/, ''),
  }
}

const two = (n: number) => String(n).padStart(2, '0')

/** A place in a clip: `0:00`, `0:01.5`, `1:02.35`, `1:01:15.5`, to the millisecond. */
export function formatTime(seconds: number): string {
  const { h, m, s, fraction } = parts(seconds)
  const clock = h > 0 ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`
  return fraction === '' ? clock : `${clock}.${fraction}`
}

/** A length: `1.5 s` under a minute, as a time (`1:02.5`) from one. */
export function formatLength(seconds: number): string {
  const { h, m, s, fraction } = parts(seconds)
  if (h > 0 || m > 0) {
    return formatTime(seconds)
  }
  return fraction === '' ? `${s} s` : `${s}.${fraction} s`
}

/** A length as it is said: `1 second`, `1.5 seconds`, and from a minute on as a time. */
export function spokenLength(seconds: number): string {
  const { h, m, s, fraction } = parts(seconds)
  if (h > 0 || m > 0) {
    return formatTime(seconds)
  }
  const number = fraction === '' ? `${s}` : `${s}.${fraction}`
  return `${number} ${number === '1' ? 'second' : 'seconds'}`
}

/**
 * The time the cuts cut out: every span one or more of them covers, counted once,
 * as the render merges them (sorted, overlapping or touching spans joined).
 */
export function cutOutSeconds(cuts: readonly { in: number; out: number }[]): number {
  const sorted = [...cuts].sort((a, b) => a.in - b.in)
  let total = 0
  let start = 0
  let end = -Infinity
  for (const cut of sorted) {
    if (cut.in > end) {
      total += end > start ? end - start : 0
      start = cut.in
      end = cut.out
    } else {
      end = Math.max(end, cut.out)
    }
  }
  return total + (end > start ? end - start : 0)
}

/** The cuts a list still plays out: the ones not removed. */
export function keptCuts<T extends ListedCut>(cuts: readonly T[]): T[] {
  return cuts.filter((cut) => cut.removed !== true)
}

/** Which field a refusal concerns: focus goes there. */
export type CutField = 'start' | 'end'

/** Why a cut is refused, at which field, with what the operator typed. */
export type CutRefusal =
  | { kind: TimeRefusal; field: CutField; typed: string }
  | { kind: 'order'; field: 'end'; start: number; end: number }
  | { kind: 'overlap'; field: 'start'; number: number; clash: { in: number; out: number } }
  // Ends after the clip's length as the browser read it (`at`: the time at `field`, in seconds).
  | { kind: 'past-end'; field: CutField; at: number; length: number }

/** A time in whole milliseconds: the precision a time is typed and shown in. */
function ms(seconds: number): number {
  return Math.round(seconds * 1000)
}

/**
 * Whether two spans share more than an instant (touching ones do not), compared to
 * the millisecond: a read cut that ends at 3.2033333 s is shown ending at 0:03.203,
 * and a cut typed from there touches it. (A sub-millisecond overlap is harmless: the
 * render merges overlapping spans.)
 */
function overlaps(a: { in: number; out: number }, b: { in: number; out: number }): boolean {
  return ms(a.in) < ms(b.out) && ms(b.in) < ms(a.out)
}

/** Whether a cut key names a cut read from `reel.yaml` (`r0`, `r1`…; `edit/draft.ts`). */
function isRead(key: string): boolean {
  return key.startsWith('r')
}

/**
 * A typed cut checked against the clip's listed cuts, in this order: each time
 * readable (the start first), the end after the start (the engine's own
 * refusals), the end not after the clip's `length` when it is known, and no
 * overlap with a listed cut that is not removed (the `reel-document` spec's
 * non-overlapping spans). `length` is the clip's length as the browser read it
 * from the file in its preview (D-16), in seconds, compared to the millisecond
 * as `formatTime` writes it, so an end set at the clip's end is never refused.
 * Without it a cut past the clip's end passes: the page does not know the length.
 */
export function checkCut(
  listed: readonly ListedCut[],
  typedIn: string,
  typedOut: string,
  length?: number,
): { ok: true; in: number; out: number } | { ok: false; refusal: CutRefusal } {
  const start = parseTime(typedIn)
  if (!start.ok) {
    return { ok: false, refusal: { kind: start.refusal, field: 'start', typed: typedIn.trim() } }
  }
  const end = parseTime(typedOut)
  if (!end.ok) {
    return { ok: false, refusal: { kind: end.refusal, field: 'end', typed: typedOut.trim() } }
  }
  const span = { in: start.ms / 1000, out: end.ms / 1000 }
  if (end.ms <= start.ms) {
    return { ok: false, refusal: { kind: 'order', field: 'end', start: span.in, end: span.out } }
  }
  if (length !== undefined && end.ms > ms(length)) {
    // A start at or after the end: no end could fix it.
    const field = start.ms >= ms(length) ? 'start' : 'end'
    const at = field === 'start' ? span.in : span.out
    return { ok: false, refusal: { kind: 'past-end', field, at, length } }
  }
  const at = listed.findIndex((cut) => cut.removed !== true && overlaps(cut, span))
  if (at !== -1) {
    return {
      ok: false,
      refusal: { kind: 'overlap', field: 'start', number: at + 1, clash: listed[at] },
    }
  }
  return { ok: true, ...span }
}

/** Why an Undo is refused: the cut it would bring back overlaps a cut now listed. */
export type RestoreRefusal = {
  number: number
  clashNumber: number
  clash: { in: number; out: number }
}

/**
 * An Undo checked as adding its cut would be: null when the removed cut `key`
 * shares no more than an instant with every other listed cut that is not removed.
 * Two cuts read from `reel.yaml` keep the spans they were read with, so an overlap
 * between them was already in the file: it never refuses an Undo, which only goes
 * back to what was read. Only a cut added since can.
 */
export function checkRestore(
  listed: readonly (ListedCut & { key: string })[],
  key: string,
): RestoreRefusal | null {
  const at = listed.findIndex((cut) => cut.key === key)
  if (at === -1) {
    return null
  }
  const cut = listed[at]
  const clash = listed.findIndex(
    (other, index) =>
      index !== at &&
      other.removed !== true &&
      !(isRead(other.key) && isRead(cut.key)) &&
      overlaps(other, cut),
  )
  return clash === -1 ? null : { number: at + 1, clashNumber: clash + 1, clash: listed[clash] }
}

/** The documented reasons of a cut (D-K): analysis findings, and a cut made by hand. */
export const KNOWN_REASONS = ['black', 'white', 'freeze', 'manual'] as const
export type KnownReason = (typeof KNOWN_REASONS)[number]

/** Not `REASON_LABEL`, which `events/labels.ts` exports for the staleness reasons. */
export const CUT_REASON_LABEL: Record<KnownReason, string> = {
  black: 'Black frames',
  white: 'White frames',
  freeze: 'Frozen picture',
  manual: 'Cut by hand',
}

function isKnown(reason: string): reason is KnownReason {
  return (KNOWN_REASONS as readonly string[]).includes(reason)
}

/**
 * A cut's reason in words: a documented one by its label, any other as written,
 * in quotes (it is the operator's own text, not a slug), and none as absent.
 */
export function reasonWords(reason: string | null | undefined): string {
  if (reason == null || reason.trim() === '') {
    return '—'
  }
  return isKnown(reason) ? CUT_REASON_LABEL[reason] : `“${reason}”`
}

/** `0:00 to 0:01.5`: a span as it is written in a sentence. */
export function spanWords(cut: { in: number; out: number }): string {
  return `${formatTime(cut.in)} to ${formatTime(cut.out)}`
}

function cutCount(count: number): string {
  return `${count} ${count === 1 ? 'cut' : 'cuts'}`
}

/** The visible summary of a clip's cuts: `2 cuts · −4.5 s`; `Cuts` with none. */
export function cutSummary(cuts: readonly ListedCut[]): string {
  const kept = keptCuts(cuts)
  return kept.length === 0
    ? 'Cuts'
    : `${cutCount(kept.length)} · −${formatLength(cutOutSeconds(kept))}`
}

/** The summary as it is said, without the minus sign: `2 cuts, 4.5 seconds cut out`. */
export function spokenSummary(cuts: readonly ListedCut[]): string {
  const kept = keptCuts(cuts)
  return kept.length === 0
    ? 'No cuts'
    : `${cutCount(kept.length)}, ${spokenLength(cutOutSeconds(kept))} cut out`
}

/** The Cuts control's name: `Cuts of a.mp4`, or `1 cut of a.mp4, 1.5 seconds cut out`. */
export function toggleName(cuts: readonly ListedCut[], name: string, typed = false): string {
  const kept = keptCuts(cuts)
  const base =
    kept.length === 0
      ? `Cuts of ${name}`
      : `${cutCount(kept.length)} of ${name}, ${spokenLength(cutOutSeconds(kept))} cut out`
  return typed ? `${base}${TYPED_SUFFIX}` : base
}

/** Said after the Cuts control's name while its panel holds a time typed but not added. */
export const TYPED_SUFFIX = ', a cut typed, not added'

/** The forms a time may take, as the hint and the refusal name them. */
export const TIME_FORMS = 'seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5)'

/** What the panel says it cannot check, beside its fields. */
export const CUT_HINT =
  'Seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). The page does not know the clip’s ' +
  'length: a cut that runs past its end stops there, and a cut over the whole clip leaves the ' +
  'clip out of the movie.'

/** The hint once the clip's preview has read its length (D-16): where the clip ends. */
export function lengthHint(length: number): string {
  return (
    `Seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). This clip ends at ` +
    `${formatTime(length)}, as this browser reads it: a cut must end by then, and a cut over ` +
    'the whole clip leaves the clip out of the movie.'
  )
}

/** Whether a listed cut ends after the clip's known length, compared to the millisecond. */
export function pastEnd(cut: { in: number; out: number }, length: number): boolean {
  return ms(cut.out) > ms(length)
}

/** The badge of a listed cut that ends after the clip's known length. */
export const PAST_END = 'Past the clip’s end'

/** A clip without cuts. */
export const NO_CUTS = 'No cuts: the whole clip plays.'

/** A refused cut, in words: what to type, which cut it overlaps, or where the clip ends. */
export function refusalWords(refusal: CutRefusal): string {
  switch (refusal.kind) {
    case 'empty':
      return refusal.field === 'start' ? 'Type where the cut starts.' : 'Type where the cut ends.'
    case 'unreadable':
      return `“${refusal.typed}” is not a time the page can read. Type ${TIME_FORMS}.`
    case 'too-precise':
      return `“${refusal.typed}” has more than three decimals. Times go to the millisecond.`
    case 'order':
      return (
        `A cut must end after it starts: ${formatTime(refusal.end)} is not after ` +
        `${formatTime(refusal.start)}.`
      )
    case 'overlap':
      return (
        `This cut overlaps cut ${refusal.number} (${spanWords(refusal.clash)}). Change the ` +
        `times, or remove cut ${refusal.number} first.`
      )
    case 'past-end':
      return refusal.field === 'end'
        ? `This cut ends at ${formatTime(refusal.at)}, after the clip’s end at ` +
            `${formatTime(refusal.length)}. Type an end up to ${formatTime(refusal.length)}.`
        : `This cut starts at ${formatTime(refusal.at)}, at or after the clip’s end at ` +
            `${formatTime(refusal.length)}. A cut must start before the clip ends.`
  }
}

/** A refused Undo, in words: `Cut 1 overlaps cut 2 (0:01 to 0:02). Remove cut 2 first.` */
export function restoreRefusalWords(refusal: RestoreRefusal): string {
  return (
    `Cut ${refusal.number} overlaps cut ${refusal.clashNumber} (${spanWords(refusal.clash)}). ` +
    `Remove cut ${refusal.clashNumber} first.`
  )
}

/** `Cut 0:00 to 0:01.5 added to s1710001.mp4. 1 cut, 1.5 seconds cut out.` */
export function addedWords(
  cut: { in: number; out: number },
  name: string,
  after: readonly ListedCut[],
): string {
  return `Cut ${spanWords(cut)} added to ${name}. ${spokenSummary(after)}.`
}

/** `Cut 1 of s1710003.mp4, 0:00 to 0:01.2, will be removed when you save.` */
export function removedReadWords(
  number: number,
  cut: { in: number; out: number },
  name: string,
): string {
  return `Cut ${number} of ${name}, ${spanWords(cut)}, will be removed when you save.`
}

/** `Cut 0:00 to 0:01.5 removed from s1710001.mp4. No cuts left.` (or `2 cuts left.`) */
export function removedAddedWords(
  cut: { in: number; out: number },
  name: string,
  after: readonly ListedCut[],
): string {
  const left = keptCuts(after).length
  const words = left === 0 ? 'No cuts' : cutCount(left)
  return `Cut ${spanWords(cut)} removed from ${name}. ${words} left.`
}

/** `Cut 1 of s1710003.mp4 is back.` */
export function restoredWords(number: number, name: string): string {
  return `Cut ${number} of ${name} is back.`
}
