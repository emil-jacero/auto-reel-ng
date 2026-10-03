import './chapters.css'

import { useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { Icon } from '../ui/Icon'
import { NAME_REFUSAL } from './chapterNames'
import type { NameRefusal } from './chapterNames'
import { decideName, nameUnsent } from './inlineName'
import type { NameCheck } from './inlineName'

/*
 * A title that is its own rename control (D-13): a native button showing the text with a pencil
 * that is always visible; pressed (pointer, Enter, Space) it becomes a text field of the same
 * font and height, with the text selected, so nothing around it moves. Which field is open is
 * the editor's to say (`open`), one at a time; what is typed is this field's own state, so a
 * keystroke renders nothing else.
 *
 * Enter (not during an input-method composition) and leaving the field keep the text; Escape
 * drops it. Enter and Escape put focus back on the button, leaving does not (focus has gone
 * where the operator put it). A refused name stays in the field, explained in a remounted
 * `role="alert"`; on Enter the field keeps focus. `InlineName` knows no chapter: `check`
 * judges the text, `notes` says what it would mean, both from the caller.
 *
 * Its refusal and notes are drawn in `host` (under the heading's header, not in the sticky
 * header, which stays one line), or beside the field while there is none.
 */

export type InlineNameProps = {
  /** What the button shows. */
  text: string
  /** Muted type: the title is not the operator's own (from the folder name, or none). */
  muted?: boolean
  /** The name the field starts with and is compared with (not always what the button shows). */
  value: string
  /** The field's accessible name. */
  fieldLabel: string
  /** The button's description: what pressing it does. */
  hint: string
  open: boolean
  /** A save or a Move clips is pending: the button says so and opens nothing. */
  locked: boolean
  check: (typed: string) => NameCheck
  /** What the typed text would mean, shown under the field: nothing when there is none. */
  notes: (typed: string) => ReactNode
  host: HTMLElement | null
  onOpen: () => void
  /** An accepted name that differs from `value`; the field is then done. */
  onKeep: (name: string) => void
  /** The field is done and nothing is kept (Escape, an unchanged name). */
  onDrop: () => void
  /** The field holds text not yet kept; called only when that changes. */
  onUnsent: (unsent: boolean) => void
}

type Refused = { refusal: NameRefusal; clash: string | null }

const PENCIL = <Icon name="pencil" />

/** Whether `element` is the text field of an open `InlineName`. */
function isOpenField(element: Element | null): element is HTMLInputElement {
  return element instanceof HTMLInputElement && element.classList.contains('inline-name-field')
}

export function InlineName(props: InlineNameProps) {
  const { text, muted, hint, open, locked, onOpen } = props
  const buttonRef = useRef<HTMLButtonElement>(null)
  const hintId = useId()
  // Focus goes back to the button once the field has closed by Enter or Escape.
  const refocus = useRef(false)

  useLayoutEffect(() => {
    if (!open && refocus.current) {
      refocus.current = false
      buttonRef.current?.focus()
    }
  }, [open])

  return (
    <span className="inline-name" data-open={open || undefined}>
      {open ? (
        <Field {...props} refocus={refocus} />
      ) : (
        <>
          <button
            ref={buttonRef}
            type="button"
            className="inline-name-button"
            data-muted={muted || undefined}
            aria-disabled={locked || undefined}
            aria-describedby={hintId}
            // Another title pressed while a field is open: the press must not blur that field
            // yet. Keeping its name can add a note above this button and move it from under
            // the pointer before the button is released; the click keeps it first instead.
            onMouseDown={(event) => {
              if (isOpenField(document.activeElement)) {
                event.preventDefault()
              }
            }}
            onClick={() => {
              if (locked) {
                return
              }
              const other = document.activeElement
              if (isOpenField(other)) {
                other.blur()
              }
              onOpen()
            }}
          >
            <span className="inline-name-text">{text}</span>
            {PENCIL}
          </button>
          <span id={hintId} hidden>
            {hint}
          </span>
        </>
      )}
    </span>
  )
}

function Field({
  value,
  fieldLabel,
  check,
  notes,
  host,
  refocus,
  onKeep,
  onDrop,
  onUnsent,
}: InlineNameProps & { refocus: { current: boolean } }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const errorId = useId()
  const notesId = useId()
  const [typed, setTyped] = useState(value)
  const [refused, setRefused] = useState<Refused | null>(null)
  const [refusals, setRefusals] = useState(0)
  // Whether the editor was last told the field holds an unkept name; whether it is done.
  const reported = useRef(false)
  const done = useRef(false)

  useLayoutEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  // A field the editor closes (Reset, a save, another field) keeps nothing, and a browser that
  // blurs a focused element as it is removed finds the field done. The editor never keeps a
  // stale "unfinished": a closed field says it holds nothing.
  const unsentRef = useRef(onUnsent)
  unsentRef.current = onUnsent
  useLayoutEffect(
    () => () => {
      done.current = true
      if (reported.current) {
        unsentRef.current(false)
      }
    },
    [],
  )

  function report(next: string): void {
    const unsent = nameUnsent(next, value)
    if (unsent !== reported.current) {
      reported.current = unsent
      onUnsent(unsent)
    }
  }

  function finish(withFocus: boolean): void {
    done.current = true
    refocus.current = withFocus
  }

  /** Keep, close, or refuse the text; true when the field is done. */
  function settle(enter: boolean): void {
    const decision = decideName(typed, value, check)
    if (decision.kind === 'refused') {
      setRefused({ refusal: decision.refusal, clash: decision.clash })
      setRefusals((count) => count + 1)
      if (enter) {
        inputRef.current?.focus()
      }
      return
    }
    finish(enter)
    if (decision.kind === 'keep') {
      onKeep(decision.name)
    } else {
      onDrop()
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
      event.preventDefault()
      settle(true)
    } else if (event.key === 'Escape') {
      // No outer handler sees it (a dialog, the page).
      event.stopPropagation()
      event.preventDefault()
      finish(true)
      onDrop()
    }
  }

  const lines = notes(typed)
  const describedBy = [refused !== null && errorId, lines !== null && notesId]
    .filter((id): id is string => id !== false)
    .join(' ')
  const messages = (
    <>
      {refused !== null && (
        <p key={refusals} className="field-error" id={errorId} role="alert">
          <Icon name="alert-triangle" />
          {NAME_REFUSAL[refused.refusal](refused.clash ?? '')}
        </p>
      )}
      {lines !== null && (
        <div className="field-hint inline-name-notes" id={notesId}>
          {lines}
        </div>
      )}
    </>
  )
  return (
    <>
      <input
        ref={inputRef}
        type="text"
        className="field-input inline-name-field"
        autoComplete="off"
        spellCheck
        aria-label={fieldLabel}
        aria-invalid={refused !== null || undefined}
        aria-describedby={describedBy === '' ? undefined : describedBy}
        value={typed}
        onChange={(event) => {
          const next = event.currentTarget.value
          setTyped(next)
          report(next)
          if (refused !== null) {
            const result = check(next)
            setRefused(result.ok ? null : { refusal: result.refusal, clash: result.clash })
          }
        }}
        onKeyDown={onKeyDown}
        onBlur={() => {
          // The window lost focus, not the field: nothing was left yet.
          if (done.current || document.activeElement === inputRef.current) {
            return
          }
          settle(false)
        }}
      />
      {host === null ? <span className="inline-name-messages">{messages}</span> : null}
      {host !== null && createPortal(messages, host)}
    </>
  )
}
