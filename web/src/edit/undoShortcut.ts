/*
 * Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y (Cmd on a Mac) in Edit mode (`editor-undo` D3): the rules, pure
 * so that they are tested (`undoShortcut.test.ts`). `EventEditor.tsx` listens and dispatches.
 */

export type UndoChord = 'undo' | 'redo'

/** The key press that means Undo or Redo, or null: Z or Y with Ctrl or Cmd, no Alt, not in an IME composition. */
export function undoChord(event: {
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey: boolean
  isComposing: boolean
  key: string
}): UndoChord | null {
  if (!(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing) {
    return null
  }
  const key = event.key.toLowerCase()
  if (key === 'z') {
    return event.shiftKey ? 'redo' : 'undo'
  }
  // Ctrl+Y is Windows' Redo; Cmd+Y is not Redo on a Mac.
  return key === 'y' && event.ctrlKey && !event.metaKey && !event.shiftKey ? 'redo' : null
}

/** Whether a key press aimed at `target` belongs to the browser's own undo (a text field). */
export function isTextTarget(
  target: { tagName?: string; type?: string; isContentEditable?: boolean } | null,
): boolean {
  if (target === null) {
    return false
  }
  const tag = target.tagName?.toUpperCase()
  if (tag === 'INPUT') {
    // A checkbox, radio, colour, range or button has no native text undo: the draft's applies.
    return target.type === undefined || TEXT_INPUTS.has(target.type.toLowerCase())
  }
  return tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable === true
}

const TEXT_INPUTS = new Set([
  '',
  'text',
  'search',
  'url',
  'tel',
  'email',
  'password',
  'number',
  'date',
  'time',
  'datetime-local',
  'month',
  'week',
])

/** What an Undo or Redo press does: nothing, say there is nothing to do, or do it. */
export type UndoKeyAction = 'ignore' | 'nothing' | 'undo' | 'redo'

/**
 * The order of the guards. A repeat, a text field (native undo), a pointer held down (a drag in
 * progress), a lifted clip, a save in flight, a move of marked clips pending and an open dialog
 * do nothing and say nothing; then an empty history says so.
 */
export function undoKeyAction(state: {
  chord: UndoChord
  repeat: boolean
  inTextField: boolean
  /** A pointer press that has not ended: a track drag, a handle drag. */
  pointerHeld: boolean
  /** A clip lifted by the list's drag and not yet dropped. */
  lifted: boolean
  /** A save is in flight (the editor is locked). */
  saving: boolean
  moving: boolean
  dialogOpen: boolean
  canUndo: boolean
  canRedo: boolean
}): UndoKeyAction {
  if (
    state.repeat ||
    state.inTextField ||
    state.pointerHeld ||
    state.lifted ||
    state.saving ||
    state.moving ||
    state.dialogOpen
  ) {
    return 'ignore'
  }
  const can = state.chord === 'undo' ? state.canUndo : state.canRedo
  return can ? state.chord : 'nothing'
}

/** What a press with nothing to undo or redo says in the live region. */
export const nothingWords = (chord: UndoChord): string =>
  chord === 'undo' ? 'Nothing to undo.' : 'Nothing to redo.'

/** The live region's words for a step undone or redone. */
export const stepWords = (chord: UndoChord, label: string): string =>
  `${chord === 'undo' ? 'Undid' : 'Redid'} ${label}.`

/** A button's accessible name: the verb and the step it acts on, or the verb alone. */
export const buttonName = (verb: 'Undo' | 'Redo', label: string | undefined): string =>
  label === undefined ? verb : `${verb} ${label}`
