import { createContext, memo, useContext } from 'react'

import { Icon } from '../ui/Icon'
import { EDIT_TITLECARD, barButton, editTitlecardName } from './chapterBar'

/*
 * "Edit Titlecard" (`edit-mode-declutter`): the button in every chapter's header bar. It selects
 * the chapter's card, the selection the Timeline's blocks share, and shows its editor in the
 * inspector, the one place for a name and a card. It writes nothing itself. Busy-control rule: while a save or
 * a move is pending it is `aria-disabled` and opens nothing.
 */

export type CardButtonModel = {
  /** The selected card's id (`cardIdOf`) or null. */
  selected: string | null
  /** Selects the card and takes focus into its editor. */
  open(id: string): void
}

export const CardButtonContext = createContext<CardButtonModel | null>(null)

const PENCIL = <Icon name="pencil" />

export const EditTitlecard = memo(function EditTitlecard({
  id,
  heading,
  locked,
}: {
  id: string
  heading: string
  locked: boolean
}) {
  const model = useContext(CardButtonContext)
  if (model === null) {
    return null
  }
  const { pressed, unavailable } = barButton(model.selected, id, locked)
  return (
    <button
      type="button"
      className="btn btn-secondary edit-titlecard"
      aria-label={editTitlecardName(heading)}
      aria-pressed={pressed}
      aria-disabled={unavailable || undefined}
      onClick={() => {
        if (!unavailable) {
          model.open(id)
        }
      }}
    >
      {PENCIL}
      {/* The bin's compact header shows the icon alone (workspace.css); the name says it all. */}
      <span className="edit-titlecard-words">{EDIT_TITLECARD}</span>
    </button>
  )
})
