import assert from 'node:assert/strict'
import { test } from 'node:test'

import { holdWords, isSaveChord, saveHold } from './saveShortcut.ts'

const key = (over: Partial<Parameters<typeof isSaveChord>[0]> = {}) => ({
  ctrlKey: true,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  isComposing: false,
  key: 's',
  ...over,
})

test('S with Ctrl or Cmd is the chord, whatever the case', () => {
  assert.equal(isSaveChord(key()), true)
  assert.equal(isSaveChord(key({ ctrlKey: false, metaKey: true })), true)
  assert.equal(isSaveChord(key({ key: 'S' })), true)
})

test('Shift, Alt, an IME composition, no modifier or another key are not the chord', () => {
  assert.equal(isSaveChord(key({ shiftKey: true })), false)
  assert.equal(isSaveChord(key({ altKey: true })), false)
  assert.equal(isSaveChord(key({ isComposing: true })), false)
  assert.equal(isSaveChord(key({ ctrlKey: false })), false)
  assert.equal(isSaveChord(key({ key: 'a' })), false)
})

test('Save is held back by a vanished event, a conflict, something unfinished, then no edits', () => {
  assert.equal(saveHold(true, false, null), null)
  assert.equal(saveHold(false, false, null), 'nothing')
  assert.equal(saveHold(true, true, null), 'unfinished')
  // A date typed in part is unfinished though nothing else was edited.
  assert.equal(saveHold(false, true, null), 'unfinished')
  assert.equal(saveHold(true, false, { kind: 'conflict' }), 'conflict')
  assert.equal(saveHold(true, true, { kind: 'conflict' }), 'conflict')
  assert.equal(saveHold(false, false, { kind: 'gone' }), 'gone')
  assert.equal(saveHold(true, true, { kind: 'gone' }), 'gone')
})

test('a failure that has its own Retry does not hold Save back', () => {
  for (const kind of ['refused', 'disk', 'unreachable', 'unpublished', 'page']) {
    assert.equal(saveHold(true, false, { kind }), null, kind)
  }
})

test('each hold says why, naming what the bar names', () => {
  assert.equal(holdWords('nothing', false, false), 'Nothing to save.')
  assert.equal(holdWords('unfinished', true, false), 'Not saved: the date is incomplete.')
  assert.equal(holdWords('unfinished', false, true), 'Not saved: a cut is typed and not added.')
  assert.equal(
    holdWords('unfinished', true, true),
    'Not saved: the date is incomplete and a cut is typed and not added.',
  )
  assert.match(holdWords('conflict', false, false), /Reload latest or Overwrite with mine/)
  assert.match(holdWords('gone', false, false), /no longer exists/)
})
