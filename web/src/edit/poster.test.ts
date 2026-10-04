import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { EventDetail } from '../api/event.ts'
import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  resetPoster,
  setPoster,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'
import {
  CHOSEN_WORDS,
  DEFAULT_WORDS,
  UNSAVED_WORDS,
  WHY_HELD,
  WHY_LOCKED,
  WHY_NO_CLIP,
  WHY_NO_FRAME,
  playedInDraft,
  posterFromPlayhead,
  posterNow,
  posterState,
  posterStateWords,
} from './poster.ts'

function setup(poster?: { clip: string; at: number } | null): { baseline: Baseline; draft: Draft } {
  const chapters = [{ key: 'r0', name: '', movable: ['a.mp4', 'b.mp4'], ignored: [] }]
  const read = {
    metadata: { title: 'Bröllop' },
    look: {},
    chapters: [{ name: '', clips: ['a.mp4', 'b.mp4'] }],
    clips: { 'a.mp4': { trims: [{ in: 1, out: 2 }] } },
    ignore: [],
    poster,
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

const detail = (source: 'event' | 'default' | null) =>
  ({ poster: source === null ? null : { clip: 'a.mp4', at: null, source } }) as unknown as EventDetail

describe('the poster draft', () => {
  it('writes nothing while it is as read', () => {
    const { baseline, draft } = setup({ clip: 'b.mp4', at: 2.5 })
    assert.equal('poster' in buildWriteBody(baseline, draft), false)
    assert.equal(isDirty(baseline, draft), false)
  })

  it('writes the chosen frame once it differs, and nothing else about it', () => {
    const { baseline, draft } = setup()
    const next = setPoster(baseline, draft, { clip: 'b.mp4', at: 12.5 })
    assert.deepEqual(buildWriteBody(baseline, next).poster, { clip: 'b.mp4', at: 12.5 })
    assert.equal(isDirty(baseline, next), true)
    // Nothing else of the body moved.
    const { poster: _poster, ...rest } = buildWriteBody(baseline, next)
    assert.deepEqual(rest, buildWriteBody(baseline, draft))
  })

  it('writes null to remove a saved poster', () => {
    const { baseline, draft } = setup({ clip: 'b.mp4', at: 2.5 })
    const next = setPoster(baseline, draft, null)
    assert.equal(buildWriteBody(baseline, next).poster, null)
    assert.equal(isDirty(baseline, next), true)
  })

  it('has no default to remove when none is saved: using the default is no change', () => {
    const { baseline, draft } = setup()
    assert.equal(setPoster(baseline, draft, null), draft)
  })

  it('drops an entry put back to the read frame, and Undo/Reset restore the saved one', () => {
    const { baseline, draft } = setup({ clip: 'b.mp4', at: 2.5 })
    const moved = setPoster(baseline, draft, { clip: 'a.mp4', at: 0.1 })
    assert.deepEqual(posterNow(baseline.read, moved.poster), { clip: 'a.mp4', at: 0.1 })
    assert.equal(setPoster(baseline, moved, { clip: 'b.mp4', at: 2.5 }).poster, undefined)
    const reset = resetPoster(moved)
    assert.equal(isDirty(baseline, reset), false)
    assert.deepEqual(posterNow(baseline.read, reset.poster), { clip: 'b.mp4', at: 2.5 })
  })

  it('choosing the same frame twice is one edit', () => {
    const { baseline, draft } = setup()
    const once = setPoster(baseline, draft, { clip: 'a.mp4', at: 1 })
    assert.equal(setPoster(baseline, once, { clip: 'a.mp4', at: 1 }), once)
  })
})

describe('the poster area words', () => {
  it('says Default, Chosen frame and Chosen frame, not saved', () => {
    const none = setup()
    assert.equal(posterStateWords(posterState(none.baseline.read, none.draft.poster, detail('default'))), DEFAULT_WORDS)
    const saved = setup({ clip: 'b.mp4', at: 2.5 })
    assert.equal(posterStateWords(posterState(saved.baseline.read, saved.draft.poster, detail('event'))), CHOSEN_WORDS)
    const edited = setPoster(saved.baseline, saved.draft, { clip: 'a.mp4', at: 1 })
    assert.equal(posterStateWords(posterState(saved.baseline.read, edited.poster, detail('event'))), UNSAVED_WORDS)
    const removed = setPoster(saved.baseline, saved.draft, null)
    assert.equal(posterStateWords(posterState(saved.baseline.read, removed.poster, detail('event'))), DEFAULT_WORDS)
  })

  it('calls a saved poster whose clip does not play the default', () => {
    const saved = setup({ clip: 'gone.mp4', at: 2.5 })
    assert.equal(posterState(saved.baseline.read, saved.draft.poster, detail('default')), 'default')
  })

  it('knows when the draft no longer plays the chosen clip', () => {
    const { draft } = setup()
    assert.equal(playedInDraft({ clip: 'b.mp4', at: 1 }, draft.orders), true)
    assert.equal(playedInDraft({ clip: 'x.mp4', at: 1 }, draft.orders), false)
    assert.equal(playedInDraft({ clip: 'b.mp4', at: 1 }, new Map([['r0', ['a.mp4']]])), false)
  })
})

describe('the poster from the playhead', () => {
  const clips = [
    { identity: 'a.mp4', facts: { durationMs: 4000 } },
    { identity: 'k/b.mp4', facts: { durationMs: 9000 } },
  ]
  const ready = { locked: false, held: false, frame: true }

  it('takes the clip and its own time to the millisecond', () => {
    assert.deepEqual(posterFromPlayhead(clips, { clip: 1, ms: 12500 }, ready), {
      pick: { clip: 'k/b.mp4', at: 12.5 },
    })
    assert.deepEqual(posterFromPlayhead(clips, { clip: 0, ms: 1234 }, ready), {
      pick: { clip: 'a.mp4', at: 1.234 },
    })
  })

  it('allows a time inside a cut: the time is before cuts', () => {
    // a.mp4 is cut 1 s to 2 s in the document; the playhead at 1.5 s still gives that time.
    assert.deepEqual(posterFromPlayhead(clips, { clip: 0, ms: 1500 }, ready), {
      pick: { clip: 'a.mp4', at: 1.5 },
    })
  })

  it('gives a reason in words, not a pick, when it cannot act', () => {
    assert.deepEqual(posterFromPlayhead(clips, { clip: 5, ms: 0 }, ready), { why: WHY_NO_CLIP })
    assert.deepEqual(posterFromPlayhead([], { clip: 0, ms: 0 }, ready), { why: WHY_NO_CLIP })
    assert.deepEqual(posterFromPlayhead(clips, { clip: 0, ms: 0 }, { ...ready, locked: true }), { why: WHY_LOCKED })
    assert.deepEqual(posterFromPlayhead(clips, { clip: 0, ms: 0 }, { ...ready, held: true }), { why: WHY_HELD })
    assert.deepEqual(posterFromPlayhead(clips, { clip: 0, ms: 0 }, { ...ready, frame: false }), { why: WHY_NO_FRAME })
  })
})
