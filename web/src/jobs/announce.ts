import { useSyncExternalStore } from 'react'

/*
 * What this slice tells assistive technology without showing it: a list row's
 * own Render (queued, or already queued or running). The row itself shows the
 * job, and a toast would cover the Render controls of the rows below it (WCAG
 * 4.1.3 asks for the status message, not for a visible notification).
 *
 * One polite, visually hidden status region says the latest message. It is
 * rendered once, by `JobsIndicator`, which the shell always mounts, so the
 * region exists before its first message. Each message is a new node, so a
 * repeat is said again. It is cleared after a while, so it does not linger in
 * the header for someone reading the page later.
 */

export type Announcement = { readonly id: number; readonly message: string }

const CLEAR_AFTER_MS = 5000

let current: Announcement | null = null
let nextId = 1
let clearTimer: number | undefined
const listeners = new Set<() => void>()

function emit(next: Announcement | null): void {
  current = next
  for (const listener of listeners) {
    listener()
  }
}

/** Say `message` politely to assistive technology, with nothing shown. */
export function announce(message: string): void {
  window.clearTimeout(clearTimer)
  emit({ id: nextId, message })
  nextId += 1
  clearTimer = window.setTimeout(() => {
    clearTimer = undefined
    emit(null)
  }, CLEAR_AFTER_MS)
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The message being said now, if any. */
export function useAnnouncement(): Announcement | null {
  return useSyncExternalStore(subscribe, () => current)
}
