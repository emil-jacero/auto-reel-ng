import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import { checkRestore } from '../cuts/times.ts'
import {
  addCut,
  buildWriteBody,
  changedCuts,
  chapterChanges,
  cutChanges,
  cutsOf,
  draftChapters,
  isDirty,
  layoutChanged,
  moveClip,
  ordersOf,
  readCuts,
  removeCut,
  restoreCut,
  trimCut,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'
import { addChapter, deleteChapter, renameChapter } from './draft.ts'

const A = 's1710001.mp4'
const B = 's1710002.mp4'

function document(trims: Record<string, { in: number; out: number; reason?: string }[]>): ReelDocument {
  return {
    metadata: {},
    look: {},
    chapters: [{ name: '', clips: [A, B] }],
    clips: Object.fromEntries(
      Object.entries(trims).map(([identity, list]) => [identity, { trims: list, exclude: false }]),
    ),
    ignore: [],
  } as unknown as ReelDocument
}

function setup(read: ReelDocument): { baseline: Baseline; draft: Draft } {
  const chapters = [{ key: 'r0', name: '', movable: [A, B], ignored: [] }]
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
  }
  return { baseline, draft }
}

const TWO = document({
  [A]: [
    { in: 1, out: 2.5, reason: 'black' },
    { in: 4, out: 5, reason: 'freeze' },
  ],
})

describe('trimCut', () => {
  it('a trimmed read cut is in the draft and makes it dirty', () => {
    const { baseline, draft } = setup(TWO)
    const next = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3.5 })
    assert.notEqual(next, draft)
    assert.equal(next.cuts.has(A), true)
    assert.equal(isDirty(baseline, next), true)
    assert.deepEqual(changedCuts(baseline, next), new Set([A]))
  })

  it('trimming and trimming back leaves no entry (what the old as-read test got wrong)', () => {
    const { baseline, draft } = setup(TWO)
    const trimmed = trimCut(baseline, draft, A, 'r0', { in: 1.04, out: 2.5 })
    assert.equal(trimmed.cuts.has(A), true)
    const back = trimCut(baseline, trimmed, A, 'r0', { in: 1, out: 2.5 })
    assert.equal(back.cuts.has(A), false)
    assert.equal(isDirty(baseline, back), false)
  })

  it('keeps the cut in place with its key and reason (a trim does not make it manual)', () => {
    const { baseline, draft } = setup(TWO)
    const next = trimCut(baseline, draft, A, 'r1', { in: 4.2, out: 5 })
    const cuts = cutsOf(baseline.cuts, next.cuts, A)
    assert.deepEqual(
      cuts.map((c) => [c.key, c.in, c.out, c.reason, c.removed]),
      [
        ['r0', 1, 2.5, 'black', false],
        ['r1', 4.2, 5, 'freeze', false],
      ],
    )
  })

  it('marks a trimmed read cut edited, and unmarks it when it is back', () => {
    const { baseline, draft } = setup(TWO)
    const one = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3 })
    assert.equal(cutsOf(baseline.cuts, one.cuts, A)[0].edited, true)
    // another cut also changed, so the list stays in the draft after r0 is back
    const two = trimCut(baseline, one, A, 'r1', { in: 4.5, out: 5 })
    const back = trimCut(baseline, two, A, 'r0', { in: 1, out: 2.5 })
    assert.equal(cutsOf(baseline.cuts, back.cuts, A)[0].edited, undefined)
    assert.equal(cutsOf(baseline.cuts, back.cuts, A)[1].edited, true)
  })

  it('an added cut that is trimmed stays an added cut', () => {
    const { baseline, draft } = setup(TWO)
    const added = addCut(baseline, draft, A, { in: 5.5, out: 6 }, 'a1')
    const trimmed = trimCut(baseline, added, A, 'a1', { in: 5.5, out: 5.9 })
    const cuts = cutsOf(baseline.cuts, trimmed.cuts, A)
    assert.deepEqual(cuts.map((c) => c.key), ['r0', 'r1', 'a1'])
    assert.equal(cuts[2].edited, undefined)
    assert.equal(cuts[2].reason, 'manual')
    assert.deepEqual(cutChanges(baseline, trimmed), { added: 1, removed: 0, trimmed: 0 })
  })

  it('returns the same draft for an unknown key, a removed cut and unchanged times', () => {
    const { baseline, draft } = setup(TWO)
    assert.equal(trimCut(baseline, draft, A, 'r9', { in: 1, out: 2 }), draft)
    assert.equal(trimCut(baseline, draft, B, 'r0', { in: 1, out: 2 }), draft)
    assert.equal(trimCut(baseline, draft, A, 'r0', { in: 1, out: 2.5 }), draft)
    const removed = removeCut(baseline, draft, A, 'r0')
    assert.equal(trimCut(baseline, removed, A, 'r0', { in: 1, out: 2 }), removed)
  })

  it('throws on a time that is not a number and on an end not after the start', () => {
    const { baseline, draft } = setup(TWO)
    assert.throws(() => trimCut(baseline, draft, A, 'r0', { in: Number.NaN, out: 2 }), RangeError)
    assert.throws(() => trimCut(baseline, draft, A, 'r0', { in: 1, out: Infinity }), RangeError)
    assert.throws(() => trimCut(baseline, draft, A, 'r0', { in: 2, out: 2 }), RangeError)
    assert.throws(() => trimCut(baseline, draft, A, 'r0', { in: 3, out: 2 }), RangeError)
  })

  it('the write body carries the changed clip’s trims only, reason kept', () => {
    const { baseline, draft } = setup(
      document({ [A]: [{ in: 1, out: 2.5, reason: 'black' }], [B]: [{ in: 0, out: 1 }] }),
    )
    const next = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3.5 })
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.clips[A].trims, [{ in: 1, out: 3.5, reason: 'black' }])
    assert.deepEqual(body.clips[B], baseline.read.clips[B])
    assert.deepEqual(body.chapters, baseline.read.chapters)
  })
})

describe('what the save bar counts', () => {
  it('counts a trimmed read cut once, beside the added and removed', () => {
    const { baseline, draft } = setup(TWO)
    const trimmed = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3 })
    assert.deepEqual(cutChanges(baseline, trimmed), { added: 0, removed: 0, trimmed: 1 })
    const more = addCut(baseline, trimmed, B, { in: 0, out: 1 }, 'a1')
    assert.deepEqual(cutChanges(baseline, more), { added: 1, removed: 0, trimmed: 1 })
  })

  it('a trimmed cut that is then removed counts as removed, not trimmed', () => {
    const { baseline, draft } = setup(TWO)
    const trimmed = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3 })
    const removed = removeCut(baseline, trimmed, A, 'r0')
    assert.deepEqual(cutChanges(baseline, removed), { added: 0, removed: 1, trimmed: 0 })
  })

  it('counts nothing for a trim that leaves the saved cuts as they were', () => {
    const { baseline, draft } = setup(TWO)
    const trimmed = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3 })
    const back = trimCut(baseline, trimmed, A, 'r0', { in: 1, out: 2.5 })
    assert.deepEqual(cutChanges(baseline, back), { added: 0, removed: 0, trimmed: 0 })
  })
})

describe('Undo over a trimmed cut', () => {
  it('is refused when a read cut was trimmed over the removed one', () => {
    const { baseline, draft } = setup(document({ [A]: [{ in: 1, out: 2.5 }, { in: 3, out: 4 }] }))
    const removed = removeCut(baseline, draft, A, 'r0')
    const trimmed = trimCut(baseline, removed, A, 'r1', { in: 2, out: 4 })
    const refusal = checkRestore(cutsOf(baseline.cuts, trimmed.cuts, A), 'r0')
    assert.notEqual(refusal, null)
    assert.equal(refusal?.clashNumber, 2)
    // and it stays removed: restoring is the caller's call, not made here
    assert.equal(cutsOf(baseline.cuts, trimmed.cuts, A)[0].removed, true)
  })

  it('is still allowed for two untouched read cuts that overlap in the file', () => {
    const { baseline, draft } = setup(document({ [A]: [{ in: 1, out: 3 }, { in: 2, out: 4 }] }))
    const removed = removeCut(baseline, draft, A, 'r0')
    assert.equal(checkRestore(cutsOf(baseline.cuts, removed.cuts, A), 'r0'), null)
    const back = restoreCut(baseline, removed, A, 'r0')
    assert.equal(back.cuts.has(A), false)
  })

  it('is refused when the removed cut itself was trimmed to overlap a read one', () => {
    const { baseline, draft } = setup(document({ [A]: [{ in: 1, out: 2 }, { in: 3, out: 4 }] }))
    const trimmed = trimCut(baseline, draft, A, 'r0', { in: 1, out: 3.5 })
    const removed = removeCut(baseline, trimmed, A, 'r0')
    assert.notEqual(checkRestore(cutsOf(baseline.cuts, removed.cuts, A), 'r0'), null)
  })
})

describe('layoutChanged', () => {
  const chapters = [
    { key: 'r0', name: '', movable: [A, B], ignored: [] },
    { key: 'r1', name: 'Kvällen', movable: [], ignored: [] },
  ]
  function two(): { baseline: Baseline; draft: Draft } {
    const read = document({})
    const baseline: Baseline = {
      read,
      chapters: draftChapters(chapters),
      original: ordersOf(chapters),
      cuts: readCuts(read),
    }
    return {
      baseline,
      draft: {
        chapters: baseline.chapters,
        orders: baseline.original,
        removed: new Map(),
        metadata: { title: '', date: '', location: '', description: '' },
        cuts: new Map(),
        rotations: new Map(),
      },
    }
  }

  it('is false for a cut-only or a metadata-only draft', () => {
    const { baseline, draft } = two()
    assert.equal(layoutChanged(baseline, draft), false)
    const cut = addCut(baseline, draft, A, { in: 1, out: 2 }, 'a1')
    assert.equal(layoutChanged(baseline, cut), false)
    const meta = { ...draft, metadata: { ...draft.metadata, title: 'Nytt' } }
    assert.equal(layoutChanged(baseline, meta), false)
  })

  it('is true after a reorder, a move, and a chapter added, renamed or deleted', () => {
    const { baseline, draft } = two()
    const orders = new Map(draft.orders).set('r0', moveClip([A, B], 0, 1))
    assert.equal(layoutChanged(baseline, { ...draft, orders }), true)
    const moved = new Map(draft.orders).set('r0', [A]).set('r1', [B])
    assert.equal(layoutChanged(baseline, { ...draft, orders: moved }), true)
    assert.equal(layoutChanged(baseline, addChapter(draft, 'a1', 'Ny')), true)
    assert.equal(layoutChanged(baseline, renameChapter(draft, 'r1', 'Natten')), true)
    assert.equal(layoutChanged(baseline, deleteChapter(draft, 'r1')), true)
    assert.equal(chapterChanges(baseline, deleteChapter(draft, 'r1').chapters).deleted, 1)
  })

  it('is false for a missing clip taken out of its chapter (it is not drawn)', () => {
    const { baseline, draft } = two()
    const orders = new Map(draft.orders).set('r0', [A])
    const removed = new Map(draft.removed).set(B, 'r0')
    assert.equal(layoutChanged(baseline, { ...draft, orders, removed }), false)
  })
})
