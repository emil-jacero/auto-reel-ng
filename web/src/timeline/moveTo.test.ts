import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { chosenOf, groupBusy, groupHeading, groupNames, moveChoices, moveWhy } from './moveTo.ts'

const chapters = [
  { key: 'c0', name: 'Main' },
  { key: 'c1', name: 'Kvällen' },
  { key: 'c2', name: 'Test' },
]

describe('moveChoices', () => {
  it('leaves the clip\'s own chapter out for one clip', () => {
    assert.deepEqual(
      moveChoices(chapters, 'c1').map((c) => c.name),
      ['Main', 'Test'],
    )
  })
  it('lists every chapter for several clips', () => {
    assert.equal(moveChoices(chapters, null).length, 3)
  })
  it('offers nothing for one clip in an event of one chapter', () => {
    assert.deepEqual(moveChoices([chapters[0]], 'c0'), [])
  })
  it('falls back to the key without a name', () => {
    assert.deepEqual(moveChoices([{ key: 'c0' }], null), [{ key: 'c0', name: 'c0' }])
  })
})

describe('chosenOf', () => {
  const choices = moveChoices(chapters, 'c1')
  it('keeps a chapter still listed', () => {
    assert.equal(chosenOf(choices, 'c2'), 'c2')
  })
  it('drops a chapter the clip moved into', () => {
    assert.equal(chosenOf(choices, 'c1'), '')
    assert.equal(chosenOf(choices, ''), '')
  })
})

describe('moveWhy', () => {
  it('says why, a save first', () => {
    assert.equal(moveWhy(false, false), 'Choose a chapter.')
    assert.equal(moveWhy(true, true), 'Unavailable while saving.')
    assert.equal(moveWhy(false, true), groupBusy(false))
  })
  it('says the clips move, not a save, while only Move to… is pending', () => {
    assert.equal(moveWhy(true, true, true), 'Unavailable while the clips move.')
    assert.equal(groupBusy(true), 'Unavailable while the clips move.')
    assert.equal(moveWhy(false, false, true), 'Choose a chapter.')
  })
  it('is null when Move can act', () => {
    assert.equal(moveWhy(true, false), null)
  })
})

describe('group words', () => {
  it('counts', () => {
    assert.equal(groupHeading(3), '3 clips selected')
  })
  it('names up to five, then how many more', () => {
    assert.deepEqual(groupNames(['a', 'b']), { shown: ['a', 'b'], more: null })
    assert.deepEqual(groupNames(['a', 'b', 'c', 'd', 'e']), { shown: ['a', 'b', 'c', 'd', 'e'], more: null })
    assert.deepEqual(groupNames(['a', 'b', 'c', 'd', 'e', 'f', 'g']), {
      shown: ['a', 'b', 'c', 'd', 'e'],
      more: 'and 2 more',
    })
  })
})
