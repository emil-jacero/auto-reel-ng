import { useSyncExternalStore } from 'react'

/*
 * The single-key shortcuts switch (`editor-shortcuts`, D5; WCAG 2.1.4, Character Key Shortcuts).
 * On by default and kept in the browser as `auto-reel:shortcuts=off`; absent means on. A tiny
 * module store, read through `useSyncExternalStore`, so the switch in the Keyboard shortcuts list
 * and the workspace's key listener agree. Every storage read and write is guarded: when the
 * browser keeps nothing the switch is on and the choice lasts for the page visit only.
 */

export const SHORTCUTS_KEY = 'auto-reel:shortcuts'

/** The part of `Storage` this module needs. */
export interface SwitchStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

/** The page's storage, or null when the browser refuses to hand it out. */
function browserStorage(): SwitchStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** On unless the stored value is `off`; a storage that throws or is absent reads as on. */
export function readEnabled(storage: SwitchStorage | null): boolean {
  try {
    return storage?.getItem(SHORTCUTS_KEY) !== 'off'
  } catch {
    return true
  }
}

/** Remember the choice: `off` is stored, on removes the key. A refusing storage is not an error. */
export function writeEnabled(enabled: boolean, storage: SwitchStorage | null): void {
  try {
    if (enabled) {
      storage?.removeItem(SHORTCUTS_KEY)
    } else {
      storage?.setItem(SHORTCUTS_KEY, 'off')
    }
  } catch {
    // The choice holds for the page visit only.
  }
}

// null: not read yet, so the first read comes from the browser, then the module holds it.
let current: boolean | null = null
const listeners = new Set<() => void>()

/** Whether the workspace answers single-key shortcuts. */
export function shortcutsEnabled(): boolean {
  if (current === null) {
    current = readEnabled(browserStorage())
  }
  return current
}

/** Turn the switch, keep the choice, and tell every reader. */
export function setShortcutsEnabled(enabled: boolean): void {
  current = enabled
  writeEnabled(enabled, browserStorage())
  for (const listener of listeners) {
    listener()
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The switch as a hook (the list's checkbox). */
export function useShortcutsEnabled(): boolean {
  return useSyncExternalStore(subscribe, shortcutsEnabled, () => true)
}

/** Test seam: forget the held value so the next read goes to storage. */
export function resetShortcutSwitch(): void {
  current = null
}
