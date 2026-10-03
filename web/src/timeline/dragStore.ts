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
  /**
   * One drag at a time: a press takes the store with its own token and is refused (false)
   * while another holds it, so a second finger on another handle cannot write its value
   * into the first one's edge. Claiming again with the same token is a yes.
   */
  claim(token: object): boolean
  /** Give the store back; only the holder's token does anything. */
  unclaim(token: object): void
  /** Whether this token holds the store. */
  owns(token: object): boolean
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
  let owner: object | null = null
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
    claim(token) {
      if (owner !== null && owner !== token) {
        return false
      }
      owner = token
      return true
    },
    unclaim(token) {
      if (owner === token) {
        owner = null
      }
    },
    owns: (token) => owner === token,
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
  }
}
