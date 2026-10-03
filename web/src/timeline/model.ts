import type { ListedCut } from '../cuts/times.ts'
import { skipSpans, toMs } from '../preview/playback.ts'
import type { Skip } from '../preview/playback.ts'

/*
 * The timeline's model (D-20): where a clip sits at a zoom, which clips are on
 * screen, how a clip's cuts are drawn and counted, how far a trim handle may go
 * and what it snaps to.
 *
 * Pure: no DOM, no React, no file or network, and no import beyond the repo's own
 * pure modules. Every time here is an integer number of milliseconds (`Ms`), as the
 * Cuts panel writes and reads them back; pixels and pixels per second are plain
 * floats. A clip's duration and frame rate are arguments with no default: a guessed
 * 25 fps would round a 29.97 fps clip's cuts to frames it does not have, and a
 * value that is not a finite number above zero is refused, never replaced.
 */

/** A time or a length in whole milliseconds. */
export type Ms = number

/** What the model needs to know about a clip. Variable frame rate is not modelled. */
export type ClipFacts = { durationMs: Ms; fps: number }

/** A value the model refuses: it names the field. */
export class ModelError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ModelError'
  }
}

function finitePositive(name: string, value: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    throw new ModelError(`${name} must be a finite number above zero, got ${String(value)}`)
  }
  return value
}

function finite(name: string, value: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new ModelError(`${name} must be a finite number, got ${String(value)}`)
  }
  return value
}

function checkFacts(f: ClipFacts): void {
  finitePositive('durationMs', f.durationMs)
  finitePositive('fps', f.fps)
}

/** A clip's facts from its length in seconds (as `facts.json` gives it) and its rate. */
export function clipFacts(durationSeconds: number, fps: number): ClipFacts {
  finitePositive('duration', durationSeconds)
  finitePositive('fps', fps)
  const durationMs = Math.round(durationSeconds * 1000)
  if (durationMs < 1) {
    throw new ModelError(`duration must be at least a millisecond, got ${durationSeconds} s`)
  }
  return { durationMs, fps }
}

// --- frames -------------------------------------------------------------------------

/**
 * The time of frame `index` at `fps`, to the millisecond: at 29.97 fps frame 1 is
 * 33 ms, not 33.3667. Whole-frame times are the grid a handle can be shown on.
 */
export function frameMs(index: number, fps: number): Ms {
  finite('frame index', index)
  finitePositive('fps', fps)
  return Math.round((index * 1000) / fps)
}

/** The frame time nearest `ms` on the grid of a clip of rate `fps`. */
export function nearestFrame(ms: Ms, fps: number): Ms {
  finite('ms', ms)
  finitePositive('fps', fps)
  return frameMs(Math.round((ms * fps) / 1000), fps)
}

/** The shortest a cut may be made: three frames. */
export function minCutMs(fps: number): Ms {
  return frameMs(3, fps)
}

/** The largest frame time at or below `ms`. */
function frameAtOrBelow(ms: Ms, fps: number): Ms {
  let n = Math.floor((ms * fps) / 1000)
  while (frameMs(n, fps) > ms) {
    n -= 1
  }
  while (frameMs(n + 1, fps) <= ms) {
    n += 1
  }
  return frameMs(n, fps)
}

/** The smallest frame time at or above `ms`. */
function frameAtOrAbove(ms: Ms, fps: number): Ms {
  let n = Math.ceil((ms * fps) / 1000)
  while (frameMs(n, fps) < ms) {
    n += 1
  }
  while (frameMs(n - 1, fps) >= ms) {
    n -= 1
  }
  return frameMs(n, fps)
}

// --- layout and pixels --------------------------------------------------------------

/** The scale's bounds and default, in pixels per second; the snap distance in pixels. */
export const MIN_PPS = 4
export const MAX_PPS = 240
export const DEFAULT_PPS = 40
export const SNAP_PX = 8

/** Clips end to end: where each starts and how long the whole is. */
export type Layout = { startsMs: readonly Ms[]; totalMs: Ms }

/** The clips laid end to end, each as long as its own duration. */
export function layout(clips: readonly ClipFacts[]): Layout {
  const startsMs: Ms[] = []
  let totalMs = 0
  clips.forEach((clip, index) => {
    finitePositive(`clips[${index}].durationMs`, clip.durationMs)
    if (!Number.isInteger(clip.durationMs)) {
      throw new ModelError(`clips[${index}].durationMs must be whole milliseconds`)
    }
    startsMs.push(totalMs)
    totalMs += clip.durationMs
  })
  return { startsMs, totalMs }
}

/**
 * The clip that holds time `t`: before zero the first, at or past the total the last,
 * a boundary the later clip; null for no clips.
 */
export function clipAt(l: Layout, t: Ms): number | null {
  const n = l.startsMs.length
  if (n === 0) {
    return null
  }
  return lastAtOrBefore(l.startsMs, t, 0, n - 1) ?? 0
}

/** The last index in [lo, hi] whose start is at or before `t`, else null. */
function lastAtOrBefore(starts: readonly Ms[], t: number, lo: number, hi: number): number | null {
  if (starts[lo] > t) {
    return null
  }
  let low = lo
  let high = hi
  while (low < high) {
    const mid = (low + high + 1) >> 1
    if (starts[mid] <= t) {
      low = mid
    } else {
      high = mid - 1
    }
  }
  return low
}

/** A time as pixels from the timeline's start. */
export function timeToPx(ms: Ms, pps: number): number {
  finite('ms', ms)
  finitePositive('pps', pps)
  return (ms * pps) / 1000
}

/** Pixels from the timeline's start as a time, to the millisecond. Not clamped. */
export function pxToTime(px: number, pps: number): Ms {
  finite('px', px)
  finitePositive('pps', pps)
  return Math.round((px * 1000) / pps)
}

// --- zoom ---------------------------------------------------------------------------

/** What is on screen: the scale, how far it is scrolled, and how wide the view is. */
export type View = { pps: number; scrollLeft: number; width: number }

function checkView(v: View): void {
  finitePositive('pps', v.pps)
  finitePositive('width', v.width)
  finite('scrollLeft', v.scrollLeft)
}

/** The scale held to [MIN_PPS, MAX_PPS]. */
export function clampPps(pps: number): number {
  finitePositive('pps', pps)
  return Math.min(MAX_PPS, Math.max(MIN_PPS, pps))
}

/**
 * The view zoomed by `factor` about `anchorX` (pixels from the view's left): the time
 * under that point stays under it, and the scroll stays within the timeline.
 */
export function zoomAt(v: View, factor: number, anchorX: number, totalMs: Ms): View {
  checkView(v)
  finitePositive('factor', factor)
  finite('anchorX', anchorX)
  if (!Number.isFinite(totalMs) || totalMs < 0) {
    throw new ModelError(`totalMs must be a finite number, zero or more, got ${String(totalMs)}`)
  }
  const pps = clampPps(v.pps * factor)
  const seconds = (v.scrollLeft + anchorX) / v.pps
  const longest = Math.max(0, (totalMs * pps) / 1000 - v.width)
  const scrollLeft = Math.min(longest, Math.max(0, seconds * pps - anchorX))
  return { pps, scrollLeft, width: v.width }
}

/** The scale at which `totalMs` fills `viewWidth`; DEFAULT_PPS for no length. */
export function fitPps(totalMs: Ms, viewWidth: number): number {
  finitePositive('width', viewWidth)
  if (!Number.isFinite(totalMs) || totalMs < 0) {
    throw new ModelError(`totalMs must be a finite number, zero or more, got ${String(totalMs)}`)
  }
  return totalMs === 0 ? DEFAULT_PPS : clampPps((viewWidth * 1000) / totalMs)
}

const TICK_STEPS_MS: readonly Ms[] = [500, 1000, 2000, 5000, 10000, 30000, 60000, 300000, 600000]
const TICK_MIN_PX = 70

/** The ruler's tick spacing: the first step at least 70 px wide at this scale, else 600 s. */
export function tickStepMs(pps: number): Ms {
  finitePositive('pps', pps)
  return TICK_STEPS_MS.find((step) => (step * pps) / 1000 >= TICK_MIN_PX) ?? 600000
}

// --- windowing ----------------------------------------------------------------------

/** The view's range in milliseconds, widened by the margin. */
function visibleRange(v: View, overscanPx: number): { loMs: number; hiMs: number } {
  checkView(v)
  if (typeof overscanPx !== 'number' || !Number.isFinite(overscanPx) || overscanPx < 0) {
    throw new ModelError(`overscan must be a finite number, zero or more, got ${String(overscanPx)}`)
  }
  return {
    loMs: ((v.scrollLeft - overscanPx) * 1000) / v.pps,
    hiMs: ((v.scrollLeft + v.width + overscanPx) * 1000) / v.pps,
  }
}

/**
 * The first and last clip (inclusive) that touch the view and its margin by more than
 * an edge; null when none does. Two searches that do not visit the clips in between:
 * the cost is the same for 80 clips and for 80,000.
 */
export function visibleClips(l: Layout, v: View, overscanPx: number): [number, number] | null {
  const { loMs, hiMs } = visibleRange(v, overscanPx)
  const starts = l.startsMs
  const n = starts.length
  if (n === 0 || loMs >= l.totalMs || hiMs <= 0) {
    return null
  }
  // The first clip that ends after loMs: the one holding it (an end is the next start).
  const first = lastAtOrBefore(starts, loMs, 0, n - 1) ?? 0
  if (starts[first] >= hiMs) {
    return null
  }
  // The last clip that starts before hiMs: gallop on from `first`, then bisect.
  let reach = 1
  while (first + reach < n && starts[first + reach] < hiMs) {
    reach *= 2
  }
  let low = first + (reach >> 1)
  let high = Math.min(n - 1, first + reach - 1)
  while (low < high) {
    const mid = (low + high + 1) >> 1
    if (starts[mid] < hiMs) {
      low = mid
    } else {
      high = mid - 1
    }
  }
  return [first, low]
}

/**
 * The ruler's ticks near the view: tick `i` is at `i * stepMs`, for `first` to `last`
 * inclusive, within the timeline; `last < first` when there are none.
 */
export function visibleTicks(
  l: Layout,
  v: View,
  overscanPx: number,
): { stepMs: Ms; first: number; last: number } {
  const { loMs, hiMs } = visibleRange(v, overscanPx)
  const stepMs = tickStepMs(v.pps)
  return {
    stepMs,
    first: Math.ceil(Math.max(0, loMs) / stepMs),
    last: Math.floor(Math.min(l.totalMs, hiMs) / stepMs),
  }
}

// --- cuts ---------------------------------------------------------------------------

/** The cuts as the render joins them: clamped to the clip, sorted, overlaps merged. */
export function cutSpans(cuts: readonly ListedCut[], durationMs: Ms): Skip[] {
  return skipSpans(cuts, durationMs)
}

/** The movie's length: the clips' durations less what their cut spans cover, once. */
export function movieLengthMs(
  clips: readonly (ClipFacts & { cuts: readonly ListedCut[] })[],
): Ms {
  let total = 0
  for (const clip of clips) {
    const cut = cutSpans(clip.cuts, clip.durationMs).reduce(
      (sum, span) => sum + (span.to - span.from),
      0,
    )
    total += clip.durationMs - cut
  }
  return total
}

/**
 * One rectangle per listed cut that is not removed, keyed by its place in the list,
 * for its own span clamped to the clip. A cut past the end is drawn up to it; one
 * wholly past it, or empty, has none.
 */
export function cutRects(
  cuts: readonly ListedCut[],
  durationMs: Ms,
  pps: number,
): { index: number; left: number; width: number }[] {
  finitePositive('pps', pps)
  const rects: { index: number; left: number; width: number }[] = []
  cuts.forEach((cut, index) => {
    if (cut.removed === true) {
      return
    }
    const from = Math.max(0, toMs(cut.in))
    const to = Math.min(durationMs, toMs(cut.out))
    if (to > from) {
      rects.push({ index, left: timeToPx(from, pps), width: timeToPx(to - from, pps) })
    }
  })
  return rects
}

/**
 * Each cut's number from 1 in order of start (a tie by end, then by place in the
 * list), null for a removed one: no two cuts of a clip share a number.
 */
export function cutOrdinals(cuts: readonly ListedCut[]): (number | null)[] {
  const ordinals: (number | null)[] = cuts.map(() => null)
  cuts
    .map((cut, index) => ({ index, from: toMs(cut.in), to: toMs(cut.out), removed: cut.removed }))
    .filter((cut) => cut.removed !== true)
    .sort((a, b) => a.from - b.from || a.to - b.to || a.index - b.index)
    .forEach((cut, rank) => {
      ordinals[cut.index] = rank + 1
    })
  return ordinals
}

// --- trim and snap ------------------------------------------------------------------

export type Edge = 'in' | 'out'

type Bounds = { from: Ms; to: Ms }

function boundsOf(cuts: readonly ListedCut[], index: number): Bounds {
  if (!Number.isInteger(index) || index < 0 || index >= cuts.length) {
    throw new ModelError(`cut ${String(index)} is not in a list of ${cuts.length}`)
  }
  return { from: toMs(cuts[index].in), to: toMs(cuts[index].out) }
}

/**
 * The lowest and highest time a cut's edge may take. The neighbours are the other
 * cuts, not removed, that do not overlap this one (touching is not overlap). A cut
 * stays three frames long, measured from the opposite edge and held to the frame
 * grid. The range always holds the edge's current value, so a cut already shorter,
 * or one overlapping a neighbour as `reel.yaml` has it, keeps its edge and the
 * range is never inverted.
 */
export function trimLimits(
  cuts: readonly ListedCut[],
  index: number,
  edge: Edge,
  f: ClipFacts,
): [Ms, Ms] {
  checkFacts(f)
  const own = boundsOf(cuts, index)
  const neighbours = cuts
    .filter((cut, at) => at !== index && cut.removed !== true)
    .map((cut) => ({ from: toMs(cut.in), to: toMs(cut.out) }))
  const short = minCutMs(f.fps)
  if (edge === 'in') {
    let lowest = 0
    for (const span of neighbours) {
      // Not overlapping, and before: ends at or before this cut's start.
      if (span.to <= own.from) {
        lowest = Math.max(lowest, span.to)
      }
    }
    const highest = frameAtOrBelow(Math.min(own.to, f.durationMs) - short, f.fps)
    return [Math.min(lowest, own.from), Math.max(highest, own.from)]
  }
  let highest = f.durationMs
  for (const span of neighbours) {
    // Not overlapping, and after: starts at or after this cut's end.
    if (span.from >= own.to) {
      highest = Math.min(highest, span.from)
    }
  }
  const lowest = frameAtOrAbove(Math.max(own.from, 0) + short, f.fps)
  return [Math.min(lowest, own.to), Math.max(highest, own.to)]
}

/**
 * The candidate nearest `ms` within SNAP_PX at this scale; two equally near give the
 * earlier, whatever the order of the list; none gives a null target.
 */
export function snapTo(
  ms: Ms,
  candidates: readonly Ms[],
  pps: number,
): { ms: Ms; target: Ms | null } {
  finite('ms', ms)
  finitePositive('pps', pps)
  let target: Ms | null = null
  let nearest = Infinity
  for (const candidate of candidates) {
    const distance = Math.abs(candidate - ms)
    if ((distance * pps) / 1000 > SNAP_PX) {
      continue
    }
    if (distance < nearest || (distance === nearest && target !== null && candidate < target)) {
      nearest = distance
      target = candidate
    }
  }
  return target === null ? { ms, target: null } : { ms: target, target }
}

/**
 * The places a trim snaps to, sorted and without repeats, inside the clip: its start
 * and end, every other cut's edges (not removed), the playhead's time in this clip
 * (null when it is in another), and the caller's extra points.
 */
export function snapCandidates(
  cuts: readonly ListedCut[],
  index: number,
  f: ClipFacts,
  playheadMs: Ms | null,
  extra: readonly Ms[],
): Ms[] {
  checkFacts(f)
  boundsOf(cuts, index)
  const found: Ms[] = [0, f.durationMs]
  cuts.forEach((cut, at) => {
    if (at !== index && cut.removed !== true) {
      found.push(toMs(cut.in), toMs(cut.out))
    }
  })
  if (playheadMs !== null) {
    found.push(playheadMs)
  }
  found.push(...extra)
  return [...new Set(found.filter((ms) => Number.isFinite(ms) && ms >= 0 && ms <= f.durationMs))].sort(
    (a, b) => a - b,
  )
}

/**
 * Where an edge dragged to `wantedMs` lands: on the nearest candidate within reach,
 * else on the nearest frame, then held to the trim limits (a limit is returned as it
 * is, not moved to the grid). `snappedTo` is a candidate only when the edge arrived
 * on it, so a snap line is never shown where the handle did not go. An edge moved to the place it holds stays there.
 */
export function trimEdge(
  cuts: readonly ListedCut[],
  index: number,
  edge: Edge,
  wantedMs: Ms,
  f: ClipFacts,
  pps: number,
  candidates: readonly Ms[],
): { ms: Ms; snappedTo: Ms | null } {
  checkFacts(f)
  finite('wantedMs', wantedMs)
  finitePositive('pps', pps)
  const own = boundsOf(cuts, index)
  const current = edge === 'in' ? own.from : own.to
  if (wantedMs === current) {
    return { ms: current, snappedTo: candidates.includes(current) ? current : null }
  }
  const [lowest, highest] = trimLimits(cuts, index, edge, f)
  const snapped = snapTo(wantedMs, candidates, pps)
  const placed = snapped.target === null ? nearestFrame(wantedMs, f.fps) : snapped.ms
  const ms = Math.min(highest, Math.max(lowest, placed))
  return { ms, snappedTo: candidates.includes(ms) ? ms : null }
}
