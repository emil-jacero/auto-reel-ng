/*
 * Ctrl+S (Cmd+S on a Mac) in Edit mode: the rules, pure so that they are tested
 * (`saveShortcut.test.ts`). `EventEditor.tsx` listens and saves; `SaveBar.tsx` asks
 * `saveHold` too, so the button and the shortcut cannot drift.
 */

/** Why Save cannot act now. */
export type SaveHold = 'gone' | 'conflict' | 'unfinished' | 'nothing'

/**
 * Why Save cannot act now, or null. A vanished event or a conflict hold Save back whatever
 * else is true; then something typed and not added (a date in part, a cut), then no edits.
 * Whether a save is in flight is separate (the busy-control rule, `pressed`).
 */
export function saveHold(
  edited: boolean,
  unfinished: boolean,
  problem: { kind: string } | null,
): SaveHold | null {
  if (problem?.kind === 'gone') {
    return 'gone'
  }
  if (problem?.kind === 'conflict') {
    return 'conflict'
  }
  if (unfinished) {
    return 'unfinished'
  }
  return edited ? null : 'nothing'
}

/** The key press that means Save: S with Ctrl or Cmd, no Shift or Alt, not in an IME composition. */
export function isSaveChord(event: {
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey: boolean
  isComposing: boolean
  key: string
}): boolean {
  return (
    (event.ctrlKey || event.metaKey) &&
    !event.shiftKey &&
    !event.altKey &&
    !event.isComposing &&
    event.key.toLowerCase() === 's'
  )
}

/** What a held-back Ctrl+S says in the live region. */
export function holdWords(hold: SaveHold, dateIncomplete: boolean, cutsTyped: boolean): string {
  switch (hold) {
    case 'nothing':
      return 'Nothing to save.'
    case 'unfinished': {
      const parts = []
      if (dateIncomplete) {
        parts.push('the date is incomplete')
      }
      if (cutsTyped) {
        parts.push('a cut is typed and not added')
      }
      return `Not saved: ${parts.join(' and ')}.`
    }
    case 'conflict':
      return 'Not saved: choose Reload latest or Overwrite with mine first.'
    case 'gone':
      return 'Not saved: this event no longer exists.'
  }
}
