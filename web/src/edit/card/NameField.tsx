import { useEffect, useId, useRef, useState } from 'react'
import type { RefObject } from 'react'

import { Icon } from '../../ui/Icon'
import { FILE_NAME_NOTE, UNTITLED } from '../inlineName.ts'
import type { NameBinding } from './editing.ts'
import { nameStep, notChangedWords } from './nameField.ts'

/*
 * The dialog's Name field (`edit-mode-declutter`), the one place a chapter is renamed and the
 * event's title is edited alike. Every accepted name is written to the draft as it is typed, so
 * the heading, the preview, the chapter's header bar and the picker of Move marked to… follow it.
 * A refused name stays in the field, explained in a remounted `role="alert"`, and holds Done and
 * Ctrl+S; the draft keeps the last accepted name. The rename is announced once, when focus
 * leaves the field or the dialog closes; closing with a refused name says it was not changed.
 * The rules are the editor's (`nameField.ts` over `checkName` and `decideName`).
 */

/** What the dialog asks of the field: is a refusal in it, and put focus in it. */
export type NameGate = { refusal(): string | null; focus(): void }

export function NameField({
  binding,
  locked,
  gate,
  announce,
  onRefused,
}: {
  binding: NameBinding
  locked: boolean
  gate: RefObject<NameGate | null>
  announce: (words: string) => void
  /** The field holds a refused name (true) or not: the dialog's tab says so. */
  onRefused: (refused: boolean) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const errorId = useId()
  const notesId = useId()
  const [typed, setTyped] = useState(binding.value)
  const [refusal, setRefusal] = useState<string | null>(null)
  const [refusals, setRefusals] = useState(0)
  // The latest of everything the closing code needs (an unmount reads these, not a stale render).
  const latest = useRef({ binding, refusal, announce })
  latest.current = { binding, refusal, announce }
  useEffect(() => onRefused(refusal !== null), [refusal, onRefused])
  // The name the field was opened with or last settled with: a rename is said once from it.
  const settledWith = useRef(binding.value)

  function settle(): void {
    const { binding: now } = latest.current
    if (settledWith.current !== now.value) {
      now.settled(settledWith.current)
      settledWith.current = now.value
    }
  }

  useEffect(() => {
    gate.current = {
      refusal: () => latest.current.refusal,
      focus: () => inputRef.current?.focus(),
    }
    return () => {
      const { binding: now, refusal: left, announce: say } = latest.current
      gate.current = null
      if (settledWith.current !== now.value) {
        now.settled(settledWith.current)
        settledWith.current = now.value
      }
      const words = notChangedWords(left)
      if (words !== null) {
        say(words)
        now.refused(false)
      }
    }
  }, [gate])

  function onChange(next: string): void {
    setTyped(next)
    const step = nameStep(next, binding.value, binding.check)
    if (step.kind === 'refused') {
      setRefusal(step.words)
      setRefusals((count) => count + 1)
      binding.refused(true)
      return
    }
    if (latest.current.refusal !== null) {
      setRefusal(null)
      binding.refused(false)
    }
    if (step.kind === 'write') {
      binding.write(step.name)
    }
  }

  const lines = binding.event ? [] : binding.notes(typed)
  const blank = binding.event && typed.trim() === ''
  const describedBy = [refusal !== null && errorId, (lines.length > 0 || binding.event) && notesId]
    .filter((id): id is string => id !== false)
    .join(' ')
  return (
    <div className="ci-field ci-name" data-field="name">
      <div className="ci-field-head">
        <label className="field-label" htmlFor={`${notesId}-input`}>
          {binding.event ? 'Title of the event' : 'Name'}
        </label>
      </div>
      <input
        ref={inputRef}
        id={`${notesId}-input`}
        type="text"
        className="field-input ci-text"
        autoComplete="off"
        spellCheck
        aria-label={binding.label}
        aria-invalid={refusal !== null || undefined}
        aria-describedby={describedBy === '' ? undefined : describedBy}
        aria-disabled={locked || undefined}
        readOnly={locked}
        placeholder={binding.event ? (binding.placeholder === '' ? UNTITLED : binding.placeholder) : ''}
        value={typed}
        onChange={(event) => {
          if (!locked) {
            onChange(event.currentTarget.value)
          }
        }}
        onBlur={() => {
          // The window lost focus, not the field: nothing was left yet.
          if (document.activeElement !== inputRef.current) {
            settle()
          }
        }}
      />
      {refusal !== null && (
        <p key={refusals} className="field-error" id={errorId} role="alert">
          <Icon name="alert-triangle" />
          {refusal}
        </p>
      )}
      <div className="field-hint ci-name-notes" id={notesId}>
        {blank && binding.hint(typed)}
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
        {binding.event && binding.fileNameChanged && <p>{FILE_NAME_NOTE}</p>}
      </div>
    </div>
  )
}
