import { useCallback, useMemo, useState } from 'react'

import { cardSelection } from './cards.ts'
import type { CardSelection } from './cards.ts'

/*
 * The one card selection of the event page (`title-card-blocks`): kept above the read view
 * and Edit mode, as the dismissals are, so a Refresh or leaving Edit mode, which close the
 * Timeline section, do not end it. By the chapter's saved name. Not stored, not in the URL.
 */

export type CardsBinding = {
  /** The selected card's chapter (its saved name; `""` is the opening), or null. */
  selected: string | null
  select(chapter: string): void
  clear(): void
  /** The chapters that are still there: ends a selection whose chapter is not among them. */
  retain(names: readonly string[]): void
}

export function useCardSelection(): CardsBinding {
  const [state, setState] = useState<CardSelection>(null)
  const select = useCallback((chapter: string) => setState((was) => cardSelection.select(was, chapter)), [])
  const clear = useCallback(() => setState((was) => cardSelection.clear(was)), [])
  const retain = useCallback(
    (names: readonly string[]) => setState((was) => cardSelection.chapters(was, names)),
    [],
  )
  const selected = state?.chapter ?? null
  return useMemo(() => ({ selected, select, clear, retain }), [selected, select, clear, retain])
}
