import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  cardOf,
  changedCards,
  deleteChapter,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  renameChapter,
  resetCard,
  restoreChapter,
  setCardField,
  addChapter,
  writtenFromView,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'
import { cardsChangedCount } from './card/model.ts'
import { readCardOf } from './draft.ts'

/* Three chapters: Main (no card), Dag 2 (a card), Tom (empty, deletable). */
function setup(documentChapters = true): { baseline: Baseline; draft: Draft } {
  const chapters = [
    { key: 'r0', name: '', movable: ['a.mp4'], ignored: [] },
    { key: 'r1', name: 'Dag 2', movable: ['b.mp4'], ignored: [] },
    { key: 'r2', name: 'Tom', movable: [], ignored: [] },
  ]
  const read = {
    metadata: {},
    look: {},
    chapters: documentChapters
      ? [
          { name: '', clips: ['a.mp4'] },
          { name: 'Dag 2', clips: ['b.mp4'], card: { position: 'top', subtitle: 'Hej' } },
          { name: 'Tom', clips: [] },
        ]
      : [],
    clips: {},
    ignore: [],
  } as unknown as ReelDocument
  const baseline: Baseline = {
    read,
    chapters: draftChapters(chapters),
    original: ordersOf(chapters),
    cuts: readCuts(read),
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

const names = (body: ReturnType<typeof buildWriteBody>) => body.chapters.map((c) => c.name)

describe('the write body', () => {
  it('an unmodified draft writes the document as read', () => {
    const { baseline, draft } = setup()
    assert.deepEqual(buildWriteBody(baseline, draft).chapters, baseline.read.chapters)
    assert.equal(isDirty(baseline, draft), false)
  })

  it('one changed card of three: only that chapter carries a card, the others as read', () => {
    const { baseline, draft } = setup()
    const next = setCardField(baseline, draft, 'r0', 'subtitle', 'Sub')
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(names(body), ['', 'Dag 2', 'Tom'])
    assert.deepEqual(body.chapters[0], { name: '', clips: ['a.mp4'], card: { subtitle: 'Sub' } })
    // Untouched chapters are the document's own, byte for byte.
    assert.equal(body.chapters[1], baseline.read.chapters[1])
    assert.equal(body.chapters[2], baseline.read.chapters[2])
    assert.equal('card' in body.chapters[2] && body.chapters[2].card != null, false)
    assert.equal(isDirty(baseline, next), true)
  })

  it('clearing every override sends {} (removes the card)', () => {
    const { baseline, draft } = setup()
    let next = setCardField(baseline, draft, 'r1', 'position', null)
    next = setCardField(baseline, next, 'r1', 'subtitle', null)
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.chapters[1], { name: 'Dag 2', clips: ['b.mp4'], card: {} })
  })

  it('a rename carries the card on the new name', () => {
    const { baseline, draft } = setup()
    let next = setCardField(baseline, draft, 'r1', 'font_family', 'DejaVu Sans')
    next = renameChapter(next, 'r1', 'Dag två')
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.chapters[1], {
      name: 'Dag två',
      clips: ['b.mp4'],
      card: { position: 'top', subtitle: 'Hej', font_family: 'DejaVu Sans' },
    })
  })

  it('a rename alone sends no card (the service carries it)', () => {
    const { baseline, draft } = setup()
    const body = buildWriteBody(baseline, renameChapter(draft, 'r1', 'Dag två'))
    assert.equal('card' in body.chapters[1], false)
  })

  it('setting the card back to what was read writes nothing', () => {
    const { baseline, draft } = setup()
    let next = setCardField(baseline, draft, 'r1', 'position', 'bottom')
    next = setCardField(baseline, next, 'r1', 'position', 'top')
    assert.equal(next.cards.size, 0)
    assert.equal(isDirty(baseline, next), false)
    assert.deepEqual(buildWriteBody(baseline, next).chapters, baseline.read.chapters)
  })

  it('a deleted chapter drops its card edit, and Undo brings it back', () => {
    const { baseline, draft } = setup()
    const edited = setCardField(baseline, draft, 'r2', 'title', 'Slut')
    const gone = deleteChapter(edited, 'r2')
    assert.equal(changedCards(baseline, gone).size, 0)
    assert.deepEqual(names(buildWriteBody(baseline, gone)), ['', 'Dag 2'])
    const back = restoreChapter(gone, 'r2')
    assert.equal(changedCards(baseline, back).size, 1)
  })

  it('a chapter added this session has no card to edit', () => {
    const { baseline, draft } = setup()
    const added = addChapter(draft, 'a1', 'Ny')
    assert.equal(setCardField(baseline, added, 'a1', 'title', 'x'), added)
  })

  it('a changed card of a chapter the document does not list is written from the view', () => {
    const { baseline, draft } = setup(false)
    const next = setCardField(baseline, draft, 'r1', 'title', 'Dag!')
    assert.equal(isDirty(baseline, next), true)
    assert.deepEqual(
      writtenFromView(baseline, next).map((c) => c.key),
      ['r0', 'r1', 'r2'],
    )
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.chapters[1], { name: 'Dag 2', clips: ['b.mp4'], card: { title: 'Dag!' } })
    assert.equal('card' in body.chapters[0], false)
  })
})

describe('the draft slice', () => {
  it('cardOf is the read card until touched; reset restores it', () => {
    const { baseline, draft } = setup()
    assert.equal(cardOf(baseline, draft, 'r1').position, 'top')
    const next = setCardField(baseline, draft, 'r1', 'position', 'center')
    assert.equal(cardOf(baseline, next, 'r1').position, 'center')
    const reset = resetCard(next, 'r1')
    assert.equal(cardOf(baseline, reset, 'r1').position, 'top')
    assert.equal(isDirty(baseline, reset), false)
    assert.equal(resetCard(reset, 'r1'), reset)
  })

  it('the count over the kept chapters', () => {
    const { baseline, draft } = setup()
    let next = setCardField(baseline, draft, 'r0', 'subtitle', 'A')
    next = setCardField(baseline, next, 'r1', 'font_family', 'F')
    assert.equal(cardsChangedCount(['r0', 'r1', 'r2'], next.cards, (k) => readCardOf(baseline, k)), 2)
  })

  it('setting an unchanged value returns the same draft', () => {
    const { baseline, draft } = setup()
    assert.equal(setCardField(baseline, draft, 'r1', 'position', 'top'), draft)
  })
})
