/*
 * The workspace inspector's four tabs (`editor-selection`), as pure rules: their names, the
 * arrow-key order, and which one shows. The tab follows the selection (`inspectorTab`); the
 * operator may pick another by hand, and the next selection picks the tab again. No DOM, no React.
 */

import { inspectorTab, sameSelection } from './selection.ts'
import type { Selection } from './selection.ts'

export type InspectorTab = ReturnType<typeof inspectorTab>

export const INSPECTOR_LIST_NAME = 'Inspector'
export const INSPECTOR_TABS: readonly InspectorTab[] = ['clip', 'card', 'suggestion', 'event']
export const INSPECTOR_TAB_NAME: Record<InspectorTab, string> = {
  clip: 'Clip',
  card: 'Title card',
  suggestion: 'Suggestion',
  event: 'Event',
}
/** What a tab with nothing of its kind selected says. */
export const INSPECTOR_TAB_EMPTY: Record<Exclude<InspectorTab, 'event'>, string> = {
  clip: 'Select a clip or a cut on the Timeline, or a clip in the bin: its fields show here.',
  card: 'Select a title card on the Timeline, or a chapter’s Edit Titlecard in the bin: its card shows here.',
  suggestion: 'Select a suggestion’s mark on the Timeline: its decision shows here.',
}

/** A tab the operator picked by hand, and the selection (and re-press count) it was picked over. */
export type PickedTab = { tab: InspectorTab; sel: Selection; again: number }

/** Whether a hand-picked tab still stands: only while the very selection it was made over stands. */
export function pickStands(picked: PickedTab | null, sel: Selection, again: number): boolean {
  return picked !== null && picked.again === again && sameSelection(picked.sel, sel)
}

/**
 * The tab shown: the operator's pick while it stands, else the one the selection gives. A pick
 * ends the moment the selection changes (the hook clears it then), so it never comes back later.
 */
export function shownTab(picked: PickedTab | null, sel: Selection, again: number): InspectorTab {
  return picked !== null && pickStands(picked, sel, again) ? picked.tab : inspectorTab(sel)
}

/** The tab a key moves to from `current`: Left and Right wrap, Home and End jump; null: not a tab key. */
export function inspectorTabAfterKey(current: InspectorTab, key: string): InspectorTab | null {
  const at = INSPECTOR_TABS.indexOf(current)
  const count = INSPECTOR_TABS.length
  switch (key) {
    case 'ArrowRight':
      return INSPECTOR_TABS[(at + 1) % count]
    case 'ArrowLeft':
      return INSPECTOR_TABS[(at + count - 1) % count]
    case 'Home':
      return INSPECTOR_TABS[0]
    case 'End':
      return INSPECTOR_TABS[count - 1]
    default:
      return null
  }
}

/**
 * Whether title cards are on, in words, for the Event tab: the service's answer as the draft has
 * it now (`TitleCardsModel`), never a guess; with no answer, that it is not known and why.
 */
export function titleCardsWords(model: {
  answer: unknown
  error: string | null
  on: boolean
}): string {
  if (model.answer === null) {
    const why = model.error === null || model.error === '' ? '' : ` ${model.error}`
    return `Whether title cards are on is not known.${why}`
  }
  return model.on ? 'Title cards are on for this event.' : 'Title cards are off for this event.'
}
