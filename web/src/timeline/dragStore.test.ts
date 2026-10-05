import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createDragStore, held, shiftMs } from './dragStore.ts'
import type { Dragging, EdgeDragging } from './dragStore.ts'

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

  it('has one owner: a second press is refused until the first lets go', () => {
    const store = createDragStore()
    const a = {}
    const b = {}
    assert.equal(store.claim(a), true)
    assert.equal(store.claim(a), true)
    assert.equal(store.claim(b), false)
    assert.equal(store.owns(a), true)
    assert.equal(store.owns(b), false)
    store.unclaim(b)
    assert.equal(store.owns(a), true)
    assert.equal(store.claim(b), false)
    store.unclaim(a)
    assert.equal(store.owns(a), false)
    assert.equal(store.claim(b), true)
  })

  it('holds a card edge in the air under the same claim, and tells readers only when it moved', () => {
    const store = createDragStore()
    let told = 0
    store.subscribe(() => {
      told += 1
    })
    const edge = { chapter: 'B', tenths: 40, snapped: true, words: 'Whole second' }
    store.setCard(edge)
    store.setCard({ ...edge })
    assert.equal(told, 1)
    assert.deepEqual(store.getCard(), edge)
    assert.equal(store.get(), null, 'a card edge is not a trim')
    store.setCard({ ...edge, tenths: 41, snapped: false, words: '' })
    assert.equal(told, 2)
    store.setCard(null)
    assert.equal(store.getCard(), null)
    assert.equal(told, 3)
  })

  it('refuses a card drag while a trim drag holds the store', () => {
    const store = createDragStore()
    const trim = {}
    const card = {}
    assert.equal(store.claim(trim), true)
    assert.equal(store.claim(card), false)
    store.unclaim(trim)
    assert.equal(store.claim(card), true)
  })
})

describe('the drag store and a clip edge (clip-edge-trim)', () => {
  const edge: EdgeDragging = {
    identity: 'a.mp4',
    side: 'start',
    x: 500,
    place: 500,
    snappedTo: null,
    joined: [],
    changeMs: -500,
    playsMs: 3020,
    extent: { inMs: 500, outMs: 6020 },
    limit: null,
    deltaMs: -500,
    cuts: [{ in: 0, out: 0.5 }],
    tip: '−0:00.5 · 0:03.02',
    notes: [],
  }

  it('holds the edge in the air and tells its readers once per move', () => {
    const store = createDragStore()
    let calls = 0
    store.subscribe(() => {
      calls += 1
    })
    store.setEdge(edge)
    store.setEdge({ ...edge })
    assert.equal(calls, 1)
    store.setEdge({ ...edge, x: 520, place: 520, deltaMs: -520, tip: 'x' })
    assert.equal(calls, 2)
    assert.equal(store.getEdge()?.x, 520)
    // Cancel: back to nothing in the air.
    store.setEdge(null)
    assert.equal(calls, 3)
    assert.equal(store.getEdge(), null)
  })

  it('an edge drag, a trim and a card share the one claim', () => {
    const store = createDragStore()
    const edgeToken = {}
    const trimToken = {}
    const cardToken = {}
    assert.equal(store.claim(edgeToken), true)
    assert.equal(store.claim(trimToken), false)
    assert.equal(store.claim(cardToken), false)
    store.unclaim(edgeToken)
    assert.equal(store.claim(trimToken), true)
    assert.equal(store.claim(edgeToken), false)
  })

  it('held: a press (before any move) or a drag holds the store; the probe leaves it free', () => {
    const store = createDragStore()
    assert.equal(held(store), false)
    assert.equal(store.claim({}), true, 'the probe gave the claim back')
    const fresh = createDragStore()
    const press = {}
    fresh.claim(press)
    assert.equal(held(fresh), true)
    assert.equal(fresh.owns(press), true, 'the probe never takes a held claim')
    fresh.unclaim(press)
    fresh.setEdge(edge)
    assert.equal(held(fresh), true)
    fresh.setEdge(null)
    fresh.setCard({ chapter: 'Beach', tenths: 35, snapped: false, words: '' })
    assert.equal(held(fresh), true)
  })

  it('shiftMs: the dragged clip edge moves what follows by its block’s change, a card by its length', () => {
    const store = createDragStore()
    assert.equal(shiftMs(store, null), 0)
    assert.equal(shiftMs(store, { kind: 'edge', identity: 'a.mp4' }), 0)
    store.setEdge(edge)
    assert.equal(shiftMs(store, { kind: 'edge', identity: 'a.mp4' }), -500)
    assert.equal(shiftMs(store, { kind: 'edge', identity: 'b.mp4' }), 0)
    store.setCard({ chapter: 'Beach', tenths: 35, snapped: false, words: '' })
    assert.equal(shiftMs(store, { kind: 'card', chapter: 'Beach', baseTenths: 30 }), 500)
  })
})
