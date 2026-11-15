import { TIME_FORMS, formatTime, parseTime } from '../cuts/times.ts'
import type { ListedCut } from '../cuts/times.ts'
import { edgeAnnouncement, edgeAt, edgeEdit, edgeLimits, edgePlaces } from './edgeTrim.ts'
import type { EdgeEdit, Side } from './edgeTrim.ts'
import type { ClipFacts } from './model.ts'

/*
 * Trim In and Trim Out typed in the inspector's Clip tab (`editor-selection`): the alternative to
 * dragging an edge. A typed time is taken as the edge tools take a key: the place goes through
 * `edgeAt` (the nearest frame, held to the limits, joined with the cuts it reaches) and the edit
 * is `edgeEdit`'s, handed to the same `onEdge` as a drag's release. There is no second path to
 * the draft. Pure: no DOM, no React.
 */

/** The field's name: Trim In is the clip's start, Trim Out its end. */
export const trimLabel = (side: Side): string => (side === 'start' ? 'Trim In' : 'Trim Out')

export type TypedEdge =
  | { kind: 'refused'; words: string }
  /** Typed where the edge already is (or only differently written): nothing to do. */
  | { kind: 'same' }
  | { kind: 'edit'; edit: EdgeEdit; words: string }

/** The place the field shows: the edge's place in the clip, as the Cuts panel's times read. */
export function typedEdgeShown(listed: readonly ListedCut[], side: Side, f: ClipFacts): string {
  return formatTime(edgePlaces(listed, f.durationMs)[side] / 1000)
}

/**
 * What typing `typed` into `side`'s field does for a clip with `listed` cuts: a refusal in words
 * (unreadable, or outside what the edge can take now), nothing, or the one edge edit.
 */
export function typedEdge(
  listed: readonly (ListedCut & { key: string })[],
  side: Side,
  typed: string,
  name: string,
  f: ClipFacts,
): TypedEdge {
  const read = parseTime(typed)
  const label = trimLabel(side)
  if (!read.ok) {
    switch (read.refusal) {
      case 'empty':
        return { kind: 'refused', words: `Type a time for ${label}.` }
      case 'unreadable':
        return {
          kind: 'refused',
          words: `“${typed.trim()}” is not a time the page can read. Type ${TIME_FORMS}.`,
        }
      case 'too-precise':
        return {
          kind: 'refused',
          words: `“${typed.trim()}” has more than three decimals. Times go to the millisecond.`,
        }
    }
  }
  const limits = edgeLimits(listed, side, f)
  // A time shown to the millisecond may sit a hair beyond a limit that is not a whole one.
  const wanted =
    Math.abs(read.ms - limits.lowest) <= 1
      ? limits.lowest
      : Math.abs(read.ms - limits.highest) <= 1
        ? limits.highest
        : read.ms
  if (wanted < limits.lowest || wanted > limits.highest) {
    return {
      kind: 'refused',
      words:
        `${label} can take ${formatTime(limits.lowest / 1000)} to ` +
        `${formatTime(limits.highest / 1000)} here. ${formatTime(read.ms / 1000)} is outside that.`,
    }
  }
  const at = edgeAt(listed, side, wanted, f, 1, { playheadMs: null, snapping: false }, limits)
  if (at.place === edgePlaces(listed, f.durationMs)[side]) {
    return { kind: 'same' }
  }
  const edit = edgeEdit(listed, side, at.x, f)
  return edit.kind === 'none'
    ? { kind: 'same' }
    : { kind: 'edit', edit, words: edgeAnnouncement(name, side, at, f.durationMs) }
}
