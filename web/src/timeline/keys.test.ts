import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { clipMoveKey, playheadKey, stepSlot, trackZoomKey } from './keys.ts'
import type { MoveKeyPress, ZoomKeyPress } from './keys.ts'
import { applyDrop } from './reorder.ts'
import type { DrawnChapter, DropSlot } from './reorder.ts'

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

describe('the edge tools\' letters (clip-edge-trim)', () => {
  it('leaves Q, W and S to the track: they are not the playhead\'s keys', () => {
    for (const key of ['q', 'w', 's', 'Q', 'W', 'S']) {
      assert.equal(playheadKey(key, false), null)
      assert.equal(playheadKey(key, true), null)
    }
  })
})

describe('clipMoveKey (track-drag-edit, D4)', () => {
  const alt = (key: string, extra: Partial<MoveKeyPress> = {}): MoveKeyPress => ({
    key,
    altKey: true,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    altGraph: false,
    ...extra,
  })

  it('takes Alt+Left and Alt+Right as one place back and forward', () => {
    assert.equal(clipMoveKey(alt('ArrowLeft')), -1)
    assert.equal(clipMoveKey(alt('ArrowRight')), 1)
  })

  it('leaves the playhead\'s arrows (no Alt) and other keys alone', () => {
    assert.equal(clipMoveKey(alt('ArrowLeft', { altKey: false })), null)
    assert.equal(clipMoveKey(alt('ArrowRight', { altKey: false, shiftKey: true })), null)
    for (const key of ['ArrowUp', 'ArrowDown', 'Home', 'a', 'Enter']) {
      assert.equal(clipMoveKey(alt(key)), null)
    }
  })

  it('ignores Alt chords with Ctrl, Cmd, Shift or AltGr', () => {
    for (const extra of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altGraph: true }]) {
      assert.equal(clipMoveKey(alt('ArrowLeft', extra)), null)
      assert.equal(clipMoveKey(alt('ArrowRight', extra)), null)
    }
  })
})

describe('stepSlot (track-drag-edit, D4)', () => {
  const lay: DrawnChapter[] = [
    { key: 'a', name: 'Main', identities: ['m1.mp4', 'm2.mp4', 'm3.mp4'] },
    { key: 'b', name: 'Kvällen', identities: ['k1.mp4', 'k2.mp4'] },
  ]
  const orders = new Map([
    ['a', ['m1.mp4', 'm2.mp4', 'm3.mp4']],
    ['b', ['k1.mp4', 'k2.mp4']],
  ])
  const apply = (identity: string, chapter: string, way: -1 | 1) => {
    const step = stepSlot(lay, identity, way)
    assert.equal(step?.kind, 'slot')
    return applyDrop(orders, { identity, chapter }, (step as { slot: DropSlot }).slot)
  }

  it('swaps with the neighbour inside a chapter', () => {
    assert.deepEqual(apply('m2.mp4', 'a', 1).get('a'), ['m1.mp4', 'm3.mp4', 'm2.mp4'])
    assert.deepEqual(apply('m2.mp4', 'a', -1).get('a'), ['m2.mp4', 'm1.mp4', 'm3.mp4'])
  })

  it('crosses into the next chapter\'s start from a last clip, and back from a first', () => {
    const forward = apply('m3.mp4', 'a', 1)
    assert.deepEqual(forward.get('a'), ['m1.mp4', 'm2.mp4'])
    assert.deepEqual(forward.get('b'), ['m3.mp4', 'k1.mp4', 'k2.mp4'])
    const back = apply('k1.mp4', 'b', -1)
    assert.deepEqual(back.get('a'), ['m1.mp4', 'm2.mp4', 'm3.mp4', 'k1.mp4'])
    assert.deepEqual(back.get('b'), ['k2.mp4'])
  })

  it('names the slot', () => {
    const step = stepSlot(lay, 'm3.mp4', 1)
    assert.equal(step?.kind === 'slot' && step.slot.words, 'Before k1.mp4')
    const end = stepSlot(lay, 'k1.mp4', -1)
    assert.equal(end?.kind === 'slot' && end.slot.words, 'At the end of Main')
  })

  it('goes into an empty neighbour chapter', () => {
    const withEmpty: DrawnChapter[] = [...lay, { key: 'c', identities: [] }]
    const step = stepSlot(withEmpty, 'k2.mp4', 1)
    assert.equal(step?.kind === 'slot' && step.slot.chapter, 'c')
    assert.equal(step?.kind === 'slot' && step.slot.beforeIdentity, null)
  })

  it('says so at the first and the last clip, and is null for an undrawn clip', () => {
    assert.deepEqual(stepSlot(lay, 'm1.mp4', -1), { kind: 'edge', words: 'm1.mp4 is already the first clip.' })
    assert.deepEqual(stepSlot(lay, 'k2.mp4', 1), { kind: 'edge', words: 'k2.mp4 is already the last clip.' })
    assert.equal(stepSlot(lay, 'zz.mp4', 1), null)
  })
})
