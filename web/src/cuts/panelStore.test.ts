import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createCutPanels } from './panelStore.ts'
import { formatTime, parseTime } from './times.ts'

/*
 * The cut-panel store (`panelStore.ts`), run by `npm test`: what the bin player's Set From and Set
 * To rely on (`clip-tab-and-player`, design D4).
 */

describe('setTyped', () => {
  it('gives a clip with no entry one holding that one field', () => {
    const { panels } = createCutPanels()
    panels.setTyped('a.mp4', 'start', '0:01.234')
    assert.deepEqual(panels.get('a.mp4'), { start: '0:01.234', end: '' })
  })

  it('keeps the other field as typed', () => {
    const { panels } = createCutPanels()
    panels.set('a.mp4', { start: '0:01', end: '0:02' })
    panels.setTyped('a.mp4', 'end', '0:03.5')
    assert.deepEqual(panels.get('a.mp4'), { start: '0:01', end: '0:03.5' })
  })

  it('writes a time the panel reads back as the same millisecond', () => {
    const { panels } = createCutPanels()
    for (const seconds of [0, 1.234, 2.5, 61.007, 3725.9]) {
      panels.setTyped('a.mp4', 'start', formatTime(seconds))
      const read = parseTime(panels.get('a.mp4')?.start ?? '')
      assert.deepEqual(read, { ok: true, ms: Math.round(seconds * 1000) })
    }
  })
})

describe('subscribe', () => {
  it("tells only the written clip's subscribers, until they unsubscribe", () => {
    const { panels } = createCutPanels()
    let a = 0
    let b = 0
    const stop = panels.subscribe('a.mp4', () => (a += 1))
    panels.subscribe('b.mp4', () => (b += 1))
    panels.setTyped('a.mp4', 'start', '0:01')
    panels.set('a.mp4', { start: '0:01', end: '' })
    assert.deepEqual([a, b], [2, 0])
    stop()
    panels.setTyped('a.mp4', 'end', '0:02')
    assert.equal(a, 2)
  })

  it('tells every clip that had an entry when it is cleared, and leaves them empty', () => {
    const { panels, clear } = createCutPanels()
    const seen: (string | undefined)[] = []
    panels.subscribe('a.mp4', () => seen.push(panels.get('a.mp4')?.start))
    panels.setTyped('a.mp4', 'start', '0:01')
    clear()
    assert.deepEqual(seen, ['0:01', undefined])
  })
})
