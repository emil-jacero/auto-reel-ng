import { clipAt, clipToLayout, emptyExtent, extentOf, frameMs } from './model.ts'
import type { Extent, Layout, Ms } from './model.ts'

/*
 * Where the playhead is and how it moves (D-20): a clip and a time in it, both on the
 * clip's frame grid, so a step is a whole frame and never skips one at a boundary.
 * Pure, in whole milliseconds like `model.ts`, whose frame times it uses.
 *
 * The playhead lives on **kept frames** (`timeline-ripple-layout`): a clip given with its kept
 * extent (`inMs`/`outMs`) offers the frames from the first at or after `inMs` to the last
 * before `outMs`; a clip without one offers all its frames. A clip that offers none is
 * passed over.
 */

/**
 * The playhead inside a black title card (`timeline-plays-cards`): the card's chapter (index
 * and saved name), the time elapsed in it and its length. The `clip`/`ms` of such a position
 * are the card's anchor clip and 0, so every consumer of clip time is unchanged.
 */
export type CardAt = { chapter: number; name: string; ms: Ms; lengthMs: Ms }

/** The playhead: the shown clip's index and the time in that clip, or a place in a card. */
export type Position = { clip: number; ms: Ms; card?: CardAt | null }

/** A clip's length and rate, and its kept extent when it has edge cuts. */
export type Timed = { durationMs: Ms; fps: number; inMs?: Ms; outMs?: Ms }

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

/** The index of the first frame at or after `ms`. */
function frameAtOrAbove(clip: Timed, ms: Ms): number {
  let n = Math.max(0, Math.ceil((ms * clip.fps) / 1000))
  while (frameMs(n, clip.fps) < ms) {
    n += 1
  }
  while (n > 0 && frameMs(n - 1, clip.fps) >= ms) {
    n -= 1
  }
  return n
}

/** The index of the first kept frame: the first frame at or after the kept start. */
export function firstKeptFrame(clip: Timed): number {
  return frameAtOrAbove(clip, extentOf(clip).inMs)
}

/**
 * The index of the last kept frame: the last frame before the kept end (before the trailing
 * cut's start, else the clip's last frame).
 */
export function lastKeptFrame(clip: Timed): number {
  const { outMs } = extentOf(clip)
  return Math.min(lastFrame(clip), frameAtOrAbove(clip, outMs) - 1)
}

/** Whether a clip has a frame to show: its extent is not empty and holds one. */
export function hasKeptFrame(clip: Timed): boolean {
  return !emptyExtent(extentOf(clip)) && firstKeptFrame(clip) <= lastKeptFrame(clip)
}

/** The time of a clip's first kept frame. */
export function firstKeptMs(clip: Timed): Ms {
  return frameMs(firstKeptFrame(clip), clip.fps)
}

/** The time of a clip's last kept frame. */
export function lastKeptMs(clip: Timed): Ms {
  return frameMs(lastKeptFrame(clip), clip.fps)
}

/** The index of the frame nearest `ms`, held to the clip's kept frames. */
function frameIndex(clip: Timed, ms: Ms): number {
  return Math.min(lastKeptFrame(clip), Math.max(firstKeptFrame(clip), Math.round((ms * clip.fps) / 1000)))
}

/** The nearest clip from `clip` (itself first, then later, then earlier) that has a kept frame; null for none. */
function withFrames(clips: readonly Timed[], clip: number): number | null {
  for (let at = clip; at < clips.length; at += 1) {
    if (hasKeptFrame(clips[at])) {
      return at
    }
  }
  for (let at = clip - 1; at >= 0; at -= 1) {
    if (hasKeptFrame(clips[at])) {
      return at
    }
  }
  return null
}

/** The position nearest `ms` in a clip held to its kept frames (a time no longer kept goes to the nearest kept frame). */
export function keptPosition(clips: readonly Timed[], clip: number, ms: Ms): Position {
  const at = withFrames(clips, clip)
  if (at === null) {
    return { clip, ms: 0 }
  }
  if (at !== clip) {
    return { clip: at, ms: at > clip ? firstKeptMs(clips[at]) : lastKeptMs(clips[at]) }
  }
  return { clip, ms: frameMs(frameIndex(clips[clip], ms), clips[clip].fps) }
}

/**
 * `p` as far as the clips allow: the page can read fewer or shorter clips than the
 * playhead was made for, and what draws it must not trip on that before the playhead is
 * moved. A clip that is no longer there means the start (where the playhead goes next);
 * a time past the clip's end is held to the end; a time no longer kept (in a leading or a
 * trailing cut) goes to the nearest kept frame of its clip.
 */
export function clampPosition(
  clips: readonly { facts: Timed; kept?: Extent }[],
  p: Position,
): Position {
  if (p.clip < 0 || p.clip >= clips.length) {
    return startPosition()
  }
  const clip = clips[p.clip]
  if (p.card != null) {
    return p
  }
  const timed = timedOf(clip)
  if (timed.inMs !== undefined && timed.outMs !== undefined) {
    const trailing = timed.outMs < timed.durationMs
    if (p.ms < timed.inMs || (trailing && p.ms >= timed.outMs) || !hasKeptFrame(timed)) {
      return keptPosition(
        clips.map((c) => timedOf(c)),
        p.clip,
        p.ms,
      )
    }
  }
  const end = timed.durationMs
  return p.ms > end ? { clip: p.clip, ms: end } : p
}

/** A clip's timing with its kept extent, from a track clip (`facts` and `kept`). */
export function timedOf(clip: { facts: Timed; kept?: Extent }): Timed {
  return clip.kept === undefined ? clip.facts : { ...clip.facts, ...clip.kept }
}

/** The time of the last frame of a clip. */
export function lastFrameMs(clip: Timed): Ms {
  return frameMs(lastFrame(clip), clip.fps)
}

/** `ms` held to the clip's frame grid: its nearest frame, held to its kept frames. */
export function onGrid(clip: Timed, ms: Ms): Ms {
  return frameMs(frameIndex(clip, ms), clip.fps)
}

/**
 * The timeline's time of a position: its clip's start plus the time less the kept start.
 * With `l` the track's layout (the clips with the black cards between them), a place in a
 * card is the card's start plus the time in it.
 */
export function globalMs(l: Layout, p: Position): Ms {
  const card = p.card
  return card == null
    ? clipToLayout(l, p.clip, p.ms)
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
 * the later clip's start), the nearest kept frame in it. Before zero is the first kept
 * frame, past the end the last; a clip with no kept frame is passed over to the next that has one.
 */
export function positionAt(l: Layout, clips: readonly Timed[], t: Ms): Position {
  const clip = clipAt(l, Math.min(Math.max(0, t), Math.max(0, l.totalMs - 1))) ?? 0
  return keptPosition(clips, clip, t - clipToLayout(l, clip, 0))
}

/**
 * The position `n` frames from `p` (negative: before it), across clip boundaries, on kept
 * frames: the frame after a clip's last kept frame is the next clip's first kept frame, and a
 * clip with none is passed over. Held to the first and the last kept frame.
 */
export function stepFrames(clips: readonly Timed[], p: Position, n: number): Position {
  const start = keptPosition(clips, p.clip, p.ms)
  let clip = start.clip
  if (!hasKeptFrame(clips[clip])) {
    return start
  }
  let index = frameIndex(clips[clip], start.ms) + n
  while (index > lastKeptFrame(clips[clip])) {
    const next = nextWithFrames(clips, clip, 1)
    if (next === null) {
      break
    }
    index = firstKeptFrame(clips[next]) + (index - lastKeptFrame(clips[clip]) - 1)
    clip = next
  }
  while (index < firstKeptFrame(clips[clip])) {
    const previous = nextWithFrames(clips, clip, -1)
    if (previous === null) {
      break
    }
    index = lastKeptFrame(clips[previous]) - (firstKeptFrame(clips[clip]) - index - 1)
    clip = previous
  }
  index = Math.min(lastKeptFrame(clips[clip]), Math.max(firstKeptFrame(clips[clip]), index))
  return { clip, ms: frameMs(index, clips[clip].fps) }
}

/** The next clip after (`dir` 1) or before (-1) `clip` that has a kept frame; null for none. */
function nextWithFrames(clips: readonly Timed[], clip: number, dir: 1 | -1): number | null {
  for (let at = clip + dir; at >= 0 && at < clips.length; at += dir) {
    if (hasKeptFrame(clips[at])) {
      return at
    }
  }
  return null
}

/** The position `delta` ms from `p` on the whole timeline, held to the timeline. */
export function stepMs(l: Layout, clips: readonly Timed[], p: Position, delta: Ms): Position {
  return positionAt(l, clips, globalMs(l, p) + delta)
}

/** The first kept frame of the timeline (`{0, 0}` without clips). */
export function startPosition(clips: readonly Timed[] = []): Position {
  const clip = clips.length === 0 ? null : withFrames(clips, 0)
  return clip === null ? { clip: 0, ms: 0 } : { clip, ms: firstKeptMs(clips[clip]) }
}

/** The last kept frame of the timeline. */
export function endPosition(clips: readonly Timed[]): Position {
  const clip = withFrames(clips, clips.length - 1) ?? clips.length - 1
  return { clip, ms: hasKeptFrame(clips[clip]) ? lastKeptMs(clips[clip]) : lastFrameMs(clips[clip]) }
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
