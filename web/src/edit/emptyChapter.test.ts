import assert from 'node:assert/strict'
import { test } from 'node:test'

import { emptyChapterWords, holdsNothing } from './emptyChapter.ts'

const LEFT_OUT = 'A chapter without clips is left out of the movie.'
const MOVE_IN = 'Move clips into it with Move to… (the Clip tab’s, or a clip’s menu).'

test('another chapter is listed: the words say how clips get in, with Move to…', () => {
  assert.equal(
    emptyChapterWords(false, true),
    `No clips. ${MOVE_IN} ${LEFT_OUT}`,
  )
  assert.equal(
    emptyChapterWords(false, false),
    `It plays no clip. ${MOVE_IN} ${LEFT_OUT}`,
  )
})

test('a lone chapter points at nothing that is not there', () => {
  assert.equal(emptyChapterWords(true, true), `No clips. ${LEFT_OUT}`)
  assert.equal(emptyChapterWords(true, false), `It plays no clip. ${LEFT_OUT}`)
  for (const wholly of [true, false]) {
    assert.doesNotMatch(emptyChapterWords(true, wholly), /Drag|Move/)
  }
  for (const alone of [true, false]) {
    for (const wholly of [true, false]) {
      assert.doesNotMatch(emptyChapterWords(alone, wholly), /Drag|Move marked/)
    }
  }
})

test('an ignored clip listed apart still makes the chapter "play no clip"', () => {
  assert.equal(holdsNothing(0, 0, 0), true)
  assert.equal(holdsNothing(0, 0, 1), false)
  assert.equal(holdsNothing(0, 1, 0), false)
  assert.equal(holdsNothing(1, 0, 0), false)
})
