import './chapters.css'

import { useDroppable } from '@dnd-kit/core'
import { memo, useId } from 'react'

import type { ChapterKey } from './draft'
import { DELETED_DROP } from './dragSlots'
import { Icon } from '../ui/Icon'
import type { NameCheck } from './inlineName'

/*
 * The chapter controls of Edit mode: a tools row under each chapter's heading
 * (its notes, Move up / Move down and Delete), the
 * placeholder a deleted chapter leaves until the save, and Add chapter after
 * the last chapter.
 *
 * The row is not in the sticky header, which stays one line (the page's scroll
 * padding counts on it). Every control is a native button that names its
 * chapter, and follows the busy-control rule: one that cannot act is
 * aria-disabled and ignores presses, never `disabled`, which would drop focus.
 * The editor decides what each chapter offers and what a press does
 * (`EventEditor.tsx`); these only show it.
 */

export type ChapterHandler = (key: ChapterKey) => void
export type ChapterMoveHandler = (key: ChapterKey, delta: -1 | 1) => void

/**
 * What a chapter's name field does, one stable object for all chapters (so a keystroke or a
 * metadata edit re-renders no list): the editor's, called with the chapter's key.
 */
export type NameFieldHandlers = {
  open: ChapterHandler
  check: (key: ChapterKey, typed: string) => NameCheck
  notes: (key: ChapterKey, typed: string) => readonly string[]
  keep: (key: ChapterKey, name: string) => void
  drop: ChapterHandler
  unsent: (unsent: boolean) => void
}

/** A chapter's place among the listed chapters, for Move up / Move down; absent when alone. */
export type ChapterPlace = { first: boolean; last: boolean }

/** What a chapter's tools row shows and does: decided by the editor, one object per chapter. */
export type ChapterToolsModel = {
  notes: readonly string[]
  /** Its name field is open (`InlineName`, in the heading): one chapter at a time. */
  naming: boolean
  /** Move up / Move down: absent when the chapter is the only one. */
  place: ChapterPlace | null
  /** Delete: absent (undefined) when the chapter is the only one; why it stays, or null. */
  deleteRefusal: string | null | undefined
  /** Whether Delete was pressed while refused: its reason shows until the next chapter edit. */
  refusalShown: boolean
  /** While a save or a move of marked clips is pending: every control is unavailable. */
  locked: boolean
  /** The name field in the heading (`ClipOrderList`), by the chapter's key. */
  nameField: NameFieldHandlers
  onMoveChapter: ChapterMoveHandler
  onDelete: ChapterHandler
}

// Constant elements, as the clip rows' (ClipOrderList).
const UP = <Icon name="arrow-up" />
const DOWN = <Icon name="arrow-down" />
const DELETE = <Icon name="x" />
const UNDO = <Icon name="rotate-ccw" />
const ADD = <Icon name="plus" />

function Notes({ notes }: { notes: readonly string[] }) {
  return notes.length === 0 ? null : (
    <div className="chapter-notes">
      {notes.map((note) => (
        <p key={note}>{note}</p>
      ))}
    </div>
  )
}

/**
 * One chapter's tools row; nothing when it has neither a note nor a control (an
 * event with one chapter, the event's own, shows none).
 */
export const ChapterTools = memo(function ChapterTools({
  chapterKey,
  heading,
  headingId,
  notes,
  place,
  deleteRefusal,
  refusalShown,
  locked,
  onMoveChapter,
  onDelete,
}: ChapterToolsModel & {
  chapterKey: ChapterKey
  /** The chapter's heading, as its controls name it. */
  heading: string
  /** The heading's id: the row is a group named by it. */
  headingId: string
}) {
  const refusalId = useId()
  const offersDelete = deleteRefusal !== undefined
  if (notes.length === 0 && place === null && !offersDelete) {
    return null
  }
  return (
    <div className="chapter-tools" role="group" aria-labelledby={headingId}>
      <Notes notes={notes} />
      {(place !== null || offersDelete) && (
        <div className="chapter-actions">
          {place !== null && (
            <span className="chapter-order">
              <button
                type="button"
                className="btn btn-ghost btn-icon chapter-up"
                aria-label={`Move chapter ${heading} up`}
                aria-disabled={locked || place.first || undefined}
                onClick={() => {
                  if (!locked && !place.first) {
                    onMoveChapter(chapterKey, -1)
                  }
                }}
              >
                {UP}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-icon chapter-down"
                aria-label={`Move chapter ${heading} down`}
                aria-disabled={locked || place.last || undefined}
                onClick={() => {
                  if (!locked && !place.last) {
                    onMoveChapter(chapterKey, 1)
                  }
                }}
              >
                {DOWN}
              </button>
            </span>
          )}
          {offersDelete && (
            <button
              type="button"
              className="btn btn-ghost chapter-delete"
              aria-label={`Delete chapter ${heading}`}
              aria-disabled={locked || deleteRefusal !== null || undefined}
              aria-describedby={deleteRefusal !== null ? refusalId : undefined}
              // A refused press shows and announces why (the editor), focus staying here.
              onClick={() => {
                if (!locked) {
                  onDelete(chapterKey)
                }
              }}
            >
              {DELETE}
              Delete
            </button>
          )}
        </div>
      )}
      {offersDelete && deleteRefusal !== null && (
        <p className="chapter-refusal" id={refusalId} hidden={!refusalShown}>
          {deleteRefusal}
        </p>
      )}
    </div>
  )
})

/**
 * A chapter the page showed, deleted on save: listed in its place, struck
 * through, with none of its clips and an Undo, until the edits are saved. A clip
 * dragged and released over it moves nothing (`/deleted/<key>`, dragSlots.ts).
 */
export const DeletedChapter = memo(function DeletedChapter({
  chapterKey,
  heading,
  notes,
  locked,
  onUndo,
}: {
  chapterKey: ChapterKey
  heading: string
  notes: readonly string[]
  locked: boolean
  onUndo: ChapterHandler
}) {
  const headingId = useId()
  const { setNodeRef } = useDroppable({ id: `${DELETED_DROP}${chapterKey}` })
  return (
    <section
      ref={setNodeRef}
      className="panel edit-chapter"
      data-deleted=""
      data-chapter-key={chapterKey}
      aria-labelledby={headingId}
    >
      <header className="panel-header">
        <h2 id={headingId}>
          <s>{heading}</s>
        </h2>
        <span className="badge" data-tone="warn">
          {DELETE}
          Deleted when you save
        </span>
      </header>
      <div className="chapter-tools" role="group" aria-labelledby={headingId}>
        <Notes notes={notes} />
        <div className="chapter-actions">
          <button
            type="button"
            className="btn btn-secondary chapter-undo"
            aria-label={`Undo deleting chapter ${heading}`}
            aria-disabled={locked || undefined}
            onClick={() => {
              if (!locked) {
                onUndo(chapterKey)
              }
            }}
          >
            {UNDO}
            Undo
          </button>
        </div>
      </div>
    </section>
  )
})

/** Add chapter, after the last chapter. */
export const AddChapter = memo(function AddChapter({
  locked,
  onAdd,
}: {
  locked: boolean
  onAdd: () => void
}) {
  return (
    <div className="chapter-add">
      <button
        type="button"
        className="btn btn-secondary chapter-add-button"
        aria-disabled={locked || undefined}
        onClick={() => {
          if (!locked) {
            onAdd()
          }
        }}
      >
        {ADD}
        Add chapter
      </button>
    </div>
  )
})
