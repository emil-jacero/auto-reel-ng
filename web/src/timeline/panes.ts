import { createContext } from 'react'

/*
 * Where Edit mode's workspace (`edit/workspace`, `editor-workspace-layout`) wants the Timeline's
 * parts: the viewer pane takes the picture and the transport, the inspector's Clip tab the clip
 * panel and its Suggestion tab the suggestion's decision. The track stays where the Timeline is
 * rendered (the bottom pane). Without a workspace (null), or before a pane is mounted, the parts
 * are stacked where the Timeline is.
 */
export type TimelinePanes = {
  viewer: HTMLElement | null
  clip: HTMLElement | null
  suggestion: HTMLElement | null
}

export const TimelinePanesContext = createContext<TimelinePanes | null>(null)
