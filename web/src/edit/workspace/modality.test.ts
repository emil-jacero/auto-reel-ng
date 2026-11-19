import assert from 'node:assert/strict'
import { test } from 'node:test'

import { installModality, lastInput, nextHeld, nextModality, pointerHeld } from './modality.ts'

const fire = (target: EventTarget, type: string, extra: Record<string, unknown> = {}) =>
  target.dispatchEvent(Object.assign(new Event(type), extra))

test('Tab gives keyboard and a pointer press gives pointer', () => {
  assert.equal(nextModality('pointer', { type: 'keydown', key: 'Tab' }), 'keyboard')
  assert.equal(nextModality('keyboard', { type: 'pointerdown', button: 0 }), 'pointer')
  assert.equal(nextModality('keyboard', { type: 'pointerdown', button: 2 }), 'pointer')
})

test('an arrow, Space or Enter keeps the last input', () => {
  for (const key of ['ArrowRight', 'ArrowLeft', ' ', 'Enter', 'q']) {
    assert.equal(nextModality('pointer', { type: 'keydown', key }), 'pointer', key)
    assert.equal(nextModality('keyboard', { type: 'keydown', key }), 'keyboard', key)
  }
  assert.equal(nextModality('pointer', { type: 'pointerup' }), 'pointer')
})

test('the start value is keyboard', () => {
  assert.equal(lastInput(), 'keyboard')
  assert.equal(pointerHeld(), false)
})

test('a primary press is held until pointerup, pointercancel, contextmenu or blur', () => {
  assert.equal(nextHeld(false, { type: 'pointerdown', button: 0 }), true)
  assert.equal(nextHeld(false, { type: 'pointerdown', button: 2 }), false)
  for (const type of ['pointerup', 'pointercancel', 'contextmenu', 'blur']) {
    assert.equal(nextHeld(true, { type }), false, type)
  }
  assert.equal(nextHeld(true, { type: 'keydown', key: 'a' }), true)
  assert.equal(nextHeld(true, { type: 'pointermove' }), true)
})

test('installed, the listeners follow the events and stop and reset on cleanup', () => {
  const doc = new EventTarget()
  const win = new EventTarget()
  const stop = installModality(doc, win)
  assert.equal(lastInput(), 'keyboard')

  fire(doc, 'pointerdown', { button: 0 })
  assert.equal(lastInput(), 'pointer')
  assert.equal(pointerHeld(), true)
  fire(doc, 'keydown', { key: 'ArrowRight' })
  assert.equal(lastInput(), 'pointer')
  assert.equal(pointerHeld(), true)

  for (const [target, type] of [
    [doc, 'pointerup'],
    [doc, 'pointercancel'],
    [doc, 'contextmenu'],
    [win, 'blur'],
  ] as const) {
    fire(doc, 'pointerdown', { button: 0 })
    assert.equal(pointerHeld(), true, `${type} before`)
    fire(target, type)
    assert.equal(pointerHeld(), false, type)
  }

  fire(doc, 'keydown', { key: 'Tab' })
  assert.equal(lastInput(), 'keyboard')
  fire(doc, 'pointerdown', { button: 0 })
  stop()
  assert.equal(lastInput(), 'keyboard')
  assert.equal(pointerHeld(), false)
  fire(doc, 'pointerdown', { button: 0 })
  assert.equal(lastInput(), 'keyboard')
  assert.equal(pointerHeld(), false)
})
