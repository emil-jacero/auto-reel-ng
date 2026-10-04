import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import { edgeAt, edgeEdit } from '../timeline/edgeTrim.ts'
import type { Side } from '../timeline/edgeTrim.ts'
import type { ClipFacts } from '../timeline/model.ts'
import {
  applyEdgeEdit,
  buildWriteBody,
  cutChanges,
  cutsOf,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  restoreCut,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

/*
 * The clip edge tools' draft edit (`clip-edge-trim`): a release is one draft change made
 * through the cut functions, so Reset, `settled`, the save bar's counts and the Cuts panel's
 * Undo treat it as any cut edit.
 */

const A = 's1710001.mp4'
const F: ClipFacts = { durationMs: 6020, fps: 50 }

function document(trims: Record<string, { in: number; out: number; reason?: string }[]>): ReelDocument {
  return {
    metadata: {},
    look: {},
    chapters: [{ name: '', clips: [A] }],
    clips: Object.fromEntries(
      Object.entries(trims).map(([identity, list]) => [identity, { trims: list, exclude: false }]),
    ),
    ignore: [],
  } as unknown as ReelDocument
}

function setup(read: ReelDocument): { baseline: Baseline; draft: Draft } {
  const chapters = [{ key: 'r0', name: '', movable: [A], ignored: [] }]
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

/** A release of `side` at `x`, as the edge tool sends it. */
function release(baseline: Baseline, draft: Draft, side: Side, x: number, key = 'a1'): Draft {
  const listed = cutsOf(baseline.cuts, draft.cuts, A)
  const at = edgeAt(listed, side, x, F, 40, { playheadMs: null, snapping: false })
  return applyEdgeEdit(baseline, draft, A, edgeEdit(listed, side, at.x, F), key)
}

const INTERIOR = document({
  [A]: [
    { in: 1, out: 2.5, reason: 'black' },
    { in: 4, out: 5, reason: 'freeze' },
  ],
})

describe('applyEdgeEdit', () => {
  it('one release is one draft change: a manual cut 0–0.5 added, counted as one cut added', () => {
    const { baseline, draft } = setup(INTERIOR)
    const next = release(baseline, draft, 'start', 500)
    assert.notEqual(next, draft)
    const listed = cutsOf(baseline.cuts, next.cuts, A)
    assert.deepEqual(listed[0], { key: 'a1', in: 0, out: 0.5, reason: 'manual', removed: false })
    assert.equal(listed.length, 3)
    assert.deepEqual(cutChanges(baseline, next), { added: 1, removed: 0, trimmed: 0 })
    assert.equal(isDirty(baseline, next), true)
  })

  it('dragged back to the start of the file, the added cut leaves the draft clean (settled)', () => {
    const { baseline, draft } = setup(INTERIOR)
    const trimmed = release(baseline, draft, 'start', 500)
    const back = release(baseline, trimmed, 'start', 0)
    assert.equal(isDirty(baseline, back), false)
    assert.equal(back.cuts.has(A), false)
  })

  it('a release where the drag began changes nothing', () => {
    const { baseline, draft } = setup(INTERIOR)
    assert.equal(release(baseline, draft, 'start', 0), draft)
  })

  it('an approved black cut at the start keeps its reason and key when extended', () => {
    const { baseline, draft } = setup(document({ [A]: [{ in: 0, out: 0.5, reason: 'black' }] }))
    const next = release(baseline, draft, 'start', 800)
    const listed = cutsOf(baseline.cuts, next.cuts, A)
    assert.deepEqual(
      listed.map((c) => [c.key, c.in, c.out, c.reason]),
      [['r0', 0, 0.8, 'black']],
    )
    assert.deepEqual(cutChanges(baseline, next), { added: 0, removed: 0, trimmed: 1 })
  })

  it('a read edge cut dragged back to the file’s limit is marked removed; the Cuts panel’s Undo restores it', () => {
    const { baseline, draft } = setup(document({ [A]: [{ in: 5.5, out: 6.02, reason: 'black' }] }))
    const removed = release(baseline, draft, 'end', 6020)
    const listed = cutsOf(baseline.cuts, removed.cuts, A)
    assert.equal(listed[0].removed, true)
    assert.deepEqual(cutChanges(baseline, removed), { added: 0, removed: 1, trimmed: 0 })
    const back = restoreCut(baseline, removed, A, 'r0')
    assert.equal(isDirty(baseline, back), false)
  })

  it('Save writes a start and an end trim beside the interior cuts', () => {
    const { baseline, draft } = setup(INTERIOR)
    const start = release(baseline, draft, 'start', 500, 'a1')
    const both = release(baseline, start, 'end', 5500, 'a2')
    const body = buildWriteBody(baseline, both) as unknown as {
      clips: Record<string, { trims: { in: number; out: number; reason?: string | null }[] }>
    }
    assert.deepEqual(
      body.clips[A].trims.map((t) => [t.in, t.out, t.reason]),
      [
        [0, 0.5, 'manual'],
        [1, 2.5, 'black'],
        [4, 5, 'freeze'],
        [5.5, 6.02, 'manual'],
      ],
    )
  })
})
