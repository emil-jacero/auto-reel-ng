import './chapters.css'

import { memo, useId } from 'react'

import { AddChapter, ChapterTools, DeletedChapter } from './ChapterTools'
import type { ChapterHandler, ChapterToolsModel } from './ChapterTools'
import { barContent } from './chapterBar'
import type { ChapterKey, DraftChapter } from './draft'
import { chapterRowHint } from './emptyChapter'
import { EditTitlecard } from './EditTitlecard'

/*
 * The Chapters list of the inspector's Event tab: one row per chapter, in the draft's order, with
 * its name, its clip count and its tools; a deleted chapter's row (with Undo) until the save; and
 * Add chapter after the last row. It is built from the draft, not from the Timeline, so it is
 * there in Prepare and with no track, and it is the one place that adds, moves or deletes a
 * chapter. The parts are the ones the bin used to carry (`ChapterTools.tsx`, `EditTitlecard.tsx`):
 * same names, reasons and tooltips; the editor decides what each does (`EventEditor.tsx`).
 *
 * A row is one line with a fine pointer (name, count, then icon buttons) and wraps with a coarse
 * one (chapters.css). The notes, Delete's refusal and the hint of a chapter without clips sit
 * under the line. Every row carries `data-chapter-key` and takes focus (`tabIndex=-1`) after Add
 * chapter, as the editor's focus effects expect.
 */

/** What one chapter's row shows that the tools do not: its heading, its counts and its hint. */
export type ChapterRowModel = {
  chapter: DraftChapter
  heading: string
  /** The clips it plays. */
  played: number
  removed: number
  ignored: number
}

const ChapterRow = memo(function ChapterRow({
  chapterKey,
  heading,
  played,
  removed,
  ignored,
  tools,
  locked,
}: {
  chapterKey: ChapterKey
  heading: string
  played: number
  removed: number
  ignored: number
  tools: ChapterToolsModel
  locked: boolean
}) {
  const nameId = useId()
  const { count } = barContent(heading, played)
  // Move to… needs a second chapter: the tools have a place only then.
  const hint = chapterRowHint(played, removed, ignored, tools.place === null)
  return (
    <li className="chapter-row" data-chapter-key={chapterKey} tabIndex={-1} aria-labelledby={nameId}>
      {/* Plain text: not a button, no hover, nothing happens on a press. Renamed in the title card editor. */}
      <span id={nameId} className="chapter-row-name" title={heading}>
        {heading}
      </span>
      <span className="chapter-row-count">{count}</span>
      <EditTitlecard id={tools.cardId} heading={heading} locked={locked} compact />
      {/* The buttons alone, icon-only with tooltips; the second copy keeps the notes and the refusal. */}
      <ChapterTools
        chapterKey={chapterKey}
        heading={heading}
        headingId={nameId}
        placement="bar"
        {...tools}
      />
      <ChapterTools
        chapterKey={chapterKey}
        heading={heading}
        headingId={nameId}
        placement="row"
        {...tools}
      />
      {hint !== null && <p className="chapter-row-hint">{hint}</p>}
    </li>
  )
})

/** The Event tab's Chapters section. */
export const ChapterList = memo(function ChapterList({
  rows,
  tools,
  notes,
  locked,
  onAdd,
  onUndo,
}: {
  rows: readonly ChapterRowModel[]
  /** A live chapter's tools; a chapter without an entry is deleted. */
  tools: ReadonlyMap<ChapterKey, ChapterToolsModel>
  /** A deleted chapter's notes (where the folder's later clips go). */
  notes: ReadonlyMap<ChapterKey, readonly string[]>
  locked: boolean
  onAdd: () => void
  onUndo: ChapterHandler
}) {
  const headingId = useId()
  return (
    <section className="panel edit-chapters" aria-labelledby={headingId}>
      <header className="panel-header">
        <h2 id={headingId} tabIndex={-1}>
          Chapters
        </h2>
      </header>
      <div className="panel-body">
        <ol className="chapter-list">
          {rows.map(({ chapter, heading, played, removed, ignored }) => {
            const model = tools.get(chapter.key)
            return chapter.deleted || model === undefined ? (
              <li key={chapter.key} className="chapter-row-deleted" data-chapter-key={chapter.key}>
                <DeletedChapter
                  chapterKey={chapter.key}
                  heading={heading}
                  notes={notes.get(chapter.key) ?? NO_NOTES}
                  locked={locked}
                  onUndo={onUndo}
                />
              </li>
            ) : (
              <ChapterRow
                key={chapter.key}
                chapterKey={chapter.key}
                heading={heading}
                played={played}
                removed={removed}
                ignored={ignored}
                tools={model}
                locked={locked}
              />
            )
          })}
        </ol>
        <AddChapter locked={locked} onAdd={onAdd} />
      </div>
    </section>
  )
})

const NO_NOTES: readonly string[] = []
