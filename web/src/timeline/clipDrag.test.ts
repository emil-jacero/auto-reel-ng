import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  CLIP_SLOP_PX,
  MOVE_ONE_WORDS,
  bandSlot,
  dropWords,
  flatMove,
  inBox,
  isOwnPlace,
  pastSlop,
  shiftOf,
  slotLineMs,
  spanHit,
} from './clipDrag.ts'
import type { DrawnChapter } from './reorder.ts'

const chapters: DrawnChapter[] = [
  { key: 'r0', name: 'Main', identities: ['a', 'b', 'c'] },
  { key: 'r1', name: 'Kvällen', identities: ['d', 'e'] },
]
const starts = [0, 1000, 2000, 3000, 4000]
const extents = [1000, 1000, 1000, 1000, 1000]

describe('the clip drag model', () => {
  it('is a press until the slop is passed', () => {
    assert.equal(pastSlop(CLIP_SLOP_PX - 1, 0), false)
    assert.equal(pastSlop(2, 2), false)
    assert.equal(pastSlop(0, CLIP_SLOP_PX), true)
    assert.equal(pastSlop(-3, 0), true)
  })

  it('gives where the clip lands in the drawn order', () => {
    assert.deepEqual(flatMove(chapters, { chapter: 'r0', index: 0 }, 'b'), { from: 1, to: 0 })
    assert.deepEqual(flatMove(chapters, { chapter: 'r0', index: 2 }, 'a'), { from: 0, to: 2 })
    // To the end of Main from Kvällen: after a, b, c.
    assert.deepEqual(flatMove(chapters, { chapter: 'r0', index: 3 }, 'd'), { from: 3, to: 3 })
    assert.deepEqual(flatMove(chapters, { chapter: 'r1', index: 0 }, 'c'), { from: 2, to: 2 })
    assert.deepEqual(flatMove(chapters, { chapter: 'r1', index: 2 }, 'a'), { from: 0, to: 4 })
  })

  it('shifts the clips the block passes, by its width, and no others', () => {
    // b to the front: a moves right.
    assert.deepEqual([0, 1, 2, 3, 4].map((i) => shiftOf(1, 0, i)), [1, 0, 0, 0, 0])
    // a to after c: b and c move left.
    assert.deepEqual([0, 1, 2, 3, 4].map((i) => shiftOf(0, 2, i)), [0, -1, -1, 0, 0])
    // Own place: nobody moves.
    assert.deepEqual([0, 1, 2].map((i) => shiftOf(1, 1, i)), [0, 0, 0])
  })

  it('knows the own place', () => {
    assert.equal(isOwnPlace(chapters, { chapter: 'r0', index: 1 }, 'b'), true)
    assert.equal(isOwnPlace(chapters, { chapter: 'r0', index: 0 }, 'b'), false)
    assert.equal(isOwnPlace(chapters, { chapter: 'r1', index: 1 }, 'b'), false)
    assert.equal(dropWords(true, { words: 'Before a' }), 'Stays where it is')
    assert.equal(dropWords(false, { words: 'Before a' }), 'Before a')
  })

  it('places the drop line at a clip start or a chapter end', () => {
    assert.equal(slotLineMs(starts, extents, chapters, { chapter: 'r0', beforeIdentity: 'a' }, 'b'), 0)
    assert.equal(slotLineMs(starts, extents, chapters, { chapter: 'r1', beforeIdentity: 'e' }, 'a'), 4000)
    // The end of Main with c dragged: after b.
    assert.equal(slotLineMs(starts, extents, chapters, { chapter: 'r0', beforeIdentity: null }, 'c'), 2000)
    assert.equal(slotLineMs(starts, extents, chapters, { chapter: 'r0', beforeIdentity: null }, 'd'), 3000)
    assert.equal(slotLineMs(starts, extents, chapters, { chapter: 'r1', beforeIdentity: null }, 'a'), 5000)
  })

  it('drops on a band at the chapter end', () => {
    const slot = bandSlot(chapters, 0, 'd')
    assert.deepEqual(slot, { chapter: 'r0', index: 3, beforeIdentity: null, words: 'At the end of Main' })
    assert.equal(bandSlot(chapters, 1, 'd')?.index, 1)
    assert.equal(bandSlot(chapters, 5, 'd'), null)
  })

  it('tests a point against a box', () => {
    const box = { left: 0, right: 10, top: 0, bottom: 10 }
    assert.equal(inBox(box, 5, 5), true)
    assert.equal(inBox(box, 11, 5), false)
  })
})

describe('the span hit test', () => {
  const cuts = [{ in: 1, out: 2 }, { in: 3, out: 4, removed: true }]
  it('tells a cut span, a card span and the rest of the body apart', () => {
    assert.equal(spanHit({ clip: 0, ms: 1500 }, 'a', 'a', cuts), 'cut')
    assert.equal(spanHit({ clip: 0, ms: 2000 }, 'a', 'a', cuts), null)
    assert.equal(spanHit({ clip: 0, ms: 3500 }, 'a', 'a', cuts), null)
    assert.equal(spanHit({ clip: 0, ms: 1500 }, 'b', 'a', cuts), null)
    assert.equal(spanHit({ clip: 0, ms: 0, card: {} }, 'a', 'a', cuts), 'card')
  })
  it('moves a clip across a chapter join with no clip to shift', () => {
    assert.deepEqual([0, 1, 2, 3, 4].map((i) => shiftOf(3, 3, i)), [0, 0, 0, 0, 0])
  })
})

describe('MOVE_ONE_WORDS', () => {
  it('says Alt and an arrow move one clip and where several move', () => {
    assert.equal(
      MOVE_ONE_WORDS,
      'Alt and an arrow move one clip. Move to\u2026 in the Clip tab moves the selected clips.',
    )
  })
})
