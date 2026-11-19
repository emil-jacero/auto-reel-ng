import './chapters.css'

import { memo, useId } from 'react'

import { chapterToolsParts } from './chapterBar'
import type { ChapterPlace } from './chapterBar'
import type { ChapterKey } from './draft'
import { Icon } from '../ui/Icon'

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

export type { ChapterPlace }

/** What a chapter's tools row shows and does: decided by the editor, one object per chapter. */
export type ChapterToolsModel = {
  notes: readonly string[]
  /** The chapter's card id (`cardIdOf`): what its Edit Titlecard button selects. */
  cardId: string
  /** Move up / Move down: absent when the chapter is the only one. */
  place: ChapterPlace | null
  /** Delete: absent (undefined) when the chapter is the only one; why it stays, or null. */
  deleteRefusal: string | null | undefined
  /** Whether Delete was pressed while refused: its reason shows until the next chapter edit. */
  refusalShown: boolean
  /** While a save or a move of marked clips is pending: every control is unavailable. */
  locked: boolean
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
 * One chapter's tools. `placement` says where its buttons are:
 * - `row`: its own row under the heading, with the notes and Delete's refusal; nothing when it
 *   has neither a note nor a control (an event with one chapter, the event's own, shows none).
 *   The clip bin renders it too: below 960 px it is the whole of the tools; from 960 px its
 *   buttons are hidden (CSS) and it keeps the notes and the refusal, if any.
 * - `bar` (the clip bin, from 960 px): the buttons alone, icon-only with a `title`, for the
 *   header bar, after the count. Delete's refusal is named by `aria-describedby`.
 */
export const ChapterTools = memo(function ChapterTools({
  chapterKey,
  heading,
  headingId,
  placement = 'row',
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
  /** The heading's id: the group is named by it, and the refusal's id derives from it. */
  headingId: string
  placement?: 'bar' | 'row'
}) {
  const refusalId = `${headingId}-refusal`
  const offersDelete = deleteRefusal !== undefined
  const inBar = placement === 'bar'
  const parts = chapterToolsParts(placement, notes.length, place, deleteRefusal)
  if (parts === null) {
    return null
  }
  const refusal = parts.refusal && (
    <p className="chapter-refusal" id={refusalId} hidden={!refusalShown}>
      {deleteRefusal}
    </p>
  )
  const buttons = parts.buttons && (
    <div
      className="chapter-actions"
      role={inBar ? 'group' : undefined}
      aria-labelledby={inBar ? headingId : undefined}
    >
      {place !== null && (
        <span className="chapter-order">
          <button
            type="button"
            className="btn btn-ghost btn-icon chapter-up"
            aria-label={`Move chapter ${heading} up`}
            title={inBar ? `Move chapter ${heading} up` : undefined}
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
            title={inBar ? `Move chapter ${heading} down` : undefined}
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
          className={`btn btn-ghost chapter-delete${inBar ? ' btn-icon' : ''}`}
          aria-label={`Delete chapter ${heading}`}
          title={inBar ? `Delete chapter ${heading}` : undefined}
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
          {!inBar && 'Delete'}
        </button>
      )}
    </div>
  )
  if (inBar) {
    return buttons
  }
  return (
    <div className="chapter-tools" role="group" aria-labelledby={headingId}>
      {parts.notes && <Notes notes={notes} />}
      {buttons}
      {refusal}
    </div>
  )
})

/**
 * A chapter the page showed, deleted on save: listed in the Chapters list
 * in its place, struck through, with none of its clips and an Undo, until the edits are saved.
 * The bin does not list it, so there is nothing to drop a clip on.
 */
export const DeletedChapter = memo(function DeletedChapter({
  chapterKey,
  heading,
  notes,
  locked,
  onUndo,
  headingLevel: Heading = 'h2',
}: {
  chapterKey: ChapterKey
  heading: string
  notes: readonly string[]
  locked: boolean
  onUndo: ChapterHandler
  /** The struck name's heading: one level below the section it is listed in. */
  headingLevel?: 'h2' | 'h3'
}) {
  const headingId = useId()
  return (
    <section
      className="panel edit-chapter"
      data-deleted=""
      data-chapter-key={chapterKey}
      aria-labelledby={headingId}
    >
      <header className="panel-header">
        <Heading id={headingId}>
          <s>{heading}</s>
        </Heading>
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
