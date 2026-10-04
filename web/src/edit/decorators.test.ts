import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { applyDecorators, readDecorators, setTitleCards, titleCardsNow } from './decorators.ts'

describe('readDecorators', () => {
  it('tells a list, an absent key and a non-list apart', () => {
    assert.deepEqual(readDecorators({ decorators: ['title'] }), { kind: 'list', names: ['title'] })
    assert.deepEqual(readDecorators({}), { kind: 'absent' })
    assert.deepEqual(readDecorators(null), { kind: 'absent' })
    assert.deepEqual(readDecorators({ decorators: null }), { kind: 'absent' })
    assert.deepEqual(readDecorators({ decorators: 'title' }), { kind: 'invalid' })
  })
})

describe('setTitleCards', () => {
  it('Off keeps the other names and their order', () => {
    assert.deepEqual(setTitleCards({ decorators: ['chapter', 'title'] }, true, false), ['chapter'])
    assert.deepEqual(setTitleCards({ decorators: ['a', 'title', 'b'] }, true, false), ['a', 'b'])
  })

  it('On puts title first and keeps the others', () => {
    assert.deepEqual(setTitleCards({ decorators: [] }, false, true), ['title'])
    assert.deepEqual(setTitleCards({ decorators: ['chapter'] }, false, true), ['title', 'chapter'])
  })

  it('an event without a list: Off writes the empty list, and Off then On is no override', () => {
    assert.deepEqual(setTitleCards({}, true, false), [])
    assert.equal(setTitleCards({}, true, true), undefined)
  })

  it('a project opt-out the event does not list: On writes the event own list', () => {
    assert.deepEqual(setTitleCards({}, false, true), ['title'])
    assert.equal(setTitleCards({}, false, false), undefined)
  })

  it('the state read is no override', () => {
    assert.equal(setTitleCards({ decorators: ['title'] }, true, true), undefined)
    assert.equal(setTitleCards({ decorators: [] }, false, false), undefined)
  })

  it('a non-string item survives', () => {
    assert.deepEqual(setTitleCards({ decorators: [7, 'title', null] }, true, false), [7, null])
  })

  it('a list that is not a list is refused', () => {
    assert.throws(() => setTitleCards({ decorators: 'title' }, true, false), /not a list/)
  })
})

describe('applyDecorators and titleCardsNow', () => {
  it('no override returns the look itself', () => {
    const look = { decorators: ['title'], title_card: { duration: 3 } }
    assert.equal(applyDecorators(look, undefined), look)
  })

  it('changes decorators alone', () => {
    const look = { fade_in: 1, decorators: ['chapter', 'title'], title_card: { duration: 3 } }
    assert.deepEqual(applyDecorators(look, ['chapter']), {
      fade_in: 1,
      decorators: ['chapter'],
      title_card: { duration: 3 },
    })
  })

  it('the position is the draft list, else the detail', () => {
    assert.equal(titleCardsNow(undefined, true), true)
    assert.equal(titleCardsNow([], true), false)
    assert.equal(titleCardsNow(['title'], false), true)
  })
})
