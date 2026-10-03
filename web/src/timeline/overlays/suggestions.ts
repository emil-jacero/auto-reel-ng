import type { Analysis, Segment } from '../../api/analysis.ts'
import {
  KNOWN_REASONS,
  checkCut,
  formatLength,
  formatTime,
  reasonWords,
  refusalWords,
  spanWords,
} from '../../cuts/times.ts'
import type { CutRefusal, ListedCut } from '../../cuts/times.ts'

/*
 * The analysis lane's rules (D-20, "Analysis overlays"), pure so that `npm test` checks
 * them: a suggestion's state derived from the cuts, the check that approves it, the keys,
 * the stacking of close marks, the roving order and the words. Type-only imports apart
 * from `cuts/times.ts` (itself pure), so a scratch script can run it under Node as it is.
 */

/** What the lane needs of one detected span: seconds in the original clip. */
export type Suggestion = Pick<Segment, 'start' | 'end' | 'kind'>

/** A cut as the lane reads it: removed ones stay in the list the Cuts panel numbers. */
export type Cut = ListedCut

export type SuggestionState = 'pending' | 'cut' | 'partly-cut' | 'dismissed'

const toMs = (seconds: number) => Math.round(seconds * 1000)

// --- state ------------------------------------------------------------------------------

/**
 * The cuts that are not removed, joined as the render joins them (sorted; overlapping or
 * touching spans merged), in whole milliseconds, as `cuts/times.ts` compares them.
 */
function joined(cuts: readonly Cut[]): { in: number; out: number }[] {
  const spans = cuts
    .filter((cut) => cut.removed !== true)
    .map((cut) => ({ in: toMs(cut.in), out: toMs(cut.out) }))
    .filter((span) => span.out > span.in)
    .sort((a, b) => a.in - b.in)
  const out: { in: number; out: number }[] = []
  for (const span of spans) {
    const last = out[out.length - 1]
    if (last !== undefined && span.in <= last.out) {
      last.out = Math.max(last.out, span.out)
    } else {
      out.push({ ...span })
    }
  }
  return out
}

/**
 * A suggestion's state, from the cuts the clip lists now and never remembered: `cut` when
 * the cuts cover its whole span (one cut, or several joined), `partly-cut` when they share
 * more than an instant with it, else `dismissed` if this page visit dismissed it, else
 * `pending`. A cut outranks a dismissal. A span under a millisecond once rounded is never
 * covered (it cannot be approved either: `checkCut` refuses it as `order`).
 */
export function suggestionState(
  cuts: readonly Cut[],
  segment: Pick<Suggestion, 'start' | 'end'>,
  dismissed: boolean,
): SuggestionState {
  const start = toMs(segment.start)
  const end = toMs(segment.end)
  if (end > start) {
    const spans = joined(cuts)
    if (spans.some((span) => span.in <= start && span.out >= end)) {
      return 'cut'
    }
    if (spans.some((span) => span.in < end && start < span.out)) {
      return 'partly-cut'
    }
  }
  return dismissed ? 'dismissed' : 'pending'
}

export const STATE_WORD: Record<SuggestionState, string> = {
  pending: 'pending',
  cut: 'cut',
  'partly-cut': 'partly cut',
  dismissed: 'dismissed',
}

/** The state's glyph: with its word it is never colour alone. */
export const STATE_GLYPH: Record<SuggestionState, string> = {
  pending: '?',
  cut: '✓',
  'partly-cut': '◐',
  dismissed: '×',
}

/** The kinds and states the legend under the lane spells out, in the order it reads them. */
export const LEGEND_KINDS = ['black', 'white', 'freeze'] as const
export const LEGEND_STATES: readonly SuggestionState[] = ['pending', 'cut', 'partly-cut', 'dismissed']

// --- approval ---------------------------------------------------------------------------

/**
 * The check an approval passes, the Cuts panel's own: the suggestion's span as
 * `formatTime` writes it (to the millisecond) against the clip's listed cuts (removed
 * ones included, so a cut's number is the one the panel shows) and its length in seconds
 * when known. The cut to add, or the refusal; nothing else decides.
 */
export function approval(
  listed: readonly Cut[],
  segment: Pick<Suggestion, 'start' | 'end'>,
  length?: number,
): ReturnType<typeof checkCut> {
  return checkCut(listed, formatTime(segment.start), formatTime(segment.end), length)
}

/** Said in the detail while a save or a Move clips is pending, as the trim fields say theirs. */
export const DECISIONS_UNAVAILABLE = 'Deciding is unavailable while a save or a move is pending.'

/** What pressing Approve or Dismiss on a mark comes to: the page applies it, this decides it. */
export type Decision =
  /** Nothing happens (locked): a key is left to the browser. */
  | { kind: 'ignored' }
  /** Nothing changes; the words are announced (already cut, restore it first). */
  | { kind: 'said'; words: string }
  /** The approval was refused; the words are shown and announced, no cut is added. */
  | { kind: 'refused'; words: string }
  /** Add this cut, with the suggestion's kind as its reason, and announce the words. */
  | { kind: 'approve'; span: { in: number; out: number }; reason: string; words: string }
  | { kind: 'dismiss'; words: string }
  | { kind: 'restore'; words: string }

type Pressed = {
  state: SuggestionState
  segment: Suggestion
  clipName: string
  /** A save or a Move clips is pending: nothing is decided meanwhile. */
  locked: boolean
}

/**
 * Approve on a mark in `state`. A cut one is already done, a dismissed one is restored
 * first, a locked page ignores the press; otherwise the Cuts panel's own check
 * (`approval`) decides: the cut to add, with the kind as its reason, or the refusal.
 */
export function decideApprove({
  state,
  segment,
  clipName,
  locked,
  listed,
  length,
}: Pressed & { listed: readonly Cut[]; length?: number }): Decision {
  if (state === 'cut') {
    return { kind: 'said', words: alreadyCutWords(segment, clipName) }
  }
  if (state === 'dismissed') {
    return { kind: 'said', words: restoreFirstWords(segment, clipName) }
  }
  if (locked) {
    return { kind: 'ignored' }
  }
  const checked = approval(listed, segment, length)
  if (!checked.ok) {
    return { kind: 'refused', words: notApprovedWords(checked.refusal) }
  }
  return {
    kind: 'approve',
    span: { in: checked.in, out: checked.out },
    reason: segment.kind,
    words: approvedWords(segment, clipName),
  }
}

/**
 * A refusal, kept with what produced it: the mark, its state and the clip's cuts as listed
 * (`cutsKey`). It stands while all three are as they were.
 */
export type Refusal = { id: string; words: string; state: SuggestionState; cuts: string }

/** The clip's cuts as listed, as one comparable string (removed ones and their numbers count). */
export function cutsKey(listed: readonly Cut[]): string {
  return listed.map((cut) => `${cut.in}-${cut.out}${cut.removed === true ? 'x' : ''}`).join(',')
}

/**
 * The words of `refusal` to show on the mark `id` now, or null: another mark, or a mark
 * whose state or whose clip's cuts changed since (a cut removed, edited or added, a Reset)
 * no longer has the refusal's reason, and its numbers may no longer be right.
 */
export function standingRefusal(
  refusal: Refusal | null,
  id: string,
  state: SuggestionState,
  listed: readonly Cut[],
): string | null {
  if (refusal === null || refusal.id !== id || refusal.state !== state) {
    return null
  }
  return refusal.cuts === cutsKey(listed) ? refusal.words : null
}

/**
 * Dismiss (R) on a mark in `state`: a dismissed one is restored, a pending one is
 * dismissed; a cut or partly cut one is decided by its cuts and says so; a locked page
 * ignores the press.
 */
export function decideDismiss({ state, segment, clipName, locked }: Pressed): Decision {
  if (state === 'dismissed') {
    return locked
      ? { kind: 'ignored' }
      : { kind: 'restore', words: restoredWords(segment, clipName) }
  }
  if (state === 'cut') {
    return { kind: 'said', words: alreadyCutWords(segment, clipName) }
  }
  if (state === 'partly-cut') {
    return { kind: 'said', words: partlyCutWords(segment, clipName) }
  }
  return locked ? { kind: 'ignored' } : { kind: 'dismiss', words: dismissedWords(segment, clipName) }
}

// --- keys -------------------------------------------------------------------------------

export type SuggestionKeyEvent = {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  altKey: boolean
  repeat: boolean
  isComposing: boolean
}

/**
 * What a key press on a focused mark asks: `a` approves, `r` dismisses (or restores).
 * Nothing when Ctrl, Meta or Alt is held (Shift is ignored: the key is a letter), on a
 * key repeat and during an IME composition. Only the mark calls this, never a document
 * listener, so "a" in a text field decides nothing.
 */
export function suggestionKey(event: SuggestionKeyEvent): 'approve' | 'dismiss' | null {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || event.isComposing) {
    return null
  }
  switch (event.key) {
    case 'a':
    case 'A':
      return 'approve'
    case 'r':
    case 'R':
      return 'dismiss'
    default:
      return null
  }
}

// --- stacking and order -----------------------------------------------------------------

/** A mark's span in ms from the track's start. */
export type MarkSpan = { startMs: number; endMs: number }

/** Where a mark is drawn: its left edge and width in px from the track's start, and its row. */
export type Placed = { left: number; width: number; row: number }

/**
 * Rows for marks so that no two overlap. Each mark is at least `minPx` wide,
 * centred on its span and held inside `[0, limitPx]` (the track), and takes the first row
 * whose last mark ends before it starts. `placed[i]` is mark i, in the order given;
 * `count` is the rows used (0 for no marks). `minPx` is what a pointer or a finger has to
 * hit (44 px).
 */
export function stackMarks(
  marks: readonly MarkSpan[],
  pps: number,
  minPx: number,
  limitPx = Infinity,
): { placed: Placed[]; count: number } {
  const boxes = marks.map((mark) => {
    const from = (mark.startMs / 1000) * pps
    const to = (mark.endMs / 1000) * pps
    const width = Math.max(minPx, to - from)
    const centred = (from + to) / 2 - width / 2
    return { left: Math.max(0, Math.min(centred, limitPx - width)), width, row: 0 }
  })
  const order = boxes.map((_, index) => index).sort((a, b) => boxes[a].left - boxes[b].left)
  const ends: number[] = []
  for (const index of order) {
    const box = boxes[index]
    let row = ends.findIndex((end) => end <= box.left)
    if (row === -1) {
      row = ends.length
      ends.push(0)
    }
    ends[row] = box.left + box.width
    box.row = row
  }
  return { placed: boxes, count: ends.length }
}

/**
 * Rows for the marks of the whole track: `groups[c][i]` is mark i of clip c, spans in ms
 * from the track's start. Stacking runs once over every mark, not clip by clip, because a
 * mark is widened to `minPx` and centred on its span, so the end of one clip and the start
 * of the next (a fade out then a fade in) reach into each other. A mark's row then does
 * not depend on which clips are drawn. `placed[c][i]` is mark i of clip c; `count` is the
 * rows the lane needs, so its height holds as the track scrolls.
 */
export function placeMarks(
  groups: readonly (readonly MarkSpan[])[],
  pps: number,
  minPx: number,
  limitPx = Infinity,
): { placed: Placed[][]; count: number } {
  const all = stackMarks(groups.flat(), pps, minPx, limitPx)
  let next = 0
  const placed = groups.map((group) => group.map(() => all.placed[next++]))
  return { placed, count: all.count }
}

export type Step = 'previous' | 'next' | 'first' | 'last'

/** The mark a roving key moves to from `from` in `order`: no wrap, null at an end. */
export function neighbour(order: readonly string[], from: string, step: Step): string | null {
  if (order.length === 0) {
    return null
  }
  const at = order.indexOf(from)
  const target =
    step === 'first'
      ? 0
      : step === 'last'
        ? order.length - 1
        : at === -1
          ? 0
          : at + (step === 'next' ? 1 : -1)
  return target < 0 || target >= order.length || order[target] === from ? null : order[target]
}

/** The step an arrow key or Home or End asks (the lane is not mirrored: left is earlier). */
export function stepOfKey(key: string): Step | null {
  switch (key) {
    case 'ArrowLeft':
      return 'previous'
    case 'ArrowRight':
      return 'next'
    case 'Home':
      return 'first'
    case 'End':
      return 'last'
    default:
      return null
  }
}

// --- dismissals -------------------------------------------------------------------------

/** What a dismissal remembers: the clip and the span and kind as the analysis wrote them. */
export function dismissalKey(identity: string, segment: Suggestion): string {
  return JSON.stringify([identity, segment.start, segment.end, segment.kind])
}

/**
 * `dismissed` without the dismissals a read no longer lists: the same set when none is
 * gone, else a new one.
 */
export function dropGone(
  dismissed: ReadonlySet<string>,
  segments: Analysis['segments'],
): ReadonlySet<string> {
  if (dismissed.size === 0) {
    return dismissed
  }
  const listed = new Set(
    Object.entries(segments).flatMap(([identity, found]) =>
      found.map((segment) => dismissalKey(identity, segment)),
    ),
  )
  const kept = [...dismissed].filter((key) => listed.has(key))
  return kept.length === dismissed.size ? dismissed : new Set(kept)
}

// --- words ------------------------------------------------------------------------------

/** The kind in words, as the Cuts panel writes a reason (an unrecognised kind as written, quoted). */
export const kindWords = reasonWords

/** The kind in the middle of a sentence: `black frames`; an unrecognised one unchanged. */
function kindInSentence(kind: string): string {
  const known = (KNOWN_REASONS as readonly string[]).includes(kind)
  const words = kindWords(kind)
  return known ? words.charAt(0).toLowerCase() + words.slice(1) : words
}

/** `0:58.1 to 1:00`. */
export function segmentSpan(segment: Pick<Suggestion, 'start' | 'end'>): string {
  return spanWords({ in: segment.start, out: segment.end })
}

/** `1.9 s`, `1:02.5`. */
export function segmentLength(segment: Pick<Suggestion, 'start' | 'end'>): string {
  return formatLength(segment.end - segment.start)
}

/** A mark's name: `Black frames 0:00 to 0:03.2 (3.2 s), pending`. */
export function markName(segment: Suggestion, state: SuggestionState): string {
  return `${kindWords(segment.kind)} ${segmentSpan(segment)} (${segmentLength(segment)}), ${STATE_WORD[state]}`
}

/** The lane group's name: `Analysis suggestions of C0012.MP4`. */
export function laneName(clipName: string): string {
  return `Analysis suggestions of ${clipName}`
}

export const READING_WORDS = 'Reading the suggestions…'
export const UNREADABLE_TITLE = 'Suggestions could not be read'
/** The event was never analysed; the root is not known to the page, so the command has a placeholder. */
export const NEVER_ANALYZED = 'Not analyzed. Run `auto-reel analyze <root>`, then Refresh.'
export const ANALYZED_CLEAN = 'Analyzed: nothing to suggest.'
export const CLIP_NOT_ANALYZED = 'Not analyzed'
export const CUTS_WAIT_UNREADABLE =
  'Suggestions are not shown because the cuts they are compared with could not be read.'
export const DISMISSAL_NOTE = 'Dismissed suggestions come back when the page is reloaded.'

/**
 * Whether any clip has a cache entry. The flag `analyzed` is not trusted for this: the
 * service sets it when the event's cache directory exists, and a render writes its manifest
 * there, so a rendered but never analysed event reads `analyzed: true` with no entries.
 */
function hasEntries(analysis: Analysis): boolean {
  return analysis.analyzed && Object.keys(analysis.segments).length > 0
}

/**
 * The event's note when the lane has nothing to draw for the whole event, else null:
 * never analysed (no clip has a cache entry, whatever the flag says), or analysed with nothing found anywhere.
 */
export function eventNote(analysis: Analysis): string | null {
  if (!hasEntries(analysis)) {
    return NEVER_ANALYZED
  }
  const found = Object.values(analysis.segments).some((segments) => segments.length > 0)
  return found ? null : ANALYZED_CLEAN
}

/**
 * Whether one clip's row says "Not analyzed": in an analysed event the clip has no entry
 * (its file changed since). A clip analysed with nothing found has an empty list, no note.
 */
export function clipNotAnalyzed(analysis: Analysis, identity: string): boolean {
  return hasEntries(analysis) && !Object.hasOwn(analysis.segments, identity)
}

/** `Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added`. */
export function approvedWords(segment: Suggestion, name: string): string {
  return `Approved ${kindInSentence(segment.kind)}, ${segmentSpan(segment)}, of ${name} as a cut; 1 cut added.`
}

/** `Dismissed black frames, 0:00 to 0:03.2, of C0012.MP4.` */
export function dismissedWords(segment: Suggestion, name: string): string {
  return `Dismissed ${kindInSentence(segment.kind)}, ${segmentSpan(segment)}, of ${name}.`
}

/** `Restored black frames, 0:00 to 0:03.2, of C0012.MP4.` */
export function restoredWords(segment: Suggestion, name: string): string {
  return `Restored ${kindInSentence(segment.kind)}, ${segmentSpan(segment)}, of ${name}.`
}

/** `Already cut: black frames, 0:00 to 0:03.2, of C0012.MP4.` */
export function alreadyCutWords(segment: Suggestion, name: string): string {
  return `Already cut: ${kindInSentence(segment.kind)}, ${segmentSpan(segment)}, of ${name}.`
}

/** A partly cut suggestion is neither approved nor dismissed: the cut that overlaps it decides. */
export function partlyCutWords(segment: Suggestion, name: string): string {
  return `Partly cut: ${kindInSentence(segment.kind)}, ${segmentSpan(segment)}, of ${name}. It is decided by the cut that overlaps it.`
}

/** A dismissed suggestion is restored before it is approved. */
export function restoreFirstWords(segment: Suggestion, name: string): string {
  return `Dismissed: ${kindInSentence(segment.kind)}, ${segmentSpan(segment)}, of ${name}. Restore it first.`
}

/**
 * A refused approval, in words. An overlap names the cut the way the Cuts panel numbers it
 * but says what a suggestion can do (it has no times to retype); every other refusal is the
 * Cuts panel's own sentence.
 */
export function notApprovedWords(refusal: CutRefusal): string {
  if (refusal.kind === 'overlap') {
    return (
      `Not approved: this overlaps cut ${refusal.number} (${spanWords(refusal.clash)}). ` +
      `Remove that cut first.`
    )
  }
  return `Not approved: ${refusalWords(refusal)}`
}
