import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  CLEARED_WORDS,
  GROUP_INSTRUCTIONS,
  NO_MARKS,
  afterMove,
  clearMarks,
  countWords,
  groupWords,
  markWords,
  MOVE_REASON_WORDS,
  NOTHING_MOVED,
  movedWords,
  moveReason,
  pruneMarks,
  toggleMark,
} from './marks.ts'

const ONE = 's1710001.mp4'
const TWO = 'Kvällen/s1710002.mp4'
const THREE = 'Kvällen/s1710003.mp4'

describe('toggleMark', () => {
  it('marks and unmarks, symmetrically', () => {
    const on = toggleMark(NO_MARKS, TWO, true)
    assert.deepEqual([...on], [TWO])
    assert.equal(toggleMark(on, TWO, false).size, 0)
    assert.equal(NO_MARKS.size, 0, 'the shared empty set is never written to')
  })

  it('returns the same set object when nothing changes', () => {
    const on = toggleMark(NO_MARKS, TWO, true)
    assert.equal(toggleMark(on, TWO, true), on)
    assert.equal(toggleMark(NO_MARKS, TWO, false), NO_MARKS)
  })

  it('does not change the set it was given', () => {
    const on = toggleMark(NO_MARKS, TWO, true)
    const both = toggleMark(on, THREE, true)
    assert.deepEqual([...on], [TWO])
    assert.deepEqual([...both].sort(), [TWO, THREE].sort())
    assert.equal(toggleMark(on, TWO, false), NO_MARKS, 'the last unmark gives the shared empty set')
  })
})

describe('clearMarks', () => {
  it('empties the marks and keeps an empty set as it is', () => {
    assert.equal(clearMarks(new Set([ONE, TWO])), NO_MARKS)
    const empty = new Set<string>()
    assert.equal(clearMarks(empty), empty)
  })
})

describe('pruneMarks', () => {
  it('drops a missing, an ignored and an absent identity', () => {
    const marked = new Set([ONE, TWO, 'borttagen.mp4', 's1710004.mp4', 'gone.mp4'])
    // The clips a listed chapter plays that are on disk: not the missing, not the ignored.
    const playedOnDisk = new Set([ONE, TWO, THREE])
    assert.deepEqual([...pruneMarks(marked, playedOnDisk)], [ONE, TWO])
  })

  it('returns the same set when it drops nothing, and the empty set when nothing is left', () => {
    const marked = new Set([ONE])
    assert.equal(pruneMarks(marked, new Set([ONE, TWO])), marked)
    assert.equal(pruneMarks(marked, new Set([TWO])), NO_MARKS)
  })
})

describe('afterMove', () => {
  it('unmarks the clips a move took and leaves the others', () => {
    const marked = new Set([ONE, TWO, THREE])
    assert.deepEqual([...afterMove(marked, [TWO, THREE])], [ONE])
  })

  it('returns the same set when the move took none of the marked clips', () => {
    const marked = new Set([ONE])
    assert.equal(afterMove(marked, [TWO]), marked)
    assert.equal(afterMove(marked, []), marked)
    assert.equal(afterMove(marked, [ONE]), NO_MARKS)
  })
})

describe('the words', () => {
  it('say a mark and the count, singular and plural', () => {
    assert.equal(markWords('s1710003.mp4', true, 2), 's1710003.mp4 marked. 2 clips marked.')
    assert.equal(markWords('s1710002.mp4', false, 0), 's1710002.mp4 unmarked. No clips marked.')
    assert.equal(markWords('s1710002.mp4', true, 1), 's1710002.mp4 marked. 1 clip marked.')
    assert.equal(CLEARED_WORDS, 'Marks cleared.')
    assert.equal(countWords(1), '1 clip marked')
    assert.equal(countWords(3), '3 clips marked')
  })

  it('say a group drag, to a chapter and within the own chapter', () => {
    assert.equal(groupWords.lift(2), 'Picked up 2 marked clips.')
    assert.equal(
      groupWords.over(2, 'Main', 1, 3),
      '2 marked clips are over “Main”, starting at position 1 of 3.',
    )
    assert.equal(
      groupWords.drop(2, 'Main', 1, 3),
      '2 clips moved to “Main”, starting at position 1 of 3.',
    )
    assert.equal(groupWords.unchanged(2), '2 marked clips dropped, unchanged.')
    assert.equal(
      groupWords.cancel(2),
      'Move cancelled. 2 marked clips are back where they were.',
    )
    assert.equal(
      groupWords.badge(2, 'Main', 1, 3),
      '2 clips to “Main”, starting at position 1 of 3',
    )
  })

  it('leave the chapter’s name out within the group’s only chapter', () => {
    assert.equal(groupWords.drop(2, null, 2, 4), '2 clips moved, starting at position 2 of 4.')
    assert.equal(groupWords.badge(2, null, 2, 4), '2 clips, starting at position 2 of 4')
    assert.match(groupWords.over(2, null, 2, 4), /starting at position 2 of 4\.$/)
    assert.doesNotMatch(groupWords.over(2, null, 2, 4), /“/)
  })

  it('say Move marked to…: the count, the chapter, the singular and the no-op', () => {
    assert.equal(movedWords(3, 'Dag 2'), '3 clips moved to “Dag 2”.')
    assert.equal(movedWords(1, 'Test'), '1 clip moved to “Test”.')
    assert.equal(NOTHING_MOVED, 'Nothing moved.')
  })

  it('give Move’s reason: marks first, then the chapter, none when it can act', () => {
    assert.equal(moveReason(0, false), 'no-marks')
    assert.equal(moveReason(0, true), 'no-marks')
    assert.equal(moveReason(2, false), 'no-chapter')
    assert.equal(moveReason(2, true), null)
    assert.equal(MOVE_REASON_WORDS['no-marks'], 'Mark clips to move them.')
    assert.equal(MOVE_REASON_WORDS['no-chapter'], 'Choose a chapter to move them to.')
  })

  it('add one sentence to the keyboard instructions', () => {
    assert.match(GROUP_INSTRUCTIONS, /^ A marked clip moves with all the marked clips/)
  })
})
