/*
 * Ctrl+S (Cmd+S on a Mac) in Edit mode: the rules, pure so that they are tested
 * (`saveShortcut.test.ts`). `EventEditor.tsx` listens and saves; `SaveBar.tsx` asks
 * `saveHold` too, so the button and the shortcut cannot drift.
 */

/** Why Save cannot act now. */
export type SaveHold = 'gone' | 'conflict' | 'unfinished' | 'nothing'

/**
 * Why Save cannot act now, or null. A vanished event or a conflict hold Save back whatever
 * else is true; then something typed and not added (a date in part, a name, a cut), then no edits.
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
export function holdWords(
  hold: SaveHold,
  dateIncomplete: boolean,
  cutsTyped: boolean,
  nameTyped = false,
): string {
  switch (hold) {
    case 'nothing':
      return 'Nothing to save.'
    case 'unfinished': {
      const parts = []
      if (dateIncomplete) {
        parts.push('the date is incomplete')
      }
      if (nameTyped) {
        parts.push('a name is typed and not kept')
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

/** What a held-back Ctrl+S says while a clip is lifted. */
export const LIFTED_WORDS = 'Not saved: drop or cancel the lifted clip first.'

/** What a Ctrl+S press does: nothing, say why Save is held back, say a clip is lifted, or save. */
export type SaveKeyAction = 'ignore' | 'announce' | 'lifted' | 'save'

/**
 * The order of the guards for a Ctrl+S press. A repeat, a save in flight (`saving`, or the
 * button pressed), a move of marked clips pending and an open dialog send nothing and say nothing; a
 * lifted clip sends nothing too but says so (the order shown is not the order that would be
 * sent); then Save's own hold.
 */
export function saveKeyAction(state: {
  repeat: boolean
  saving: boolean
  pressed: boolean
  moving: boolean
  lifted: boolean
  dialogOpen: boolean
  hold: SaveHold | null
}): SaveKeyAction {
  if (state.repeat || state.saving || state.pressed || state.moving || state.dialogOpen) {
    return 'ignore'
  }
  if (state.lifted) {
    return 'lifted'
  }
  return state.hold === null ? 'save' : 'announce'
}
