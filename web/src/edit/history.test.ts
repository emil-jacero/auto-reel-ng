import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  MAX_STEPS,
  canRedo,
  canUndo,
  cleared,
  record,
  redo,
  redoLabel,
  undo,
  undoLabel,
} from './history.ts'

test('record then undo/redo walks the states with labels', () => {
  let h = cleared(0)
  h = record(h, 1, 'one')
  h = record(h, 2, 'two')
  assert.equal(h.present, 2)
  assert.equal(undoLabel(h), 'two')
  h = undo(h)
  assert.equal(h.present, 1)
  assert.equal(undoLabel(h), 'one')
  assert.equal(redoLabel(h), 'two')
  h = undo(h)
  assert.equal(h.present, 0)
  assert.equal(canUndo(h), false)
  assert.equal(undo(h), h)
  h = redo(redo(h))
  assert.equal(h.present, 2)
  assert.equal(canRedo(h), false)
  assert.equal(redo(h), h)
  assert.equal(undoLabel(h), 'two')
  assert.equal(redoLabel(h), undefined)
})

test('a new edit clears the future', () => {
  let h = record(record(cleared(0), 1, 'a'), 2, 'b')
  h = undo(h)
  h = record(h, 9, 'c')
  assert.deepEqual(h.future, [])
  assert.equal(redoLabel(h), undefined)
  assert.equal(h.present, 9)
})

test('recording the identical present is a no-op', () => {
  const h = record(cleared(0), 1, 'a')
  assert.equal(record(h, 1, 'again'), h)
})

test('coalesces by key within 1000 ms, measured from the last record', () => {
  let h = cleared('')
  h = record(h, 'a', 'Edit title', 'title', 0)
  h = record(h, 'ab', 'Edit title', 'title', 900)
  h = record(h, 'abc', 'Edit title', 'title', 1800) // 900 since last record: still merges
  assert.equal(h.past.length, 1)
  assert.equal(h.present, 'abc')
  h = undo(h)
  assert.equal(h.present, '')
})

test('does not coalesce across keys, after the window, or without a key', () => {
  let h = cleared('')
  h = record(h, 'a', 'Edit title', 'title', 0)
  h = record(h, 'b', 'Edit date', 'date', 10)
  assert.equal(h.past.length, 2)
  h = record(h, 'c', 'Edit date', 'date', 1010) // exactly 1000 ms: new step
  assert.equal(h.past.length, 3)
  h = record(h, 'd', 'Move', undefined, 1020)
  h = record(h, 'e', 'Move', undefined, 1030)
  assert.equal(h.past.length, 5)
})

test('undo ends a coalescing run', () => {
  let h = record(cleared(''), 'a', 'Edit title', 'title', 0)
  h = redo(undo(h))
  h = record(h, 'ab', 'Edit title', 'title', 10)
  assert.equal(h.past.length, 2)
})

test('caps past at 200, dropping the oldest and keeping labels aligned', () => {
  let h = cleared(0)
  for (let i = 1; i <= MAX_STEPS + 5; i++) h = record(h, i, `e${i}`)
  assert.equal(h.past.length, MAX_STEPS)
  assert.equal(h.labels.length, MAX_STEPS)
  assert.equal(h.past[0], 5)
  assert.equal(h.labels[0], 'e6')
  assert.equal(undoLabel(h), `e${MAX_STEPS + 5}`)
})

test('cleared drops everything', () => {
  const h = cleared(7)
  assert.deepEqual(h, { past: [], present: 7, future: [], labels: [], futureLabels: [] })
})
