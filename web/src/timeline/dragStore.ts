import type { Edge, Ms } from './model.ts'

/*
 * The trim drag's store: the one place an edge being dragged lives until the pointer is
 * released. Only the parts that show it (the dragged handle, the cut's live span and the
 * selected cut's fields) subscribe, through `useSyncExternalStore`, so a drag re-renders
 * those and not the track, the Cuts panels or the save bar: the draft is written once,
 * on release. Plain JavaScript, so `npm test` runs it.
 */

/** An edge in the air: whose it is, where it is now, and what it snapped to. */
export type Dragging = {
  identity: string
  /** The cut's key in the draft (`r0`, `a1`…). */
  key: string
  edge: Edge
  ms: Ms
  /** The place the edge snapped to, or null. */
  snappedTo: Ms | null
  /** What it snapped to, in words (empty when it did not). */
  words: string
}

export type DragStore = {
  get(): Dragging | null
  /** Move the edge, or end the drag with null; listeners run only when something changed. */
  set(next: Dragging | null): void
  subscribe(listener: () => void): () => void
}

function same(a: Dragging | null, b: Dragging | null): boolean {
  if (a === null || b === null) {
    return a === b
  }
  return (
    a.identity === b.identity &&
    a.key === b.key &&
    a.edge === b.edge &&
    a.ms === b.ms &&
    a.snappedTo === b.snappedTo &&
    a.words === b.words
  )
}

export function createDragStore(): DragStore {
  let at: Dragging | null = null
  const listeners = new Set<() => void>()
  return {
    get: () => at,
    set(next) {
      if (same(at, next)) {
        return
      }
      at = next === null ? null : { ...next }
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
