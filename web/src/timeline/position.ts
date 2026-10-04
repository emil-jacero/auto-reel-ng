import { clipAt, frameMs } from './model.ts'
import type { Layout, Ms } from './model.ts'

/*
 * Where the playhead is and how it moves (D-20): a clip and a time in it, both on the
 * clip's frame grid, so a step is a whole frame and never skips one at a boundary.
 * Pure, in whole milliseconds like `model.ts`, whose frame times it uses.
 */

/**
 * The playhead inside a black title card (`timeline-plays-cards`): the card's chapter (index
 * and saved name), the time elapsed in it and its length. The `clip`/`ms` of such a position
 * are the card's anchor clip and 0, so every consumer of clip time is unchanged.
 */
export type CardAt = { chapter: number; name: string; ms: Ms; lengthMs: Ms }

/** The playhead: the shown clip's index and the time in that clip, or a place in a card. */
export type Position = { clip: number; ms: Ms; card?: CardAt | null }

type Timed = { durationMs: Ms; fps: number }

/** The index of the clip's last frame: the largest whose time lies before the clip's end. */
export function lastFrame(clip: Timed): number {
  let n = Math.max(0, Math.ceil((clip.durationMs * clip.fps) / 1000) - 1)
  while (n > 0 && frameMs(n, clip.fps) >= clip.durationMs) {
    n -= 1
  }
  while (frameMs(n + 1, clip.fps) < clip.durationMs) {
    n += 1
  }
  return n
}

/** The index of the frame nearest `ms`, held to the clip's frames. */
function frameIndex(clip: Timed, ms: Ms): number {
  return Math.min(lastFrame(clip), Math.max(0, Math.round((ms * clip.fps) / 1000)))
}

/**
 * `p` as far as the clips allow: the page can read fewer or shorter clips than the
 * playhead was made for, and what draws it must not trip on that before the playhead is
 * moved. A clip that is no longer there means the start (where the playhead goes next);
 * a time past the clip's end is held to the end.
 */
export function clampPosition(
  clips: readonly { facts: { durationMs: Ms } }[],
  p: Position,
): Position {
  if (p.clip < 0 || p.clip >= clips.length) {
    return startPosition()
  }
  const end = clips[p.clip].facts.durationMs
  return p.ms > end ? { clip: p.clip, ms: end } : p
}

/** The time of the last frame of a clip. */
export function lastFrameMs(clip: Timed): Ms {
  return frameMs(lastFrame(clip), clip.fps)
}

/** `ms` held to the clip's frame grid: its nearest frame, and no later than the last. */
export function onGrid(clip: Timed, ms: Ms): Ms {
  return frameMs(frameIndex(clip, ms), clip.fps)
}

/**
 * The timeline's time of a position. With `l` the track's layout (the clips with the black
 * cards between them), a place in a card is the card's start plus the time in it.
 */
export function globalMs(l: Layout, p: Position): Ms {
  const card = p.card
  return card == null
    ? l.startsMs[p.clip] + p.ms
    : // A render between a layout change (the cards switched off) and the playhead being put back
      // reads a card position the layout no longer has: never a time before zero.
      Math.max(0, l.startsMs[p.clip] - card.lengthMs + card.ms)
}

/** Whether two positions are the same place. */
export function samePosition(a: Position, b: Position): boolean {
  const x = a.card ?? null
  const y = b.card ?? null
  return (
    a.clip === b.clip &&
    a.ms === b.ms &&
    (x === y ||
      (x !== null && y !== null && x.chapter === y.chapter && x.ms === y.ms && x.lengthMs === y.lengthMs))
  )
}

/**
 * The position of a time on the whole timeline: the clip that holds it (a boundary is
 * the later clip's start), the nearest frame in it. Before zero is the first frame, past
 * the end the last.
 */
export function positionAt(l: Layout, clips: readonly Timed[], t: Ms): Position {
  const clip = clipAt(l, Math.min(Math.max(0, t), Math.max(0, l.totalMs - 1))) ?? 0
  return { clip, ms: onGrid(clips[clip], t - l.startsMs[clip]) }
}

/**
 * The position `n` frames from `p` (negative: before it), across clip boundaries: the
 * frame after a clip's last is the next clip's first. Held to the first and the last frame.
 */
export function stepFrames(clips: readonly Timed[], p: Position, n: number): Position {
  let clip = p.clip
  let index = frameIndex(clips[clip], p.ms) + n
  while (index > lastFrame(clips[clip]) && clip < clips.length - 1) {
    index -= lastFrame(clips[clip]) + 1
    clip += 1
  }
  while (index < 0 && clip > 0) {
    clip -= 1
    index += lastFrame(clips[clip]) + 1
  }
  index = Math.min(lastFrame(clips[clip]), Math.max(0, index))
  return { clip, ms: frameMs(index, clips[clip].fps) }
}

/** The position `delta` ms from `p` on the whole timeline, held to the timeline. */
export function stepMs(l: Layout, clips: readonly Timed[], p: Position, delta: Ms): Position {
  return positionAt(l, clips, globalMs(l, p) + delta)
}

/** The first frame of the timeline. */
export function startPosition(): Position {
  return { clip: 0, ms: 0 }
}

/** The last frame of the timeline. */
export function endPosition(clips: readonly Timed[]): Position {
  const clip = clips.length - 1
  return { clip, ms: lastFrameMs(clips[clip]) }
}

/**
 * The time to give a `<video>` to show the frame at `ms` of a clip of rate `fps`: a
 * quarter of a frame in. Frame times are rounded to whole ms, and at 29.97 fps frame 1
 * is 33.37 ms, so seeking to its rounded 33 ms can show frame 0; a quarter frame in is
 * inside the frame at every rate and never reaches the next.
 */
export function seekSeconds(ms: Ms, fps: number): number {
  return (ms + 250 / fps) / 1000
}
