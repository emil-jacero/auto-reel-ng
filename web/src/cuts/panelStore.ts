import { createClipPreviews } from '../preview/previews.ts'
import type { CutPanels, PanelState } from './CutsPanel'

/*
 * The editor's cut-panel store (`CutPanels`): each clip's two fields as typed, by identity. A
 * write tells that clip's subscribers (its panel, the bin's player), and a clear tells every clip
 * that had one, so a mounted panel empties its fields. Reset empties it and closes every clip
 * preview (one open at a time, `preview/previews.ts`).
 */
export function createCutPanels(): { panels: CutPanels; clear: () => void } {
  const held = new Map<string, PanelState>()
  const listeners = new Map<string, Set<() => void>>()
  const previews = createClipPreviews()
  const tell = (identity: string): void => {
    for (const listener of [...(listeners.get(identity) ?? [])]) {
      listener()
    }
  }
  const panels: CutPanels = {
    get: (identity) => held.get(identity),
    set: (identity, next) => {
      held.set(identity, next)
      tell(identity)
    },
    setTyped: (identity, field, text) => {
      const was = held.get(identity)
      held.set(identity, {
        start: field === 'start' ? text : (was?.start ?? ''),
        end: field === 'end' ? text : (was?.end ?? ''),
      })
      tell(identity)
    },
    subscribe: (identity, listener) => {
      const set = listeners.get(identity) ?? new Set<() => void>()
      listeners.set(identity, set.add(listener))
      return () => {
        set.delete(listener)
        if (set.size === 0 && listeners.get(identity) === set) {
          listeners.delete(identity)
        }
      }
    },
    previews,
  }
  return {
    panels,
    clear: () => {
      held.clear()
      previews.hideAll()
      for (const identity of [...listeners.keys()]) {
        tell(identity)
      }
    },
  }
}
