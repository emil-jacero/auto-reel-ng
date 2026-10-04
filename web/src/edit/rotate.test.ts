import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { ReelDocument } from '../api/reel.ts'
import {
  addCut,
  buildWriteBody,
  changedRotations,
  draftChapters,
  isDirty,
  ordersOf,
  readCuts,
  rotateClip,
  rotateGroup,
  rotationChanges,
  savedTurn,
  turnOf,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'

const A = 'a.mp4'
const B = 'b.mp4'
const C = 'c.mp4'
const MISSING = 'gone.mp4'

type Clips = Record<string, Record<string, unknown>>

function setup(clips: Clips = {}): { baseline: Baseline; draft: Draft } {
  const chapters = [{ key: 'r0', name: '', movable: [A, B, C, MISSING], ignored: [] }]
  const read = {
    metadata: {},
    look: {},
    chapters: [{ name: '', clips: [A, B, C, MISSING] }],
    clips: Object.fromEntries(
      Object.entries(clips).map(([identity, entry]) => [
        identity,
        { trims: [], exclude: false, ...entry },
      ]),
    ),
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
  }
  return { baseline, draft }
}

const onDisk = (identity: string) => identity !== MISSING

describe('rotateClip', () => {
  it('turns right 0 -> 90 -> 180 and writes rotate', () => {
    const { baseline, draft } = setup()
    const once = rotateClip(baseline, draft, A, 'right', onDisk)
    const twice = rotateClip(baseline, once, A, 'right', onDisk)
    assert.equal(turnOf(baseline, once, A), 90)
    assert.equal(turnOf(baseline, twice, A), 180)
    assert.equal(isDirty(baseline, twice), true)
    assert.deepEqual(buildWriteBody(baseline, twice).clips[A], { trims: [], rotate: 180, exclude: false })
  })

  it('turns left from none to 270', () => {
    const { baseline, draft } = setup()
    const next = rotateClip(baseline, draft, A, 'left', onDisk)
    assert.equal(turnOf(baseline, next, A), 270)
    assert.equal(buildWriteBody(baseline, next).clips[A]?.rotate, 270)
  })

  it('back to the saved value is clean', () => {
    const { baseline, draft } = setup({ [A]: { rotate: 90 } })
    const there = rotateClip(baseline, draft, A, 'right', onDisk)
    const back = rotateClip(baseline, there, A, 'left', onDisk)
    assert.equal(isDirty(baseline, there), true)
    assert.equal(isDirty(baseline, back), false)
    assert.equal(back.rotations.size, 0)
    assert.equal(rotationChanges(baseline, back), 0)
  })

  it('a turn of 0 removes the key and never writes rotate: 0', () => {
    const { baseline, draft } = setup({ [A]: { rotate: 90, title: true }, [B]: { rotate: 90 } })
    const next = rotateClip(baseline, rotateClip(baseline, draft, A, 'left', onDisk), B, 'left', onDisk)
    const clips = buildWriteBody(baseline, next).clips
    // A keeps its other property, loses the key; B had nothing else: its entry goes.
    assert.deepEqual(clips[A], { trims: [], title: true, exclude: false })
    assert.equal('rotate' in (clips[A] ?? {}), false)
    assert.equal(B in clips, false)
    assert.equal(JSON.stringify(clips).includes('"rotate":0'), false)
  })

  it('keeps the trims and the title of a turned clip', () => {
    const { baseline, draft } = setup({
      [A]: { title: true, trims: [{ in: 1, out: 2, reason: null }] },
    })
    const next = rotateClip(baseline, draft, A, 'right', onDisk)
    assert.deepEqual(buildWriteBody(baseline, next).clips[A], {
      trims: [{ in: 1, out: 2, reason: null }],
      title: true,
      rotate: 90,
      exclude: false,
    })
  })

  it('a saved turn of -90 is 270 and equal to a draft of 270', () => {
    const { baseline, draft } = setup({ [A]: { rotate: -90 } })
    assert.equal(savedTurn(baseline.read, A), 270)
    const there = rotateClip(baseline, draft, A, 'right', onDisk)
    const back = rotateClip(baseline, there, A, 'left', onDisk)
    assert.equal(isDirty(baseline, back), false)
    assert.equal(buildWriteBody(baseline, back).clips[A]?.rotate, -90)
  })

  it('refuses a missing, an ignored (unplayed) and a removed clip', () => {
    const { baseline, draft } = setup()
    assert.equal(rotateClip(baseline, draft, MISSING, 'right', onDisk), draft)
    assert.equal(rotateClip(baseline, draft, 'ignored.mp4', 'right', onDisk), draft)
    const removed = { ...draft, removed: new Map([[C, 'r0']]) }
    assert.equal(rotateClip(baseline, removed, C, 'right', onDisk), removed)
  })

  it('writes the turn with a cut change in the same body', () => {
    const { baseline, draft } = setup()
    const cut = addCut(baseline, draft, A, { in: 1000, out: 2000 }, 'a1')
    const both = rotateClip(baseline, cut, A, 'right', onDisk)
    const entry = buildWriteBody(baseline, both).clips[A]
    assert.equal(entry?.rotate, 90)
    assert.equal(entry?.trims.length, 1)
  })

  it('a removed clip does not count', () => {
    const { baseline, draft } = setup()
    const next = rotateClip(baseline, draft, A, 'right', onDisk)
    const gone = { ...next, removed: new Map([[A, 'r0']]) }
    assert.equal(changedRotations(baseline, gone).size, 0)
  })
})

describe('rotateGroup', () => {
  it('turns three clips with turns 0/90/270 right to 90/180/0 in one step', () => {
    const { baseline, draft } = setup({ [B]: { rotate: 90 }, [C]: { rotate: 270 } })
    const next = rotateGroup(baseline, draft, [A, B, C], 'right', onDisk)
    assert.equal(turnOf(baseline, next, A), 90)
    assert.equal(turnOf(baseline, next, B), 180)
    assert.equal(turnOf(baseline, next, C), 0)
    assert.equal(rotationChanges(baseline, next), 3)
    const clips = buildWriteBody(baseline, next).clips
    assert.equal(clips[A]?.rotate, 90)
    assert.equal(clips[B]?.rotate, 180)
    assert.equal(C in clips, false)
  })

  it('skips clips that cannot be turned and is the same draft with none', () => {
    const { baseline, draft } = setup()
    const next = rotateGroup(baseline, draft, [A, MISSING], 'right', onDisk)
    assert.equal(turnOf(baseline, next, A), 90)
    assert.equal(turnOf(baseline, next, MISSING), 0)
    assert.equal(rotateGroup(baseline, draft, [MISSING], 'right', onDisk), draft)
    assert.equal(rotateGroup(baseline, draft, [], 'right', onDisk), draft)
  })

  it('a NEW clip (not in the document) is adopted with its turn', () => {
    const { baseline, draft } = setup()
    const withNew = {
      ...baseline,
      read: { ...baseline.read, chapters: [{ name: 'Main', clips: [B] }] },
    }
    const next = rotateClip(withNew, draft, A, 'right', onDisk)
    const body = buildWriteBody(withNew, next)
    assert.equal(body.clips[A]?.rotate, 90)
    assert.ok(body.chapters.some((chapter) => chapter.clips.includes(A)))
  })
})
