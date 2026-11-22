import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  CHOOSE_CHAPTER_WORDS,
  GROUP_DROP_WORDS,
  MOVING_WORDS,
  NOTHING_IGNORED,
  NOTHING_MOVED,
  SAVING_WORDS,
  movedWords,
} from './moveWords.ts'

describe('the words of a move', () => {
  it('say Move to…: the count, the chapter, the singular and the no-op', () => {
    assert.equal(movedWords(3, 'Dag 2'), '3 clips moved to “Dag 2”.')
    assert.equal(movedWords(1, 'Test'), '1 clip moved to “Test”.')
    assert.equal(NOTHING_MOVED, 'Nothing moved.')
    assert.equal(NOTHING_IGNORED, 'Nothing ignored.')
  })

  it('give the reasons a move control is unavailable', () => {
    assert.equal(SAVING_WORDS, 'Unavailable while saving.')
    assert.equal(CHOOSE_CHAPTER_WORDS, 'Choose a chapter.')
    assert.equal(MOVING_WORDS, 'Unavailable while the clips move.')
  })

  it('say that a group is not dropped on the track, and where Include clips is', () => {
    assert.ok(GROUP_DROP_WORDS.includes('cannot be dropped on the video track'))
    assert.ok(GROUP_DROP_WORDS.includes('Nothing moved.'))
    assert.ok(GROUP_DROP_WORDS.includes('Include clips in the Clip tab'))
  })
})
