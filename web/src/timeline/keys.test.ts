import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { playheadKey } from './keys.ts'

describe('playheadKey', () => {
  it('steps a frame with Left and Right, a second with Shift, five seconds with Page', () => {
    assert.deepEqual(playheadKey('ArrowLeft', false), { kind: 'frames', n: -1 })
    assert.deepEqual(playheadKey('ArrowRight', false), { kind: 'frames', n: 1 })
    assert.deepEqual(playheadKey('ArrowLeft', true), { kind: 'ms', ms: -1000 })
    assert.deepEqual(playheadKey('ArrowRight', true), { kind: 'ms', ms: 1000 })
    assert.deepEqual(playheadKey('PageDown', false), { kind: 'ms', ms: -5000 })
    assert.deepEqual(playheadKey('PageUp', false), { kind: 'ms', ms: 5000 })
  })

  it('goes to the start and the end with Home and End, and plays with Space', () => {
    assert.deepEqual(playheadKey('Home', false), { kind: 'to', where: 'start' })
    assert.deepEqual(playheadKey('End', false), { kind: 'to', where: 'end' })
    assert.deepEqual(playheadKey(' ', false), { kind: 'toggle' })
  })

  it('answers the slider\'s Up and Down as Right and Left, and leaves other keys alone', () => {
    assert.deepEqual(playheadKey('ArrowUp', false), { kind: 'frames', n: 1 })
    assert.deepEqual(playheadKey('ArrowDown', false), { kind: 'frames', n: -1 })
    for (const key of ['a', 'Enter', 'Tab', '+', '-', '0', 'Escape']) {
      assert.equal(playheadKey(key, false), null)
    }
  })
})
