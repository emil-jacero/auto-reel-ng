import { useCallback, useEffect, useMemo, useState } from 'react'

import type { TabId } from '../card/tabs.ts'
import { clearState, dismissState, keepState, NOTHING, openState, selectState } from './selection.ts'
import type { Selection, SelectionState, World } from './selection.ts'

/*
 * The event page's one selection (`editor-selection`, design D1): kept above Edit mode, as the
 * dismissals are, so a Refresh, a Save or leaving and re-entering Edit mode, which mount the
 * Timeline section anew, do not end it. Not stored, not in the URL. The Timeline's cut presses,
 * the suggestion marks and the card blocks and rows all read and write it through `set`.
 *
 * The card dialog (still the card editor until it docks) is open only for the selected card.
 */

export type SelectionBinding = {
  selection: Selection
  /** Counts the presses on the clip that was already selected (re-press: show me). */
  again: number
  /** Selects `next`, which ends whatever was selected; the same target again changes nothing. */
  set(next: Selection): void
  /** Escape and the like: nothing is selected. */
  clear(): void
  /** Ends the selection when its target is gone from `part` of the world (`keptSelection`). */
  keep(part: Partial<World>): void
  /** The selected card's chapter (its saved name; `""` is the opening), or null. */
  selected: string | null
  /** The chapter whose card dialog is open (Edit mode), or null. Always the selected one. */
  editing: string | null
  /** Selects the card without opening: a press on a duration handle. */
  select(chapter: string): void
  /** The tab the open dialog was asked to start on, or null: the dialog picks its own. */
  tab: TabId | null
  /** Selects and opens the dialog, also when the card is already selected; on `tab` if given. */
  open(chapter: string, tab?: TabId): void
  /** Closes the dialog; the card stays selected. */
  dismiss(): void
}

/** Whether Escape on `target` belongs to something else: a field, or a dialog that is open. */
export function escapeIsElsewhere(target: EventTarget | null, dialogOpen: boolean): boolean {
  if (dialogOpen) {
    return true
  }
  const element = target as HTMLElement | null
  if (element === null || typeof element.tagName !== 'string') {
    return false
  }
  const tag = element.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || element.isContentEditable === true
}

export function useSelection(): SelectionBinding {
  const [state, setState] = useState<SelectionState>(NOTHING)
  const set = useCallback((next: Selection) => setState((was) => selectState(was, next)), [])
  const clear = useCallback(() => setState(clearState), [])
  const keep = useCallback(
    (part: Partial<World>) => setState((was) => keepState(was, part)),
    [],
  )
  const select = useCallback((chapter: string) => set({ kind: 'card', chapter }), [set])
  const open = useCallback(
    (chapter: string, tab?: TabId) => setState((was) => openState(was, chapter, tab)),
    [],
  )
  const dismiss = useCallback(() => setState(dismissState), [])

  // Escape clears the selection, unless a field, an open dialog, a drag or a control that took
  // the key itself (`defaultPrevented`, or stopped) has it.
  const selecting = state.sel.kind !== 'none'
  useEffect(() => {
    if (!selecting) {
      return
    }
    const onKey = (event: KeyboardEvent) => {
      if (
        event.key !== 'Escape' ||
        event.defaultPrevented ||
        event.ctrlKey ||
        event.altKey ||
        event.metaKey ||
        event.isComposing ||
        escapeIsElsewhere(event.target, document.querySelector('dialog[open]') !== null)
      ) {
        return
      }
      clear()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [selecting, clear])

  const card = state.sel.kind === 'card' ? state.sel.chapter : null
  const editing = state.dialog !== null ? card : null
  const tab = editing !== null ? (state.dialog?.tab ?? null) : null
  return useMemo(
    () => ({ selection: state.sel, again: state.again, set, clear, keep, selected: card, editing, tab, select, open, dismiss }),
    [state.sel, state.again, set, clear, keep, card, editing, tab, select, open, dismiss],
  )
}
