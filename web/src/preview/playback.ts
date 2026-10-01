import { formatTime } from '../cuts/times'
import type { CutField, ListedCut } from '../cuts/times'

/*
 * A clip's preview in numbers and words: the spans Skip cuts jumps over, where
 * playback goes on each presented frame, where Play starts, the playhead's keys
 * and its words, and the preview's copy (D-16).
 *
 * Pure: no DOM, no React. Every time here is in whole milliseconds, as the cut
 * fields are: in floating point, a frame at 0.96 s plus a 0.04 s step falls
 * short of a cut at 1 s, and that frame would show.
 */

/** A span Skip cuts jumps over, in whole ms. */
export type Skip = { from: number; to: number }

/** A span that ends less than this before the browser's length runs to the clip's end. */
export const END_SLACK_MS = 100

/** A time in seconds as whole milliseconds. */
export function toMs(seconds: number): number {
  return Math.round(seconds * 1000)
}

/** Whether `span` runs to the clip's end: `lengthMs - span.to < END_SLACK_MS`. */
export function toEnd(span: Skip, lengthMs: number): boolean {
  return lengthMs - span.to < END_SLACK_MS
}

/**
 * The listed, not-removed cuts as the render joins them (`kept_spans`): clamped to
 * [0, length], empty ones dropped, sorted, overlapping or touching ones merged.
 */
export function skipSpans(cuts: readonly ListedCut[], lengthMs: number): Skip[] {
  const spans = cuts
    .filter((cut) => cut.removed !== true)
    .map((cut) => ({
      from: Math.max(0, toMs(cut.in)),
      to: Math.min(lengthMs, toMs(cut.out)),
    }))
    .filter((span) => span.to > span.from)
    .sort((a, b) => a.from - b.from)
  const merged: Skip[] = []
  for (const span of spans) {
    const last = merged.at(-1)
    if (last !== undefined && span.from <= last.to) {
      last.to = Math.max(last.to, span.to)
    } else {
      merged.push({ ...span })
    }
  }
  return merged
}

/**
 * Where playback goes when the frame at `atMs` is shown and the next comes `stepMs`
 * later (both whole ms): for the first span with `from <= atMs + stepMs < to`,
 * `{stop: from}` when it runs to the end, else `{seek: to}`; null to play on.
 * On the next frame's start, not the shown one's: after a seek to a `to` between two
 * frames, the frame that straddles it is shown and left alone, never sought again.
 */
export function skipAt(
  spans: readonly Skip[],
  atMs: number,
  stepMs: number,
  lengthMs: number,
): { seek: number } | { stop: number } | null {
  const next = atMs + stepMs
  const span = spans.find((skip) => skip.from <= next && next < skip.to)
  if (span === undefined) {
    return null
  }
  return toEnd(span, lengthMs) ? { stop: span.from } : { seek: span.to }
}

/** The clip's first footage outside every span, or null when the spans cover it all. */
function firstFootage(spans: readonly Skip[], lengthMs: number): number | null {
  const first = spans[0]
  if (first === undefined || first.from > 0) {
    return 0
  }
  return toEnd(first, lengthMs) ? null : first.to
}

/**
 * Where Play starts: `atMs`, a span's end, the first footage from 0 (also when `atMs` is
 * within `END_SLACK_MS` of the end, or inside a span that runs to the end), or null (all cut).
 */
export function playFrom(spans: readonly Skip[], atMs: number, lengthMs: number): number | null {
  if (lengthMs - atMs < END_SLACK_MS) {
    return firstFootage(spans, lengthMs)
  }
  const span = spans.find((skip) => skip.from <= atMs && atMs < skip.to)
  if (span === undefined) {
    return atMs
  }
  return toEnd(span, lengthMs) ? firstFootage(spans, lengthMs) : span.to
}

/** The playhead after a key on the slider, in ms, clamped to [0, length]; null: not its key. */
export function seekKey(key: string, atMs: number, lengthMs: number): number | null {
  const clamp = (ms: number) => Math.min(lengthMs, Math.max(0, ms))
  switch (key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      return clamp(atMs - 100)
    case 'ArrowRight':
    case 'ArrowUp':
      return clamp(atMs + 100)
    case 'PageDown':
      return clamp(atMs - 1000)
    case 'PageUp':
      return clamp(atMs + 1000)
    case 'Home':
      return 0
    case 'End':
      return lengthMs
    default:
      return null
  }
}

/** A time's place along the bar, 0–100 (%), clamped. */
export function along(ms: number, lengthMs: number): number {
  if (!(lengthMs > 0)) {
    return 0
  }
  return Math.min(100, Math.max(0, (ms / lengthMs) * 100))
}

/**
 * `0:01.234 of 0:06.02`, plus `, in cut 2` when `atMs` lies inside a listed cut that is
 * not removed; the number is the cut's number in the panel's list.
 */
export function playheadWords(atMs: number, lengthMs: number, cuts: readonly ListedCut[]): string {
  const words = `${formatTime(atMs / 1000)} of ${formatTime(lengthMs / 1000)}`
  const at = cuts.findIndex(
    (cut) => cut.removed !== true && toMs(cut.in) <= atMs && atMs < toMs(cut.out),
  )
  return at === -1 ? words : `${words}, in cut ${at + 1}`
}

// The preview's copy. `<name>` is the clip's name as its row names it.

export const WATCH = 'Watch'
/** The panel's toggle while its preview is open: a press closes the player. */
export const HIDE_PLAYER = 'Hide player'
export const LOADING = 'Loading…'
export const SKIP_CUTS = 'Skip cuts'
export const SET_WORDS: Record<CutField, string> = { start: 'Set From', end: 'Set To' }
export const PLAYHEAD_KEYS =
  'Space plays or pauses. Arrows move 0.1 seconds, Page Up and Page Down one second, Home and ' +
  'End to the start and the end.'
export const ALL_CUT = 'Nothing plays: the cuts cover the whole clip.'

/** The bar's kinds of span, as the legend names them. */
export type SpanKind = 'cut' | 'removed' | 'typed'
export const SPAN_LABEL: Record<SpanKind, string> = {
  cut: 'Cut',
  removed: 'Removed when you save',
  typed: 'Typed, not added',
}

export const watchName = (name: string) => `Watch ${name}`
export const hideName = (name: string) => `Hide player of ${name}`
export const regionName = (name: string) => `Player for ${name}`
export const closeName = (name: string) => `Close the player of ${name}`
export const playName = (name: string, playing: boolean) => `${playing ? 'Pause' : 'Play'} ${name}`
export const playheadName = (name: string) => `Playhead of ${name}`
export const skipName = (name: string) => `Skip cuts of ${name}`
export const setName = (field: CutField, name: string) =>
  `${SET_WORDS[field]} at the playhead of ${name}`

/** Announced once an opened preview has read the clip: `s1710001.mp4 is ready to play, 0:06.02.` */
export function readyWords(name: string, seconds: number): string {
  return Number.isFinite(seconds) && seconds > 0
    ? `${name} is ready to play, ${formatTime(seconds)}.`
    : `${name} is ready to play.`
}

/** Announced after Set From / Set To: `From set to 0:01.234.` */
export function setWords(field: CutField, seconds: number): string {
  return `${field === 'start' ? 'From' : 'To'} set to ${formatTime(seconds)}.`
}

/** The visible time: `0:01.234 / 0:06.02`, or `0:00 / —` before the length is read. */
export function timeWords(atMs: number, lengthMs: number | null): string {
  return `${formatTime(atMs / 1000)} / ${lengthMs === null ? '—' : formatTime(lengthMs / 1000)}`
}

/** What a note or a failure says: its title, then its detail. */
export type NoteWords = { title: string; detail: string }

/**
 * After a clip that is gone or changed on disk: never "Refresh", which in Edit mode
 * asks about unsaved changes and then leaves Edit mode. The edits stay until then.
 */
export const STOP_EDITING =
  'Stop editing (save first if you want to keep your edits) to read the event again, then open ' +
  'the player anew.'

export function noSoundWords(name: string): NoteWords {
  return {
    title: 'No sound in this browser.',
    detail:
      `This browser finds no sound it can play in ${name}. If a Sony camera recorded it, its ` +
      'sound is PCM, which Firefox does not play and Chrome does; the render keeps it.',
  }
}

export function noPictureWords(name: string): NoteWords {
  return {
    title: `This browser cannot show the picture of ${name}.`,
    detail: 'It reads the clip but not its video format. The clip is unchanged on disk.',
  }
}

export function goneWords(name: string, detail: string): NoteWords {
  return { title: `${name} is no longer on disk.`, detail: `${detail} ${STOP_EDITING}` }
}

export function changedWords(name: string): NoteWords {
  return { title: `${name} changed on disk since the page was read.`, detail: STOP_EDITING }
}

export function emptyWords(name: string): NoteWords {
  return { title: `The file of ${name} is empty.`, detail: 'There is nothing to play.' }
}

export function formatWords(name: string): NoteWords {
  return {
    title: `This browser cannot play ${name}.`,
    detail: 'Its format is not one this browser plays. The clip is unchanged on disk.',
  }
}

/** The title of a clip the service cannot read (502); the failure kind's pill follows it. */
export const unreadableTitle = (name: string) => `${name} could not be read.`

/** The Download action's words: `Download <file name>`. */
export const downloadWords = (fileName: string) => `Download ${fileName}`

export const TRY_AGAIN = 'Try again'
