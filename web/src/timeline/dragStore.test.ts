import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createDragStore } from './dragStore.ts'
import type { Dragging } from './dragStore.ts'

const drag: Dragging = { identity: 'a.mp4', key: 'r0', edge: 'out', ms: 3500, snappedTo: null, words: '' }

describe('the drag store', () => {
  it('holds the edge in the air and tells its readers only when it moved', () => {
    const store = createDragStore()
    let calls = 0
    store.subscribe(() => {
      calls += 1
    })
    assert.equal(store.get(), null)
    store.set(drag)
    store.set({ ...drag })
    assert.equal(calls, 1)
    store.set({ ...drag, ms: 3540, snappedTo: 4000, words: 'Snapped to cut 2 start' })
    assert.equal(calls, 2)
    assert.equal(store.get()?.ms, 3540)
    store.set(null)
    store.set(null)
    assert.equal(calls, 3)
    assert.equal(store.get(), null)
  })

  it('a reader that left is not told', () => {
    const store = createDragStore()
    let calls = 0
    const off = store.subscribe(() => {
      calls += 1
    })
    off()
    store.set(drag)
    assert.equal(calls, 0)
  })
})
