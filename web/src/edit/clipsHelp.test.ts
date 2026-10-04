import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { OWN_CHAPTER_NOTE } from './chapterNames.ts'
import { IGNORED_NOTE, MISSING_NOTE, REORDER_ONE, REORDER_SEVERAL, clipsHelpLines, newClipsLine } from './clipsHelp.ts'
import { MARK_HINT } from './marks.ts'

describe('the Clips help', () => {
  const plain = { several: false, hasIgnored: false, hasMissing: false, ownChapter: true }

  it('holds the reorder words of one chapter and of several, then the marking words', () => {
    assert.deepEqual(clipsHelpLines(plain), [REORDER_ONE, MARK_HINT])
    assert.deepEqual(clipsHelpLines({ ...plain, several: true, ownChapter: false }), [REORDER_SEVERAL, MARK_HINT])
  })

  it('keeps the old words: the instructions begin as they did', () => {
    assert.match(REORDER_SEVERAL, /^Drag a clip by its handle, or use its arrows, to reorder it\./)
    assert.match(REORDER_ONE, /^Drag a clip by its handle, or use its arrows\./)
    assert.match(MARK_HINT, /^Mark clips with the box at the top right/)
  })

  it('adds the ignored and missing notes only when they apply', () => {
    const lines = clipsHelpLines({ ...plain, hasIgnored: true, hasMissing: true })
    assert.deepEqual(lines, [REORDER_ONE, IGNORED_NOTE, MISSING_NOTE, MARK_HINT])
  })

  it('says the own chapter once, only while other chapters are listed', () => {
    assert.ok(clipsHelpLines({ ...plain, several: true }).includes(OWN_CHAPTER_NOTE))
    assert.ok(!clipsHelpLines(plain).includes(OWN_CHAPTER_NOTE))
    assert.ok(!clipsHelpLines({ ...plain, several: true, ownChapter: false }).includes(OWN_CHAPTER_NOTE))
  })
})

describe('the new clips line', () => {
  it('says what saving adds while a clip is new, and nothing otherwise', () => {
    assert.equal(newClipsLine(2, true, '2 new clips'), 'Saving adds 2 new clips to reel.yaml.')
    assert.equal(
      newClipsLine(0, true, ''),
      'A new clip joins reel.yaml once its chapter’s order, one of its cuts, or the list of chapters is saved.',
    )
    assert.equal(newClipsLine(0, false, ''), null)
  })
})
