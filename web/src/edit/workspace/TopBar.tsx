import type { ReactNode } from 'react'

import { ThemeControl } from '../../shell/AppShell'
import { Icon } from '../../ui/Icon'

/*
 * The workspace's top bar (`editor-workspace-layout`, design D4): back to the event list, the
 * event's title with its date and location, the save bar's states (`SaveBar` in its top form),
 * Done and the theme switch. Back and Done leave Edit mode through the page's leave flow, the
 * unsaved guard included; both wait while a save is in flight (busy-control rule: aria-disabled,
 * never `disabled`, so focus stays).
 */

/** What the event page gives the workspace: its heading, facts, leave flow and render region. */
export type WorkspaceFrame = {
  /** The event's title as the level-one heading (the page's own, focused on entering). */
  heading: ReactNode
  /** `date · location`, or null when the event has neither. */
  facts: string | null
  /** Leaves Edit mode as Done does, then shows the event list. */
  onBack(): void
  onDone(): void
  /** A save in flight: Back and Done wait for its answer. */
  held: boolean
  /** The page's parts the inspector's Event tab shows under the fields (the render region, notes). */
  aside: ReactNode
}

export function TopBar({ frame, saveBar }: { frame: WorkspaceFrame; saveBar: ReactNode }) {
  return (
    <div className="ws-topbar">
      <button
        type="button"
        className="btn btn-ghost ws-back"
        aria-disabled={frame.held || undefined}
        onClick={() => {
          if (!frame.held) {
            frame.onBack()
          }
        }}
      >
        <Icon name="chevron-left" />
        Events
      </button>
      <div className="ws-title">
        {frame.heading}
        {frame.facts !== null && <span className="ws-facts">{frame.facts}</span>}
      </div>
      <div className="ws-save">{saveBar}</div>
      <button
        type="button"
        className="btn btn-secondary ws-done"
        aria-disabled={frame.held || undefined}
        onClick={() => {
          if (!frame.held) {
            frame.onDone()
          }
        }}
      >
        <Icon name="check" />
        Done
      </button>
      <ThemeControl />
    </div>
  )
}
