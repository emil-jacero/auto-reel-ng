import type { ReactNode } from 'react'

import type { ReadCutsState } from '../../cuts/ReadCuts'
import type { TrackClip } from '../layout'
import type { EditBinding } from '../editing'
import type { Layout } from '../model'
import type { Dismissals } from './Dismissals'
import type { Cut, Suggestion, SuggestionState } from './suggestions'

/*
 * What the Timeline is given to show the analysis lane (D-20, "Analysis overlays"): the
 * clip's cuts as they are now, the page's dismissals, and, in Edit mode only, how to
 * decide. Absent, the Timeline is the one without a lane. The read view builds it in
 * `TimelineSection`; Edit mode builds it from the draft where it mounts the Timeline.
 */

export type DecideControl = {
  /** Add a cut for an approved suggestion: its span in seconds, its kind as the reason. */
  onApprove(identity: string, span: { in: number; out: number }, kind: string): void
  /** A save or a Move clips is pending: no decision is taken meanwhile. */
  locked: boolean
  /** Say it through the page's one polite live region. */
  announce(message: string): void
}

/**
 * The decisions Edit mode gives the lane: approving adds a cut to the editor's draft
 * (`onAdd`, the Cuts panel's own add), and the lock and the live region are the editor's.
 * Null for the read view, whose binding is null: reading a screen never changes state.
 */
export function decideControl(
  editing: Pick<EditBinding, 'onAdd' | 'locked' | 'announce'> | null,
): DecideControl | null {
  if (editing === null) {
    return null
  }
  return {
    onApprove: (identity, span, kind) => editing.onAdd(identity, span, kind),
    locked: editing.locked,
    announce: (message) => editing.announce(message),
  }
}

export type AnalysisControl = {
  eventId: string
  /**
   * Whether the clips' cuts are known: while they are being read, or could not be, a
   * suggestion's state is unknown and no mark is drawn.
   */
  cutsState: 'reading' | 'unreadable' | 'ok'
  /** The clip's cuts as listed now, removed ones included (the Cuts panel's numbering). */
  cutsOf(identity: string): readonly Cut[]
  dismissals: Dismissals
  /** Null outside Edit mode: the lane shows state and offers no decision. */
  decide: DecideControl | null
}

const NO_CUTS: readonly never[] = []

/**
 * The analysis lane's control for one Timeline, from what `TimelineSection` has: in the
 * read view the cuts as read and no decision (reading a screen never changes state), in
 * Edit mode the draft's, as the Cuts panel lists them, and the editor's own add, lock and
 * live region to decide with. Pure, so that `npm test` checks the wiring.
 */
export function analysisOf(
  eventId: string,
  read: ReadCutsState,
  editing: Pick<EditBinding, 'onAdd' | 'locked' | 'announce' | 'listed'> | null,
  dismissals: Dismissals,
): AnalysisControl {
  let cutsState: AnalysisControl['cutsState'] = 'reading'
  if (editing !== null || read.cuts !== null) {
    cutsState = 'ok'
  } else if (read.failure !== null) {
    cutsState = 'unreadable'
  }
  return {
    eventId,
    cutsState,
    cutsOf: (identity) =>
      editing !== null ? editing.listed(identity) : (read.cuts?.get(identity) ?? NO_CUTS),
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
