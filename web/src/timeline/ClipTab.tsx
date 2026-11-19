import { useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import { CutList } from '../cuts/CutsPanel'
import {
  UNAVAILABLE,
  formatTime,
  removedAddedWords,
  removedReadWords,
  spanWords,
} from '../cuts/times'
import type { DraftCut } from '../edit/draft'
import { RotateButtons } from '../rotate/RotateButtons'
import { Icon } from '../ui/Icon'
import { MOVE_LOCKED } from './clipDrag'
import { addCutAtPlayhead } from './cutAtPlayhead'
import { held as dragHeld } from './dragStore'
import type { DragStore } from './dragStore'
import { typedEdge, typedEdgeShown, trimLabel } from './edgeTyped'
import type { Side } from './edgeTrim'
import type { EditBinding } from './editing'
import type { TrackClip } from './layout'
import type { Playhead } from './playhead'

/*
 * What the inspector's Clip tab edits of the selected clip (`editor-selection`), below its header:
 * Trim In and Trim Out as typed times, Rotate left and right, the clip's cuts with Remove and
 * "+ Cut at playhead", Use frame as poster and Ignore clip (`track-drag-edit`). Every control makes the one draft edit the
 * track's own tools make (`EditBinding`): a typed trim is the edge tools' `onEdge`, a rotate the
 * rotate buttons' action, a cut the Cuts panel's add and remove, the poster the Timeline's.
 */

const SIDES: Side[] = ['start', 'end']

export function ClipTab({
  clip,
  clips,
  editing,
  drag,
  playhead,
  selectedKey,
  onSelectCut,
  onSelectClip,
  poster,
}: {
  clip: TrackClip
  clips: readonly TrackClip[]
  editing: EditBinding
  drag: DragStore
  playhead: Playhead
  /** The selected cut's key when it is this clip's. */
  selectedKey: string | null
  onSelectCut: (identity: string, key: string) => void
  onSelectClip: (identity: string) => void
  /** The Timeline's Use as poster control. */
  poster: ReactNode
}) {
  return (
    <div className="ct-tab">
      <div className="ct-row">
        <TrimFields key={`${editing.epoch}:${clip.identity}`} clip={clip} editing={editing} drag={drag} />
        <RotateButtons
          identity={clip.identity}
          name={clip.name}
          locked={editing.locked}
          onRotate={editing.onRotate}
        />
      </div>
      <ClipCuts
        clip={clip}
        clips={clips}
        editing={editing}
        playhead={playhead}
        selectedKey={selectedKey}
        onSelectCut={onSelectCut}
        onSelectClip={onSelectClip}
      />
      {poster}
      <button
        type="button"
        className="btn btn-secondary ct-ignore"
        aria-disabled={editing.locked || undefined}
        onClick={() => {
          if (editing.locked) {
            editing.announce(MOVE_LOCKED)
            return
          }
          editing.onIgnore(clip.identity)
        }}
      >
        <Icon name="eye-off" />
        Ignore clip
      </button>
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

function ClipCuts({
  clip,
  clips,
  editing,
  playhead,
  selectedKey,
  onSelectCut,
  onSelectClip,
}: {
  clip: TrackClip
  clips: readonly TrackClip[]
  editing: EditBinding
  playhead: Playhead
  selectedKey: string | null
  onSelectCut: (identity: string, key: string) => void
  onSelectClip: (identity: string) => void
}) {
  const listed = editing.listed(clip.identity)
  const [refusal, setRefusal] = useState<string | null>(null)
  const errorId = useId()
  const locked = editing.locked

  const add = () => {
    if (locked) {
      return
    }
    setRefusal(addCutAtPlayhead({ clip, clips, editing, playhead }))
  }
  // The pressed Remove leaves with its cut (a read cut shows "Removed when you save", an added
  // one is dropped): focus goes to the next cut's control, else + Cut at playhead, before a paint.
  const section = useRef<HTMLElement>(null)
  const pressed = useRef<{ button: HTMLElement; row: number } | null>(null)
  useLayoutEffect(() => {
    const was = pressed.current
    if (was === null || was.button.isConnected) {
      return
    }
    pressed.current = null
    const rows = Array.from(section.current?.querySelectorAll<HTMLElement>('li') ?? [])
    const next = rows
      .slice(was.row)
      .map((row) => row.querySelector<HTMLElement>('button'))
      .find((button) => button !== null)
    const target = next ?? section.current?.querySelector<HTMLElement>('button.ct-add')
    target?.focus({ preventScroll: true })
  })
  const remove = (cut: DraftCut, number: number, button: HTMLElement) => {
    if (locked) {
      return
    }
    pressed.current = { button, row: number - 1 }
    editing.onRemove(clip.identity, cut.key)
    // The removed cut was the selection: the clip it belongs to is, so the tab stays.
    if (selectedKey === cut.key) {
      onSelectClip(clip.identity)
    }
    editing.announce(
      cut.key.startsWith('r')
        ? removedReadWords(number, cut, clip.name)
        : removedAddedWords(
            cut,
            clip.name,
            listed.filter((c) => c.key !== cut.key),
          ),
    )
  }
  return (
    <section ref={section} className="ct-cuts" aria-label={`Cuts of ${clip.name}`}>
      {listed.length === 0 ? (
        <p className="cuts-none">No cuts: the whole clip plays.</p>
      ) : (
        <CutList
          cuts={listed}
          label={`Cuts of ${clip.name}`}
          keyOf={(cut) => cut.key}
          controls={(cut, number) =>
            cut.removed === true ? (
              <span className="cut-length">Removed when you save</span>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-ghost btn-compact"
                  aria-label={`Edit cut ${number} of ${clip.name}, ${spanWords(cut)}`}
                  aria-pressed={selectedKey === cut.key}
                  onClick={() => onSelectCut(clip.identity, cut.key)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-compact cut-remove"
                  aria-label={`Remove cut ${number} of ${clip.name}, ${spanWords(cut)}`}
                  aria-disabled={locked || undefined}
                  onClick={(event) => remove(cut, number, event.currentTarget)}
                >
                  Remove
                </button>
              </>
            )
          }
        />
      )}
      <button
        type="button"
        className="btn btn-secondary ct-add"
        aria-disabled={locked || undefined}
        aria-describedby={refusal === null ? undefined : errorId}
        onClick={add}
      >
        + Cut at playhead
      </button>
      {refusal !== null && (
        <p className="field-error" id={errorId}>
          <Icon name="alert-triangle" />
          {refusal}
        </p>
      )}
    </section>
  )
}
