import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { playheadKey, trackZoomKey } from './keys.ts'
import type { ZoomKeyPress } from './keys.ts'

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
    for (const key of ['a', 'Enter', 'Tab', '+', '=', '-', '_', '0', '\\', 'Escape']) {
      assert.equal(playheadKey(key, false), null)
    }
  })
})

describe('trackZoomKey', () => {
  const press = (key: string, mods: Partial<Omit<ZoomKeyPress, 'key'>> = {}): ZoomKeyPress => ({
    key,
    ctrlKey: false,
    altKey: false,
    metaKey: false,
    altGraph: false,
    ...mods,
  })

  it('takes the zoom keys unmodified and nothing else', () => {
    for (const key of ['+', '=', '-', '_', '0', '\\']) {
      assert.equal(trackZoomKey(press(key)), key)
    }
    for (const key of ['a', '1', 'ArrowLeft', ' ']) {
      assert.equal(trackZoomKey(press(key)), null)
    }
  })

  it('leaves Ctrl and Cmd zoom keys to the browser', () => {
    assert.equal(trackZoomKey(press('-', { ctrlKey: true })), null)
    assert.equal(trackZoomKey(press('0', { ctrlKey: true })), null)
    assert.equal(trackZoomKey(press('=', { metaKey: true })), null)
    assert.equal(trackZoomKey(press('\\', { metaKey: true, altKey: true })), null)
  })

  it('takes a backslash typed with AltGr (Windows Ctrl+Alt, Linux AltGraph) or Option (macOS)', () => {
    assert.equal(trackZoomKey(press('\\', { ctrlKey: true, altKey: true })), '\\')
    assert.equal(trackZoomKey(press('\\', { ctrlKey: true, altKey: true, altGraph: true })), '\\')
    assert.equal(trackZoomKey(press('\\', { altGraph: true })), '\\')
    assert.equal(trackZoomKey(press('\\', { altKey: true })), '\\')
    assert.equal(trackZoomKey(press('\\', { ctrlKey: true })), null)
  })

  it('takes any zoom key typed with AltGr, and none with Alt alone but the backslash', () => {
    assert.equal(trackZoomKey(press('+', { ctrlKey: true, altKey: true, altGraph: true })), '+')
    assert.equal(trackZoomKey(press('=', { altGraph: true })), '=')
    assert.equal(trackZoomKey(press('-', { altKey: true })), null)
  })
})
