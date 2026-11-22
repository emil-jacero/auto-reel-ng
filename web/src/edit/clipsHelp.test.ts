import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { OWN_CHAPTER_NOTE } from './chapterNames.ts'
import {
  IGNORED_NOTE,
  MENU_NOTE,
  MISSING_NOTE,
  MOVE_NOTE,
  NEW_CLIP_NOTE,
  SELECT_NOTE,
  clipsHelpLines,
  newClipsLine,
} from './clipsHelp.ts'

describe('the Clips help', () => {
  const plain = { several: false, hasIgnored: false, hasMissing: false, ownChapter: true }
  const always = [SELECT_NOTE, MENU_NOTE, MOVE_NOTE]

  it('says how to select, open the menu and move, in the words of the plain list', () => {
    assert.deepEqual(clipsHelpLines(plain), always)
    assert.equal(SELECT_NOTE, 'Press a clip to select it; Ctrl or Cmd adds one, Shift selects a range.')
    assert.equal(MENU_NOTE, 'Right-click a clip, or press Shift+F10, for its menu.')
    assert.equal(
      MOVE_NOTE,
      'Move clips on the Timeline, or with Move earlier, Move later and Move to… in the Clip tab.',
    )
  })

  it('names no handle, mark or arrow: the bin has none', () => {
    for (const line of [...always, IGNORED_NOTE]) {
      assert.doesNotMatch(line, /handle|mark|arrows|Move up|Move down/i)
    }
  })

  it('adds the ignored and missing notes only when they apply', () => {
    const lines = clipsHelpLines({ ...plain, hasIgnored: true, hasMissing: true })
    assert.deepEqual(lines, [...always, IGNORED_NOTE, MISSING_NOTE])
    assert.equal(IGNORED_NOTE, 'Ignored clips are not played; drag one onto the Timeline to include it.')
  })

  it('says the own chapter once, only while other chapters are listed', () => {
    assert.ok(clipsHelpLines({ ...plain, several: true }).includes(OWN_CHAPTER_NOTE))
    assert.ok(!clipsHelpLines(plain).includes(OWN_CHAPTER_NOTE))
    assert.ok(!clipsHelpLines({ ...plain, several: true, ownChapter: false }).includes(OWN_CHAPTER_NOTE))
  })
})

describe('the Clips help for a new clip', () => {
  it('adds the joins-reel.yaml sentence only while a new clip waits', () => {
    const plain = { several: false, hasIgnored: false, hasMissing: false, ownChapter: true }
    assert.ok(!clipsHelpLines(plain).includes(NEW_CLIP_NOTE))
    assert.deepEqual(clipsHelpLines({ ...plain, hasNewClip: true }), [
      SELECT_NOTE,
      MENU_NOTE,
      MOVE_NOTE,
      NEW_CLIP_NOTE,
    ])
    assert.deepEqual(
      clipsHelpLines({ several: true, hasIgnored: true, hasMissing: true, ownChapter: true, hasNewClip: true }),
      [SELECT_NOTE, MENU_NOTE, MOVE_NOTE, IGNORED_NOTE, MISSING_NOTE, OWN_CHAPTER_NOTE, NEW_CLIP_NOTE],
    )
    assert.equal(NEW_CLIP_NOTE, newClipsLine(0, true, ''))
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
