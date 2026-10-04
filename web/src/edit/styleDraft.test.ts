import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  resetStyle,
  setStyleField,
  styleIsChanged,
  styleOf,
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

describe('the card style in the draft', () => {
  it('writes look as read for an untouched draft, the same object', () => {
    const { baseline, draft } = setup({ title_card: { fade_in: 0.5 }, other: 1 })
    assert.equal(buildWriteBody(baseline, draft).look, baseline.read.look)
    assert.equal(isDirty(baseline, draft), false)
  })

  it('changes look.title_card alone, the rest of the document as read', () => {
    const { baseline, draft } = setup({ title_card: { fade_in: 0.5 }, other: 1 })
    const edited = setStyleField(baseline, draft, 'text_color', '#FFFFFF')
    assert.equal(isDirty(baseline, edited), true)
    assert.equal(styleIsChanged(baseline, edited), true)
    const body = buildWriteBody(baseline, edited)
    assert.deepEqual(body.look, { title_card: { fade_in: 0.5, text_color: '#FFFFFF' }, other: 1 })
    assert.deepEqual(body.chapters, baseline.read.chapters)
    assert.deepEqual(body.clips, baseline.read.clips)
    assert.deepEqual(body.ignore, baseline.read.ignore)
    assert.equal(body.metadata.title, 'Bröllop')
  })

  it('leaves nothing to save once an edit is put back', () => {
    const { baseline, draft } = setup({ title_card: { title_font_size: 80 } })
    const edited = setStyleField(baseline, draft, 'title_font_size', '90')
    assert.equal(isDirty(baseline, edited), true)
    const back = setStyleField(baseline, edited, 'title_font_size', '80')
    assert.equal(isDirty(baseline, back), false)
    assert.equal(back.style, undefined)
    assert.equal(buildWriteBody(baseline, back).look, baseline.read.look)
  })

  it('removes title_card when the last field is cleared', () => {
    const { baseline, draft } = setup({ title_card: { font_family: 'A' } })
    const cleared = setStyleField(baseline, draft, 'font_family', null)
    assert.deepEqual(buildWriteBody(baseline, cleared).look, {})
  })

  it('returns the same draft for a no-op edit and resets to as read', () => {
    const { baseline, draft } = setup({})
    assert.equal(setStyleField(baseline, draft, 'position', null), draft)
    const edited = setStyleField(baseline, draft, 'position', 'top')
    assert.equal(styleOf(baseline, edited).position, 'top')
    const reset = resetStyle(edited)
    assert.equal(isDirty(baseline, reset), false)
    assert.equal(resetStyle(draft), draft)
  })

  it('does not touch the chapters when only the style changes', () => {
    const { baseline, draft } = setup({})
    const edited = setStyleField(baseline, draft, 'background', 'video')
    assert.equal(buildWriteBody(baseline, edited).chapters, baseline.read.chapters)
  })
})
