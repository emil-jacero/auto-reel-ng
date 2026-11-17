import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  buildWriteBody,
  draftChapters,
  ignoreChanges,
  ignoreClip,
  ignoredLists,
  ignoredNow,
  includeClip,
  isDirty,
  ordersOf,
  readCuts,
  setCardLength,
  withIgnoreStatus,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

const A1 = 'a1.mp4'
const A2 = 'a2.mp4'
const A3 = 'a3.mp4'
const B1 = 'b1.mp4'
const OLD = 'old.mp4'

function setup(): { baseline: Baseline; draft: Draft } {
  const chapters = [
    { key: 'r0', name: '', movable: [A1, A2, A3], ignored: [OLD] },
    { key: 'r1', name: 'B', movable: [B1], ignored: [] },
  ]
  const read = {
    metadata: {},
    look: {},
    chapters: [
      { name: '', clips: [A1, A2] },
      { name: 'B', clips: [B1] },
    ],
    clips: { [A2]: { trims: [{ in: 1, out: 2 }] } },
    ignore: [OLD],
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

describe('ignoring a clip', () => {
  it('takes it out of the order and into the saved ignore list', () => {
    const { baseline, draft } = setup()
    const next = ignoreClip(baseline, draft, 'r0', A3)
    assert.deepEqual(next.orders.get('r0'), [A1, A2])
    assert.deepEqual(ignoredNow(baseline, next), [OLD, A3])
    assert.deepEqual(ignoreChanges(next), { ignored: 1, included: 0, total: 1 })
    assert.equal(isDirty(baseline, next), true)
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.ignore, [OLD, A3])
    assert.ok(body.chapters.every((chapter) => !chapter.clips.includes(A3)))
  })

  it('drops the properties of a clip ignored here, as the engine refuses them', () => {
    const { baseline, draft } = setup()
    const body = buildWriteBody(baseline, ignoreClip(baseline, draft, 'r0', A2))
    assert.deepEqual(body.clips, {})
  })

  it('refuses a clip the chapter does not play', () => {
    const { baseline, draft } = setup()
    assert.equal(ignoreClip(baseline, draft, 'r1', A1), draft)
    assert.equal(ignoreClip(baseline, draft, 'r0', OLD), draft)
  })
})

describe('including a clip', () => {
  it('places it in the order and out of the saved ignore list', () => {
    const { baseline, draft } = setup()
    const next = includeClip(baseline, draft, 'r1', OLD, 0)
    assert.deepEqual(next.orders.get('r1'), [OLD, B1])
    assert.deepEqual(ignoreChanges(next), { ignored: 0, included: 1, total: 1 })
    const body = buildWriteBody(baseline, next)
    assert.deepEqual(body.ignore, [])
    assert.deepEqual(body.chapters.find((chapter) => chapter.name === 'B')?.clips, [OLD, B1])
  })

  it('clamps the index and refuses a clip that is not ignored', () => {
    const { baseline, draft } = setup()
    assert.deepEqual(includeClip(baseline, draft, 'r0', OLD, 99).orders.get('r0'), [A1, A2, A3, OLD])
    assert.equal(includeClip(baseline, draft, 'r0', A1, 0), draft)
    assert.equal(includeClip(baseline, draft, 'nope', OLD, 0), draft)
  })

  it('puts an ignored clip back as read, with no entry left to save', () => {
    const { baseline, draft } = setup()
    const back = includeClip(baseline, ignoreClip(baseline, draft, 'r0', A3), 'r0', A3, 2)
    assert.deepEqual(back.orders.get('r0'), [A1, A2, A3])
    assert.equal(ignoreChanges(back).total, 0)
    assert.equal(isDirty(baseline, back), false)
    assert.deepEqual(buildWriteBody(baseline, back).ignore, [OLD])
  })

  it('ignores an included clip again as read', () => {
    const { baseline, draft } = setup()
    const out = ignoreClip(baseline, includeClip(baseline, draft, 'r0', OLD, 1), 'r0', OLD)
    assert.equal(ignoreChanges(out).total, 0)
    assert.equal(isDirty(baseline, out), false)
  })
})

describe('an untouched draft', () => {
  it('writes ignore as read', () => {
    const { baseline, draft } = setup()
    assert.equal(buildWriteBody(baseline, draft).ignore, baseline.read.ignore)
    assert.equal(isDirty(baseline, draft), false)
    assert.equal(isDirty(baseline, setCardLength(baseline, draft, 'r1', 2, 3)), true)
  })
})

describe('what the lists and the track show of an ignore edit', () => {
  const read = new Map([
    ['r0', [OLD]],
    ['r1', []],
  ])

  it('lists a clip ignored here under the chapter it was played in', () => {
    const { baseline, draft } = setup()
    const lists = ignoredLists(baseline, ignoreClip(baseline, draft, 'r1', B1), read)
    assert.deepEqual(lists.get('r0'), [OLD])
    assert.deepEqual(lists.get('r1'), [B1])
  })

  it('stops listing a clip included here', () => {
    const { baseline, draft } = setup()
    const lists = ignoredLists(baseline, includeClip(baseline, draft, 'r0', OLD, 0), read)
    assert.deepEqual(lists.get('r0'), [])
  })

  it('is the page lists when nothing is edited', () => {
    const { baseline, draft } = setup()
    assert.equal(ignoredLists(baseline, draft, read), read)
  })

  it('shows the status of an edited clip and leaves the others', () => {
    const { baseline, draft } = setup()
    const detail = {
      chapters: [
        {
          name: '',
          clips: [
            { identity: A1, status: 'active' },
            { identity: OLD, status: 'ignored' },
          ],
        },
      ],
    } as unknown as Parameters<typeof withIgnoreStatus>[0]
    assert.equal(withIgnoreStatus(detail, undefined), detail)
    const ignored = withIgnoreStatus(detail, ignoreClip(baseline, draft, 'r0', A1).ignoreEdits)
    assert.deepEqual(
      ignored.chapters[0].clips.map((clip) => clip.status),
      ['ignored', 'ignored'],
    )
    const included = withIgnoreStatus(
      detail,
      includeClip(baseline, draft, 'r0', OLD, 0).ignoreEdits,
    )
    assert.deepEqual(
      included.chapters[0].clips.map((clip) => clip.status),
      ['active', 'active'],
    )
  })
})
