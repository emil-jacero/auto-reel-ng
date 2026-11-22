/*
 * What the Timeline lends the Clip tab's Cuts panel while the track draws a clip
 * (`plain-clip-bin` D4): "+ Cut at playhead" and each cut's Edit, which need the track's playhead
 * and its cut selection. The panel is the editor's, the track is the Timeline's; this store is the
 * one thing between them. The Timeline sets a new view when what it draws or selects changes, and
 * clears it when it unmounts; the panel reads it with `useSyncExternalStore`. Pure: no DOM, no React.
 */

/** The track's side of the panel: a clip it draws, the selected cut, and the two things it does. */
export type TrackCutsView = {
  /** The identities the track draws. */
  drawn: ReadonlySet<string>
  /** The selected cut, whichever clip's it is; null when no cut is selected. */
  selected: { identity: string; key: string } | null
  /** Edit: select the cut on the track. */
  select(identity: string, key: string): void
  /** Select the clip itself (a removed cut that was the selection leaves the clip selected). */
  selectClip(identity: string): void
  /** "+ Cut at playhead" in `identity`: the refusal in words (already announced), or null when the cut was made. */
  add(identity: string): string | null
}

export type TrackCutsBridge = {
  get(): TrackCutsView | null
  set(view: TrackCutsView | null): void
  /** Called after each change of the view; returns its unsubscribe. */
  subscribe(listener: () => void): () => void
}

export function createTrackCuts(): TrackCutsBridge {
  let view: TrackCutsView | null = null
  const listeners = new Set<() => void>()
  return {
    get: () => view,
    set: (next) => {
      if (next === view) {
        return
      }
      view = next
      for (const listener of [...listeners]) {
        listener()
      }
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
  }
}

/** The track-only extras for `identity`'s panel, or null when the track does not draw it. */
export function trackCutsOf(view: TrackCutsView | null, identity: string) {
  if (view === null || !view.drawn.has(identity)) {
    return null
  }
  return {
    selectedKey: view.selected?.identity === identity ? view.selected.key : null,
    select: (key: string) => view.select(identity, key),
    selectClip: () => view.selectClip(identity),
    add: () => view.add(identity),
  }
}

export type TrackCuts = NonNullable<ReturnType<typeof trackCutsOf>>
