import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import { addCut, buildWriteBody, cutChanges, isDirty, readCuts, removeCut } from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

/*
 * The reason of an added cut (`addCut`): `manual` for a cut made by hand, the suggestion's
 * kind for an approved analysis suggestion, and the save writes it. Run by `npm test`.
 */

const read: ReelDocument = {
  metadata: { title: 'T', date: '2024-05-01' },
  look: {},
  chapters: [{ name: '', clips: ['a.mp4'] }],
  clips: { 'a.mp4': { exclude: false, trims: [{ in: 10, out: 11, reason: 'manual' }] } },
  ignore: [],
}

const baseline: Baseline = {
  read,
  chapters: [{ key: 'r0', readName: '', name: '', deleted: false }],
  original: new Map([['r0', ['a.mp4']]]),
  cuts: readCuts(read),
}

const draft: Draft = {
  chapters: baseline.chapters,
  orders: baseline.original,
  removed: new Map(),
  metadata: { title: 'T', date: '2024-05-01', location: '', description: '' },
  cuts: new Map(),
  rotations: new Map(),
  cards: new Map(),
}

const reasonsOf = (d: Draft) => (d.cuts.get('a.mp4') ?? []).map((cut) => cut.reason)

describe('addCut’s reason', () => {
  it('lists manual when no reason is given', () => {
    const next = addCut(baseline, draft, 'a.mp4', { in: 0, out: 3.2 }, 'a1')
    assert.deepEqual(reasonsOf(next), ['manual', 'manual'])
  })

  it('lists the kind it is given', () => {
    const next = addCut(baseline, draft, 'a.mp4', { in: 0, out: 3.2 }, 'a1', 'freeze')
    assert.deepEqual(reasonsOf(next), ['freeze', 'manual'])
    assert.equal(cutChanges(baseline, next).added, 1)
  })

  it('keeps an unrecognised kind as written', () => {
    const next = addCut(baseline, draft, 'a.mp4', { in: 0, out: 3.2 }, 'a1', 'speech')
    assert.deepEqual(reasonsOf(next), ['speech', 'manual'])
  })

  it('is written by the save as the clip’s trim, the read trims unchanged', () => {
    const next = addCut(baseline, draft, 'a.mp4', { in: 0, out: 3.2 }, 'a1', 'freeze')
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.clips['a.mp4'].trims, [
      { in: 0, out: 3.2, reason: 'freeze' },
      { in: 10, out: 11, reason: 'manual' },
    ])
    // Nothing else of the document moves.
    assert.deepEqual(body.chapters, read.chapters)
    assert.deepEqual(body.ignore, read.ignore)
  })

  it('leaves nothing to save once the added cut is removed again', () => {
    const added = addCut(baseline, draft, 'a.mp4', { in: 0, out: 3.2 }, 'a1', 'black')
    assert.equal(isDirty(baseline, added), true)
    const back = removeCut(baseline, added, 'a.mp4', 'a1')
    assert.equal(isDirty(baseline, back), false)
    assert.equal(back.cuts.has('a.mp4'), false)
  })
})
