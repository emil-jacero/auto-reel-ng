import assert from 'node:assert/strict'
import { test } from 'node:test'

import { emptyChapterWords, holdsNothing } from './emptyChapter.ts'

const LEFT_OUT = 'A chapter without clips is left out of the movie.'

test('another chapter is listed: today’s words, with how clips get in', () => {
  assert.equal(
    emptyChapterWords(false, true),
    `No clips. Drag clips here, or move them here with Move marked to…. ${LEFT_OUT}`,
  )
  assert.equal(
    emptyChapterWords(false, false),
    `It plays no clip. Drag clips here, or move them here with Move marked to…. ${LEFT_OUT}`,
  )
})

test('a lone chapter points at nothing that is not there', () => {
  assert.equal(emptyChapterWords(true, true), `No clips. ${LEFT_OUT}`)
  assert.equal(emptyChapterWords(true, false), `It plays no clip. ${LEFT_OUT}`)
  for (const wholly of [true, false]) {
    assert.doesNotMatch(emptyChapterWords(true, wholly), /Drag|Move marked/)
  }
})

test('an ignored clip listed apart still makes the chapter "play no clip"', () => {
  assert.equal(holdsNothing(0, 0, 0), true)
  assert.equal(holdsNothing(0, 0, 1), false)
  assert.equal(holdsNothing(0, 1, 0), false)
  assert.equal(holdsNothing(1, 0, 0), false)
})
