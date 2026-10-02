import assert from 'node:assert/strict'
import { test } from 'node:test'

import { clampScroll, dragModel, stepChapter } from './dragSlots.ts'

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
