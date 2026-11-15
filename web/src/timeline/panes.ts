import { createContext } from 'react'

/*
 * Where Edit mode's workspace (`edit/workspace`, `editor-workspace-layout`) wants the Timeline's
 * parts: the viewer pane takes the picture and the transport, the inspector's Cut tab the cut
 * panel. The track stays where the Timeline is rendered (the bottom pane). Without a workspace
 * (null), or before a pane is mounted, the parts are stacked where the Timeline is.
 */
export type TimelinePanes = {
  viewer: HTMLElement | null
  cut: HTMLElement | null
  /** A cut or a suggestion was selected on the track: the inspector shows its Cut tab. */
  onCutSelected(): void
}

export const TimelinePanesContext = createContext<TimelinePanes | null>(null)
