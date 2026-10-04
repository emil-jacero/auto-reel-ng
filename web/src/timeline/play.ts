import { clipTimeAt } from './cards.ts'
import type { CardMap, Placement } from './cards.ts'
import { keptExtent, ModelError } from './model.ts'
import type { Layout, Ms } from './model.ts'
import { endPosition, firstKeptMs, positionAt, stepFrames } from './position.ts'
import type { Position, Timed } from './position.ts'

/*
 * Playing a movie of clips and cards on one clock (D-20, `timeline-plays-cards`): the play
 * order as stages in track time, a position on the track and its track time, what is shown at
 * a position (a card and its opacity from the fades), the hand-over from a card to its clip,
 * the card clock and the steps of the keys across cards. Pure: no DOM, no React, no network, no
 * media read, and no clock of its own: real time is passed in. Clip time stays the one time of
 * cuts, handles and marks; a place in a black card holds the card's anchor clip at 0.
 */

/** The engine's default fades (`render/title/config.py`): 2 s in, 2 s out, clamped together. */
export const DEFAULT_FADE_MS = 2000

/** A step inside a card when the movie's output rate is not known to the page. */
export const CARD_STEP_MS = 100

/** A card's length, refused when it is not a finite number above zero. */
function lengthOf(what: string, lengthMs: Ms): Ms {
  if (typeof lengthMs !== 'number' || !Number.isFinite(lengthMs) || lengthMs <= 0) {
    throw new ModelError(`${what} must have a length above zero, got ${String(lengthMs)}`)
  }
  return lengthMs
}

// --- the stages -------------------------------------------------------------------------

export type Stage =
  | { kind: 'card'; chapter: number; clip: number; startMs: Ms; lengthMs: Ms }
  | { kind: 'clip'; clip: number; startMs: Ms; lengthMs: Ms }

/**
 * The play order on the track: for each shown clip, its black card (if its chapter has one
 * there) and then the clip, as long as its kept extent. `lay` is the clips' layout without cards; the stage times add up to
 * the track's total.
 */
export function stagesOf(map: CardMap, lay: Layout): Stage[] {
  const stages: Stage[] = []
  let at = 0
  lay.startsMs.forEach((start, clip) => {
    const gap = map.gaps.find((g) => g.clip === clip)
    if (gap !== undefined) {
      stages.push({ kind: 'card', chapter: gap.chapter, clip, startMs: at, lengthMs: gap.lengthMs })
      at += gap.lengthMs
    }
    const end = lay.startsMs[clip + 1] ?? lay.totalMs
    stages.push({ kind: 'clip', clip, startMs: at, lengthMs: end - start })
    at += end - start
  })
  return stages
}

/**
 * The position at a track time (cards counted): a card's elapsed time, or a clip's time on its
 * frame grid. A boundary is the later stage's start, before zero the first instant and past the
 * end the last frame. `names` are the chapters' saved names, by index.
 */
export function positionOnTrack(
  map: CardMap,
  lay: Layout,
  clips: readonly Timed[],
  names: readonly string[],
  trackMs: Ms,
): Position {
  const at = clipTimeAt(map, Math.max(0, trackMs))
  if (at.kind === 'clip') {
    return positionAt(lay, clips, at.ms)
  }
  const gap = map.gaps[at.index]
  return {
    clip: gap.clip,
    ms: 0,
    card: {
      chapter: gap.chapter,
      name: names[gap.chapter] ?? '',
      ms: Math.max(0, Math.round(trackMs) - (gap.atMs + gap.beforeMs)),
      lengthMs: gap.lengthMs,
    },
  }
}

/** The first instant of the track: the opening card when it is black, else the first frame. */
export function trackStart(
  map: CardMap,
  lay: Layout,
  clips: readonly Timed[],
  names: readonly string[],
): Position {
  return positionOnTrack(map, lay, clips, names, 0)
}

// --- what is shown ----------------------------------------------------------------------

/**
 * The fades of a card `lengthMs` long: the defaults, scaled down together so that their sum
 * does not exceed the length (as the render clamps them).
 */
export function fadesOf(lengthMs: Ms): { inMs: Ms; outMs: Ms } {
  const length = lengthOf('a title card', lengthMs)
  const scale = Math.min(1, length / (2 * DEFAULT_FADE_MS))
  return { inMs: DEFAULT_FADE_MS * scale, outMs: DEFAULT_FADE_MS * scale }
}

/** A card's opacity `elapsedMs` into its `lengthMs`: 0 at the start, 1 between the fades, 0 at the end. */
export function opacityAt(elapsedMs: Ms, lengthMs: Ms): number {
  const { inMs, outMs } = fadesOf(lengthMs)
  const at = Math.min(Math.max(elapsedMs, 0), lengthMs)
  const fadeIn = inMs === 0 ? 1 : at / inMs
  const fadeOut = outMs === 0 ? 1 : (lengthMs - at) / outMs
  return Math.min(1, fadeIn, fadeOut)
}

export type Shown =
  | { kind: 'clip' }
  | { kind: 'black'; chapter: number; opacity: number }
  | { kind: 'video'; chapter: number; opacity: number }

/**
 * What the picture shows at `p`: a black card (and its opacity), or the clip with the video
 * card, if any, whose window holds the clip time. A video card's window is from the start of
 * the first kept span for the card's width (held to the footage).
 */
export function shownAt(p: Position, placements: readonly Placement[]): Shown {
  if (p.card != null) {
    return { kind: 'black', chapter: p.card.chapter, opacity: opacityAt(p.card.ms, p.card.lengthMs) }
  }
  for (const place of placements) {
    if (
      place.kind === 'anchored' &&
      place.background === 'video' &&
      place.clip === p.clip &&
      p.ms >= place.atMs &&
      p.ms < place.atMs + place.widthMs
    ) {
      return { kind: 'video', chapter: place.chapter, opacity: opacityAt(p.ms - place.atMs, place.widthMs) }
    }
  }
  return { kind: 'clip' }
}

// --- the hand-over ----------------------------------------------------------------------

/** What the hand-over needs of a clip: its length and its joined cut spans. */
export type HandOverClip = { durationMs: Ms; spans: readonly { from: Ms; to: Ms }[] }

/**
 * The time of the anchor clip that follows its black card: its kept start (`keptExtent`: the
 * end of a cut that begins at zero, else zero). A clip that is gone, or keeps nothing, gives 0.
 */
export function handOverMs(clip: HandOverClip | undefined): Ms {
  return clip === undefined ? 0 : keptExtent(clip.spans, clip.durationMs).inMs
}

/** What the video is asked to show while a position is a card: the anchor clip at its first kept time. */
export function videoTarget(
  p: Position,
  clipOf: (clip: number) => HandOverClip | undefined,
): { clip: number; ms: Ms } {
  return p.card == null ? { clip: p.clip, ms: p.ms } : { clip: p.clip, ms: handOverMs(clipOf(p.clip)) }
}

/**
 * Whether a card whose time is up may hand over to its clip now: the clip is loaded and its
 * seek has finished. If not, the card stays on its last frame.
 */
export function handOverReady(s: { busy: boolean; loadedClip: number | null; anchor: number }): boolean {
  return !s.busy && s.loadedClip === s.anchor
}

// --- the card clock ---------------------------------------------------------------------

export type CardClock = {
  /** Begin (or go on) at `fromMs` of a card `lengthMs` long, `nowMs` being real time. */
  start(nowMs: number, fromMs: Ms, lengthMs: Ms): void
  /** Stop at `nowMs`; the time reached. */
  stop(nowMs: number): Ms
  /** The time reached at `nowMs`, held to the length, and whether the card is over. */
  read(nowMs: number): { ms: Ms; due: boolean }
  running(): boolean
}

/**
 * The card clock: elapsed real time, not a count of frames, so a slow frame does not stretch
 * the card. It reads no clock itself.
 */
export function createCardClock(): CardClock {
  let base = 0
  let startedAt = 0
  let length = 1
  let on = false
  const reach = (nowMs: number): number => base + (on ? Math.max(0, nowMs - startedAt) : 0)
  return {
    start(nowMs, fromMs, lengthMs) {
      length = lengthOf('a title card', lengthMs)
      base = Math.min(Math.max(fromMs, 0), length)
      startedAt = nowMs
      on = true
    },
    stop(nowMs) {
      base = Math.min(reach(nowMs), length)
      on = false
      return base
    },
    read(nowMs) {
      const elapsed = reach(nowMs)
      return { ms: Math.min(elapsed, length), due: elapsed >= length }
    },
    running: () => on,
  }
}

// --- steps across cards -----------------------------------------------------------------

/**
 * The position `n` frames from `p` on the track with cards: a frame step into a card from the
 * clip before it lands on the card's first instant, from a card's end on the clip's first
 * kept frame; within a card a step is `CARD_STEP_MS` (the page does not know the movie's rate).
 * `clips` carry their kept extents, so steps land on kept frames only.
 */
export function stepFramesOnTrack(
  map: CardMap,
  clips: readonly Timed[],
  names: readonly string[],
  p: Position,
  n: number,
): Position {
  const cardOf = (clip: number) => map.gaps.find((g) => g.clip === clip)
  if (p.card != null) {
    const ms = p.card.ms + n * CARD_STEP_MS
    if (ms >= p.card.lengthMs) {
      return { clip: p.clip, ms: firstKeptMs(clips[p.clip]) }
    }
    if (ms < 0) {
      return p.clip === 0 ? { ...p, card: { ...p.card, ms: 0 } } : endPositionOf(clips, p.clip - 1)
    }
    return { ...p, card: { ...p.card, ms } }
  }
  const next = stepFrames(clips, p, n)
  if (next.clip > p.clip && n > 0) {
    const gap = cardOf(next.clip)
    if (gap !== undefined) {
      return { clip: gap.clip, ms: 0, card: { chapter: gap.chapter, name: names[gap.chapter] ?? '', ms: 0, lengthMs: gap.lengthMs } }
    }
  }
  if (next.clip < p.clip && n < 0) {
    const gap = cardOf(p.clip)
    if (gap !== undefined) {
      return {
        clip: gap.clip,
        ms: 0,
        card: {
          chapter: gap.chapter,
          name: names[gap.chapter] ?? '',
          ms: Math.max(0, gap.lengthMs - CARD_STEP_MS),
          lengthMs: gap.lengthMs,
        },
      }
    }
  }
  return next
}

function endPositionOf(clips: readonly Timed[], clip: number): Position {
  const last = endPosition(clips.slice(0, clip + 1))
  return last
}
