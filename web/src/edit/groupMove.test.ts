import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  draftChapters,
  groupOf,
  groupPlace,
  isDirty,
  moveClipTo,
  moveGroup,
  moveMarkedToEnd,
  movedSet,
  keptOriginal,
  ordersOf,
  readCuts,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

const A1 = 'a1'
const A2 = 'a2'
const A3 = 'a3'
const A4 = 'a4'
const B1 = 'b1'
const B2 = 'b2'

function setup(lists: Record<string, string[]>): { baseline: Baseline; draft: Draft } {
  const keys = Object.keys(lists)
  const chapters = keys.map((key) => ({ key, name: key === 'r0' ? '' : key, movable: lists[key], ignored: [] }))
  const read = {
    metadata: {},
    look: {},
    chapters: chapters.map((chapter) => ({ name: chapter.name, clips: chapter.movable })),
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

const WORKED = { r0: [A1, A2, A3, A4], r1: [B1, B2] }

function listed(draft: Draft): Record<string, readonly string[]> {
  return Object.fromEntries(draft.orders)
}

describe('groupOf', () => {
  const { draft } = setup(WORKED)

  it('is the marked clips in page order across chapters, not the order they were marked in', () => {
    const marked = new Set([B1, A4, A2])
    assert.deepEqual(groupOf(draft.orders, ['r0', 'r1'], marked), [A2, A4, B1])
    assert.deepEqual(groupOf(draft.orders, ['r1', 'r0'], marked), [B1, A2, A4])
  })

  it('keeps only clips a listed chapter plays: a stale or unlisted identity is dropped', () => {
    const marked = new Set([A2, 'stale.mp4', B1])
    assert.deepEqual(groupOf(draft.orders, ['r0'], marked), [A2])
    assert.deepEqual(groupOf(draft.orders, [], marked), [])
    assert.deepEqual(groupOf(draft.orders, ['r0', 'r1'], new Set()), [])
  })
})

describe('moveGroup', () => {
  it('gathers the group at a gap of another chapter (the design’s worked example)', () => {
    const { draft } = setup(WORKED)
    const next = moveGroup(draft, [A2, A4, B1], 'r1', 1)
    assert.deepEqual(listed(next), { r0: [A1, A3], r1: [A2, A4, B1, B2] })
  })

  it('gathers it at a gap of its own chapter', () => {
    const { draft } = setup(WORKED)
    const next = moveGroup(draft, [A2, A4, B1], 'r0', 4)
    assert.deepEqual(listed(next), { r0: [A1, A3, A2, A4, B1], r1: [B2] })
    const toEnd = moveGroup(draft, [A2, A4, B1], 'r1', 2)
    assert.deepEqual(listed(toEnd), { r0: [A1, A3], r1: [B2, A2, A4, B1] })
  })

  it('counts the gap over the chapter as it is now, the group included', () => {
    const { draft } = setup(WORKED)
    // Gap 2 of r0 lies above a1 and a2: one non-member (a1) above it, so the run goes before a3.
    assert.deepEqual(listed(moveGroup(draft, [A2, A4], 'r0', 2)), { r0: [A1, A2, A4, A3], r1: [B1, B2] })
    // Gap 3 lies above a1, a2, a3: two non-members, so the run goes after a3.
    assert.deepEqual(listed(moveGroup(draft, [A2, A4], 'r0', 3)), { r0: [A1, A3, A2, A4], r1: [B1, B2] })
    assert.deepEqual(listed(moveGroup(draft, [A2, A4], 'r0', 0)), { r0: [A2, A4, A1, A3], r1: [B1, B2] })
  })

  it('clamps a gap past the end, and below zero', () => {
    const { draft } = setup(WORKED)
    assert.deepEqual(listed(moveGroup(draft, [A1, A2], 'r1', 99)), { r0: [A3, A4], r1: [B1, B2, A1, A2] })
    assert.deepEqual(listed(moveGroup(draft, [A1, A2], 'r1', -5)), { r0: [A3, A4], r1: [A1, A2, B1, B2] })
  })

  it('returns the same draft object for a gap beside the group and for a repeated call', () => {
    const { draft } = setup(WORKED)
    // a2 a3 as a run: the gaps before a2, between them and after a3 all leave the order.
    for (const gap of [1, 2, 3]) {
      assert.equal(moveGroup(draft, [A2, A3], 'r0', gap), draft)
    }
    const moved = moveGroup(draft, [A2, A4, B1], 'r1', 1)
    assert.notEqual(moved, draft)
    assert.equal(moveGroup(moved, [A2, A4, B1], 'r1', 0), moved)
    assert.equal(moveGroup(moved, [A2, A4, B1], 'r1', 3), moved)
  })

  it('keeps the order and chapter of every non-member', () => {
    const { draft } = setup({ r0: [A1, A2, A3, A4], r1: [B1, B2], r2: ['c1'] })
    const next = moveGroup(draft, [A2, B1], 'r2', 0)
    assert.deepEqual(listed(next), { r0: [A1, A3, A4], r1: [B2], r2: [A2, B1, 'c1'] })
  })

  it('leaves the arrays of chapters the group did not touch as they were', () => {
    const { draft } = setup({ r0: [A1, A2], r1: [B1, B2], r2: ['c1'] })
    const next = moveGroup(draft, [A2], 'r1', 0)
    assert.equal(next.orders.get('r2'), draft.orders.get('r2'))
  })

  it('leaves a chapter that loses all its clips playing none', () => {
    const { draft } = setup(WORKED)
    const next = moveGroup(draft, [B1, B2], 'r0', 0)
    assert.deepEqual(listed(next), { r0: [B1, B2, A1, A2, A3, A4], r1: [] })
  })

  it('moves nothing for an unknown chapter, an empty group or clips no chapter plays', () => {
    const { draft } = setup(WORKED)
    assert.equal(moveGroup(draft, [A1], 'nope', 0), draft)
    assert.equal(moveGroup(draft, [], 'r1', 0), draft)
    assert.equal(moveGroup(draft, ['stale.mp4'], 'r1', 0), draft)
  })

  it('takes a repeated clip once', () => {
    const { draft } = setup(WORKED)
    assert.deepEqual(listed(moveGroup(draft, [A1, A1], 'r1', 0)), { r0: [A2, A3, A4], r1: [A1, B1, B2] })
  })

  it('equals moveClipTo for a one-clip group into another chapter', () => {
    const { draft } = setup(WORKED)
    for (const gap of [0, 1, 2]) {
      assert.deepEqual(
        listed(moveGroup(draft, [A3], 'r1', gap)),
        listed(moveClipTo(draft, 'r0', 'r1', A3, gap)),
      )
    }
  })

  it('does not change the draft it was given', () => {
    const { draft } = setup(WORKED)
    moveGroup(draft, [A2, A4, B1], 'r1', 1)
    assert.deepEqual(listed(draft), WORKED)
  })
})

describe('groupPlace', () => {
  const { draft } = setup(WORKED)

  it('says where the run starts and how many clips the chapter then plays', () => {
    assert.deepEqual(groupPlace(draft.orders, [A2, A4, B1], 'r1', 1), { position: 1, total: 4 })
    assert.deepEqual(groupPlace(draft.orders, [A2, A4, B1], 'r1', 2), { position: 2, total: 4 })
    assert.deepEqual(groupPlace(draft.orders, [A2, A4, B1], 'r0', 4), { position: 3, total: 5 })
  })

  it('agrees with where moveGroup puts the run', () => {
    for (const gap of [0, 1, 2]) {
      const group = [A2, A4, B1]
      const place = groupPlace(draft.orders, group, 'r1', gap)
      const next = moveGroup(draft, group, 'r1', gap)
      const order = next.orders.get('r1') ?? []
      assert.equal(order.indexOf(A2) + 1, place?.position)
      assert.equal(order.length, place?.total)
    }
  })

  it('is null for a chapter it does not know', () => {
    assert.equal(groupPlace(draft.orders, [A1], 'nope', 0), null)
  })
})

describe('a group in the draft', () => {
  it('moved away and back over a contiguous original place leaves nothing to save', () => {
    const { baseline, draft } = setup({ r0: [A1, B1, 'b1b', A2], r1: [B2] })
    const away = moveGroup(draft, [B1, 'b1b'], 'r1', 1)
    assert.equal(isDirty(baseline, away), true)
    // Back above a2: the original contiguous place.
    const back = moveGroup(away, [B1, 'b1b'], 'r0', 1)
    assert.deepEqual(listed(back), listed(draft))
    assert.equal(isDirty(baseline, back), false)
    for (const [key, order] of back.orders) {
      const original = baseline.original.get(key) ?? []
      assert.equal(movedSet(keptOriginal(original, order), order, B1).size, 0)
    }
  })

  it('counts each moved clip once, in its new chapter, and writes it once', () => {
    const { baseline, draft } = setup(WORKED)
    const next = moveGroup(draft, [A2, A4, B1], 'r1', 1)
    assert.equal(isDirty(baseline, next), true)
    const body = buildWriteBody(baseline, next)
    const written = body.chapters.flatMap((chapter) => chapter.clips)
    assert.deepEqual([...written].sort(), [A1, A2, A3, A4, B1, B2])
    assert.equal(new Set(written).size, written.length)
    assert.deepEqual(
      body.chapters.map((chapter) => chapter.clips),
      [[A1, A3], [A2, A4, B1, B2]],
    )
    // a2 and a4 are new in r1: counted there; b1 stays in place relative to b2.
    const inR1 = movedSet(keptOriginal(baseline.original.get('r1') ?? [], next.orders.get('r1') ?? []), next.orders.get('r1') ?? [], A4)
    assert.deepEqual([...inR1].sort(), [A2, A4])
  })
})

describe('moveMarkedToEnd', () => {
  const lists = ['r0', 'r1']

  it('puts marks from two chapters last in the target, in page order', () => {
    const { draft } = setup({ r0: [A1, A2, A3], r1: [B1, B2], r2: ['c1'] })
    const keys = ['r0', 'r1', 'r2']
    const result = moveMarkedToEnd(draft, keys, new Set([B1, A2]), 'r2')
    assert.deepEqual(listed(result.draft), { r0: [A1, A3], r1: [B2], r2: ['c1', A2, B1] })
    assert.deepEqual(result.moved, [A2, B1])
  })

  it('lets a marked clip already in the target join the run at the end', () => {
    const { draft } = setup(WORKED)
    const result = moveMarkedToEnd(draft, lists, new Set([B1, A1]), 'r1')
    assert.deepEqual(listed(result.draft), { r0: [A2, A3, A4], r1: [B2, A1, B1] })
  })

  it('is a no-op, the same draft, when the group is already last there', () => {
    const { draft } = setup(WORKED)
    const result = moveMarkedToEnd(draft, lists, new Set([B2]), 'r1')
    assert.equal(result.draft, draft)
    assert.deepEqual(result.moved, [])
    const none = moveMarkedToEnd(draft, lists, new Set(), 'r1')
    assert.equal(none.draft, draft)
  })

  it('ignores a stale mark and an unlisted or unknown target', () => {
    const { draft } = setup(WORKED)
    assert.equal(moveMarkedToEnd(draft, lists, new Set(['gone']), 'r1').draft, draft)
    assert.equal(moveMarkedToEnd(draft, ['r0'], new Set([A1]), 'r1').draft, draft)
    assert.equal(moveMarkedToEnd(draft, lists, new Set([A1]), 'nope').draft, draft)
  })

  it('leaves a chapter that lost every clip playing none', () => {
    const { draft } = setup(WORKED)
    const result = moveMarkedToEnd(draft, lists, new Set([B1, B2]), 'r0')
    assert.deepEqual(listed(result.draft), { r0: [A1, A2, A3, A4, B1, B2], r1: [] })
  })

  it('does not restore a returning clip to its old place (the drag’s edit)', () => {
    const { baseline, draft } = setup({ r0: [A1, A2, A3], r1: [B1] })
    const away = moveMarkedToEnd(draft, lists, new Set([A1]), 'r1').draft
    const back = moveMarkedToEnd(away, lists, new Set([A1]), 'r0').draft
    assert.deepEqual(listed(back), { r0: [A2, A3, A1], r1: [B1] })
    assert.equal(isDirty(baseline, back), true)
  })
})
