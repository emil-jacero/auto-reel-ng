import { useSyncExternalStore } from 'react'

/*
 * Whether the bin's player is hidden (`clip-tab-and-player`, design D3). Kept in the browser as
 * `auto-reel:bin-player=hidden`; absent means shown. A tiny module store, read through
 * `useSyncExternalStore`, the pattern the single-key shortcuts switch uses, so the player, its Hide
 * and Show controls and the row's Watch agree. Every storage read and write is guarded: when the
 * browser keeps nothing the player is shown and a choice lasts for the page visit only.
 */

export const BIN_PLAYER_KEY = 'auto-reel:bin-player'

/** The part of `Storage` this module needs. */
export interface PrefStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

/** The page's storage, or null when the browser refuses to hand it out. */
function browserStorage(): PrefStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** Shown unless the stored value is `hidden`; a storage that throws or is absent reads as shown. */
export function readShown(storage: PrefStorage | null): boolean {
  try {
    return storage?.getItem(BIN_PLAYER_KEY) !== 'hidden'
  } catch {
    return true
  }
}

/** Remember the choice: `hidden` is stored, shown removes the key. A refusing storage is not an error. */
export function writeShown(shown: boolean, storage: PrefStorage | null): void {
  try {
    if (shown) {
      storage?.removeItem(BIN_PLAYER_KEY)
    } else {
      storage?.setItem(BIN_PLAYER_KEY, 'hidden')
    }
  } catch {
    // The choice holds for the page visit only.
  }
}

// null: not read yet, so the first read comes from the browser, then the module holds it.
let current: boolean | null = null
const listeners = new Set<() => void>()

/** Whether the player is shown. */
export function binPlayerShown(): boolean {
  if (current === null) {
    current = readShown(browserStorage())
  }
  return current
}

/** Show or hide the player, keep the choice, and tell every reader. */
export function setBinPlayerShown(shown: boolean): void {
  current = shown
  writeShown(shown, browserStorage())
  for (const listener of listeners) {
    listener()
  }
}

/** Tell `listener` whenever the choice changes; returns the way to stop. */
export function subscribeBinPlayer(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The preference as a hook. */
export function useBinPlayerShown(): boolean {
  return useSyncExternalStore(subscribeBinPlayer, binPlayerShown, () => true)
}

/** Test seam: forget the held value so the next read goes to storage. */
export function resetBinPlayerPref(): void {
  current = null
}
