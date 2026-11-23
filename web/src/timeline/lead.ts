import { toEnd } from '../preview/playback.ts'
import type { Skip } from '../preview/playback.ts'
import type { Ms } from './model.ts'

/*
 * The early start's numbers (change `seamless-playback`, design D4). Two per session,
 * learned from the real hand-overs and reset when the audio device changes:
 *  - LEAD, the play start-up latency (`play()` to the first presented frame), and
 *  - P, the pre-roll the incoming clip is sought before its first kept frame, closed loop
 *    on the signed alignment error (Firefox runs about 28 ms ahead at P = 0; Chrome 0).
 * Pure, in milliseconds; the hook owns the clock and the media elements.
 */

export const LEAD_FIRST_MS = 40
export const LEAD_MAX_MS = 250
export const PREROLL_MAX_MS = 40
/** Hand-overs the medians look at. */
export const WINDOW = 9

export type Calibration = {
  /** Newest last. */
  readonly leads: readonly Ms[]
  readonly needs: readonly Ms[]
}

export const FRESH: Calibration = { leads: [], needs: [] }

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value))
}

/** The median; the mean of the two middle values for an even count. */
export function median(values: readonly number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = sorted.length >> 1
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function pushed(list: readonly number[], value: number): readonly number[] {
  return [...list, value].slice(-WINDOW)
}

/** LEAD: 40 ms before any sample, then the median of the last 9, clamped to [0, 250]. */
export function leadOf(c: Calibration): Ms {
  return c.leads.length === 0 ? LEAD_FIRST_MS : clamp(median(c.leads), 0, LEAD_MAX_MS)
}

/** P for a clip whose first kept frame is at `inMs`: never before the clip's start. */
export function preRollOf(c: Calibration, inMs: Ms): Ms {
  const p = c.needs.length === 0 ? 0 : clamp(median(c.needs), 0, PREROLL_MAX_MS)
  return Math.min(p, Math.max(0, inMs))
}

/** One hand-over's play start-up latency: `play()` to the first presented frame. */
export function withLeadSample(c: Calibration, latencyMs: Ms): Calibration {
  return { ...c, leads: pushed(c.leads, latencyMs) }
}

/**
 * One hand-over's alignment error, measured with the pre-roll that was applied
 * (`preRollUsedMs`): positive is the incoming clip ahead (content skipped). The sample is
 * the pre-roll that was needed, `max(0, P_used + error)`, a negative error included (an
 * overshoot gives a smaller one). A hand-over whose first kept frame is the clip's frame
 * 0 (`inMs` = 0) could apply no pre-roll and gives no sample.
 */
export function withAlignmentSample(
  c: Calibration,
  errorMs: Ms,
  preRollUsedMs: Ms,
  inMs: Ms,
): Calibration {
  if (inMs <= 0) {
    return c
  }
  return { ...c, needs: pushed(c.needs, Math.max(0, preRollUsedMs + errorMs)) }
}

/** After `devicechange`: LEAD 40 ms and P 0 again. */
export function resetCalibration(): Calibration {
  return FRESH
}

// --- the timing helper -------------------------------------------------------------------

/** A presented frame: the `requestVideoFrameCallback` time and its `mediaTime`, in ms. */
export type FrameSample = { atMs: number; mediaMs: Ms }

/**
 * The frame clock: callback time minus media time, the median over the samples of the
 * last second before `nowMs`. Null with no sample in that second.
 */
export function frameClock(samples: readonly FrameSample[], nowMs: number): number | null {
  const recent = samples.filter((s) => nowMs - s.atMs <= 1000 && s.atMs <= nowMs)
  return recent.length === 0 ? null : median(recent.map((s) => s.atMs - s.mediaMs))
}

export type EarlyTimes = {
  /** When to start the standby, on the same clock as `nowMs` (never before it). */
  startAt: number
  /** When to decide: the kept end less `DECIDE_MARGIN_MS` at most, so the last kept frame is presented first. */
  decideAt: number
  /** The start time was already past, or the lead is longer than the time left: start at once. */
  startNow: boolean
}

/**
 * When the standby starts and when the hand-over decides, from the shown slot's frame
 * clock, its kept end and the lead. `startAt` is the kept end less `leadMs`; `decideAt` is
 * the kept end less a small margin (`decideMarginOf`), so S's last kept frame is presented
 * before the pause. Neither is before `nowMs`, and `decideAt` is not before `startAt`.
 */
/** The most the decision is early: timer lateness was at most 5 ms, so a frame due at the kept end cannot show. */
export const DECIDE_MARGIN_MS = 6

/** How long before the kept end the decision runs: `DECIDE_MARGIN_MS`, and at most half a frame interval. */
export function decideMarginOf(frameIntervalMs: Ms): Ms {
  return Math.min(DECIDE_MARGIN_MS, frameIntervalMs / 2)
}

/**
 * Whether the standby's shown picture is already the first kept frame at the decision, so the
 * swap can run with the pause. With no pre-roll the pre-sought frame is frame IN itself; with
 * pre-roll it is footage inside the cut until a presented frame reaches `wantMs`.
 */
export function shownIsFirstKept(
  preRollMs: Ms,
  newestMediaMs: Ms | null,
  wantMs: Ms,
  frameIntervalMs: Ms,
): boolean {
  if (preRollMs <= 0) {
    return true
  }
  return newestMediaMs !== null && newestMediaMs >= wantMs - frameIntervalMs / 2
}

export function earlyTimes(
  clockMs: number,
  keptEndMs: Ms,
  leadMs: Ms,
  frameIntervalMs: Ms,
  nowMs: number,
): EarlyTimes {
  const endAt = clockMs + keptEndMs
  const rawStart = endAt - leadMs
  const startAt = Math.max(nowMs, rawStart)
  return {
    startAt,
    decideAt: Math.max(startAt, endAt - decideMarginOf(frameIntervalMs)),
    startNow: rawStart <= nowMs,
  }
}

/**
 * The end of a clip's kept footage: the start of a cut that runs to its end, else its length.
 * The shown slot's last kept frame is one frame interval before it.
 */
export function keptEndOf(spans: readonly Skip[], durationMs: Ms): Ms {
  const last = spans[spans.length - 1]
  return last !== undefined && toEnd(last, durationMs) ? last.from : durationMs
}
