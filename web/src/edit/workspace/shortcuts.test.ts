import assert from 'node:assert/strict'
import { test } from 'node:test'

import { blockYieldsSpace, focusFacts, SHORTCUT_GROUPS, SHORTCUTS, workspaceCommand } from './shortcuts.ts'
import type { Command, ElementLike, Env, FocusFacts, Press, PressSpec } from './shortcuts.ts'

const press = (over: PressSpec): Press => ({
  shiftKey: false,
  ctrlKey: false,
  altKey: false,
  metaKey: false,
  altGraph: false,
  repeat: false,
  isComposing: false,
  defaultPrevented: false,
  ...over,
})

const facts = (over: Partial<FocusFacts> = {}): FocusFacts => ({
  enabled: true,
  field: false,
  dialogOpen: false,
  inPreview: false,
  dragging: false,
  arrowWidget: false,
  spaceControl: false,
  modality: 'keyboard',
  ...over,
})

const env = (over: Partial<Env> = {}): Env => ({
  enabled: true,
  dialogOpen: false,
  dragging: false,
  pointerHeld: false,
  modality: 'keyboard',
  ...over,
})

const run = (over: PressSpec, f: Partial<FocusFacts> = {}) => workspaceCommand(press(over), facts(f))

// --- rule 1: where nothing acts -------------------------------------------------------------

test('rule 1: the switch, a handled key, a composition, a field, a dialog, a preview and a drag give null', () => {
  const blocks: Partial<FocusFacts>[] = [
    { enabled: false },
    { field: true },
    { dialogOpen: true },
    { inPreview: true },
    { dragging: true },
  ]
  for (const block of blocks) {
    for (const key of [' ', 'ArrowRight', '+', 'q', '?']) {
      assert.equal(run({ key }, block), null, `${key} ${JSON.stringify(block)}`)
    }
  }
  assert.equal(run({ key: ' ', defaultPrevented: true }), null)
  assert.equal(run({ key: ' ', isComposing: true }), null)
  assert.equal(run({ key: 'q', isComposing: true }), null)
})

// --- rule 2: ? ---------------------------------------------------------------------------------

test('rule 2: ? opens the list, with Shift, never with Ctrl, Cmd or Alt, and as an AltGr character', () => {
  assert.deepEqual(run({ key: '?' }), { kind: 'help' })
  assert.deepEqual(run({ key: '?', shiftKey: true }), { kind: 'help' })
  assert.equal(run({ key: '?', ctrlKey: true }), null)
  assert.equal(run({ key: '?', metaKey: true }), null)
  assert.equal(run({ key: '?', altKey: true }), null)
  // Windows reports AltGr as Ctrl+Alt with AltGraph set, Linux as AltGraph alone.
  assert.deepEqual(run({ key: '?', ctrlKey: true, altKey: true, altGraph: true }), { kind: 'help' })
  assert.deepEqual(run({ key: '?', altGraph: true }), { kind: 'help' })
})

// --- rule 3: Space -----------------------------------------------------------------------------

test('rule 3: Space toggles Play; a held Space is hold', () => {
  const toggle: Command = { kind: 'playhead', action: { kind: 'toggle' } }
  assert.deepEqual(run({ key: ' ' }), toggle)
  assert.deepEqual(run({ key: 'Spacebar' }), toggle)
  assert.deepEqual(run({ key: ' ', repeat: true }), { kind: 'hold' })
})

test('rule 3: Space with a modifier is not a shortcut', () => {
  for (const mod of ['shiftKey', 'ctrlKey', 'altKey', 'metaKey']) {
    assert.equal(run({ key: ' ', [mod]: true }), null, mod)
  }
})

test('rule 3: Space on a control reached by keyboard is null, after a pointer press it plays', () => {
  const toggle: Command = { kind: 'playhead', action: { kind: 'toggle' } }
  assert.equal(run({ key: ' ' }, { spaceControl: true, modality: 'keyboard' }), null)
  assert.equal(run({ key: ' ', repeat: true }, { spaceControl: true, modality: 'keyboard' }), null)
  assert.deepEqual(run({ key: ' ' }, { spaceControl: true, modality: 'pointer' }), toggle)
  // a held Space on a clicked button does not press it on release either
  assert.deepEqual(run({ key: ' ', repeat: true }, { spaceControl: true, modality: 'pointer' }), {
    kind: 'hold',
  })
  // not a Space control: the modality does not matter
  assert.deepEqual(run({ key: ' ' }, { modality: 'keyboard' }), toggle)
})

// --- rule 4: Left and Right -------------------------------------------------------------------

test('rule 4: Left and Right step a frame, with Shift a second, and a repeat steps again', () => {
  assert.deepEqual(run({ key: 'ArrowLeft' }), {
    kind: 'playhead',
    action: { kind: 'frames', n: -1 },
  })
  assert.deepEqual(run({ key: 'ArrowRight', repeat: true }), {
    kind: 'playhead',
    action: { kind: 'frames', n: 1 },
  })
  assert.deepEqual(run({ key: 'ArrowRight', shiftKey: true }), {
    kind: 'playhead',
    action: { kind: 'ms', ms: 1000 },
  })
  assert.deepEqual(run({ key: 'ArrowLeft', shiftKey: true }), {
    kind: 'playhead',
    action: { kind: 'ms', ms: -1000 },
  })
})

test('rule 4: arrows on a range or role=slider (any arrow widget) give null, Alt+arrow too', () => {
  assert.equal(run({ key: 'ArrowRight' }, { arrowWidget: true }), null)
  assert.equal(run({ key: 'ArrowLeft', shiftKey: true }, { arrowWidget: true }), null)
  assert.equal(run({ key: 'ArrowLeft', altKey: true }, { arrowWidget: true }), null)
  // Space is not an arrow: a widget that is also a Space control is rule 3's business
  assert.deepEqual(run({ key: ' ' }, { arrowWidget: true }), {
    kind: 'playhead',
    action: { kind: 'toggle' },
  })
})

test('rule 4: Alt+Left and Alt+Right move the clip; other Ctrl, Cmd, Alt chords are null', () => {
  assert.deepEqual(run({ key: 'ArrowLeft', altKey: true }), { kind: 'move', way: -1 })
  assert.deepEqual(run({ key: 'ArrowRight', altKey: true }), { kind: 'move', way: 1 })
  assert.equal(run({ key: 'ArrowLeft', ctrlKey: true }), null)
  assert.equal(run({ key: 'ArrowRight', metaKey: true }), null)
  assert.equal(run({ key: 'ArrowRight', altKey: true, shiftKey: true }), null)
  assert.equal(run({ key: 'ArrowRight', altKey: true, ctrlKey: true }), null)
  assert.equal(run({ key: 'ArrowRight', altKey: true, altGraph: true }), null)
})

test('Up, Down, Page Up, Page Down, Home and End are not workspace keys', () => {
  for (const key of ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End']) {
    assert.equal(run({ key }), null, key)
  }
})

// --- rules 5 and 6: zoom and edge keys ---------------------------------------------------------

test('rule 5: the zoom keys, and AltGr characters among them', () => {
  for (const key of ['+', '=', '-', '_', '0', '\\']) {
    assert.deepEqual(run({ key }), { kind: 'zoom', key }, key)
  }
  // Ctrl alone and Cmd are the browser's page zoom
  assert.equal(run({ key: '-', ctrlKey: true }), null)
  assert.equal(run({ key: '0', ctrlKey: true }), null)
  assert.equal(run({ key: '0', metaKey: true }), null)
  // AltGr types a character: `\` on a Swedish layout is AltGr+`+`, and Option+7 on a Mac
  assert.deepEqual(run({ key: '\\', altGraph: true }), { kind: 'zoom', key: '\\' })
  assert.deepEqual(run({ key: '\\', ctrlKey: true, altKey: true }), { kind: 'zoom', key: '\\' })
  assert.deepEqual(run({ key: '\\', altKey: true }), { kind: 'zoom', key: '\\' })
  assert.equal(run({ key: '-', altKey: true }), null)
})

test('rule 6: bare Q, W and S, either case; no Ctrl, Cmd or Alt', () => {
  for (const key of ['q', 'w', 's']) {
    assert.deepEqual(run({ key }), { kind: 'edge', key })
    assert.deepEqual(run({ key: key.toUpperCase() }), { kind: 'edge', key })
    assert.equal(run({ key, ctrlKey: true }), null, `ctrl ${key}`)
    assert.equal(run({ key, metaKey: true }), null, `cmd ${key}`)
    assert.equal(run({ key, altKey: true }), null, `alt ${key}`)
  }
})

test('rule 7: anything else is null', () => {
  for (const key of ['a', 'r', 'Enter', 'Tab', 'Escape', 'Delete', 'j', 'k', 'l', '1']) {
    assert.equal(run({ key }), null, key)
  }
})

// --- the table ---------------------------------------------------------------------------------

const sig = (command: Command): string => JSON.stringify(command)

test('every workspace row maps to a command', () => {
  for (const row of SHORTCUTS) {
    if (row.scope !== 'workspace') {
      continue
    }
    assert.ok(row.presses.length > 0, row.words)
    for (const spec of row.presses) {
      const command = workspaceCommand(press(spec), facts())
      assert.notEqual(command, null, `${row.words}: ${JSON.stringify(spec)}`)
    }
  }
})

test('every command a press can give has a workspace row', () => {
  const rowed = new Set<string>()
  for (const row of SHORTCUTS) {
    if (row.scope === 'workspace') {
      for (const spec of row.presses) {
        const command = workspaceCommand(press(spec), facts())
        if (command !== null) {
          rowed.add(sig(command))
        }
      }
    }
  }
  const keys = [
    ...Array.from({ length: 95 }, (_, i) => String.fromCharCode(32 + i)),
    'Spacebar',
    'ArrowLeft',
    'ArrowRight',
    'ArrowUp',
    'ArrowDown',
    'PageUp',
    'PageDown',
    'Home',
    'End',
    'Enter',
    'Tab',
    'Escape',
    'Delete',
    'Backspace',
    'Dead',
  ]
  let given = 0
  for (const key of keys) {
    for (let mods = 0; mods < 32; mods++) {
      for (const repeat of [false, true]) {
        const spec: PressSpec = {
          key,
          shiftKey: (mods & 1) !== 0,
          ctrlKey: (mods & 2) !== 0,
          altKey: (mods & 4) !== 0,
          metaKey: (mods & 8) !== 0,
          altGraph: (mods & 16) !== 0,
          repeat,
        }
        for (const modality of ['keyboard', 'pointer'] as const) {
          const command = workspaceCommand(press(spec), facts({ modality, spaceControl: true }))
          if (command !== null) {
            given++
            assert.ok(rowed.has(sig(command)), `${JSON.stringify(spec)} gives ${sig(command)}`)
          }
        }
      }
    }
  }
  assert.ok(given > 100)
})

test('the table has the four groups, each used, and words on every row', () => {
  assert.deepEqual([...SHORTCUT_GROUPS], ['Playback', 'Zoom', 'Editing', 'Mouse'])
  for (const group of SHORTCUT_GROUPS) {
    assert.ok(SHORTCUTS.some((row) => row.group === group), group)
  }
  for (const row of SHORTCUTS) {
    assert.ok(row.words.length > 0 && row.keys.length > 0 && row.keys.every((c) => c.length > 0))
  }
  const space = SHORTCUTS.find((row) => row.keys[0]?.[0] === 'Space')
  assert.equal(space?.words, 'Play or pause')
  const q = SHORTCUTS.find((row) => row.keys[0]?.[0] === 'Q')
  assert.equal(q?.words, "Trim the clip's start to the playhead")
  const wheel = SHORTCUTS.find((row) => row.scope === 'mouse')
  assert.deepEqual(wheel?.keys, [['Ctrl', 'wheel over the Timeline']])
  assert.equal(wheel?.words, 'zoom')
  assert.ok(SHORTCUTS.some((row) => row.scope === 'chord'))
})

test('the clip menu has its two rows, neither a workspace row', () => {
  const keyed = SHORTCUTS.find((row) => row.keys[0]?.join('+') === 'Shift+F10')
  assert.equal(keyed?.group, 'Editing')
  assert.deepEqual(keyed?.keys, [['Shift', 'F10'], ['Menu']])
  assert.equal(keyed?.words, 'On a clip: open its menu')
  assert.equal(keyed?.scope, 'focused')
  const mouse = SHORTCUTS.find((row) => row.keys[0]?.[0] === 'Right-click a clip')
  assert.equal(mouse?.group, 'Mouse')
  assert.equal(mouse?.words, 'Open its menu')
  assert.equal(mouse?.scope, 'mouse')
})

// --- focusFacts --------------------------------------------------------------------------------

const el = (tagName: string, over: Partial<ElementLike> & { role?: string; inPreview?: boolean } = {}): ElementLike => {
  const { role, inPreview, ...rest } = over
  return {
    tagName,
    getAttribute: (name) => (name === 'role' ? (role ?? null) : null),
    closest: (selector) => (inPreview === true && selector === '.clip-preview' ? {} : null),
    ...rest,
  }
}

test('focusFacts: no focus, or the page itself, is all false', () => {
  for (const target of [null, el('BODY')]) {
    const f = focusFacts(target, env())
    assert.equal(f.field, false)
    assert.equal(f.arrowWidget, false)
    assert.equal(f.spaceControl, false)
    assert.equal(f.inPreview, false)
    assert.equal(f.enabled, true)
    assert.equal(f.modality, 'keyboard')
  }
})

test('focusFacts: fields are text inputs, textarea, select and editable text', () => {
  assert.equal(focusFacts(el('INPUT', { type: 'text' }), env()).field, true)
  assert.equal(focusFacts(el('TEXTAREA'), env()).field, true)
  assert.equal(focusFacts(el('SELECT'), env()).field, true)
  assert.equal(focusFacts(el('DIV', { isContentEditable: true }), env()).field, true)
  assert.equal(focusFacts(el('INPUT', { type: 'checkbox' }), env()).field, false)
  assert.equal(focusFacts(el('BUTTON'), env()).field, false)
})

test('focusFacts: arrow widgets are ranges, radios and the roles that take arrows', () => {
  assert.equal(focusFacts(el('INPUT', { type: 'range' }), env()).arrowWidget, true)
  assert.equal(focusFacts(el('INPUT', { type: 'radio' }), env()).arrowWidget, true)
  for (const role of [
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
  ]) {
    assert.equal(focusFacts(el('DIV', { role }), env()).arrowWidget, true, role)
  }
  assert.equal(focusFacts(el('DIV', { role: 'Slider' }), env()).arrowWidget, true)
  assert.equal(focusFacts(el('BUTTON'), env()).arrowWidget, false)
  assert.equal(focusFacts(el('INPUT', { type: 'checkbox' }), env()).arrowWidget, false)
  assert.equal(focusFacts(el('DIV', { role: 'button' }), env()).arrowWidget, false)
})

test('focusFacts: Space controls are buttons, checkboxes, radios, summaries and their roles', () => {
  assert.equal(focusFacts(el('BUTTON'), env()).spaceControl, true)
  assert.equal(focusFacts(el('SUMMARY'), env()).spaceControl, true)
  assert.equal(focusFacts(el('INPUT', { type: 'checkbox' }), env()).spaceControl, true)
  assert.equal(focusFacts(el('INPUT', { type: 'radio' }), env()).spaceControl, true)
  assert.equal(focusFacts(el('INPUT', { type: 'color' }), env()).spaceControl, true)
  assert.equal(focusFacts(el('INPUT', { type: 'file' }), env()).spaceControl, true)
  assert.equal(focusFacts(el('INPUT', { type: 'checkbox' }), env()).spaceControl, true)
  for (const role of ['button', 'checkbox', 'radio', 'switch', 'option', 'menuitem', 'tab']) {
    assert.equal(focusFacts(el('DIV', { role }), env()).spaceControl, true, role)
  }
  assert.equal(focusFacts(el('VIDEO'), env()).spaceControl, false)
  assert.equal(focusFacts(el('DIV', { role: 'slider' }), env()).spaceControl, false)
  assert.equal(focusFacts(el('INPUT', { type: 'range' }), env()).spaceControl, false)
})

test('focusFacts: inside a clip preview, and what the page says', () => {
  assert.equal(focusFacts(el('BUTTON', { inPreview: true }), env()).inPreview, true)
  assert.equal(focusFacts(el('BUTTON'), env()).inPreview, false)
  // an element with no closest (a plain object) is not in a preview
  assert.equal(focusFacts({ tagName: 'BUTTON' }, env()).inPreview, false)

  assert.equal(focusFacts(null, env({ enabled: false })).enabled, false)
  assert.equal(focusFacts(null, env({ dialogOpen: true })).dialogOpen, true)
  assert.equal(focusFacts(null, env({ dragging: true })).dragging, true)
  assert.equal(focusFacts(null, env({ pointerHeld: true })).dragging, true)
  assert.equal(focusFacts(null, env()).dragging, false)
  assert.equal(focusFacts(null, env({ modality: 'pointer' })).modality, 'pointer')
})

test('focusFacts through workspaceCommand: Rotate after Tab keeps Space, after a click plays', () => {
  const rotate = el('BUTTON')
  const space = press({ key: ' ' })
  assert.equal(workspaceCommand(space, focusFacts(rotate, env({ modality: 'keyboard' }))), null)
  assert.deepEqual(workspaceCommand(space, focusFacts(rotate, env({ modality: 'pointer' }))), {
    kind: 'playhead',
    action: { kind: 'toggle' },
  })
  // a trim drag holds everything still
  assert.equal(workspaceCommand(space, focusFacts(null, env({ pointerHeld: true }))), null)
})

test('a clip block yields Space only when the workspace listener will take it', () => {
  assert.equal(blockYieldsSpace('pointer', true, false), true)
  assert.equal(blockYieldsSpace('pointer', false, false), false, 'switch off: the block selects')
  assert.equal(blockYieldsSpace('pointer', true, true), false, 'pointer held')
  assert.equal(blockYieldsSpace('keyboard', true, false), false)
})
