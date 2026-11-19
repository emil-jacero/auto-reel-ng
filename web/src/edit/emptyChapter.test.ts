import assert from 'node:assert/strict'
import { test } from 'node:test'

import { chapterRowHint, emptyChapterWords, holdsNothing } from './emptyChapter.ts'

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

test('a row says nothing while its chapter plays a clip', () => {
  assert.equal(chapterRowHint(1, 0, 0, false), null)
  assert.equal(chapterRowHint(3, 2, 1, true), null)
})

test('a row of a chapter that plays none says it, as the words do', () => {
  assert.equal(chapterRowHint(0, 0, 0, false), emptyChapterWords(false, true))
  assert.equal(chapterRowHint(0, 1, 0, false), emptyChapterWords(false, false))
  assert.equal(chapterRowHint(0, 0, 2, true), emptyChapterWords(true, false))
  assert.match(chapterRowHint(0, 0, 0, true) ?? '', /left out of the movie/)
  assert.doesNotMatch(chapterRowHint(0, 0, 0, true) ?? '', /Move to/)
  assert.match(chapterRowHint(0, 0, 0, false) ?? '', /Move to…/)
})
