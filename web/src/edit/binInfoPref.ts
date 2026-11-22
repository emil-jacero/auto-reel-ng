import { useSyncExternalStore } from 'react'

import type { PrefStorage } from './binPlayerPref.ts'

/*
 * Whether the bin's information panel is shown (`plain-clip-bin`, design D3). It starts shown;
 * Hide information collapses it to its heading and the choice is kept in the browser
 * (`auto-reel:bin-info` = `shown` or `hidden` in `localStorage`), as the player's is. A tiny module
 * store read through `useSyncExternalStore`, so the panel and its toggle agree. Every storage read
 * and write is guarded: when the browser keeps nothing the panel starts shown, and a choice made
 * lasts for the page visit only.
 */

export const BIN_INFO_KEY = 'auto-reel:bin-info'

/** The page's storage, or null when the browser refuses to hand it out. */
function browserStorage(): PrefStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** Whether the stored choice is `hidden`; anything else, a storage that throws or none is shown. */
export function readHidden(storage: PrefStorage | null): boolean {
  try {
    return storage?.getItem(BIN_INFO_KEY) === 'hidden'
  } catch {
    return false
  }
}

/** Remember the choice. A refusing storage is not an error. */
export function writeHidden(hidden: boolean, storage: PrefStorage | null): void {
  try {
    storage?.setItem(BIN_INFO_KEY, hidden ? 'hidden' : 'shown')
  } catch {
    // The choice holds for the page visit only.
  }
}

// undefined: not read yet, so the first read comes from the browser, then the module holds it.
let current: boolean | undefined
const listeners = new Set<() => void>()

/** Whether the information is hidden, read from the browser once. */
export function binInfoHidden(): boolean {
  if (current === undefined) {
    current = readHidden(browserStorage())
  }
  return current
}

/** Hide or show the information: kept, and every reader told. */
export function setBinInfoHidden(hidden: boolean): void {
  current = hidden
  writeHidden(hidden, browserStorage())
  for (const listener of listeners) {
    listener()
  }
}

/** Tell `listener` whenever the choice changes; returns the way to stop. */
export function subscribeBinInfo(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Whether the information is hidden, as a hook. */
export function useBinInfoHidden(): boolean {
  return useSyncExternalStore(subscribeBinInfo, binInfoHidden, () => false)
}

/** Test seam: forget the held value so the next read goes to storage. */
export function resetBinInfoPref(): void {
  current = undefined
}
