import { useCallback, useMemo, useState } from 'react'

import { cardSelection } from './cards.ts'
import type { CardSelection } from './cards.ts'

/*
 * The one card selection of the event page (`title-card-blocks`): kept above Edit mode, as
 * the dismissals are, so a Refresh, a Save or leaving and re-entering Edit mode, which mount
 * the Timeline section anew, do not end it. By the chapter's saved name. Not stored, not in the URL.
 */

export type CardsBinding = {
  /** The selected card's chapter (its saved name; `""` is the opening), or null. */
  selected: string | null
  /** The chapter whose card dialog is open (Edit mode), or null. Always the selected one. */
  editing: string | null
  /** Selects without opening: a press on a duration handle. */
  select(chapter: string): void
  /** Selects and opens the dialog, also when the card is already selected. */
  open(chapter: string): void
  /** Closes the dialog; the card stays selected. */
  dismiss(): void
  clear(): void
  /** The chapters that are still there: ends a selection whose chapter is not among them. */
  retain(names: readonly string[]): void
}

export function useCardSelection(): CardsBinding {
  const [state, setState] = useState<CardSelection>(null)
  const select = useCallback((chapter: string) => setState((was) => cardSelection.select(was, chapter)), [])
  const open = useCallback((chapter: string) => setState((was) => cardSelection.open(was, chapter)), [])
  const dismiss = useCallback(() => setState((was) => cardSelection.dismiss(was)), [])
  const clear = useCallback(() => setState((was) => cardSelection.clear(was)), [])
  const retain = useCallback(
    (names: readonly string[]) => setState((was) => cardSelection.chapters(was, names)),
    [],
  )
  const selected = state?.chapter ?? null
  const editing = state?.editing ? state.chapter : null
  return useMemo(
    () => ({ selected, editing, select, open, dismiss, clear, retain }),
    [selected, editing, select, open, dismiss, clear, retain],
  )
}
