import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { CardSpec } from '../timeline/cards.ts'
import { ADDED_WORDS, NO_SUBTITLE, cardRowInfo } from './cardRows.ts'

const specs: CardSpec[] = [
  {
    chapter: '',
    card: { duration: 3, background: 'black', title: 'Sommaren', subtitle: '', fontFamily: 'Sofia Sans' },
    error: null,
  },
  {
    chapter: 'Dag 2',
    card: { duration: 4, background: 'video', title: 'Dag två', subtitle: 'Stranden', fontFamily: 'Sofia Sans' },
    error: null,
  },
  { chapter: 'Dag 3', card: null, error: 'card.font_family' },
]

describe('cardRowInfo', () => {
  it('words a row from the chapter’s saved card', () => {
    assert.deepEqual(cardRowInfo({ readName: 'Dag 2', name: 'Dag 2' }, specs), {
      kind: 'card',
      chapter: 'Dag 2',
      title: 'Dag två',
      subtitle: 'Stranden',
      length: '4.0 s',
      look: 'Video',
      font: 'Sofia Sans',
      words: 'Title card for Dag 2, 4.0 s, over video',
      overrides: 'Uses the event style',
      savedName: null,
    })
  })

  it('says what the draft card overrides', () => {
    const row = cardRowInfo({ readName: 'Dag 2', name: 'Dag 2' }, specs, 'Overrides font, color')
    assert.ok(row?.kind === 'card')
    assert.equal(row.overrides, 'Overrides font, color')
  })

  it('makes Main’s row the opening card, with "No subtitle" for an empty one', () => {
    const row = cardRowInfo({ readName: '', name: '' }, specs)
    assert.ok(row?.kind === 'card')
    assert.equal(row.words, 'Title card for the opening, 3.0 s, on black')
    assert.equal(row.subtitle, NO_SUBTITLE)
    assert.equal(row.title, 'Sommaren')
  })

  it('says the saved name of a renamed chapter and keeps its saved card', () => {
    const row = cardRowInfo({ readName: 'Dag 2', name: 'Dag två' }, specs)
    assert.ok(row?.kind === 'card')
    assert.equal(row.savedName, 'Dag 2')
    assert.equal(row.words, 'Title card for Dag 2, 4.0 s, over video')
  })

  it('has no card yet for an added chapter', () => {
    assert.deepEqual(cardRowInfo({ readName: null, name: 'Dag 9' }, specs), { kind: 'added' })
    assert.match(ADDED_WORDS, /after Save/)
  })

  it('shows no values for a card that could not be resolved', () => {
    assert.deepEqual(cardRowInfo({ readName: 'Dag 3', name: 'Dag 3' }, specs), {
      kind: 'unresolved',
      chapter: 'Dag 3',
      error: 'card.font_family',
      savedName: null,
    })
    const bad: CardSpec[] = [
      { chapter: 'X', card: { duration: 0, background: 'black', title: '', subtitle: '', fontFamily: 'F' }, error: null },
    ]
    assert.equal(cardRowInfo({ readName: 'X', name: 'X' }, bad)?.kind, 'unresolved')
  })

  it('has nothing for a chapter the event does not list', () => {
    assert.equal(cardRowInfo({ readName: 'Gone', name: 'Gone' }, specs), null)
  })
})
