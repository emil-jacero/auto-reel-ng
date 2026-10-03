import { createContext, memo, useContext, useId, useState } from 'react'
import type { ReactNode } from 'react'

import { InlineName } from './InlineName'
import { FILE_NAME_NOTE, acceptAnything, titleLine } from './inlineName'

/*
 * The event's own chapter is the main title card (D-13): under its heading, a line that shows
 * the event's title as a press-to-edit title, the same control a chapter's name is. It edits
 * `metadata.title` in the editor's draft, the field the metadata form's Title edits, so the two
 * stay in step. The editor provides the line's model through a context: the line follows the
 * title as it is typed in the form, and a chapter's list (memoised, up to hundreds of rows)
 * is never re-rendered by it.
 */

export type TitleCardModel = {
  /** `draft.metadata.title`: '' when it inherits from the folder name. */
  draftTitle: string
  /** The title the page resolved from the folder name, if any. */
  resolvedTitle: string | null
  /** The draft's title differs from the one read: saving renames the movie's file. */
  changed: boolean
  open: boolean
  locked: boolean
  /** The metadata form's words for a title left empty, or null. */
  inheritHint: (typed: string) => ReactNode
  onOpen: () => void
  onKeep: (title: string) => void
  onDrop: () => void
  onUnsent: (unsent: boolean) => void
}

export const TitleCardContext = createContext<TitleCardModel | null>(null)

/** "Main title card": the line's label. */
export const TITLE_CARD_LABEL = 'Main title card'

const NO_NOTES = () => null

export const TitleCard = memo(function TitleCard() {
  const model = useContext(TitleCardContext)
  const labelId = useId()
  const [host, setHost] = useState<HTMLElement | null>(null)
  if (model === null) {
    return null
  }
  const line = titleLine(model.draftTitle, model.resolvedTitle)
  return (
    <div className="title-card" role="group" aria-labelledby={labelId}>
      <span id={labelId} className="title-card-label">
        {TITLE_CARD_LABEL}
      </span>
      <InlineName
        text={line.text}
        muted={line.source !== 'draft'}
        value={model.draftTitle}
        fieldLabel="Title of the main title card"
        hint="Press to edit the event's title."
        open={model.open}
        locked={model.locked}
        check={acceptAnything}
        notes={model.open ? model.inheritHint : NO_NOTES}
        host={host}
        onOpen={model.onOpen}
        onKeep={model.onKeep}
        onDrop={model.onDrop}
        onUnsent={model.onUnsent}
      />
      {line.source === 'folder' && <span className="title-card-source">From the folder name</span>}
      <div ref={setHost} className="title-card-messages" />
      {model.changed && <p className="title-card-note">{FILE_NAME_NOTE}</p>}
    </div>
  )
})
