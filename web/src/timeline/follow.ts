import { END_SLACK_MS, skipAt, toEnd } from '../preview/playback.ts'
import type { Skip } from '../preview/playback.ts'
import type { Ms } from './model.ts'
import type { Position } from './position.ts'

/*
 * Playing the timeline as the movie will play (D-16's rules, reused from
 * `preview/playback.ts`): where Play starts, what each presented frame does, and where a
 * clip's end leads. Pure, in whole milliseconds.
 */

/** What a presented frame asks for while playing. */
export type Frame =
  // play on
  | { kind: 'play' }
  // jump over a cut to this time of the clip
  | { kind: 'seek'; ms: Ms }
  // this clip is over (a cut runs to its end): go on into the next
  | { kind: 'end' }

/**
 * The frame shown at `atMs` of a clip `lengthMs` long, the next `stepMs` later: a cut
 * the next frame would fall in is skipped, or ends the clip when it runs to its end
 * (`skipAt`). The playhead stays on frames the movie shows.
 */
export function onFrame(spans: readonly Skip[], atMs: Ms, stepMs: Ms, lengthMs: Ms): Frame {
  const skip = skipAt(spans, atMs, stepMs, lengthMs)
  if (skip === null) {
    return { kind: 'play' }
  }
  return 'seek' in skip ? { kind: 'seek', ms: skip.seek } : { kind: 'end' }
}

type Playable = { durationMs: Ms; spans: readonly Skip[] }

/**
 * Where playing begins from `p`: the playhead itself, the end of a cut it sits in, or the
 * next clip's first footage when the rest of its clip is cut or under `END_SLACK_MS`
 * (the preview's `playFrom` would start that clip over; the timeline goes on). Null when
 * nothing after `p` plays: the caller starts the timeline over.
 */
export function startFrom(clips: readonly Playable[], p: Position): Position | null {
  const { spans, durationMs } = clips[p.clip]
  if (durationMs - p.ms < END_SLACK_MS) {
    return nextClip(clips, p.clip)
  }
  const span = spans.find((skip) => skip.from <= p.ms && p.ms < skip.to)
  if (span === undefined) {
    return p
  }
  return toEnd(span, durationMs) ? nextClip(clips, p.clip) : { clip: p.clip, ms: span.to }
}

/**
 * The start of the first clip after `clip` that has footage outside its cuts (a clip all
 * cut is skipped, as the render skips it); null when there is none.
 */
export function nextClip(clips: readonly Playable[], clip: number): Position | null {
  for (let next = clip + 1; next < clips.length; next += 1) {
    const { spans, durationMs } = clips[next]
    const first = spans[0]
    if (first === undefined || first.from > 0) {
      return { clip: next, ms: 0 }
    }
    if (!toEnd(first, durationMs)) {
      return { clip: next, ms: first.to }
    }
  }
  return null
}

/**
 * Whether the Timeline's video may start now. The operator's own Play always starts. A
 * start the Timeline makes by itself (after a clip swap or a settled seek, while the
 * operator's Play still holds) yields when another video plays: the page's one video is
 * that one, and the Timeline's resume would be the last start and pause it.
 */
export function resumeOrYield(operatorAsked: boolean, anotherPlays: boolean): 'start' | 'yield' {
  return operatorAsked || !anotherPlays ? 'start' : 'yield'
}
