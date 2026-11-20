import { useId } from 'react'

import { RotateButtons } from '../rotate/RotateButtons'
import { MOVE_LOCKED } from '../timeline/clipDrag'
import type { EditBinding } from '../timeline/editing'
import { MoveTo } from '../timeline/MoveTo'
import { Icon } from '../ui/Icon'
import type { IconName } from '../ui/Icon'
import { draftPlaceWords, offersOf } from './clipInspector'
import type { ClipState, DraftPlace } from './clipInspector'
import type { ChapterKey } from './draft'

/*
 * The inspector's Clip tab for one selected clip (`clip-tab-and-player`, design D5), built from the
 * draft and the event's read, not from the track: it is there in Prepare, and for a clip the track
 * does not draw (ignored, missing). Name, chapter and place, status in words; Move earlier and
 * Move later, Move to… and Rotate for a clip a chapter plays; and one button at its end by status:
 * Ignore clip, Include clip, Remove from reel.yaml or Undo. Each makes the draft edit the bin row's
 * own control makes. The Timeline adds what needs the track (trims, cuts, poster) into `slot`.
 *
 * The button at the end is one element for every status, so keyboard focus stays on it when the
 * press changes the status: after Include it is Ignore clip, after Remove it is Undo.
 */

type EndButton = { label: string; icon: IconName }

const END_BUTTON: Record<'ignore' | 'include' | 'remove' | 'undo', EndButton> = {
  ignore: { label: 'Ignore clip', icon: 'eye-off' },
  include: { label: 'Include clip', icon: 'plus' },
  remove: { label: 'Remove from reel.yaml', icon: 'x' },
  undo: { label: 'Undo', icon: 'rotate-ccw' },
}

export function ClipInspector({
  identity,
  name,
  place,
  state,
  status,
  chapters,
  own,
  editing,
  edges,
  onStep,
  onMoveTo,
  onEnd,
  slot,
}: {
  identity: string
  /** The clip's name as its row names it. */
  name: string
  place: DraftPlace | null
  state: ClipState | null
  /** The status in words (`statusWords`). */
  status: string
  /** The chapters the draft lists, for Move to…. */
  chapters: readonly { key: ChapterKey; name: string }[]
  /** The clip's chapter, left out of the picker; null when no chapter plays it. */
  own: ChapterKey | null
  editing: EditBinding
  /** Why Move earlier (-1) and Move later (1) cannot step, or null when they can. */
  edges: { earlier: string | null; later: string | null }
  onStep: (way: -1 | 1) => void
  onMoveTo: (to: ChapterKey) => void
  /** The end button: its action by `offersOf(state).action`. */
  onEnd: () => void
  /** Where the Timeline puts what needs the track, when it draws the clip. */
  slot: (node: HTMLElement | null) => void
}) {
  const offers = offersOf(state)
  const locked = editing.locked
  const stepId = useId()
  const end = offers.action === null ? null : END_BUTTON[offers.action]
  const stepButton = (way: -1 | 1, label: string, icon: IconName) => {
    const edge = way === -1 ? edges.earlier : edges.later
    const unavailable = locked || edge !== null
    return (
      <button
        type="button"
        className="btn btn-secondary ct-step"
        aria-disabled={unavailable || undefined}
        aria-describedby={unavailable ? `${stepId}-${way}` : undefined}
        title={locked ? MOVE_LOCKED : (edge ?? undefined)}
        onClick={() => {
          if (locked) {
            editing.announce(MOVE_LOCKED)
          } else if (edge !== null) {
            editing.announce(edge)
          } else {
            onStep(way)
          }
        }}
      >
        <Icon name={icon} />
        {label}
      </button>
    )
  }
  return (
    <div className="ct-tab ct-clip">
      <header className="tl-clip-head">
        <h3 className="tl-clip-name">{name}</h3>
        {place !== null && <p className="tl-clip-where">{draftPlaceWords(place)}</p>}
        <p className="tl-clip-status">{status}</p>
      </header>
      {offers.step && (
        <div className="ct-row ct-steps">
          {stepButton(-1, 'Move earlier', 'arrow-up')}
          {stepButton(1, 'Move later', 'arrow-down')}
          {/* The reasons a step cannot be made, for the buttons' descriptions. */}
          <span id={`${stepId}--1`} className="visually-hidden">
            {locked ? MOVE_LOCKED : (edges.earlier ?? '')}
          </span>
          <span id={`${stepId}-1`} className="visually-hidden">
            {locked ? MOVE_LOCKED : (edges.later ?? '')}
          </span>
          {offers.edits && (
            <RotateButtons
              identity={identity}
              name={name}
              locked={locked}
              onRotate={editing.onRotate}
            />
          )}
        </div>
      )}
      {offers.edits && (
        <MoveTo
          selectLabel={`Chapter to move ${name} to`}
          chapters={chapters}
          own={own}
          locked={locked}
          moving={editing.moving}
          announce={editing.announce}
          onMove={onMoveTo}
        />
      )}
      {offers.edits && <div ref={slot} className="ct-track-slot" />}
      {end !== null && (
        <button
          type="button"
          className="btn btn-secondary ct-ignore"
          aria-disabled={locked || undefined}
          aria-label={offers.action === 'undo' ? `Undo removing ${name}` : undefined}
          onClick={() => {
            if (locked) {
              editing.announce(MOVE_LOCKED)
              return
            }
            onEnd()
          }}
        >
          <Icon name={end.icon} />
          {end.label}
        </button>
      )}
    </div>
  )
}
