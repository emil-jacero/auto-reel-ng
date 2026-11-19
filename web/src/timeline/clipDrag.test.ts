import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  CLIP_SLOP_PX,
  IGNORE_GROUP_WORDS,
  MOVE_ONE_WORDS,
  bandSlot,
  dropWords,
  flatMove,
  groupBandSlot,
  groupCount,
  groupSlot,
  inBox,
  isGroupOwnPlace,
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

describe('the group slot (clip-multi-select D4)', () => {
  // Main: a b c, Kvällen: d e; each clip 1 s long, end to end.
  const named: DrawnChapter[] = [
    { key: 'r0', name: 'Main', identities: ['a', 'b', 'c'] },
    { key: 'r1', name: 'Kvällen', identities: ['d', 'e'] },
  ]
  const group = (...ids: string[]) => new Set(ids)

  it('counts the clips of the group the track draws', () => {
    assert.equal(groupCount(named, group('b', 'd', 'zz')), 2)
  })

  it('goes before the clip nearest the pointer that is not in the group', () => {
    // d and e dragged to 100 ms: the line stands before a.
    const slot = groupSlot(named, group('d', 'e'), starts, extents, 100)
    assert.deepEqual(slot, {
      chapter: 'r0',
      beforeIdentity: 'a',
      place: 'Before a',
      words: '2 clips \u00b7 Before a',
      lineMs: 0,
    })
  })

  it('offers no boundary before a held clip: the line goes to the next clip outside the group', () => {
    // b and c held, the pointer at 2.4 s: c's start (2000) is not offered, so the nearest is the
    // end of Main (3000), which is also where d starts; the pointer is before it, so it is Main's end.
    const slot = groupSlot(named, group('b', 'c'), starts, extents, 2400)
    assert.equal(slot?.chapter, 'r0')
    assert.equal(slot?.beforeIdentity, null)
    assert.equal(slot?.words, '2 clips \u00b7 End of Main')
    assert.equal(slot?.lineMs, 3000)
    // With b held alone, c's start is offered and the pointer at 2.4 s is nearest to it.
    assert.equal(groupSlot(named, group('b'), starts, extents, 2100)?.beforeIdentity, 'c')
  })

  it('takes the earlier boundary of a shared time before it and the later at or after it', () => {
    // Main ends at 3000 where d starts.
    const before = groupSlot(named, group('a'), starts, extents, 2900)
    assert.equal(before?.chapter, 'r0')
    assert.equal(before?.beforeIdentity, null)
    assert.equal(before?.words, '1 clips \u00b7 End of Main')
    const after = groupSlot(named, group('a'), starts, extents, 3000)
    assert.equal(after?.chapter, 'r1')
    assert.equal(after?.beforeIdentity, 'd')
    assert.equal(after?.words, '1 clips \u00b7 Before d')
  })

  it('ends at the last chapter when the pointer is past it', () => {
    const slot = groupSlot(named, group('a', 'b'), starts, extents, 99_000)
    assert.equal(slot?.chapter, 'r1')
    assert.equal(slot?.beforeIdentity, null)
    assert.equal(slot?.place, 'End of Kvällen')
    assert.equal(slot?.lineMs, 5000)
  })

  it('names a chapter by its key when it has no name', () => {
    const slot = groupSlot([{ key: 'r0', identities: ['a', 'b'] }], group('a'), [0, 1000], [1000, 1000], 9000)
    assert.equal(slot?.place, 'End of r0')
  })

  it('draws no slot over no chapter', () => {
    assert.equal(groupSlot([], group('a'), [], [], 0), null)
  })

  it('drops on a chapter band at that chapter end', () => {
    const slot = groupBandSlot(named, group('d'), starts, extents, 0)
    assert.equal(slot?.chapter, 'r0')
    assert.equal(slot?.beforeIdentity, null)
    assert.equal(slot?.words, '1 clips \u00b7 End of Main')
    assert.equal(slot?.lineMs, 3000)
    assert.equal(groupBandSlot(named, group('d'), starts, extents, 5), null)
  })

  it('knows a drop that leaves the order as it is', () => {
    // b and c, the end of Main: where they are. Before d, they join Kvällen.
    assert.equal(isGroupOwnPlace(named, group('b', 'c'), { chapter: 'r0', beforeIdentity: null }), true)
    assert.equal(isGroupOwnPlace(named, group('b', 'c'), { chapter: 'r1', beforeIdentity: 'd' }), false)
    assert.equal(isGroupOwnPlace(named, group('a', 'c'), { chapter: 'r0', beforeIdentity: 'b' }), false)
    assert.equal(isGroupOwnPlace(named, group('a', 'b'), { chapter: 'r0', beforeIdentity: 'c' }), true)
    assert.equal(isGroupOwnPlace(named, group('d', 'e'), { chapter: 'r1', beforeIdentity: null }), true)
    // A run that is not contiguous gathers before the clip: a and c before b is a change.
    assert.equal(isGroupOwnPlace(named, group('a', 'c'), { chapter: 'r0', beforeIdentity: null }), false)
  })

  it('says what a release over the bin does', () => {
    assert.equal(IGNORE_GROUP_WORDS, 'Release on the bin to ignore the clips')
  })
})
