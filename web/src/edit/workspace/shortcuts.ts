import { clipMoveKey, playheadKey, trackZoomKey } from '../../timeline/keys.ts'
import type { KeyAction } from '../../timeline/keys.ts'
import { isTextTarget } from '../undoShortcut.ts'
import type { Modality } from './modality.ts'

/*
 * The workspace's keys (`editor-shortcuts`, D1): which Timeline key does what wherever focus is in
 * Edit mode's workspace, the facts about focus that decide it, and the table the Keyboard
 * shortcuts list is drawn from. Pure, so that `shortcuts.test.ts` checks every rule and that the
 * list and the keys cannot disagree. `useTimeline` listens and dispatches.
 */

export type Command =
  // Space (toggle), Left/Right (frames ±1), Shift+Left/Right (ms ±1000)
  | { kind: 'playhead'; action: KeyAction }
  // a held Space: the key is taken (preventDefault) and nothing toggles
  | { kind: 'hold' }
  // + = - _ 0 \  (`trackZoomKey`)
  | { kind: 'zoom'; key: string }
  | { kind: 'edge'; key: 'q' | 'w' | 's' }
  // Alt+Left / Alt+Right (`clipMoveKey`)
  | { kind: 'move'; way: -1 | 1 }
  // ?
  | { kind: 'help' }

/** What a rule reads of a keydown (`altGraph` is `getModifierState('AltGraph')`). */
export type Press = {
  key: string
  shiftKey: boolean
  ctrlKey: boolean
  altKey: boolean
  metaKey: boolean
  altGraph: boolean
  repeat: boolean
  isComposing: boolean
  defaultPrevented: boolean
}

/** What the rules need to know of where focus is and what the page is doing. */
export type FocusFacts = {
  /** The single-key switch (D5). */
  enabled: boolean
  /** `isTextTarget`: text inputs, textarea, select, contenteditable. */
  field: boolean
  /** A `dialog[open]` is on the page. */
  dialogOpen: boolean
  /** Focus is inside an open `.clip-preview`. */
  inPreview: boolean
  /** The Timeline's drag store holds a drag, or a pointer is held (D2). */
  dragging: boolean
  /** A range input, or a role that takes the arrows itself. */
  arrowWidget: boolean
  /** A button, checkbox, radio, summary, or a role that takes Space itself. */
  spaceControl: boolean
  modality: Modality
}

const isSpace = (key: string) => key === ' ' || key === 'Spacebar'

/**
 * What a keydown does in the workspace, or null to leave it to the browser and to the focused
 * element. Rules in this order:
 * 1. Not enabled, already handled, in a composition, in a field, a dialog or a clip preview, or
 *    during a drag: null.
 * 2. `?` (Shift is how it is typed; AltGr is a typed character): the list.
 * 3. Space with no modifier: a control reached by keyboard keeps it; otherwise a repeat is `hold`
 *    and a press toggles.
 * 4. Left and Right: a widget that takes arrows keeps them; Alt alone moves the selected clip;
 *    any other Ctrl, Cmd or Alt chord is the browser's; the rest step the playhead (a repeat
 *    steps again, as on the grip).
 * 5. The zoom keys.
 * 6. Bare Q, W and S, either case.
 * 7. Anything else: null.
 */
export function workspaceCommand(press: Press, focus: FocusFacts): Command | null {
  if (
    !focus.enabled ||
    press.defaultPrevented ||
    press.isComposing ||
    focus.field ||
    focus.dialogOpen ||
    focus.inPreview ||
    focus.dragging
  ) {
    return null
  }
  const { key, ctrlKey, altKey, metaKey, shiftKey, altGraph } = press
  const chord = ctrlKey || altKey || metaKey
  if (key === '?' && !metaKey && (!chord || altGraph)) {
    return { kind: 'help' }
  }
  if (isSpace(key)) {
    if (chord || shiftKey) {
      return null
    }
    if (focus.spaceControl && focus.modality === 'keyboard') {
      return null
    }
    return press.repeat ? { kind: 'hold' } : { kind: 'playhead', action: { kind: 'toggle' } }
  }
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    if (focus.arrowWidget) {
      return null
    }
    const way = clipMoveKey({ key, altKey, ctrlKey, metaKey, shiftKey, altGraph })
    if (way !== null) {
      return { kind: 'move', way }
    }
    if (chord) {
      return null
    }
    const action = playheadKey(key, shiftKey)
    return action === null ? null : { kind: 'playhead', action }
  }
  const zoom = trackZoomKey({ key, ctrlKey, altKey, metaKey, altGraph })
  if (zoom !== null) {
    return { kind: 'zoom', key: zoom }
  }
  if (!chord) {
    const letter = key.toLowerCase()
    if (letter === 'q' || letter === 'w' || letter === 's') {
      return { kind: 'edge', key: letter }
    }
  }
  return null
}

// --- facts about focus ------------------------------------------------------------------------

/** What `focusFacts` reads of an element: `HTMLElement` fits, and so does a plain object. */
export type ElementLike = {
  tagName?: string
  type?: string
  isContentEditable?: boolean
  getAttribute?: (name: string) => string | null
  closest?: (selector: string) => unknown
}

/** What the page says apart from the element. */
export type Env = {
  enabled: boolean
  dialogOpen: boolean
  /** The Timeline's drag store holds a drag. */
  dragging: boolean
  /** `pointerHeld()` of `modality.ts`. */
  pointerHeld: boolean
  /** `lastInput()` of `modality.ts`. */
  modality: Modality
}

const ARROW_ROLES = new Set([
  'slider',
  'radio',
  'radiogroup',
  'tab',
  'tablist',
  'listbox',
  'option',
  'menu',
  'menuitem',
  'menuitemcheckbox',
  'menuitemradio',
  'spinbutton',
  'grid',
  'gridcell',
  'tree',
  'treeitem',
])

const SPACE_ROLES = new Set([
  'button',
  'checkbox',
  'radio',
  'switch',
  'option',
  'menuitem',
  'menuitemcheckbox',
  'menuitemradio',
  'tab',
])

const SPACE_INPUTS = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'image'])

/** The facts `workspaceCommand` needs, read from the focused `target` (null: the page itself). */
export function focusFacts(target: ElementLike | null, env: Env): FocusFacts {
  const tag = target?.tagName?.toUpperCase()
  const type = target?.type?.toLowerCase()
  const role = target?.getAttribute?.('role')?.trim().split(/\s+/)[0]?.toLowerCase() ?? null
  const input = tag === 'INPUT'
  const arrowWidget =
    (input && (type === 'range' || type === 'radio')) || (role !== null && ARROW_ROLES.has(role))
  const spaceControl =
    tag === 'BUTTON' ||
    tag === 'SUMMARY' ||
    (input && type !== undefined && SPACE_INPUTS.has(type)) ||
    (role !== null && SPACE_ROLES.has(role))
  const preview = target?.closest?.('.clip-preview')
  return {
    enabled: env.enabled,
    field: isTextTarget(target),
    dialogOpen: env.dialogOpen,
    inPreview: preview !== undefined && preview !== null,
    dragging: env.dragging || env.pointerHeld,
    arrowWidget,
    spaceControl,
    modality: env.modality,
  }
}

// --- the table the list is drawn from ----------------------------------------------------------

export type ShortcutGroup = 'Playback' | 'Zoom' | 'Editing' | 'Mouse'
export const SHORTCUT_GROUPS: readonly ShortcutGroup[] = ['Playback', 'Zoom', 'Editing', 'Mouse']

/** A press a `workspace` row stands for (the rest is `false`). */
export type PressSpec = Partial<Press> & { key: string }

type Row = {
  group: ShortcutGroup
  /** Alternatives, each a chord drawn as key caps: `[['Shift', 'Left'], ['Shift', 'Right']]`. */
  keys: readonly (readonly string[])[]
  words: string
}

/**
 * One line of the list. `workspace`: the workspace layer answers it wherever focus is (and
 * `presses` is what is fed to `workspaceCommand`); `focused`: only the focused playhead, handle or
 * mark answers it; `chord`: a Ctrl or Cmd chord, another listener; `mouse`: a pointer gesture.
 */
export type Shortcut =
  | (Row & { scope: 'workspace'; presses: readonly PressSpec[] })
  | (Row & { scope: 'focused' | 'chord' | 'mouse' })

export const SHORTCUTS: readonly Shortcut[] = [
  // Playback
  {
    group: 'Playback',
    keys: [['Space']],
    words: 'Play or pause',
    scope: 'workspace',
    presses: [{ key: ' ' }, { key: ' ', repeat: true }],
  },
  {
    group: 'Playback',
    keys: [['Left'], ['Right']],
    words: 'Step one frame back or forward',
    scope: 'workspace',
    presses: [{ key: 'ArrowLeft' }, { key: 'ArrowRight' }],
  },
  {
    group: 'Playback',
    keys: [['Shift', 'Left'], ['Shift', 'Right']],
    words: 'Step one second back or forward',
    scope: 'workspace',
    presses: [
      { key: 'ArrowLeft', shiftKey: true },
      { key: 'ArrowRight', shiftKey: true },
    ],
  },
  {
    group: 'Playback',
    keys: [['Page Up'], ['Page Down']],
    words: 'On the playhead: step five seconds',
    scope: 'focused',
  },
  {
    group: 'Playback',
    keys: [['Home'], ['End']],
    words: 'On the playhead: go to the start or the end',
    scope: 'focused',
  },
  // Zoom
  {
    group: 'Zoom',
    keys: [['+'], ['=']],
    words: 'Zoom the track in',
    scope: 'workspace',
    presses: [{ key: '+', shiftKey: true }, { key: '=' }],
  },
  {
    group: 'Zoom',
    keys: [['-'], ['_']],
    words: 'Zoom the track out',
    scope: 'workspace',
    presses: [{ key: '-' }, { key: '_', shiftKey: true }],
  },
  {
    group: 'Zoom',
    keys: [['0']],
    words: 'Fit the whole event',
    scope: 'workspace',
    presses: [{ key: '0' }],
  },
  {
    group: 'Zoom',
    keys: [['\\']],
    words: 'Fit the whole event, and back',
    scope: 'workspace',
    presses: [{ key: '\\' }],
  },
  // Editing
  {
    group: 'Editing',
    keys: [['Q']],
    words: "Trim the clip's start to the playhead",
    scope: 'workspace',
    presses: [{ key: 'q' }],
  },
  {
    group: 'Editing',
    keys: [['W']],
    words: "Trim the clip's end to the playhead",
    scope: 'workspace',
    presses: [{ key: 'w' }],
  },
  {
    group: 'Editing',
    keys: [['S']],
    words: 'Switch edge snapping on or off',
    scope: 'workspace',
    presses: [{ key: 's' }],
  },
  {
    group: 'Editing',
    keys: [['Alt', 'Left'], ['Alt', 'Right']],
    words: 'Move the selected clip one place earlier or later',
    scope: 'workspace',
    presses: [
      { key: 'ArrowLeft', altKey: true },
      { key: 'ArrowRight', altKey: true },
    ],
  },
  {
    group: 'Editing',
    keys: [['?']],
    words: 'Show or hide this list',
    scope: 'workspace',
    presses: [{ key: '?', shiftKey: true }],
  },
  { group: 'Editing', keys: [['Ctrl', 'S'], ['Cmd', 'S']], words: 'Save', scope: 'chord' },
  { group: 'Editing', keys: [['Ctrl', 'Z'], ['Cmd', 'Z']], words: 'Undo', scope: 'chord' },
  {
    group: 'Editing',
    keys: [['Ctrl', 'Shift', 'Z'], ['Cmd', 'Shift', 'Z'], ['Ctrl', 'Y']],
    words: 'Redo',
    scope: 'chord',
  },
  {
    group: 'Editing',
    keys: [['A']],
    words: 'On a suggestion: approve it',
    scope: 'focused',
  },
  {
    group: 'Editing',
    keys: [['R']],
    words: 'On a suggestion: dismiss it',
    scope: 'focused',
  },
  {
    group: 'Editing',
    keys: [['Escape']],
    words: 'Close this list, or clear the selection',
    scope: 'focused',
  },
  // Mouse
  {
    group: 'Mouse',
    keys: [['Ctrl', 'wheel over the Timeline']],
    words: 'zoom',
    scope: 'mouse',
  },
  {
    group: 'Mouse',
    keys: [['Double-click the track']],
    words: 'Place the playhead',
    scope: 'mouse',
  },
]
