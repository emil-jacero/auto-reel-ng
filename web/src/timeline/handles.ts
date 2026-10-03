import { frameMs, nearestFrame } from './model.ts'
import type { Ms } from './model.ts'

/*
 * The pure parts of a trim handle that the model does not have (D-20): what a key does
 * to an edge, where Enter puts it, which handle a finger on two overlapping areas means
 * (and when a mouse press never reached the handle as a pointer press), and what a snap
 * says. In whole milliseconds like `model.ts`, whose frame grid it uses; no DOM and no
 * React, so `npm test` runs it. (Not `trim.ts`: `trim.test.ts` is the
 * model's own trim functions.)
 */

const SECOND_MS = 1000
const PAGE_MS = 5000

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

/** The smallest frame time strictly above `ms`. */
function frameAfter(ms: Ms, fps: number): Ms {
  const below = frameAtOrBelow(ms, fps)
  let n = Math.round((below * fps) / 1000)
  while (frameMs(n, fps) <= ms) {
    n += 1
  }
  return frameMs(n, fps)
}

/** The largest frame time strictly below `ms`. */
function frameBefore(ms: Ms, fps: number): Ms {
  const below = frameAtOrBelow(ms, fps)
  if (below < ms) {
    return below
  }
  let n = Math.round((below * fps) / 1000) - 1
  while (frameMs(n, fps) >= ms) {
    n -= 1
  }
  return frameMs(n, fps)
}

function within(ms: Ms, range: readonly [Ms, Ms]): Ms {
  return Math.min(range[1], Math.max(range[0], ms))
}

/**
 * Where a key puts an edge now at `nowMs`, held to `range` (the handle's limits, which
 * hold `nowMs`), or null for a key that is not a handle's own.
 *
 * - Left and Right: one frame of the clip's rate; an edge off the grid (a typed time)
 *   goes to the nearest frame in that direction.
 * - With Shift: one second; Page Down and Page Up: five seconds; the result is the
 *   nearest frame.
 * - Home and End: the range's ends, which the model keeps on the frame grid.
 *
 * A key at a limit returns the limit, which is `nowMs`.
 */
export function stepEdge(
  key: string,
  shift: boolean,
  nowMs: Ms,
  range: readonly [Ms, Ms],
  fps: number,
): Ms | null {
  switch (key) {
    case 'ArrowLeft':
      return within(
        shift ? nearestFrame(nowMs - SECOND_MS, fps) : frameBefore(nowMs, fps),
        range,
      )
    case 'ArrowRight':
      return within(shift ? nearestFrame(nowMs + SECOND_MS, fps) : frameAfter(nowMs, fps), range)
    case 'PageDown':
      return within(nearestFrame(nowMs - PAGE_MS, fps), range)
    case 'PageUp':
      return within(nearestFrame(nowMs + PAGE_MS, fps), range)
    case 'Home':
      return range[0]
    case 'End':
      return range[1]
    default:
      return null
  }
}

/**
 * Enter: the edge at the playhead. `playheadMs` is the playhead's time in this clip (null
 * when it is in another); the clip's end counts as inside it. The nearest frame, held to
 * the handle's range; anything else is refused.
 */
export function atPlayhead(
  playheadMs: Ms | null,
  clipDurationMs: Ms,
  range: readonly [Ms, Ms],
  fps: number,
): { ms: Ms } | { refused: 'not-in-clip' } {
  if (playheadMs === null || playheadMs < 0 || playheadMs > clipDurationMs) {
    return { refused: 'not-in-clip' }
  }
  return { ms: within(nearestFrame(playheadMs, fps), range) }
}

/**
 * Which of overlapping handle areas a press belongs to: among the handles whose edge lies
 * within `reachPx` of the press, the nearest; of two equally near, the earlier in time
 * (the smaller `px`). Null when none is in reach.
 */
export function nearestHandle(
  pressPx: number,
  handles: readonly { id: string; px: number }[],
  reachPx: number,
): string | null {
  let best: { id: string; px: number } | null = null
  let distance = Infinity
  for (const handle of handles) {
    const d = Math.abs(handle.px - pressPx)
    if (d > reachPx) {
      continue
    }
    if (d < distance || (d === distance && best !== null && handle.px < best.px)) {
      best = handle
      distance = d
    }
  }
  return best === null ? null : best.id
}

/**
 * Whether a `mousedown` is a mouse press that arrived with no pointer events (Firefox
 * under touch emulation delivers `mousedown`, `mouseup` and `click` alone): the main
 * button, and no `pointerdown` since the last pointer sequence ended. Such a press never
 * reaches the handle's press handling, so the browser focuses the handle under the
 * pointer, and that handle's focus would select its cut; the caller hands it over by
 * position, as a pointer press is. A `mousedown` that follows a `pointerdown` still in
 * progress (an ordinary mouse press, whose pointer press already ran) is not handed over.
 * Where pointer events exist, the touch tap's compatibility `mousedown` comes after its
 * `pointerup`, so it passes this test too: it hands over to the handle the pointer press
 * already took (the same `nearestHandle` winner), which is idempotent.
 */
export function bareMousePress(pointerSeen: boolean, button: number): boolean {
  return !pointerSeen && button === 0
}

/** What a drag can snap to, for words: the playhead, the clip, and the clip's other cuts. */
export type SnapContext = {
  /** The playhead's time in this clip; null when it is in another. */
  playheadMs: Ms | null
  durationMs: Ms
  /** The other cuts of the clip, by the Cuts panel's number. */
  others: readonly { n: number; inMs: Ms; outMs: Ms }[]
}

/**
 * Says what the edge snapped to: the playhead first, then the clip's start or end, then a
 * cut's edge by the panel's number (`cut 2 start`). A place that is none of these (the
 * model only snaps to these) gets no words.
 */
export function snapWords(target: Ms, ctx: SnapContext): string {
  if (ctx.playheadMs !== null && ctx.playheadMs === target) {
    return 'Snapped to the playhead'
  }
  if (target === 0) {
    return 'Snapped to the clip’s start'
  }
  if (target === ctx.durationMs) {
    return 'Snapped to the clip’s end'
  }
  for (const other of ctx.others) {
    if (other.inMs === target) {
      return `Snapped to cut ${other.n} start`
    }
    if (other.outMs === target) {
      return `Snapped to cut ${other.n} end`
    }
  }
  return ''
}

/** What a key does to a focused handle. */
export type KeyOutcome =
  /** Not a handle's key: left to the browser (Tab, typing). */
  | { kind: 'ignore' }
  /** A handle's key that leaves the edge where it is (at a limit): nothing to write. */
  | { kind: 'stay' }
  /** Move the edge here; `stopped` when Enter could not reach the playhead's frame. */
  | { kind: 'set'; ms: Ms; stopped: boolean }
  /** Enter with the playhead in another clip: nothing changes, and it is said. */
  | { kind: 'refused' }

/**
 * A key on a focused handle, whole: the steps of `stepEdge`, and Enter at the playhead
 * (`atPlayhead`). The caller writes `set` once and says `refused` and a `stopped` Enter.
 */
export function keyOutcome(
  key: string,
  shift: boolean,
  nowMs: Ms,
  range: readonly [Ms, Ms],
  fps: number,
  clipDurationMs: Ms,
  playheadMs: Ms | null,
): KeyOutcome {
  if (key === 'Enter') {
    const placed = atPlayhead(playheadMs, clipDurationMs, range, fps)
    if ('refused' in placed) {
      return { kind: 'refused' }
    }
    const wanted = playheadMs as Ms
    const stopped = placed.ms !== wanted && placed.ms !== nearestFrame(wanted, fps)
    return placed.ms === nowMs && !stopped
      ? { kind: 'stay' }
      : { kind: 'set', ms: placed.ms, stopped }
  }
  const next = stepEdge(key, shift, nowMs, range, fps)
  if (next === null) {
    return { kind: 'ignore' }
  }
  return next === nowMs ? { kind: 'stay' } : { kind: 'set', ms: next, stopped: false }
}
