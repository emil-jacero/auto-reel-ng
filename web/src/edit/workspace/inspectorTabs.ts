/*
 * The workspace inspector's two tabs (`editor-workspace-layout`), as pure rules: their names and
 * the arrow-key order. A new cut or suggestion selection on the Timeline shows Cut
 * (`TimelinePanes.onCutSelected`). No DOM, no React.
 */

export type InspectorTab = 'event' | 'cut'

export const INSPECTOR_LIST_NAME = 'Inspector'
export const INSPECTOR_TABS: readonly InspectorTab[] = ['event', 'cut']
export const INSPECTOR_TAB_NAME: Record<InspectorTab, string> = {
  event: 'Event',
  cut: 'Cut',
}
/** The Cut tab with nothing selected. */
export const CUT_TAB_EMPTY =
  'Select a cut by its handle or its span, or a suggestion’s mark, on the Timeline: its fields show here.'

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
