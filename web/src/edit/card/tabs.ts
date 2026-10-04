/*
 * The card dialog's two tabs (`edit-mode-declutter`), as pure rules: their names, the arrow-key
 * order, the label of a tab that holds a problem the operator
 * cannot see, and the tab the dialog opens on. No DOM, no React.
 */

export type TabId = 'card' | 'event'

export const TAB_LIST_NAME = 'Title card settings'
export const TAB_ORDER: readonly TabId[] = ['card', 'event']
export const TAB_NAME: Record<TabId, string> = {
  card: 'This title card',
  event: 'All title cards in this event',
}

/** The tab a key moves to from `current`: Left and Right wrap, Home and End jump; null: not a tab key. */
export function tabAfterKey(current: TabId, key: string): TabId | null {
  const at = TAB_ORDER.indexOf(current)
  switch (key) {
    case 'ArrowRight':
      return TAB_ORDER[(at + 1) % TAB_ORDER.length]
    case 'ArrowLeft':
      return TAB_ORDER[(at + TAB_ORDER.length - 1) % TAB_ORDER.length]
    case 'Home':
      return TAB_ORDER[0]
    case 'End':
      return TAB_ORDER[TAB_ORDER.length - 1]
    default:
      return null
  }
}

/** How many problems each tab holds (the service's refusals and the fields the dialog refused). */
export type Problems = Record<TabId, number>

/** A tab's label: its name, and the count when it holds a problem. */
export function tabLabel(tab: TabId, problems: Problems): string {
  const count = problems[tab]
  return count === 0 ? TAB_NAME[tab] : `${TAB_NAME[tab]}, ${count} ${count === 1 ? 'problem' : 'problems'}`
}

/**
 * The tab the dialog opens on: the first that holds a problem the service's last answer named,
 * else "This title card". Nothing is remembered between openings.
 */
export function openingTab(named: Problems): TabId {
  return TAB_ORDER.find((tab) => named[tab] > 0) ?? 'card'
}
