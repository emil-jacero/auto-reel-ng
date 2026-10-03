import assert from 'node:assert/strict'
import { describe, it, test } from 'node:test'

import { clampScroll, dragModel, stepChapter } from './dragSlots.ts'
import { overIdOf, pointerTarget, slotOf, slotsOf, stepSlot } from './dragSlots.ts'
import type { Span } from './dragSlots.ts'

// `2024-08-20 - Två kapitel - Tjörn`: Main plays one clip, Kvällen three.
const R0 = 'r0'
const R1 = 'r1'
const ONE = 's1710001.mp4'
const TWO = 'Kvällen/s1710002.mp4'
const THREE = 'Kvällen/s1710003.mp4'
const FOUR = 'Kvällen/s1710004.mp4'

const orders = new Map([
  [R0, [ONE]],
  [R1, [TWO, THREE, FOUR]],
])
const model = dragModel(orders, [R0, R1])

test('a clip steps to the first slot of the next or the previous chapter', () => {
  assert.deepEqual(stepChapter(model, ONE, false, { chapter: R0, index: 0 }, 1), {
    chapter: R1,
    index: 0,
  })
  assert.deepEqual(stepChapter(model, ONE, false, { chapter: R1, index: 2 }, -1), {
    chapter: R0,
    index: 0,
  })
})

test('there is no step past the first or the last chapter', () => {
  assert.equal(stepChapter(model, ONE, false, { chapter: R0, index: 0 }, -1), null)
  assert.equal(stepChapter(model, ONE, false, { chapter: R1, index: 0 }, 1), null)
})

test('a clip of the later chapter enters the earlier one at its first gap, and back at position 1', () => {
  assert.deepEqual(stepChapter(model, TWO, false, { chapter: R1, index: 1 }, -1), {
    chapter: R0,
    index: 0,
  })
  assert.deepEqual(stepChapter(model, TWO, false, { chapter: R0, index: 1 }, 1), {
    chapter: R1,
    index: 0,
  })
})

test('a clip that stays home has no other chapter', () => {
  assert.equal(stepChapter(model, ONE, true, { chapter: R0, index: 0 }, 1), null)
  assert.equal(stepChapter(model, TWO, true, { chapter: R1, index: 0 }, -1), null)
})

test('one listed chapter has nowhere to jump', () => {
  const lone = dragModel(orders, [R1])
  assert.equal(stepChapter(lone, TWO, false, { chapter: R1, index: 0 }, 1), null)
  assert.equal(stepChapter(lone, TWO, false, { chapter: R1, index: 2 }, -1), null)
})

test('an unknown clip, or a slot in an unlisted chapter, gives null', () => {
  assert.equal(stepChapter(model, 'nope.mp4', false, { chapter: R0, index: 0 }, 1), null)
  assert.equal(stepChapter(model, ONE, false, { chapter: 'r9', index: 0 }, 1), null)
})

test('an empty listed chapter is entered at its area, a deleted one is passed over', () => {
  const withEmpty = new Map([...orders, ['r2', [] as string[]]])
  const listed = dragModel(withEmpty, [R0, R1, 'r2'])
  assert.deepEqual(stepChapter(listed, ONE, false, { chapter: R1, index: 0 }, 1), {
    chapter: 'r2',
    index: 0,
  })
  const passed = dragModel(withEmpty, [R0, 'r2'])
  assert.deepEqual(stepChapter(passed, ONE, false, { chapter: R0, index: 0 }, 1), {
    chapter: 'r2',
    index: 0,
  })
  const onlyDeleted = dragModel(withEmpty, [R0])
  assert.equal(stepChapter(onlyDeleted, ONE, false, { chapter: R0, index: 0 }, 1), null)
})

test('the last chapter is the end even when the clip is held in the middle of it', () => {
  assert.equal(stepChapter(model, THREE, false, { chapter: R1, index: 1 }, 1), null)
  assert.deepEqual(stepChapter(model, FOUR, false, { chapter: R1, index: 2 }, -1), {
    chapter: R0,
    index: 0,
  })
})

test('a page scroll is clamped to the document, and the clamped part is left over', () => {
  assert.deepEqual(clampScroll(300, 100, 1000), { applied: 300, left: 0 })
  assert.deepEqual(clampScroll(300, 800, 1000), { applied: 200, left: 100 })
  assert.deepEqual(clampScroll(-300, 100, 1000), { applied: -100, left: -200 })
  assert.deepEqual(clampScroll(300, 0, 0), { applied: 0, left: 300 })
})

// Gap mode: a group is held, so the clip's own chapter offers gaps like any other.
describe('a held group (gaps)', () => {
  const R2 = 'r2'
  const three = new Map([
    [R0, [ONE]],
    [R1, [TWO, THREE, FOUR]],
    [R2, []],
  ])
  const gaps = dragModel(three, [R0, R1, R2], true)
  const plain = dragModel(three, [R0, R1, R2])

  it('is off by default, and a plain model keeps its positions', () => {
    assert.equal(plain.gaps, false)
    assert.equal(gaps.gaps, true)
    assert.equal(slotsOf(plain, TWO, false).filter((slot) => slot.chapter === R1).length, 3)
  })

  it('offers a chapter of n clips n + 1 slots, its own too, and an empty chapter one', () => {
    const count = (key: string) => slotsOf(gaps, TWO, false).filter((s) => s.chapter === key).length
    assert.equal(count(R0), 2)
    assert.equal(count(R1), 4)
    assert.equal(count(R2), 1)
  })

  it('steps through every gap of the own chapter, then the next chapter’s', () => {
    let at = { chapter: R1, index: 0 }
    const seen = [at]
    for (let step = stepSlot(gaps, TWO, false, at, 1); step !== null; ) {
      seen.push(step)
      at = step
      step = stepSlot(gaps, TWO, false, at, 1)
    }
    assert.deepEqual(
      seen.map((slot) => `${slot.chapter}:${slot.index}`),
      ['r1:0', 'r1:1', 'r1:2', 'r1:3', 'r2:0'],
    )
    assert.deepEqual(stepSlot(gaps, TWO, false, { chapter: R1, index: 0 }, -1), {
      chapter: R0,
      index: 1,
    })
  })

  it('enters every chapter at gap 0 with the Page keys', () => {
    assert.deepEqual(stepChapter(gaps, TWO, false, { chapter: R1, index: 2 }, -1), {
      chapter: R0,
      index: 0,
    })
    assert.deepEqual(stepChapter(gaps, ONE, false, { chapter: R0, index: 0 }, 1), {
      chapter: R1,
      index: 0,
    })
  })

  it('maps a slot to its droppable and back, for all slots of the model', () => {
    for (const identity of [ONE, TWO, THREE, FOUR]) {
      for (const slot of slotsOf(gaps, identity, false)) {
        assert.deepEqual(slotOf(gaps, identity, overIdOf(gaps, identity, slot)), slot)
      }
    }
  })

  it('names the gap after the last clip of the own chapter /chapter/<key>', () => {
    assert.equal(overIdOf(gaps, TWO, { chapter: R1, index: 3 }), '/chapter/r1')
    assert.deepEqual(slotOf(gaps, TWO, '/chapter/r1'), { chapter: R1, index: 3 })
    // Without a group the own chapter has no gap after its last clip.
    assert.equal(overIdOf(plain, TWO, { chapter: R1, index: 2 }), FOUR)
    assert.deepEqual(slotOf(plain, TWO, '/chapter/r1'), { chapter: R1, index: 2 })
  })

  it('takes the first row below the pointer in the own chapter, else the chapter itself', () => {
    const rows = new Map<string, Span>([
      [ONE, { top: 100, bottom: 140 }],
      [TWO, { top: 300, bottom: 340 }],
      [THREE, { top: 340, bottom: 380 }],
      [FOUR, { top: 380, bottom: 420 }],
    ])
    const chapters = new Map<string, Span>([
      [R0, { top: 60, bottom: 160 }],
      [R1, { top: 260, bottom: 460 }],
      [R2, { top: 500, bottom: 560 }],
    ])
    const at = (y: number, model = gaps) =>
      pointerTarget(model, TWO, false, y, (key) => chapters.get(key), [], (row) => rows.get(row))
    // The first row whose centre lies below the pointer: the gap before it.
    assert.equal(at(310), TWO)
    assert.equal(at(330), THREE)
    assert.equal(at(345), THREE)
    assert.equal(at(370), FOUR)
    assert.equal(at(405), '/chapter/r1')
    assert.equal(at(440), '/chapter/r1')
    // A plain drag over its own row is the clip itself, as it was.
    assert.equal(at(310, plain), TWO)
    assert.equal(at(330, plain), TWO)
    assert.equal(at(345, plain), THREE)
  })
})
