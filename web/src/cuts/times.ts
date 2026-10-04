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

/**
 * Whether a cut is one read from `reel.yaml` (key `r0`, `r1`…; `edit/draft.ts`) and still
 * has the times it was read with. A trimmed one (`edited`) no longer does: an overlap with
 * it was not already in the file.
 */
function isAsRead(cut: { key: string; edited?: true }): boolean {
  return cut.key.startsWith('r') && cut.edited !== true
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
 * Two cuts read from `reel.yaml` that still have the spans they were read with: an overlap
 * between them was already in the file, so it never refuses an Undo, which only goes
 * back to what was read. A cut added since can refuse it, and so can a read cut that was
 * trimmed (`edited`), whose new span may lie over the removed one.
 */
export function checkRestore(
  listed: readonly (ListedCut & { key: string; edited?: true })[],
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
      !(isAsRead(other) && isAsRead(cut)) &&
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

/**
 * What a cut over the whole clip does, said after both hints. The page cannot tell
 * which clip is its chapter's title clip, so the sentence is conditional.
 */
export const WHOLE_CLIP_CUT =
  'a cut over the whole clip leaves the clip out of the movie. If it is its chapter’s ' +
  'title clip, the chapter’s title card moves to the next clip that plays.'

/** What the panel says it cannot check, beside its fields. */
export const CUT_HINT =
  'Seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). The page does not know the clip’s ' +
  `length: a cut that runs past its end stops there, and ${WHOLE_CLIP_CUT}`

/**
 * The clip's length for the panel: what its preview has read from the file (D-16), else
 * the duration the event detail gives (the length the thumbnail operation measured), else
 * unknown. The preview's wins because Set From and Set To write times in it, and a browser
 * can read up to 60 ms more than the probe. A `null`, absent, zero, negative or non-finite
 * duration is unknown, never a length of zero.
 */
export function clipLength(
  previewed: number | undefined,
  duration: number | null | undefined,
): number | undefined {
  if (previewed !== undefined) {
    return previewed
  }
  return typeof duration === 'number' && Number.isFinite(duration) && duration > 0
    ? duration
    : undefined
}

/**
 * The hint once the page knows the clip's length: where the clip ends, and whose length it is
 * (the browser's, once the preview read it, else the one recorded for the clip, measured when its thumbnail was made).
 */
export function lengthHint(length: number, previewed = true): string {
  return (
    `Seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). This clip ends at ` +
    `${formatTime(length)}, ${previewed ? 'as this browser reads it' : 'as recorded for this clip'}: ` +
    `a cut must end by then, and ${WHOLE_CLIP_CUT}`
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

// --- trimming a cut on the timeline ------------------------------------------------------

/**
 * A typed start or end of a cut that is already listed (the timeline's fields), checked as
 * `checkCut` checks a new cut: the cut itself is marked removed in a copy of the list, so
 * its own old span is never its own clash and the other cuts keep the panel's numbers.
 * `field` is the one typed; `otherText` is the other field as shown. An edge the operator
 * did not change keeps the cut's exact value (a time read as 3.2033333 is shown as
 * 0:03.203, and typing in the other field must not move it).
 */
export function checkTrim(
  listed: readonly ListedCut[],
  index: number,
  field: CutField,
  typed: string,
  otherText: string,
  length?: number,
): { ok: true; in: number; out: number } | { ok: false; refusal: CutRefusal } {
  const own = listed[index]
  const copy = listed.map((cut, at) => (at === index ? { ...cut, removed: true } : cut))
  // A cut read past the clip's end is saved as read until its end is moved: typing a start
  // beside that end is not a reason to refuse it, but the start still has to be in the clip.
  const keepsPastEnd =
    field === 'start' &&
    length !== undefined &&
    otherText.trim() === formatTime(own.out) &&
    pastEnd(own, length)
  const checked =
    field === 'start'
      ? checkCut(copy, typed, otherText, keepsPastEnd ? undefined : length)
      : checkCut(copy, otherText, typed, length)
  if (!checked.ok) {
    return checked
  }
  if (keepsPastEnd && length !== undefined && ms(checked.in) >= ms(length)) {
    return {
      ok: false,
      refusal: { kind: 'past-end', field: 'start', at: checked.in, length },
    }
  }
  return {
    ok: true,
    in: field === 'end' && otherText.trim() === formatTime(own.in) ? own.in : checked.in,
    out: field === 'start' && otherText.trim() === formatTime(own.out) ? own.out : checked.out,
  }
}

/** Which edge a handle moves. */
export type TrimEdge = 'in' | 'out'

/** The keys of a trim handle, said once beside the track (`aria-describedby`). */
export const TRIM_KEYS =
  'Trim handle keys: Left and Right move one frame, Shift with Left or Right one second, ' +
  'Page Up and Page Down five seconds, Home and End go to the lowest and highest time the ' +
  'handle can take, Enter sets the edge at the playhead.'

/** `Cut 1 start of s1710001.mp4`: the handle's name; `n` is the cut's number in its Cuts panel. */
export function handleName(edge: TrimEdge, n: number, name: string): string {
  return `Cut ${n} ${edge === 'in' ? 'start' : 'end'} of ${name}`
}

/**
 * What a handle's value says: its time, then the cut's span, and when the cut runs past
 * the clip's end, that: `0:01.5, the cut runs 0:01.5 to 0:03` (times in seconds).
 */
export function handleValueText(
  seconds: number,
  cut: { in: number; out: number },
  clipLength?: number,
): string {
  const past = clipLength !== undefined && pastEnd(cut, clipLength)
  return (
    `${formatTime(seconds)}, the cut runs ${spanWords(cut)}` +
    (past ? ', past the clip’s end' : '')
  )
}

/** The selected cut's group: `Cut 1 of s1710001.mp4`. */
export function selectedName(n: number, name: string): string {
  return `Cut ${n} of ${name}`
}

/** A selected cut's field: `Start of cut 1 of s1710001.mp4`. */
export function fieldName(field: CutField, n: number, name: string): string {
  return `${field === 'start' ? 'Start' : 'End'} of cut ${n} of ${name}`
}

/** The group with no selected cut. */
export const NO_SELECTED_CUT =
  'No cut selected. Select a cut by its handle or its span to type its times.'

/** The group while a save or a move of marked clips is pending. */
export const UNAVAILABLE = 'Trimming is unavailable while a save or a move is pending.'

/** Said when Enter is pressed on a handle and the playhead is in another clip. */
export function NOT_IN_CLIP(name: string): string {
  return `The playhead is not in ${name}.`
}

/**
 * `Cut 1 of s1710001.mp4 now 0:01 to 0:03.5, snapped to the playhead. 2 cuts, 2.5 seconds
 * cut out.` `snap` is what the edge snapped to, already in words (`Snapped to …`), if it did.
 */
export function trimmedWords(
  n: number,
  name: string,
  cut: { in: number; out: number },
  after: readonly ListedCut[],
  snap?: string | null,
): string {
  const snapped = snap == null ? '' : `, ${snap.charAt(0).toLowerCase()}${snap.slice(1)}`
  return `Cut ${n} of ${name} now ${spanWords(cut)}${snapped}. ${spokenSummary(after)}.`
}

/** Said when Enter could not put an edge at the playhead: `Cut 1 end of a.mp4 stopped at 0:04, the nearest it can go.` */
export function stoppedWords(handle: string, seconds: number): string {
  return `${handle} stopped at ${formatTime(seconds)}, the nearest it can go.`
}
