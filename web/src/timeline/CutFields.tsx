import { useId, useRef, useState, useSyncExternalStore } from 'react'
import type { KeyboardEvent } from 'react'

import {
  UNAVAILABLE,
  checkTrim,
  fieldName,
  formatTime,
  refusalWords,
  selectedName,
} from '../cuts/times'
import type { CutField, CutRefusal } from '../cuts/times'
import { Icon } from '../ui/Icon'
import type { DraftCut } from '../edit/draft'
import type { DragStore } from './dragStore'
import type { EditBinding } from './editing'
import type { TrackClip } from './layout'

/*
 * The selected cut's times, typed (`timeline-trim`): the alternative to dragging a handle
 * (WCAG 2.5.7) and the exact way to a time that is not a frame. Two text fields in the
 * forms the Cuts panel accepts, taken on Enter or when the field loses focus, through the
 * panel's own checks (`checkTrim`), and kept in step with the handles: a drag shows in them
 * on every frame, a typed time moves the handle. A field with unsent text is left alone.
 */

export type Selected = { identity: string; key: string }

const ALERT = <Icon name="alert-triangle" />

const FIELDS: CutField[] = ['start', 'end']

export function CutFields({
  selected,
  clips,
  editing,
  drag,
  hintId,
}: {
  selected: Selected | null
  clips: readonly TrackClip[]
  editing: EditBinding
  drag: DragStore
  /** The id of the Timeline help's paragraph that says what the fields take. */
  hintId: string
}) {
  const clip = selected === null ? undefined : clips.find((c) => c.identity === selected.identity)
  const listed = selected === null ? [] : editing.listed(selected.identity)
  const at = selected === null ? -1 : listed.findIndex((c) => c.key === selected.key && !c.removed)
  if (selected === null || clip === undefined || at === -1) {
    // Nothing is drawn without a selected cut; the Timeline's help says how to select one.
    return null
  }
  return (
    <Fields
      key={`${editing.epoch}:${selected.identity}:${selected.key}`}
      selected={selected}
      clip={clip}
      listed={listed}
      at={at}
      editing={editing}
      drag={drag}
      hintId={hintId}
    />
  )
}

function Fields({
  selected,
  clip,
  listed,
  at,
  editing,
  drag,
  hintId,
}: {
  selected: Selected
  clip: TrackClip
  listed: readonly DraftCut[]
  at: number
  editing: EditBinding
  drag: DragStore
  hintId: string
}) {
  const cut = listed[at]
  const number = at + 1
  const base = useId()
  const refs = { start: useRef<HTMLInputElement>(null), end: useRef<HTMLInputElement>(null) }
  const [typed, setTyped] = useState<Record<CutField, string | null>>({ start: null, end: null })
  const [refusal, setRefusal] = useState<CutRefusal | null>(null)
  // The text last refused, so that leaving the field it was refused in says nothing twice.
  const refused = useRef<string | null>(null)
  // The edge being dragged in this cut: its fields show it on every frame.
  const live = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.get()
    return d !== null && d.identity === selected.identity && d.key === selected.key ? d : null
  })
  const now = {
    start: formatTime(live?.edge === 'in' ? live.ms / 1000 : cut.in),
    end: formatTime(live?.edge === 'out' ? live.ms / 1000 : cut.out),
  }
  const shown = (field: CutField): string => typed[field] ?? now[field]
  // The Cuts panel's fields are in the clip's own time, against its full length.
  const length = clip.facts.durationMs / 1000
  const errorId = `${base}-error`

  /** Take what was typed in `field` (and the other field's text as it shows). */
  const commit = (field: CutField, byEnter: boolean) => {
    const text = typed[field]
    if (text === null) {
      return
    }
    if (text.trim() === now[field]) {
      setTyped((was) => ({ ...was, [field]: null }))
      return
    }
    if (!byEnter && refused.current === `${field}:${text}`) {
      return
    }
    const other: CutField = field === 'start' ? 'end' : 'start'
    const checked = checkTrim(listed, at, field, text, shown(other), length)
    if (!checked.ok) {
      refused.current = `${field}:${text}`
      setRefusal(checked.refusal)
      editing.announce(refusalWords(checked.refusal))
      if (byEnter) {
        refs[checked.refusal.field].current?.focus()
      }
      return
    }
    refused.current = null
    setRefusal(null)
    setTyped({ start: null, end: null })
    editing.onTrim(
      selected.identity,
      selected.key,
      { in: checked.in, out: checked.out },
      { name: clip.name, spoken: true },
    )
  }

  const onKeyDown = (field: CutField) => (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      if (!editing.locked) {
        commit(field, true)
      }
    } else if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      setTyped((was) => ({ ...was, [field]: null }))
      setRefusal(null)
    }
  }

  const name = selectedName(number, clip.name)
  const locked = editing.locked
  return (
    <div className="tl-fields" role="group" aria-label={name} data-unavailable={locked || undefined}>
      <p className="tl-fields-name" aria-hidden="true">
        {name}
      </p>
      {FIELDS.map((field) => (
        <div className="field tl-field" key={field}>
          <label className="field-label" htmlFor={`${base}-${field}`} aria-hidden="true">
            {field === 'start' ? 'Start' : 'End'}
          </label>
          <input
            ref={refs[field]}
            id={`${base}-${field}`}
            className="field-input cut-time"
            type="text"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="done"
            aria-label={fieldName(field, number, clip.name)}
            value={shown(field)}
            readOnly={locked}
            aria-disabled={locked || undefined}
            aria-invalid={refusal?.field === field || undefined}
            aria-describedby={
              refusal?.field === field ? `${errorId} ${hintId}` : hintId
            }
            onChange={(event) => {
              const text = event.currentTarget.value
              setRefusal(null)
              setTyped((was) => ({ ...was, [field]: text }))
            }}
            onKeyDown={onKeyDown(field)}
            onBlur={() => {
              if (!locked) {
                commit(field, false)
              }
            }}
          />
        </div>
      ))}
      {refusal !== null && (
        <p className="field-error tl-fields-error" id={errorId}>
          {ALERT}
          {refusalWords(refusal)}
        </p>
      )}
      {locked && <p className="tl-fields-locked">{UNAVAILABLE}</p>}
    </div>
  )
}
