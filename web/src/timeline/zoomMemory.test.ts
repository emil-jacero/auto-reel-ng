import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { MAX_PPS } from './model.ts'
import { createZoomMemory, parseZoom, restoredZoom, zoomKey } from './zoomMemory.ts'
import type { MemoStorage } from './zoomMemory.ts'

/** A stand-in for `sessionStorage`. */
function store(initial: Record<string, string> = {}): MemoStorage & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial))
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value)
    },
  }
}

const throwing: MemoStorage = {
  getItem: () => {
    throw new Error('SecurityError')
  },
  setItem: () => {
    throw new Error('QuotaExceededError')
  },
}

describe('parseZoom', () => {
  it('reads a kept zoom', () => {
    assert.deepEqual(parseZoom('{"fitted":false,"pps":60}'), { fitted: false, pps: 60 })
    assert.deepEqual(parseZoom('{"fitted":true,"pps":12.5}'), { fitted: true, pps: 12.5 })
  })

  it('refuses a missing, unparsable, non-finite or misshapen value: the Timeline opens at Fit', () => {
    for (const raw of [null, '', 'not json', '{', '42', 'null', '[]', '{"fitted":false}',
      '{"fitted":"no","pps":60}', '{"fitted":false,"pps":"60"}', '{"fitted":false,"pps":0}',
      '{"fitted":false,"pps":-3}', '{"fitted":false,"pps":1e999}']) {
      assert.equal(parseZoom(raw), null, String(raw))
    }
  })
})

describe('restoredZoom', () => {
  it('keeps Fit as Fit, at the current Fit', () => {
    assert.deepEqual(restoredZoom({ fitted: true, pps: 3 }, 17, MAX_PPS), { fitted: true, pps: 17 })
  })

  it('holds a kept scale to the current Fit and maximum', () => {
    assert.deepEqual(restoredZoom({ fitted: false, pps: 60 }, 17, MAX_PPS), { fitted: false, pps: 60 })
    assert.deepEqual(restoredZoom({ fitted: false, pps: 900 }, 17, MAX_PPS), { fitted: false, pps: MAX_PPS })
    assert.deepEqual(restoredZoom({ fitted: false, pps: 5 }, 17, MAX_PPS), { fitted: true, pps: 17 })
  })

  it('gives nothing for nothing kept', () => {
    assert.equal(restoredZoom(null, 17, MAX_PPS), null)
  })
})

describe('createZoomMemory', () => {
  it('keeps the zoom per event under its own key', () => {
    const s = store()
    const memory = createZoomMemory(() => s)
    memory.write('2024/a', { fitted: false, pps: 60 })
    memory.write('2024/b', { fitted: true, pps: 9 })
    assert.equal(s.data.get(zoomKey('2024/a')), '{"fitted":false,"pps":60}')
    assert.equal(zoomKey('2024/a'), 'auto-reel:timeline-zoom:2024/a')
    assert.deepEqual(memory.read('2024/a'), { fitted: false, pps: 60 })
    assert.deepEqual(memory.read('2024/b'), { fitted: true, pps: 9 })
    assert.equal(memory.read('2024/c'), null)
  })

  it('reads what an earlier page of the tab kept (a reload)', () => {
    const s = store({ [zoomKey('ev')]: '{"fitted":false,"pps":80}' })
    assert.deepEqual(createZoomMemory(() => s).read('ev'), { fitted: false, pps: 80 })
  })

  it('opens at Fit for a corrupt value', () => {
    const s = store({ [zoomKey('ev')]: '{"fitted":false,"pps":NaN}' })
    assert.equal(createZoomMemory(() => s).read('ev'), null)
  })

  it('keeps the zoom for the page when storage throws, and never throws itself', () => {
    const memory = createZoomMemory(() => throwing)
    assert.equal(memory.read('ev'), null)
    memory.write('ev', { fitted: false, pps: 60 })
    assert.deepEqual(memory.read('ev'), { fitted: false, pps: 60 })
    const gone = createZoomMemory(() => {
      throw new Error('no sessionStorage here')
    })
    gone.write('ev', { fitted: false, pps: 30 })
    assert.deepEqual(gone.read('ev'), { fitted: false, pps: 30 })
  })

  it('works with no storage at all', () => {
    const memory = createZoomMemory(() => null)
    memory.write('ev', { fitted: true, pps: 4 })
    assert.deepEqual(memory.read('ev'), { fitted: true, pps: 4 })
  })
})
