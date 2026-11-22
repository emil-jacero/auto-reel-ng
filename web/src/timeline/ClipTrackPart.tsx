import { useId, useRef, useState, useSyncExternalStore } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import { UNAVAILABLE, formatTime } from '../cuts/times'
import { Icon } from '../ui/Icon'
import { held as dragHeld } from './dragStore'
import type { DragStore } from './dragStore'
import { typedEdge, typedEdgeShown, trimLabel } from './edgeTyped'
import type { Side } from './edgeTrim'
import type { EditBinding } from './editing'
import type { TrackClip } from './layout'

/*
 * The part of the inspector's Clip tab that needs the track (`clip-tab-and-player`, design D5):
 * what the Timeline adds, through a slot in `ClipInspector`, for a clip it draws. Its length in
 * the movie, Trim In and Trim Out as typed times, the clip's cuts with Edit, Remove and "+ Cut at
 * playhead", and Use frame as poster. Every control makes the one draft edit the track's own tools
 * make (`EditBinding`): a typed trim is the edge tools' `onEdge`, a cut the Cuts panel's add and
 * remove, the poster the Timeline's. The name, place, status, Move, Rotate and Ignore are the
 * editor's (`edit/ClipInspector.tsx`).
 */

const SIDES: Side[] = ['start', 'end']

export function ClipTrackPart({
  clip,
  length,
  editing,
  drag,
  poster,
}: {
  clip: TrackClip
  /** "12 s in the movie". */
  length: string | null
  editing: EditBinding
  drag: DragStore
  /** The Timeline's Use as poster control. */
  poster: ReactNode
}) {
  return (
    <div className="ct-tab ct-track">
      {length !== null && <p className="tl-clip-length">{length}</p>}
      <div className="ct-row">
        <TrimFields key={`${editing.epoch}:${clip.identity}`} clip={clip} editing={editing} drag={drag} />
      </div>
      {poster}
    </div>
  )
}

function TrimFields({
  clip,
  editing,
  drag,
}: {
  clip: TrackClip
  editing: EditBinding
  drag: DragStore
}) {
  const base = useId()
  const listed = editing.listed(clip.identity)
  const [typed, setTyped] = useState<Record<Side, string | null>>({ start: null, end: null })
  const [refusal, setRefusal] = useState<{ side: Side; words: string } | null>(null)
  // The text last refused, so that leaving the field it was refused in says nothing twice.
  const refused = useRef<string | null>(null)
  // The edge being dragged on the track: its field shows it on every frame.
  const live = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.getEdge()
    return d !== null && d.identity === clip.identity ? d : null
  })
  const shown = (side: Side): string =>
    typed[side] ??
    (live !== null && live.side === side
      ? formatTime(live.place / 1000)
      : typedEdgeShown(listed, side, clip.facts))
  const locked = editing.locked
  const errorId = `${base}-error`

  const commit = (side: Side, byEnter: boolean) => {
    // A press or a drag in progress holds the editor still until its release (as Q/W do).
    if (dragHeld(drag)) {
      return
    }
    const text = typed[side]
    if (text === null) {
      return
    }
    if (!byEnter && refused.current === `${side}:${text}`) {
      return
    }
    const result = typedEdge(listed, side, text, clip.name, clip.facts)
    if (result.kind === 'refused') {
      refused.current = `${side}:${text}`
      setRefusal({ side, words: result.words })
      editing.announce(result.words)
      return
    }
    refused.current = null
    setRefusal(null)
    setTyped((was) => ({ ...was, [side]: null }))
    if (result.kind === 'edit') {
      editing.onEdge(clip.identity, result.edit, result.words)
    }
  }
  const onKeyDown = (side: Side) => (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      if (!locked) {
        commit(side, true)
      }
    } else if (event.key === 'Escape' && typed[side] !== null) {
      event.preventDefault()
      event.stopPropagation()
      setTyped((was) => ({ ...was, [side]: null }))
      setRefusal(null)
    }
  }
  return (
    <div className="tl-fields ct-trim" role="group" aria-label={`Trim ${clip.name}`} data-unavailable={locked || undefined}>
      {SIDES.map((side) => (
        <div className="field tl-field" key={side}>
          <label className="field-label" htmlFor={`${base}-${side}`}>
            {trimLabel(side)}
          </label>
          <input
            id={`${base}-${side}`}
            className="field-input cut-time"
            type="text"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="done"
            value={shown(side)}
            readOnly={locked}
            aria-disabled={locked || undefined}
            aria-invalid={refusal?.side === side || undefined}
            aria-describedby={refusal?.side === side ? errorId : undefined}
            onChange={(event) => {
              const text = event.currentTarget.value
              setRefusal(null)
              setTyped((was) => ({ ...was, [side]: text }))
            }}
            onKeyDown={onKeyDown(side)}
            onBlur={() => {
              if (!locked) {
                commit(side, false)
              }
            }}
          />
        </div>
      ))}
      {refusal !== null && (
        <p className="field-error tl-fields-error" id={errorId}>
          <Icon name="alert-triangle" />
          {refusal.words}
        </p>
      )}
      {locked && <p className="tl-fields-locked">{UNAVAILABLE}</p>}
    </div>
  )
}
