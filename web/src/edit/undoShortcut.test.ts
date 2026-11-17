import assert from 'node:assert/strict'
import { test } from 'node:test'

import { buttonName, isTextTarget, stepWords, undoChord, undoKeyAction } from './undoShortcut.ts'

const key = (over: Partial<Parameters<typeof undoChord>[0]> = {}) => ({
  ctrlKey: true,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  isComposing: false,
  key: 'z',
  ...over,
})

test('Z with Ctrl or Cmd is Undo, with Shift Redo, whatever the case', () => {
  assert.equal(undoChord(key()), 'undo')
  assert.equal(undoChord(key({ ctrlKey: false, metaKey: true })), 'undo')
  assert.equal(undoChord(key({ shiftKey: true, key: 'Z' })), 'redo')
  assert.equal(undoChord(key({ ctrlKey: false, metaKey: true, shiftKey: true })), 'redo')
})

test('Ctrl+Y is Redo; Cmd+Y and Ctrl+Shift+Y are not', () => {
  assert.equal(undoChord(key({ key: 'y' })), 'redo')
  assert.equal(undoChord(key({ key: 'y', ctrlKey: false, metaKey: true })), null)
  assert.equal(undoChord(key({ key: 'y', shiftKey: true })), null)
})

test('Alt, a composition, no modifier or another key is no chord', () => {
  assert.equal(undoChord(key({ altKey: true })), null)
  assert.equal(undoChord(key({ isComposing: true })), null)
  assert.equal(undoChord(key({ ctrlKey: false })), null)
  assert.equal(undoChord(key({ key: 's' })), null)
})

test('inputs, text areas, selects and editable content keep the browser undo', () => {
  assert.equal(isTextTarget({ tagName: 'INPUT' }), true)
  assert.equal(isTextTarget({ tagName: 'INPUT', type: 'text' }), true)
  assert.equal(isTextTarget({ tagName: 'INPUT', type: 'number' }), true)
  for (const type of ['radio', 'checkbox', 'color', 'range', 'button', 'file']) {
    assert.equal(isTextTarget({ tagName: 'INPUT', type }), false, type)
  }
  assert.equal(isTextTarget({ tagName: 'textarea' }), true)
  assert.equal(isTextTarget({ tagName: 'SELECT' }), true)
  assert.equal(isTextTarget({ tagName: 'DIV', isContentEditable: true }), true)
  assert.equal(isTextTarget({ tagName: 'BUTTON' }), false)
  assert.equal(isTextTarget({ tagName: 'BODY' }), false)
  assert.equal(isTextTarget(null), false)
})

const idle = {
  chord: 'undo' as const,
  repeat: false,
  inTextField: false,
  pointerHeld: false,
  lifted: false,
  saving: false,
  moving: false,
  dialogOpen: false,
  canUndo: true,
  canRedo: true,
}

test('a press acts when nothing guards it, and says so when the history is empty', () => {
  assert.equal(undoKeyAction(idle), 'undo')
  assert.equal(undoKeyAction({ ...idle, chord: 'redo' }), 'redo')
  assert.equal(undoKeyAction({ ...idle, canUndo: false }), 'nothing')
  assert.equal(undoKeyAction({ ...idle, chord: 'redo', canRedo: false }), 'nothing')
})

test('each guard ignores the press, even with an empty history', () => {
  for (const guard of ['repeat', 'inTextField', 'pointerHeld', 'lifted', 'saving', 'moving', 'dialogOpen']) {
    assert.equal(undoKeyAction({ ...idle, [guard]: true }), 'ignore', guard)
    assert.equal(undoKeyAction({ ...idle, [guard]: true, canUndo: false }), 'ignore', guard)
  }
})

test('words', () => {
  assert.equal(stepWords('undo', 'move of a.mp4'), 'Undid move of a.mp4.')
  assert.equal(stepWords('redo', 'cut added'), 'Redid cut added.')
  assert.equal(buttonName('Undo', 'title'), 'Undo title')
  assert.equal(buttonName('Redo', undefined), 'Redo')
})
