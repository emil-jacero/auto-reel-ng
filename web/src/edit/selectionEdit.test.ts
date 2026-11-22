import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import { draftChapters, ignoredNow, isDirty, ordersOf, readCuts } from './draft.ts'
import type { Baseline, Draft } from './draft.ts'
import { cleared, record, redoLabel, undo, undoLabel } from './history.ts'
import type { History } from './history.ts'
import { NOTHING_INCLUDED, selectionLabel, selectionStep } from './selectionEdit.ts'
import type { SelectionEdit, SelectionTarget } from './selectionEdit.ts'

const A1 = 'a1.mp4'
const A2 = 'a2.mp4'
const A3 = 'a3.mp4'
const A4 = 'a4.mp4'
const B1 = 'b1.mp4'
const B2 = 'b2.mp4'

const ALL = (): boolean => true

function target(): SelectionTarget {
  const chapters = [
    { key: 'r0', name: '', movable: [A1, A2, A3, A4], ignored: [] },
    { key: 'r1', name: 'B', movable: [B1, B2], ignored: [] },
  ]
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
  return { baseline, draft, lastMoved: null }
}

const lists = (state: SelectionTarget): Record<string, readonly string[]> =>
  Object.fromEntries(state.draft.orders)

/** What the editor's reducer does around `selectionStep`: record the step under its label. */
function apply(
  history: History<SelectionTarget>,
  action: SelectionEdit,
): History<SelectionTarget> {
  const before = history.present
  const next = selectionStep(before, action)
  return next === before ? history : record(history, next, selectionLabel(action, before))
}

describe('selection-move', () => {
  it('puts the shipped clips last in the target, in page order', () => {
    const next = selectionStep(target(), { onDisk: ALL, type: 'selection-move', identities: [B1, A2], to: 'r1' })
    assert.deepEqual(lists(next), { r0: [A1, A3, A4], r1: [B2, A2, B1] })
  })

  it('does not move an ignored or unknown identity of the set', () => {
    const state = target()
    // a3 was ignored after the set was taken: it is in no chapter's order any more.
    const gone: SelectionTarget = {
      ...state,
      draft: { ...state.draft, orders: new Map(state.draft.orders).set('r0', [A1, A2, A4]) },
    }
    const next = selectionStep(gone, {
      onDisk: ALL,
      type: 'selection-move',
      identities: [A2, A3, 'unknown.mp4'],
      to: 'r1',
    })
    assert.deepEqual(lists(next), { r0: [A1, A4], r1: [B1, B2, A2] })
    assert.equal(
      selectionStep(gone, { onDisk: ALL, type: 'selection-move', identities: [A3], to: 'r1' }),
      gone,
    )
  })

  it('does not move a missing clip, which stays in its chapter: a range over the bin holds it', () => {
    const state = target()
    const notA4 = (identity: string): boolean => identity !== A4
    const next = selectionStep(state, {
      onDisk: notA4,
      type: 'selection-move',
      identities: [A3, A4, B1],
      to: 'r1',
    })
    assert.deepEqual(lists(next), { r0: [A1, A2, A4], r1: [B2, A3, B1] })
    assert.equal(
      selectionStep(state, { onDisk: notA4, type: 'selection-move', identities: [A4], to: 'r1' }),
      state,
    )
    const drop = selectionStep(state, {
      onDisk: notA4,
      type: 'selection-drop',
      identities: [A3, A4],
      dragged: A3,
      to: 'r1',
      gap: 0,
    })
    assert.deepEqual(lists(drop), { r0: [A1, A2, A4], r1: [A3, B1, B2] })
    assert.equal(
      selectionLabel({ onDisk: notA4, type: 'selection-move', identities: [A3, A4], to: 'r1' }, state),
      'move of a3.mp4',
    )
  })

  it('is a no-op for an unlisted target', () => {
    const state = target()
    assert.equal(selectionStep(state, { onDisk: ALL, type: 'selection-move', identities: [A1], to: 'nope' }), state)
  })
})

describe('selection-drop', () => {
  it('drops the shipped clips as one run at the gap and names the dragged one', () => {
    const next = selectionStep(target(), {
      onDisk: ALL, type: 'selection-drop',
      identities: [A4, B1, A2],
      dragged: A4,
      to: 'r1',
      gap: 1,
    })
    assert.deepEqual(lists(next), { r0: [A1, A3], r1: [A2, A4, B1, B2] })
    assert.equal(next.lastMoved, A4)
  })

  it('leaves the state alone for a drop that changes nothing or holds nothing', () => {
    const state = target()
    assert.equal(
      selectionStep(state, { onDisk: ALL, type: 'selection-drop', identities: [A2, A3], dragged: A2, to: 'r0', gap: 2 }),
      state,
    )
    assert.equal(
      selectionStep(state, { onDisk: ALL, type: 'selection-drop', identities: ['gone'], dragged: 'gone', to: 'r1', gap: 0 }),
      state,
    )
  })
})

describe('ignore-many', () => {
  it('ignores every listed clip of the set in one draft edit', () => {
    const state = target()
    const next = selectionStep(state, { onDisk: ALL, type: 'ignore-many', identities: [A2, B1, 'unknown.mp4'] })
    assert.deepEqual(lists(next), { r0: [A1, A3, A4], r1: [B2] })
    assert.deepEqual(ignoredNow(next.baseline, next.draft), [A2, B1])
    assert.equal(isDirty(next.baseline, next.draft), true)
  })

  it('does not ignore a missing clip: it stays in its chapter, with no ignore entry', () => {
    const state = target()
    const next = selectionStep(state, {
      onDisk: (identity) => identity !== A2,
      type: 'ignore-many',
      identities: [A1, A2],
    })
    assert.deepEqual(lists(next), { r0: [A2, A3, A4], r1: [B1, B2] })
    assert.deepEqual(ignoredNow(next.baseline, next.draft), [A1])
    assert.equal(
      selectionStep(state, { onDisk: () => false, type: 'ignore-many', identities: [A1, A2] }),
      state,
    )
  })

  it('is no change for a set none of whose clips a chapter plays', () => {
    const state = target()
    assert.equal(selectionStep(state, { onDisk: ALL, type: 'ignore-many', identities: ['gone'] }), state)
    assert.equal(selectionStep(state, { onDisk: ALL, type: 'ignore-many', identities: [] }), state)
  })

  it('is one Undo step, however many clips it ignores', () => {
    let history = cleared(target())
    history = apply(history, { onDisk: ALL, type: 'ignore-many', identities: [A1, A3, B2] })
    assert.equal(history.past.length, 1)
    assert.equal(undoLabel(history), 'ignore of 3 clips')
    const back = undo(history)
    assert.deepEqual(lists(back.present), { r0: [A1, A2, A3, A4], r1: [B1, B2] })
    assert.equal(back.past.length, 0)
    assert.equal(redoLabel(back), 'ignore of 3 clips')
    assert.equal(isDirty(back.present.baseline, back.present.draft), false)
  })
})

/** A state with `a2` and `b1` ignored in the document, as read: `ignored` of each chapter. */
function ignoring(): SelectionTarget {
  const state = target()
  const baseline: Baseline = { ...state.baseline, read: { ...state.baseline.read, ignore: [A2, B1] } }
  const orders = new Map(state.draft.orders)
  orders.set('r0', [A1, A3, A4])
  orders.set('r1', [B2])
  return {
    ...state,
    baseline: { ...baseline, original: orders },
    draft: { ...state.draft, orders },
  }
}
const CHAPTER_OF: Record<string, string> = { [A2]: 'r0', [B1]: 'r1' }
const chapterOf = (identity: string) => CHAPTER_OF[identity]

describe('include-many', () => {
  it('includes each ignored clip at the end of its chapter, in the set\'s order, as one edit', () => {
    const state = ignoring()
    const next = selectionStep(state, { onDisk: ALL, type: 'include-many', identities: [A2, B1], chapterOf })
    assert.deepEqual(lists(next), { r0: [A1, A3, A4, A2], r1: [B2, B1] })
    assert.deepEqual(ignoredNow(next.baseline, next.draft), [])
    assert.equal(next.draft.ignoreEdits?.get(A2), 'include')
    assert.equal(next.draft.ignoreEdits?.get(B1), 'include')
    assert.equal(isDirty(next.baseline, next.draft), true)
  })

  it('leaves out a clip that is played, unknown, not on disk, or whose chapter is gone', () => {
    const state = ignoring()
    const next = selectionStep(state, {
      onDisk: (identity) => identity !== B1,
      type: 'include-many',
      identities: [A1, A2, B1, 'gone.mp4'],
      chapterOf: (identity) => (identity === A1 ? 'r0' : chapterOf(identity)),
    })
    assert.deepEqual(lists(next), { r0: [A1, A3, A4, A2], r1: [B2] })
    const deleted: SelectionTarget = {
      ...state,
      draft: { ...state.draft, chapters: state.draft.chapters.map((c) => (c.key === 'r1' ? { ...c, deleted: true } : c)) },
    }
    assert.deepEqual(
      lists(selectionStep(deleted, { onDisk: ALL, type: 'include-many', identities: [A2, B1], chapterOf })),
      { r0: [A1, A3, A4, A2], r1: [B2] },
    )
  })

  it('is no change for a set with nothing to include', () => {
    const state = ignoring()
    assert.equal(selectionStep(state, { onDisk: ALL, type: 'include-many', identities: [A1, A3], chapterOf: () => 'r0' }), state)
    assert.equal(selectionStep(state, { onDisk: ALL, type: 'include-many', identities: [], chapterOf }), state)
    assert.equal(NOTHING_INCLUDED, 'Nothing included.')
  })

  it('is one Undo step labelled "include of N clips", and one Redo', () => {
    let history = cleared(ignoring())
    history = apply(history, { onDisk: ALL, type: 'include-many', identities: [A2, B1], chapterOf })
    assert.equal(history.past.length, 1)
    assert.equal(undoLabel(history), 'include of 2 clips')
    const back = undo(history)
    assert.deepEqual(lists(back.present), { r0: [A1, A3, A4], r1: [B2] })
    assert.deepEqual(ignoredNow(back.present.baseline, back.present.draft), [A2, B1])
    assert.equal(back.past.length, 0)
    assert.equal(redoLabel(back), 'include of 2 clips')
    assert.equal(isDirty(back.present.baseline, back.present.draft), false)
  })

  it('names one clip by its name, and counts only the clips it includes', () => {
    const state = ignoring()
    assert.equal(
      selectionLabel({ onDisk: ALL, type: 'include-many', identities: [A2], chapterOf }, state),
      'include of a2.mp4',
    )
    assert.equal(
      selectionLabel({ onDisk: ALL, type: 'include-many', identities: [A1, A2, B1], chapterOf }, state),
      'include of 2 clips',
    )
  })

  it('includes a clip ignored in this draft again, dropping its ignore entry', () => {
    const base = target()
    const ignoredHere = selectionStep(base, { onDisk: ALL, type: 'ignore-many', identities: [A2, B1] })
    const next = selectionStep(ignoredHere, {
      onDisk: ALL,
      type: 'include-many',
      identities: [A2, B1],
      chapterOf: (identity) => (identity === A2 ? 'r0' : 'r1'),
    })
    assert.equal(next.draft.ignoreEdits?.size, 0)
    assert.deepEqual(lists(next), { r0: [A1, A3, A4, A2], r1: [B2, B1] })
  })
})

describe('the labels', () => {
  it('names a step by its clip or its count', () => {
    const state = target()
    const one = selectionLabel({ onDisk: ALL, type: 'selection-move', identities: [A2], to: 'r1' }, state)
    assert.equal(one, 'move of a2.mp4')
    const many = selectionLabel({ onDisk: ALL, type: 'selection-move', identities: [A2, B1, 'gone'], to: 'r1' }, state)
    assert.equal(many, 'move of 2 clips')
    const drop = selectionLabel(
      { onDisk: ALL, type: 'selection-drop', identities: [A2, A3, A4], dragged: A2, to: 'r1', gap: 0 },
      state,
    )
    assert.equal(drop, 'move of 3 clips')
    assert.equal(selectionLabel({ onDisk: ALL, type: 'ignore-many', identities: [A1, A2] }, state), 'ignore of 2 clips')
    assert.equal(selectionLabel({ onDisk: ALL, type: 'ignore-many', identities: [A1] }, state), 'ignore of a1.mp4')
  })
})
