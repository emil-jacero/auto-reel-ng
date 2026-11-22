import { useEffect, useId, useState } from 'react'

import type { ChapterKey } from '../edit/draft'
import { Icon } from '../ui/Icon'
import { chosenOf, moveChoices, moveWhy } from './moveTo'

/*
 * The Clip tab's Move to… (`clip-multi-select` D5), one component for one clip and for several:
 * a native chapter picker and a Move button, with the reasons Move cannot act in words
 * (`aria-disabled`, never `disabled`, so focus stays on the button).
 * `own` is the one clip's chapter, left out of the picker; null for several clips. The tab
 * dispatches the edit: `onMove` is called only when a chapter is chosen and nothing is pending.
 */
export function MoveTo({
  selectLabel,
  chapters,
  own,
  locked,
  moving,
  announce,
  onMove,
}: {
  /** The picker's accessible name: "Chapter to move s1710003.mp4 to". */
  selectLabel: string
  chapters: readonly { key: ChapterKey; name?: string }[]
  own: ChapterKey | null
  /** A save or a move of several clips is pending. */
  locked: boolean
  /** Only a move of several clips is pending (no save): the reason says so. */
  moving: boolean
  announce(words: string): void
  onMove(to: ChapterKey): void
}) {
  const base = useId()
  const [value, setValue] = useState('')
  // The reason line shows only once Move is pressed while it cannot act; it goes when Move can.
  const [shown, setShown] = useState(false)
  const choices = moveChoices(chapters, own)
  const chosen = chosenOf(choices, value)
  const why = moveWhy(chosen !== '', locked, moving)
  useEffect(() => {
    if (why === null) {
      setShown(false)
    }
  }, [why])
  if (choices.length === 0) {
    return null
  }
  const press = () => {
    if (why !== null) {
      setShown(true)
      announce(why)
      return
    }
    onMove(chosen)
  }
  return (
    <div className="ct-move" role="group" aria-labelledby={`${base}-label`}>
      <label id={`${base}-label`} htmlFor={`${base}-select`} className="ct-move-label">
        Move to…
      </label>
      <select
        id={`${base}-select`}
        className="field-input ct-move-select"
        aria-label={selectLabel}
        value={chosen}
        aria-disabled={locked || undefined}
        aria-describedby={`${base}-why`}
        onChange={(event) => {
          if (!locked) {
            setValue(event.currentTarget.value)
          }
        }}
      >
        <option value="">Choose a chapter</option>
        {choices.map((choice) => (
          <option key={choice.key} value={choice.key}>
            {choice.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn-secondary ct-move-go"
        aria-disabled={why !== null || undefined}
        aria-describedby={`${base}-why`}
        title={why ?? undefined}
        onClick={press}
      >
        <Icon name="arrow-right" />
        Move
      </button>
      <p id={`${base}-why`} className={shown ? 'ct-move-why' : 'visually-hidden'}>
        {why ?? ''}
      </p>
    </div>
  )
}
