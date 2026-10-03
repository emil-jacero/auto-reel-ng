import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

import type { ClipStatus } from '../api/event'
import { plural } from '../events/common'
import { CLIP_STATUS_LABEL } from '../events/labels'
import { CLIP_STATUS_LOOK } from '../events/tones'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { NAME_REFUSAL, checkName, nameDialogNote } from './chapterNames'
import type { NameRefusal, NoteInput } from './chapterNames'
import type { ChapterKey } from './draft'
import { markedAmong, pickMarked } from './marks'

/*
 * The two chapter dialogs of Edit mode, over the shared `Dialog`: the name
 * dialog (Add chapter; a chapter is renamed at its title, `InlineName.tsx`) and Move clips. Each is plain native form
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

/** A clip Move clips offers: on disk and played, named as its chapter names it. */
export type MovableClip = { identity: string; name: string; status: ClipStatus; position: number }

/** "Not offered: …": the clips of the chapter the dialog leaves out, and why. */
function notOffered(missing: number, ignored: number): string | null {
  const parts = [
    missing === 1 &&
      '1 missing clip, which stays in its chapter until its file is restored or it is removed',
    missing > 1 &&
      `${missing} missing clips, which stay in their chapter until their files are restored or ` +
        'they are removed',
    ignored > 0 &&
      `${plural(ignored, 'ignored clip', 'ignored clips')}, ` +
        `which ${ignored === 1 ? 'is' : 'are'} not played`,
  ].filter((part): part is string => part !== false)
  return parts.length === 0 ? null : `Not offered: ${parts.join(', and ')}.`
}

/**
 * Move clips: the chapter's clips on disk as checkboxes, in play order, and the
 * other chapters as radio buttons (the only one already chosen), with a Pick all
 * box before the clips (mixed while some are picked). Space picks a clip; Enter
 * on any box or radio moves the picked clips, so a long list need not be tabbed
 * through. Asking with no clip, or no chapter, says which is
 * missing at it and moves focus there.
 */
export function MoveClipsDialog({
  heading,
  clips,
  missing,
  ignored,
  targets,
  marked,
  onConfirm,
  onCancel,
}: {
  /** The chapter's heading. */
  heading: string
  clips: readonly MovableClip[]
  /** How many clips it plays that are missing, and how many it ignores: not offered. */
  missing: number
  ignored: number
  /** The other listed chapters, by heading, in the order shown. */
  targets: readonly { key: ChapterKey; heading: string }[]
  /** The marked clips (edit/marks.ts): Pick marked picks those of this chapter's offered. */
  marked: ReadonlySet<string>
  onConfirm: (identities: string[], to: ChapterKey) => void
  onCancel: () => void
}) {
  const formId = useId()
  const radioName = useId()
  const clipsErrorId = useId()
  const targetErrorId = useId()
  const firstBoxRef = useRef<HTMLInputElement>(null)
  const allRef = useRef<HTMLInputElement>(null)
  const firstRadioRef = useRef<HTMLInputElement>(null)
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set())
  const [target, setTarget] = useState<ChapterKey | null>(
    targets.length === 1 ? targets[0].key : null,
  )
  // Counters: non-zero while the error shows; a repeated refusal remounts it.
  const [clipsError, setClipsError] = useState(0)
  const [targetError, setTargetError] = useState(0)
  // Pick marked was pressed with no offered clip marked: said beside it, in words.
  const [noneMarked, setNoneMarked] = useState(false)
  const hint = notOffered(missing, ignored)
  const all = clips.length > 0 && picked.size === clips.length
  const offered = useMemo(() => clips.map((clip) => clip.identity), [clips])

  // Pick all is mixed (indeterminate) while some clips are picked: a DOM property only.
  useEffect(() => {
    if (allRef.current !== null) {
      allRef.current.indeterminate = picked.size > 0 && picked.size < clips.length
    }
  }, [picked, clips.length])

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (picked.size === 0) {
      setClipsError((count) => count + 1)
      firstBoxRef.current?.focus()
      return
    }
    if (target === null) {
      setTargetError((count) => count + 1)
      firstRadioRef.current?.focus()
      return
    }
    onConfirm(
      clips.filter((clip) => picked.has(clip.identity)).map((clip) => clip.identity),
      target,
    )
  }

  // Enter on a box or a radio moves, once: the browser's own submit on Enter (where
  // it has one) is prevented, and the form is submitted here instead.
  function onKeyDown(event: KeyboardEvent<HTMLFormElement>): void {
    if (event.key === 'Enter' && event.target instanceof HTMLInputElement) {
      event.preventDefault()
      event.currentTarget.requestSubmit()
    }
  }

  return (
    <Dialog
      open
      title={`Move clips from “${heading}”`}
      onClose={onCancel}
      initialFocus={firstBoxRef}
    >
      <p>
        The clips you pick join the end of the chapter you choose. Space picks a clip; Enter moves
        the picked clips.
      </p>
      <form
        className="dialog-fields move-clips"
        id={formId}
        noValidate
        onSubmit={onSubmit}
        onKeyDown={onKeyDown}
      >
        <fieldset
          className="choice-group"
          aria-describedby={clipsError > 0 ? clipsErrorId : undefined}
        >
          <legend>
            Clips{' '}
            <span className="choice-count">
              {picked.size} of {clips.length} picked
            </span>
          </legend>
          {clipsError > 0 && (
            <p key={clipsError} className="field-error" id={clipsErrorId} role="alert">
              <Icon name="alert-triangle" />
              Pick at least one clip.
            </p>
          )}
          {/* The marked clips of this chapter: aria-disabled, never disabled, when none is. */}
          <div className="choice-picks">
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              aria-disabled={markedAmong(offered, marked) === 0 || undefined}
              onClick={() => {
                if (markedAmong(offered, marked) === 0) {
                  setNoneMarked(true)
                  return
                }
                setNoneMarked(false)
                const next = pickMarked(offered, marked, picked)
                setPicked(next)
                if (next.size > 0) {
                  setClipsError(0)
                }
              }}
            >
              Pick marked
            </button>
            {noneMarked && (
              <span className="field-hint" role="status">
                No clip of “{heading}” is marked.
              </span>
            )}
          </div>
          {/* Every clip at once: emptying or splitting a long chapter is one press. */}
          <label className="choice choice-all">
            <input
              ref={allRef}
              type="checkbox"
              checked={all}
              onChange={(event) => {
                const next = event.currentTarget.checked
                  ? new Set(clips.map((clip) => clip.identity))
                  : new Set<string>()
                setPicked(next)
                if (next.size > 0) {
                  setClipsError(0)
                }
              }}
            />
            <span className="choice-name">Pick all</span>
          </label>
          <ul className="choice-list choice-clips">
            {clips.map((clip, index) => (
              <li key={clip.identity}>
                <label className="choice">
                  <input
                    ref={index === 0 ? firstBoxRef : undefined}
                    type="checkbox"
                    value={clip.identity}
                    checked={picked.has(clip.identity)}
                    onChange={(event) => {
                      const next = new Set(picked)
                      if (event.currentTarget.checked) {
                        next.add(clip.identity)
                      } else {
                        next.delete(clip.identity)
                      }
                      setPicked(next)
                      if (next.size > 0) {
                        setClipsError(0)
                      }
                    }}
                  />
                  <span className="choice-pos">{clip.position}</span>
                  <span className="choice-name">
                    <span className="choice-file">{clip.name}</span>
                    {clip.status === 'new' && (
                      <span className="badge" data-tone={CLIP_STATUS_LOOK.new.tone}>
                        <Icon name={CLIP_STATUS_LOOK.new.icon} />
                        {CLIP_STATUS_LABEL.new}
                      </span>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
        <fieldset
          className="choice-group"
          aria-describedby={targetError > 0 ? targetErrorId : undefined}
        >
          <legend>Move to</legend>
          {targetError > 0 && (
            <p key={targetError} className="field-error" id={targetErrorId} role="alert">
              <Icon name="alert-triangle" />
              Choose a chapter to move them to.
            </p>
          )}
          <ul className="choice-list">
            {targets.map((chapter, index) => (
              <li key={chapter.key}>
                <label className="choice">
                  <input
                    ref={index === 0 ? firstRadioRef : undefined}
                    type="radio"
                    name={radioName}
                    value={chapter.key}
                    checked={target === chapter.key}
                    onChange={() => {
                      setTarget(chapter.key)
                      setTargetError(0)
                    }}
                  />
                  <span className="choice-name">{chapter.heading}</span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
        {hint !== null && <p className="field-hint">{hint}</p>}
      </form>
      <div className="dialog-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" form={formId} className="btn btn-primary">
          <Icon name="arrow-right" />
          Move clips
        </button>
      </div>
    </Dialog>
  )
}
