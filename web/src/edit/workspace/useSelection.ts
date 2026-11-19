import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { flushSync } from 'react-dom'

import type { TabId } from '../card/tabs.ts'
import { clearState, consumeState, keepState, NOTHING, openState, selectState } from './selection.ts'
import type { Selection, SelectionState, World } from './selection.ts'

/*
 * The event page's one selection (`editor-selection`, design D1): kept above Edit mode, as the
 * dismissals are, so a Refresh, a Save or leaving and re-entering Edit mode, which mount the
 * Timeline section anew, do not end it. Not stored, not in the URL. The Timeline's cut presses,
 * the suggestion marks and the card blocks and rows all read and write it through `set`.
 *
 * The card editor is docked in the inspector (design D3): it shows whenever a card is selected.
 * `open` also asks it to take focus; `leave` is Escape from inside it.
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
  /** Selects the card without asking for focus: a press on a duration handle. */
  select(chapter: string): void
  /** Set when the selected card was asked for (`open`): the editor takes focus. Null: it was not. */
  opened: { tab: TabId | null; focus: boolean } | null
  /** Selects the card, asks for its editor on `tab` if given, and for focus in it, also when selected. */
  open(chapter: string, tab?: TabId): void
  /** Selects the card and shows its editor (the Title card tab) but leaves focus where it is: a press on its block. */
  reveal(chapter: string): void
  /** The editor has acted on `opened` (tab and focus): the request ends, the selection stays. */
  handled(): void
  /**
   * Escape from inside the card editor: focus goes to the control that selected the card (the
   * Edit Titlecard button or the card block), then nothing is selected, so the focused field
   * never unmounts onto the page body.
   */
  leave(): void
}

/** Whether the Keyboard shortcuts list (`#ws-keys`, a popover) is open: Escape then closes only it. */
function keysListOpen(): boolean {
  try {
    return document.querySelector('#ws-keys:popover-open') !== null
  } catch {
    // A browser without `:popover-open` has no popover to close.
    return false
  }
}

/**
 * Whether Escape on `target` belongs to something else: a field, a dialog that is open, or the
 * Keyboard shortcuts list (`popoverOpen`, which Escape closes natively).
 */
export function escapeIsElsewhere(
  target: EventTarget | null,
  dialogOpen: boolean,
  popoverOpen = false,
): boolean {
  if (dialogOpen || popoverOpen) {
    return true
  }
  const element = target as HTMLElement | null
  if (element === null || typeof element.tagName !== 'string') {
    return false
  }
  const tag = element.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || element.isContentEditable === true
}

/** Whether `element` is on the page and not inside a hidden tab. */
function isShown(element: HTMLElement): boolean {
  return element.isConnected && element.closest('[hidden]') === null
}

/**
 * Where Escape from the card editor puts focus: the first of `candidates`, in order, that is
 * shown (`kept`: the control that selected the card; then the card's Edit Titlecard button, its
 * block, and the Chapters heading; a card selected from its block has no `kept`, so `leave` puts
 * the block before the button), or null.
 */
export function returnTarget<T>(
  candidates: readonly (T | null | undefined)[],
  shown: (element: T) => boolean,
): T | null {
  for (const candidate of candidates) {
    if (candidate !== null && candidate !== undefined && shown(candidate)) {
      return candidate
    }
  }
  return null
}

export function useSelection(): SelectionBinding {
  const [state, setState] = useState<SelectionState>(NOTHING)
  // The control that asked for the card's editor, to give focus back to.
  const opener = useRef<HTMLElement | null>(null)
  const set = useCallback((next: Selection) => {
    opener.current = null
    setState((was) => selectState(was, next))
  }, [])
  const clear = useCallback(() => setState(clearState), [])
  const keep = useCallback(
    (part: Partial<World>) => setState((was) => keepState(was, part)),
    [],
  )
  const select = useCallback((chapter: string) => set({ kind: 'card', chapter }), [set])
  const handled = useCallback(() => setState(consumeState), [])
  const reveal = useCallback((chapter: string) => {
    opener.current = null
    setState((was) => openState(was, chapter, undefined, false))
  }, [])
  const open = useCallback((chapter: string, tab?: TabId) => {
    const active = document.activeElement
    opener.current = active instanceof HTMLElement && active !== document.body ? active : null
    setState((was) => openState(was, chapter, tab))
  }, [])

  // Escape clears the selection, unless a field, an open dialog or shortcuts list, a drag or a control that took
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
        escapeIsElsewhere(event.target, document.querySelector('dialog[open]') !== null, keysListOpen())
      ) {
        return
      }
      clear()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [selecting, clear])

  const card = state.sel.kind === 'card' ? state.sel.chapter : null
  const leave = useCallback(() => {
    const kept = opener.current
    const byCard = (selector: string) =>
      card === null
        ? undefined
        : Array.from(document.querySelectorAll<HTMLElement>(selector)).find(
            (candidate) => candidate.dataset.card === card,
          )
    // The card's own Edit Titlecard button (its chapter's row), and the card block: where the
    // opener is gone but the chapter is not (the row was drawn anew).
    const button = byCard('.edit-chapters button.edit-titlecard[data-card]')
    const block = byCard('button.tl-card[data-card]')
    opener.current = null
    // Nothing is selected first, so the Event tab (which hides the opener while the Title card
    // tab shows) is visible again when focus moves: the focused field never unmounts onto the body.
    flushSync(clear)
    // Last, the Chapters heading: the chapter was deleted meanwhile, so no button or block is left.
    const heading = document.querySelector<HTMLElement>('.edit-chapters > .panel-header > h2')
    // No opener recorded: the card was selected from its Timeline block (`reveal`), so the block
    // comes before the row's button, which the Event tab shows again.
    const candidates = kept === null ? [block, button, heading] : [kept, button, block, heading]
    returnTarget(candidates, isShown)?.focus({ preventScroll: true })
  }, [card, clear])
  const { opened } = state
  return useMemo(
    () => ({ selection: state.sel, again: state.again, set, clear, keep, selected: card, select, opened, open, reveal, handled, leave }),
    [state.sel, state.again, set, clear, keep, card, select, opened, open, reveal, handled, leave],
  )
}
