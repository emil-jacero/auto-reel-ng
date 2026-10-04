/*
 * Whether each section's Help panel is open, kept per section (not per event) in the
 * browser's localStorage (`help-text-declutter`). Pure over an injected storage, so a
 * storage that throws or is absent is testable: it reads as closed and writes nothing.
 */

/** The sections that have a Help toggle. The Timeline's is one state for both modes. */
export const HELP_SECTIONS = ['details', 'poster', 'timeline', 'clips', 'cards'] as const
export type HelpSection = (typeof HELP_SECTIONS)[number]

/** The part of `Storage` this module needs. */
export interface HelpStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

export function helpKey(section: HelpSection): string {
  return `auto-reel.help.${section}`
}

/** The page's storage, or null when the browser refuses to hand it out. */
export function browserStorage(): HelpStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** Open only when the stored value says so; anything else, a throw included, is closed. */
export function readHelp(section: HelpSection, storage: HelpStorage | null): boolean {
  try {
    return storage?.getItem(helpKey(section)) === 'open'
  } catch {
    return false
  }
}

/** Remember the state; a refusing storage is not an error (the page visit keeps its own). */
export function writeHelp(section: HelpSection, open: boolean, storage: HelpStorage | null): void {
  try {
    storage?.setItem(helpKey(section), open ? 'open' : 'closed')
  } catch {
    // The state lives for the page visit only.
  }
}
