import type { ReactNode } from 'react'

import type { TrackClip } from '../layout'
import type { EditBinding } from '../editing'
import type { Layout } from '../model'
import type { Dismissals } from './Dismissals'
import type { Cut, Suggestion, SuggestionState } from './suggestions'

/*
 * What the Timeline is given to show the analysis lane (D-20, "Analysis overlays"): the
 * clip's cuts as they are now, the page's dismissals, and how to decide. Absent, the
 * Timeline is the one without a lane. `TimelineSection` builds it from Edit mode's draft
 * (the Timeline is shown only in Edit mode).
 */

export type DecideControl = {
  /** Add a cut for an approved suggestion: its span in seconds, its kind as the reason. */
  onApprove(identity: string, span: { in: number; out: number }, kind: string): void
  /** A save or a move of marked clips is pending: no decision is taken meanwhile. */
  locked: boolean
  /** Say it through the page's one polite live region. */
  announce(message: string): void
}

/**
 * The decisions Edit mode gives the lane: approving adds a cut to the editor's draft
 * (`onAdd`, the Cuts panel's own add), and the lock and the live region are the editor's.
 */
export function decideControl(
  editing: Pick<EditBinding, 'onAdd' | 'locked' | 'announce'>,
): DecideControl {
  return {
    onApprove: (identity, span, kind) => editing.onAdd(identity, span, kind),
    locked: editing.locked,
    announce: (message) => editing.announce(message),
  }
}

export type AnalysisControl = {
  eventId: string
  /** The clip's cuts as listed now, removed ones included (the Cuts panel's numbering). */
  cutsOf(identity: string): readonly Cut[]
  dismissals: Dismissals
  decide: DecideControl
}

/**
 * The analysis lane's control for one Timeline, from Edit mode's binding: the draft's cuts, as
 * the Cuts panel lists them, and the editor's own add, lock and live region to decide with.
 * Pure, so that `npm test` checks the wiring.
 */
export function analysisOf(
  eventId: string,
  editing: Pick<EditBinding, 'onAdd' | 'locked' | 'announce' | 'listed'>,
  dismissals: Dismissals,
): AnalysisControl {
  return {
    eventId,
    cutsOf: (identity) => editing.listed(identity),
    dismissals,
    decide: decideControl(editing),
  }
}

/** One suggestion as the lane draws it: its state from the cuts, its box in px on the track. */
export type MarkModel = {
  /** `dismissalKey`: the clip, the span and the kind as the analysis wrote them. */
  id: string
  identity: string
  clipIndex: number
  segment: Suggestion
  state: SuggestionState
  left: number
  width: number
  row: number
  /** The span itself inside the box, in px from the box's left edge. */
  barLeft: number
  barWidth: number
}

/** What `Track` knows and hands the lane to draw its window of the track. */
export type LaneView = {
  clips: readonly TrackClip[]
  lay: Layout
  pps: number
  /** The clips in the window, as `visibleClips` gives them. */
  shown: [number, number] | null
  /** Whether the clip is behind a title card being dragged: its marks move. */
  shifted?: (clipIndex: number) => boolean
}

/** The lane as `Track` draws it: a canvas row of `rows` mark rows, filled by `render`. */
export type LaneSlot = {
  rows: number
  render(view: LaneView): ReactNode
}
