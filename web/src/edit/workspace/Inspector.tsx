import { useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import {
  INSPECTOR_LIST_NAME,
  INSPECTOR_TABS,
  INSPECTOR_TAB_EMPTY,
  INSPECTOR_TAB_NAME,
  inspectorTabAfterKey,
} from './inspectorTabs.ts'
import type { InspectorTab } from './inspectorTabs.ts'

/*
 * The workspace inspector (`editor-selection`): the tabs Clip, Title card, Suggestion and Event.
 * The tab shown follows the selection (`shownTab`), and the operator may pick another by hand.
 * Event holds the editor's event content; Clip, Title card and Suggestion are slots the Timeline
 * portals its panels and the card editor into (`TimelinePanesContext`), mounted while hidden so
 * the portals have somewhere to go.
 */

export function Inspector({
  tab,
  onTab,
  event,
  clipSlot,
  suggestionSlot,
  cardSlot,
}: {
  tab: InspectorTab
  onTab: (tab: InspectorTab) => void
  /** The Event tab. */
  event: ReactNode
  /** Where the Timeline's clip panel goes (the Clip tab), its suggestion panel and the card editor. */
  clipSlot: (node: HTMLElement | null) => void
  suggestionSlot: (node: HTMLElement | null) => void
  cardSlot: (node: HTMLElement | null) => void
}) {
  // Roving tabindex, arrow keys, Home and End (as the card editor's tabs).
  const tabsId = useId()
  const tabButtons = useRef(new Map<InspectorTab, HTMLButtonElement>())
  const onTabKey = (keyEvent: KeyboardEvent<HTMLButtonElement>) => {
    const next = inspectorTabAfterKey(tab, keyEvent.key)
    if (next !== null) {
      keyEvent.preventDefault()
      onTab(next)
      tabButtons.current.get(next)?.focus()
    }
  }
  const panel = (id: InspectorTab, children: ReactNode) => (
    <div
      role="tabpanel"
      id={`${tabsId}-panel-${id}`}
      aria-labelledby={`${tabsId}-tab-${id}`}
      className="ws-insp-panel"
      hidden={tab !== id}
      tabIndex={id === 'event' ? undefined : 0}
    >
      {children}
    </div>
  )
  return (
    <>
      <div className="ws-insp-tabs" role="tablist" aria-label={INSPECTOR_LIST_NAME}>
        {INSPECTOR_TABS.map((id) => (
          <button
            key={id}
            ref={(node) => {
              if (node === null) {
                tabButtons.current.delete(id)
              } else {
                tabButtons.current.set(id, node)
              }
            }}
            type="button"
            role="tab"
            id={`${tabsId}-tab-${id}`}
            className="ws-insp-tab"
            aria-selected={tab === id}
            aria-controls={`${tabsId}-panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => onTab(id)}
            onKeyDown={onTabKey}
          >
            {INSPECTOR_TAB_NAME[id]}
          </button>
        ))}
      </div>
      {panel(
        'clip',
        <>
          <div ref={clipSlot} className="ws-slot" />
          <p className="ws-empty">{INSPECTOR_TAB_EMPTY.clip}</p>
        </>,
      )}
      {panel(
        'card',
        <>
          <div ref={cardSlot} className="ws-slot ws-card-slot" />
          <p className="ws-empty">{INSPECTOR_TAB_EMPTY.card}</p>
        </>,
      )}
      {panel(
        'suggestion',
        <>
          <div ref={suggestionSlot} className="ws-slot" />
          <p className="ws-empty">{INSPECTOR_TAB_EMPTY.suggestion}</p>
        </>,
      )}
      {panel('event', event)}
    </>
  )
}
