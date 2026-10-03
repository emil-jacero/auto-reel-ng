import type { Position } from './position.ts'

/*
 * The playhead's store: the one place the position lives, read through
 * `useSyncExternalStore` so a scrub re-renders only the components that read it, not
 * the track. Plain JavaScript, so `npm test` runs it.
 */

export type Playhead = {
  get(): Position
  /** Move the playhead; listeners run only when it moved. */
  set(p: Position): void
  subscribe(listener: () => void): () => void
}

export function createPlayhead(initial: Position): Playhead {
  let at = initial
  const listeners = new Set<() => void>()
  return {
    get: () => at,
    set(p) {
      if (p.clip === at.clip && p.ms === at.ms) {
        return
      }
      at = { clip: p.clip, ms: p.ms }
      for (const listener of [...listeners]) {
        listener()
      }
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
  }
}
