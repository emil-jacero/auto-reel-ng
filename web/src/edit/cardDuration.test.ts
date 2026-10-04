import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  changedCards,
  deleteChapter,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  setCardLength,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

/* A title card's length from the Timeline (`title-card-duration-drag`): one edit of the card's duration. */

const A = 'a.mp4'
const B = 'b.mp4'

function setup(): { baseline: Baseline; draft: Draft } {
  const chapters = [
    { key: 'r0', name: '', movable: [A], ignored: [] },
    { key: 'r1', name: 'Dag 2', movable: [B], ignored: [] },
  ]
  const document = {
    metadata: {},
    look: {},
    chapters: [
      { name: '', clips: [A] },
      { name: 'Dag 2', clips: [B], card: { title: 'Dag två', duration: 3 } },
    ],
    clips: {},
    ignore: [],
  } as unknown as ReelDocument
  const baseline: Baseline = {
    read: document,
    chapters: draftChapters(chapters),
    original: ordersOf(chapters),
    cuts: readCuts(document),
  }
  const draft: Draft = {
    chapters: baseline.chapters,
    orders: baseline.original,
    removed: new Map(),
    metadata: { title: '', date: '', location: '', description: '' },
    cuts: new Map(),
    rotations: new Map(),
    cards: new Map(),
  }
  return { baseline, draft }
}

describe('setCardLength', () => {
  it('is one edit: the draft is dirty and counts one card', () => {
    const { baseline, draft } = setup()
    assert.equal(isDirty(baseline, draft), false)
    const next = setCardLength(baseline, draft, 'r0', 6, 4)
    assert.equal(isDirty(baseline, next), true)
    assert.deepEqual([...changedCards(baseline, next)], ['r0'])
    assert.equal(next.cards.get('r0')?.duration, 6)
  })

  it('a length equal to the resolved one is no override, and setting it back removes the edit', () => {
    const { baseline, draft } = setup()
    assert.equal(setCardLength(baseline, draft, 'r0', 4, 4), draft)
    const away = setCardLength(baseline, draft, 'r0', 6, 4)
    const back = setCardLength(baseline, away, 'r0', 4, 4)
    assert.equal(isDirty(baseline, back), false)
    assert.equal(back.cards.size, 0)
  })

  it('a card that reads its own duration goes back to it', () => {
    const { baseline, draft } = setup()
    const away = setCardLength(baseline, draft, 'r1', 5, 3)
    assert.equal(away.cards.get('r1')?.duration, 5)
    assert.equal(setCardLength(baseline, away, 'r1', 3, 3).cards.size, 0)
  })

  it('keeps one decimal exactly', () => {
    const { baseline, draft } = setup()
    assert.equal(setCardLength(baseline, draft, 'r0', 0.1 + 0.2 + 5.7, 4).cards.get('r0')?.duration, 6)
    assert.equal(setCardLength(baseline, draft, 'r0', 4.3000000001, 4).cards.get('r0')?.duration, 4.3)
  })

  it('refuses a length that is not a number above zero, by name', () => {
    const { baseline, draft } = setup()
    assert.throws(() => setCardLength(baseline, draft, 'r0', Number.NaN, 4), /card duration/)
    assert.throws(() => setCardLength(baseline, draft, 'r0', 0, 4), RangeError)
  })

  it('does nothing for a chapter that is unknown or deleted', () => {
    const { baseline, draft } = setup()
    assert.equal(setCardLength(baseline, draft, 'zz', 6, 4), draft)
    const gone = deleteChapter(draft, 'r1')
    assert.equal(setCardLength(baseline, gone, 'r1', 6, 4), gone)
  })

  it('is written with the card’s other overrides and the new duration', () => {
    const { baseline, draft } = setup()
    const body = buildWriteBody(baseline, setCardLength(baseline, draft, 'r1', 6.5, 3))
    assert.deepEqual(body.chapters[1], {
      name: 'Dag 2',
      clips: [B],
      card: { title: 'Dag två', duration: 6.5 },
    })
  })
})
