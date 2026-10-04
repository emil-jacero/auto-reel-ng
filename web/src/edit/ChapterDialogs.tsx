import { useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { NAME_REFUSAL, checkName, nameDialogNote } from './chapterNames'
import type { NameRefusal, NoteInput } from './chapterNames'

/*
 * The chapter dialog of Edit mode, over the shared `Dialog`: the name dialog
 * (Add chapter; a chapter is renamed at its title, `InlineName.tsx`).
 * Each is plain native form
 * controls in a `.dialog-fields` form, so its description is its one-sentence
 * explanation, never its fields (Dialog.tsx). Each is rendered only while open:
 * closing unmounts it, and `Dialog` returns focus to the control that opened it.
 *
 * While a modal is open the editor's live region outside it is inert, so each
 * dialog says a refusal through its own `role="alert"`, remounted (keyed by a
 * counter) so that the same refusal is said again.
 */

const NAME_DESCRIPTION = "The name is the heading of the chapter's title card in the movie."

/**
 * Add chapter. Checked on submit (`checkName`); once refused, again as the name is
 * typed, so the refusal leaves once the name is good. The notes say, as typed, what
 * the name will mean for clips added later.
 */
export function NameDialog({
  notes,
  onConfirm,
  onCancel,
}: {
  /** The chapter list and what the notes need (`nameDialogNote`). */
  notes: NoteInput
  /** An accepted name: trimmed. */
  onConfirm: (name: string) => void
  onCancel: () => void
}) {
  const formId = useId()
  const inputId = useId()
  const errorId = useId()
  const notesId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [value, setValue] = useState('')
  const [refused, setRefused] = useState<{ refusal: NameRefusal; clash: string | null } | null>(
    null,
  )
  const [refusals, setRefusals] = useState(0)

  const lines = nameDialogNote(notes, null, value)
  const describedBy = [refused !== null && errorId, lines.length > 0 && notesId]
    .filter((id): id is string => id !== false)
    .join(' ')

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    const result = checkName(notes.chapters, value, null)
    if (!result.ok) {
      setRefused({ refusal: result.refusal, clash: result.clash })
      setRefusals((count) => count + 1)
      // The field keeps (or gets back) keyboard focus, where the refusal is said.
      inputRef.current?.focus()
      return
    }
    onConfirm(result.name)
  }

  return (
    <Dialog open title="Add a chapter" onClose={onCancel} initialFocus={inputRef}>
      <p>{NAME_DESCRIPTION}</p>
      <form className="dialog-fields" id={formId} noValidate onSubmit={onSubmit}>
        <div className="field">
          <label className="field-label" htmlFor={inputId}>
            Name
          </label>
          <input
            ref={inputRef}
            id={inputId}
            className="field-input"
            type="text"
            autoComplete="off"
            spellCheck
            value={value}
            aria-invalid={refused !== null || undefined}
            aria-describedby={describedBy === '' ? undefined : describedBy}
            onChange={(event) => {
              const typed = event.currentTarget.value
              setValue(typed)
              if (refused !== null) {
                const result = checkName(notes.chapters, typed, null)
                setRefused(result.ok ? null : { refusal: result.refusal, clash: result.clash })
              }
            }}
          />
          {refused !== null && (
            <p key={refusals} className="field-error" id={errorId} role="alert">
              <Icon name="alert-triangle" />
              {NAME_REFUSAL[refused.refusal](refused.clash ?? '')}
            </p>
          )}
          {lines.length > 0 && (
            <div className="field-hint chapter-name-notes" id={notesId}>
              {lines.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          )}
        </div>
      </form>
      <div className="dialog-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" form={formId} className="btn btn-primary">
          <Icon name="plus" />
          Add chapter
        </button>
      </div>
    </Dialog>
  )
}
