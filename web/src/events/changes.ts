import { useSyncExternalStore } from 'react'

/*
 * "An event changed": a per-tab counter that says only that some event changed
 * since a given read — through a save on an event page, a finished render, or
 * anything else the client learned of — not which one or how.
 *
 * The event list records the version at the start of every read, and reads
 * again when it is shown with a newer one, so Back stays request-free unless
 * something changed meanwhile. Whoever learns of a change calls
 * `markEventsChanged()`. In memory only: a reload reads everything anyway.
 */

let version = 0
const listeners = new Set<() => void>()

/** Record that an event changed. */
export function markEventsChanged(): void {
  version += 1
  for (const listener of listeners) {
    listener()
  }
}

/** The version now, for a read to record at its start. */
export function currentEventsVersion(): number {
  return version
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The version, re-rendering on every mark. */
export function useEventsVersion(): number {
  return useSyncExternalStore(subscribe, currentEventsVersion)
}
