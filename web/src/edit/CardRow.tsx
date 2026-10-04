import { createContext, memo, useContext, useId } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import { Icon } from '../ui/Icon'
import { ADDED_WORDS } from './cardRows'
import { USES_EVENT_STYLE } from './cardStyle.ts'
import type { CardRowInfo } from './cardRows'

/*
 * The chapter's card row (`title-card-blocks`): at the head of each chapter in Edit mode, its
 * card in words (title, subtitle, length, Black or Video, font). Main's row is the opening
 * card and holds the event-title control (D-13) beside it. Pressing the row selects the card,
 * the selection the Timeline's block shares; it writes nothing and requests nothing. A
 * chapter added in this session has no saved card, so its row says so and is not selectable.
 */

export type CardRowsModel = {
  /** The row of a chapter, by its key for the session; null when the event lists no such chapter. */
  rowOf(key: string): CardRowInfo | null
  /** The selected card's chapter (saved name) or null. */
  selected: string | null
  select(chapter: string): void
  clear(): void
}

export const CardRowsContext = createContext<CardRowsModel | null>(null)

export const CardRow = memo(function CardRow({
  chapterKey,
  children,
}: {
  chapterKey: string
  /** Main's event-title control, kept inside the row. */
  children?: ReactNode
}) {
  const model = useContext(CardRowsContext)
  const factsId = useId()
  const info = model?.rowOf(chapterKey) ?? null
  if (model === null || info === null) {
    return <>{children}</>
  }
  return (
    <div className="card-row" data-kind={info.kind}>
      {info.kind === 'added' && (
        <p className="card-row-body">
          <span className="card-row-label">Title card</span>
          <span className="card-row-words">{ADDED_WORDS}</span>
        </p>
      )}
      {info.kind === 'unresolved' && (
        <p className="card-row-body">
          <span className="card-row-label">Title card</span>
          <span className="card-row-words">
            Could not be resolved: {info.error}
            {info.savedName !== null && ` Saved name: ${info.savedName}.`}
          </span>
        </p>
      )}
      {info.kind === 'card' && (
        <button
          type="button"
          className="card-row-select"
          aria-pressed={model.selected === info.chapter}
          aria-label={info.words}
          aria-describedby={factsId}
          data-selected={model.selected === info.chapter || undefined}
          onClick={() => model.select(info.chapter)}
          onKeyDown={(event: KeyboardEvent<HTMLButtonElement>) => {
            if (event.key === 'Escape' && model.selected === info.chapter) {
              event.preventDefault()
              model.clear()
            }
          }}
        >
          <span className="card-row-label">
            {model.selected === info.chapter && <Icon name="check" size={16} />}
            Title card
          </span>
          <span id={factsId} className="card-row-facts">
            <span className="card-row-title">{info.title}</span>
            <span className="card-row-subtitle" data-empty={info.subtitle === 'No subtitle' || undefined}>
              {info.subtitle}
            </span>
            <span className="card-row-length">{info.length}</span>
            <span className="card-row-look">{info.look}</span>
            <span className="card-row-font">{info.font}</span>
            <span className="card-row-overrides" data-overrides={info.overrides !== USES_EVENT_STYLE || undefined}>
              {info.overrides}
            </span>
            {info.savedName !== null && (
              <span className="card-row-saved">Saved name: {info.savedName}</span>
            )}
          </span>
        </button>
      )}
      {children}
    </div>
  )
})
