import { useSyncExternalStore } from 'react'

import type { PrefStorage } from '../binPlayerPref.ts'
import { paneHidden, parsePanes, serializePanes } from './paneSizes.ts'
import type { PaneId, PanePrefs } from './paneSizes.ts'

/*
 * The workspace's kept pane sizes and hidden panes (`resizable-panes`, design D2), in the browser
 * for every event and visit (`auto-reel:workspace-panes` in `localStorage`). A tiny module store
 * read through `useSyncExternalStore`, as `binPlayerPref.ts` is; every storage access is guarded,
 * so when the browser keeps nothing the choices last for the page visit. Beside it, the one source
 * of "stacked" (the page below 960 CSS px, where no pane is resized or hidden) and the request
 * that shows a hidden pane from outside the workspace.
 */

export const PANES_KEY = 'auto-reel:workspace-panes'

export type { PrefStorage }

const EMPTY: PanePrefs = Object.freeze({ sizes: Object.freeze({}), hidden: Object.freeze([]) })

/** The page's storage, or null when the browser refuses to hand it out. */
function browserStorage(): PrefStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** The stored panes; anything unparsable, a storage that throws or none is the empty prefs. */
export function readPanes(storage: PrefStorage | null): PanePrefs {
  try {
    const stored = storage?.getItem(PANES_KEY)
    return parsePanes(stored ?? null) ?? EMPTY
  } catch {
    return EMPTY
  }
}

/** Remember the panes (the key is removed when there is nothing to keep). A refusing storage is not an error. */
export function writePanes(prefs: PanePrefs, storage: PrefStorage | null): void {
  try {
    const raw = serializePanes(prefs)
    if (raw === null) {
      storage?.removeItem(PANES_KEY)
    } else {
      storage?.setItem(PANES_KEY, raw)
    }
  } catch {
    // The choice holds for the page visit only.
  }
}

// undefined: not read yet, so the first read comes from the browser, then the module holds it.
let current: PanePrefs | undefined
const listeners = new Set<() => void>()

/** The kept panes, read from the browser once; the same object until they change. */
export function panePrefs(): PanePrefs {
  if (current === undefined) {
    current = readPanes(browserStorage())
  }
  return current
}

/** Keep `next` (what `commitPanes` returned) and tell every reader. */
export function setPanePrefs(next: PanePrefs): void {
  current = next
  writePanes(next, browserStorage())
  for (const listener of listeners) {
    listener()
  }
}

/** Tell `listener` whenever the panes change; returns the way to stop. */
export function subscribePanePrefs(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The kept panes, as a hook. */
export function usePanePrefs(): PanePrefs {
  return useSyncExternalStore(subscribePanePrefs, panePrefs, () => EMPTY)
}

/** Test seam: forget the held value so the next read goes to storage. */
export function resetPanePrefs(): void {
  current = undefined
}

// --- stacked -----------------------------------------------------------------------------------

/** The same media query as `workspace.css`'s stacked layout (a viewport query, scrollbar included). */
export const STACKED_QUERY = '(width < 960px)'

function stackedList(): MediaQueryList | null {
  try {
    return window.matchMedia(STACKED_QUERY)
  } catch {
    return null
  }
}

/** Whether the page is stacked (false where the browser has no `matchMedia`). */
export function isStacked(): boolean {
  return stackedList()?.matches ?? false
}

function subscribeStacked(listener: () => void): () => void {
  const list = stackedList()
  list?.addEventListener('change', listener)
  return () => {
    list?.removeEventListener('change', listener)
  }
}

/** Whether the page is stacked, as a hook. */
export function useStacked(): boolean {
  return useSyncExternalStore(subscribeStacked, isStacked, () => false)
}

/** Whether `pane` is hidden as laid out now (never while stacked), read at call time. */
export function isPaneHidden(pane: PaneId): boolean {
  return paneHidden(pane, panePrefs(), isStacked())
}

/** Whether `pane` is hidden, as a hook. */
export function usePaneHidden(pane: PaneId): boolean {
  return paneHidden(pane, usePanePrefs(), useStacked())
}

// --- showing a pane from outside the workspace -------------------------------------------------

let shower: ((pane: PaneId) => void) | null = null

/** The workspace registers how a hidden pane is shown; returns the way to unregister. */
export function registerPaneShower(fn: (pane: PaneId) => void): () => void {
  shower = fn
  return () => {
    if (shower === fn) {
      shower = null
    }
  }
}

/** Show `pane` if it is hidden (at its kept size); nothing when no workspace is mounted. */
export function showPane(pane: PaneId): void {
  shower?.(pane)
}
