import { useSyncExternalStore } from 'react'

/*
 * Whether the bin's player starts shown or hidden (`clip-tab-and-player`, design D3). The operator's
 * choice is one of three: none, shown or hidden. With a choice, it always wins, also across visits
 * (`auto-reel:bin-player` = `shown` or `hidden` in `localStorage`). With none, the window decides:
 * in the side pane's layout (from 960 CSS pixels wide, no coarse pointer) the player starts hidden
 * in a window shorter than 70.125rem, the height at which Tjorn's four played rows fit whole with
 * the player shown (1122 px at a 16 px root, measured in Firefox 159 and Chrome 158 at 1440 wide),
 * and shown otherwise; a stacked page or a coarse pointer starts shown. Only while there is no
 * choice does a window resize change the player.
 *
 * A tiny module store read through `useSyncExternalStore`, the pattern the single-key shortcuts
 * switch uses, so the player, its Hide and Show controls and the row's Watch agree. Every storage
 * read and write is guarded: when the browser keeps nothing there is no stored choice, so the
 * height rule decides, and a choice made lasts for the page visit only.
 */

export const BIN_PLAYER_KEY = 'auto-reel:bin-player'

/**
 * The windows that start with the player hidden when the operator has made no choice: the side
 * pane's layout (`@media (width >= 960px) and (not (pointer: coarse))`, as the compact player) and
 * shorter than the height at which Tjorn's four played rows fit whole under the player.
 */
export const SHORT_WINDOW_QUERY = '(width >= 960px) and (not (pointer: coarse)) and (height < 70.125rem)'

/** The operator's choice: none yet, or one of the two states. */
export type PlayerChoice = 'shown' | 'hidden' | null

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

/** The stored choice: `shown` or `hidden`; anything else, a storage that throws or none is no choice. */
export function readChoice(storage: PrefStorage | null): PlayerChoice {
  try {
    const stored = storage?.getItem(BIN_PLAYER_KEY)
    return stored === 'shown' || stored === 'hidden' ? stored : null
  } catch {
    return null
  }
}

/** Remember the choice. A refusing storage is not an error. */
export function writeChoice(choice: 'shown' | 'hidden', storage: PrefStorage | null): void {
  try {
    storage?.setItem(BIN_PLAYER_KEY, choice)
  } catch {
    // The choice holds for the page visit only.
  }
}

/** Whether the player is shown: the choice when there is one, otherwise the height rule. */
export function playerShown(choice: PlayerChoice, shortWindow: boolean): boolean {
  return choice === null ? !shortWindow : choice === 'shown'
}

// undefined: not read yet, so the first read comes from the browser, then the module holds it.
let current: PlayerChoice | undefined
const listeners = new Set<() => void>()

/** The operator's choice, read from the browser once. */
export function binPlayerChoice(): PlayerChoice {
  if (current === undefined) {
    current = readChoice(browserStorage())
  }
  return current
}

/** Show or hide the player: an explicit choice that wins from now on. It is kept, and every reader told. */
export function setBinPlayerShown(shown: boolean): void {
  current = shown ? 'shown' : 'hidden'
  writeChoice(current, browserStorage())
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

/** The height rule's media query list, or null where the browser has no `matchMedia`. */
function shortList(): MediaQueryList | null {
  try {
    return window.matchMedia(SHORT_WINDOW_QUERY)
  } catch {
    return null
  }
}

/** Whether the window is one that starts with the player hidden. */
export function windowIsShort(): boolean {
  return shortList()?.matches ?? false
}

/** Tell `listener` when the window crosses the height rule; returns the way to stop. */
export function subscribeShortWindow(listener: () => void): () => void {
  const list = shortList()
  list?.addEventListener('change', listener)
  return () => {
    list?.removeEventListener('change', listener)
  }
}

/** Whether the player is shown, as a hook: the choice, or the window's height while there is none. */
export function useBinPlayerShown(): boolean {
  const choice = useSyncExternalStore(subscribeBinPlayer, binPlayerChoice, () => null)
  const shortWindow = useSyncExternalStore(subscribeShortWindow, windowIsShort, () => false)
  return playerShown(choice, shortWindow)
}

/** Test seam: forget the held value so the next read goes to storage. */
export function resetBinPlayerPref(): void {
  current = undefined
}
