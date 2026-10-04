import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  decoratorsChanged,
  resetDecorators,
  setStyleField,
  setTitleCardsOn,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

/* One chapter, a look with fade_in beside the style, metadata, a clip and an ignored one. */
function setup(look: Record<string, unknown>): { baseline: Baseline; draft: Draft } {
  const chapters = [{ key: 'r0', name: '', movable: ['a.mp4'], ignored: [] }]
  const read = {
    metadata: { title: 'Bröllop' },
    look,
    chapters: [{ name: '', clips: ['a.mp4'], card: { subtitle: 'Hej' } }],
    clips: { 'a.mp4': { trims: [{ in: 1, out: 2 }] } },
    ignore: ['x.mp4'],
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
    metadata: { title: 'Bröllop', date: '', location: '', description: '' },
    cuts: new Map(),
    rotations: new Map(),
    cards: new Map(),
  }
  return { baseline, draft }
}

describe('the Title cards switch in the draft', () => {
  it('writes look as read for an untouched draft, the same object', () => {
    const { baseline, draft } = setup({ decorators: ['title'], other: 1 })
    assert.equal(buildWriteBody(baseline, draft).look, baseline.read.look)
    assert.equal(isDirty(baseline, draft), false)
    assert.equal(decoratorsChanged(draft), false)
  })

  it('changes look.decorators alone, the rest of the document as read', () => {
    const { baseline, draft } = setup({ decorators: ['chapter', 'title'], title_card: { fade_in: 0.5 } })
    const off = setTitleCardsOn(baseline, draft, true, false)
    assert.equal(isDirty(baseline, off), true)
    assert.equal(decoratorsChanged(off), true)
    const body = buildWriteBody(baseline, off)
    assert.deepEqual(body.look, { decorators: ['chapter'], title_card: { fade_in: 0.5 } })
    assert.equal(body.chapters, baseline.read.chapters)
    assert.deepEqual(body.clips, baseline.read.clips)
    assert.deepEqual(body.ignore, baseline.read.ignore)
    assert.equal(body.metadata.title, 'Bröllop')
  })

  it('an event with no list: Off writes the empty list', () => {
    const { baseline, draft } = setup({})
    const off = setTitleCardsOn(baseline, draft, true, false)
    assert.deepEqual(buildWriteBody(baseline, off).look, { decorators: [] })
  })

  it('toggled twice is no change', () => {
    const { baseline, draft } = setup({ other: 1 })
    const off = setTitleCardsOn(baseline, draft, true, false)
    const back = setTitleCardsOn(baseline, off, true, true)
    assert.equal(back.decorators, undefined)
    assert.equal(isDirty(baseline, back), false)
    assert.equal(buildWriteBody(baseline, back).look, baseline.read.look)
  })

  it('composes with a style edit and resets to as read', () => {
    const { baseline, draft } = setup({ decorators: [] })
    const both = setStyleField(baseline, setTitleCardsOn(baseline, draft, false, true), 'position', 'top')
    assert.deepEqual(buildWriteBody(baseline, both).look, {
      decorators: ['title'],
      title_card: { position: 'top' },
    })
    const reset = resetDecorators(both)
    assert.deepEqual(buildWriteBody(baseline, reset).look, { decorators: [], title_card: { position: 'top' } })
    assert.equal(resetDecorators(draft), draft)
  })
})
