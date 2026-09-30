import { useEffect, useSyncExternalStore } from 'react'

import { setNavigationGuard } from '../route'

/*
 * Unsaved edits are never discarded silently. While the mounted editor holds
 * unsaved edits (`useUnsavedGuard`), every way of leaving them asks first:
 *
 * - closing or reloading the tab: the browser's own prompt (`beforeunload`)
 * - Back, Forward, a link or a typed address: the route's navigation guard
 *   undoes the move, keeps the page, and records how to redo it
 * - Refresh and leaving Edit mode: the page asks through `requestLeave`
 *
 * The question is one dialog, rendered by the editor while a leave is pending
 * (`usePendingLeave`). Keep editing drops the pending leave; Discard drops the
 * guard, then goes where the operator was going.
 */

type Guard = (proceed: () => void) => boolean

// The guard installed now. Only its owner removes it: the StrictMode replay
// (install, clean up, install) leaves exactly one.
let installed: Guard | null = null
// The open question: what Discard runs, and a number that tells it from the one
// before, so a question asked again before a render still opens a dialog. Null
// while nothing asks.
let pending: { id: number; proceed: () => void } | null = null
let asked = 0
const listeners = new Set<() => void>()

function setPending(proceed: (() => void) | null): void {
  asked += proceed === null ? 0 : 1
  pending = proceed === null ? null : { id: asked, proceed }
  for (const listener of listeners) {
    listener()
  }
}

function uninstall(): void {
  installed = null
  setNavigationGuard(null)
}

/** Run `proceed` at once when nothing is unsaved; otherwise ask first. */
export function requestLeave(proceed: () => void): void {
  if (installed === null) {
    proceed()
  } else {
    setPending(proceed)
  }
}

/** The answer "Keep editing" (or Escape): nothing leaves. */
export function keepEditing(): void {
  setPending(null)
}

/** The answer "Discard": drop the guard, then leave as asked. */
export function discardAndLeave(): void {
  const proceed = pending?.proceed
  setPending(null)
  if (installed !== null) {
    uninstall()
  }
  proceed?.()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The open question's number, to key its dialog by; 0 while nothing asks. */
export function usePendingLeave(): number {
  return useSyncExternalStore(subscribe, () => pending?.id ?? 0)
}

/** While `dirty`, guard every way of leaving. Used once, by the mounted editor. */
export function useUnsavedGuard(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) {
      return
    }
    const guard: Guard = (proceed) => {
      setPending(proceed)
      return false
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      // Engines that predate preventDefault() here ask only when this is set.
      event.returnValue = ''
    }
    installed = guard
    setNavigationGuard(guard)
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload)
      if (installed === guard) {
        uninstall()
        // The editor that would answer the question is gone with its edits.
        setPending(null)
      }
    }
  }, [dirty])
}
