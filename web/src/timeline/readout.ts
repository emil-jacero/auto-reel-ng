import { clockCell, clockScale } from '../clock.ts'
import type { ClockCell, ClockScale } from '../clock.ts'
import type { Layout } from './model.ts'
import { clampPosition, globalMs } from './position.ts'
import type { Position } from './position.ts'

/*
 * The Timeline's readout under the video, as data: the clip's name, then the time in the
 * clip and the clip's length, then the time in the whole timeline and its length, each
 * with the width of its cell. The clip pair is written to the scale of the event's
 * longest clip and the event pair to the scale of the whole timeline, so passing from
 * one clip into another changes no width. Pure; `PlayheadReadout` only draws it.
 */

export type ReadoutPair = { time: ClockCell; length: ClockCell }

export type Readout = {
  /** The clip the playhead is in; the whole name is the tooltip. */
  name: string
  clip: ReadoutPair
  event: ReadoutPair
}

type Clips = readonly { name: string; facts: { durationMs: number } }[]
export type ReadoutScales = { clip: ClockScale; event: ClockScale }

/** The two scales depend only on the clips and layout, so a caller can hold them across ticks. */
export function readoutScales(clips: Clips, lay: Layout): ReadoutScales {
  let longest = 0
  for (const c of clips) longest = Math.max(longest, c.facts.durationMs)
  return { clip: clockScale(longest), event: clockScale(lay.totalMs) }
}

export function readoutOf(
  at: Position,
  clips: Clips,
  lay: Layout,
  scales: ReadoutScales = readoutScales(clips, lay),
): Readout {
  const here = clampPosition(clips, at)
  const clip = clips[here.clip]
  const clipScale = scales.clip
  const eventScale = scales.event
  return {
    name: clip.name,
    clip: {
      time: clockCell(here.ms, clipScale),
      length: clockCell(clip.facts.durationMs, clipScale),
    },
    event: {
      time: clockCell(globalMs(lay, here), eventScale),
      length: clockCell(lay.totalMs, eventScale),
    },
  }
}

/** The readout as one line of text: `Clip 0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76`. */
export function readoutWords(r: Readout): string {
  return `Clip ${r.clip.time.text} of ${r.clip.length.text} · Event ${r.event.time.text} of ${r.event.length.text}`
}

/**
 * The trim tip's time: the edge's time in the clip to the millisecond, because that is
 * what the cut will hold, to the scale of its clip's length so it never changes width.
 */
export function tipOf(edgeMs: number, clipDurationMs: number): ClockCell {
  return clockCell(edgeMs, clockScale(clipDurationMs, 3))
}
