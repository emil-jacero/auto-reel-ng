import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Orders } from '../edit/draft.ts'
import { layout } from './model.ts'
import { applyDrop, dropSlot } from './reorder.ts'
import type { DrawnChapter } from './reorder.ts'
import { cardMap } from './cards.ts'
import type { CardMap, Placement } from './cards.ts'

const NONE: CardMap = { gaps: [], totalMs: 0 }

/** Clips of `len` ms each, laid in the chapters' order. */
function lay(chapters: readonly DrawnChapter[], len = 1000) {
  const count = chapters.reduce((sum, c) => sum + c.identities.length, 0)
  return layout(Array.from({ length: count }, () => ({ durationMs: len, fps: 25 })))
}

const chapters: DrawnChapter[] = [
  {
    key: 'r0',
    name: 'Main',
    identities: ['s1710001.mp4', 's1710002.mp4', 's1710003.mp4'],
  },
  { key: 'r1', name: 'Kvällen', identities: ['s1710005.mp4', 's1710004.mp4'] },
]
const orders: Orders = new Map(chapters.map((c) => [c.key, c.identities]))

describe('dropSlot', () => {
  it('reorders inside a chapter', () => {
    // s1710002 spans 1000..2000; its centre is dragged to the boundary at 0.
    const slot = dropSlot(lay(chapters), NONE, chapters, 100, 's1710002.mp4')
    assert.deepEqual(slot, {
      chapter: 'r0',
      index: 0,
      beforeIdentity: 's1710001.mp4',
      words: 'Before s1710001.mp4',
    })
    const next = applyDrop(orders, { identity: 's1710002.mp4', chapter: 'r0' }, slot)
    assert.deepEqual(next.get('r0'), ['s1710002.mp4', 's1710001.mp4', 's1710003.mp4'])
  })

  it('moves later inside a chapter with the lists index semantics', () => {
    const slot = dropSlot(lay(chapters), NONE, chapters, 2900, 's1710001.mp4')
    assert.equal(slot.chapter, 'r0')
    assert.equal(slot.index, 2)
    assert.equal(slot.beforeIdentity, null)
    assert.equal(slot.words, 'At the end of Main')
    assert.deepEqual(
      applyDrop(orders, { identity: 's1710001.mp4', chapter: 'r0' }, slot).get('r0'),
      ['s1710002.mp4', 's1710003.mp4', 's1710001.mp4'],
    )
  })

  it('goes across chapters to the end of Main', () => {
    const slot = dropSlot(lay(chapters), NONE, chapters, 2900, 's1710004.mp4')
    assert.equal(slot.chapter, 'r0')
    assert.equal(slot.index, 3)
    assert.equal(slot.beforeIdentity, null)
    const next = applyDrop(orders, { identity: 's1710004.mp4', chapter: 'r1' }, slot)
    assert.deepEqual(next.get('r0'), [
      's1710001.mp4',
      's1710002.mp4',
      's1710003.mp4',
      's1710004.mp4',
    ])
    assert.deepEqual(next.get('r1'), ['s1710005.mp4'])
  })

  it('stays in the clip own place nearest its own boundaries', () => {
    for (const ms of [1000, 1400, 1600, 2000]) {
      const slot = dropSlot(lay(chapters), NONE, chapters, ms, 's1710002.mp4')
      assert.equal(slot.chapter, 'r0')
      assert.equal(slot.index, 1)
      assert.equal(applyDrop(orders, { identity: 's1710002.mp4', chapter: 'r0' }, slot), orders)
    }
  })

  it('prefers the own place on a tie with another boundary', () => {
    const slot = dropSlot(lay(chapters), NONE, chapters, 1500, 's1710002.mp4')
    assert.equal(slot.index, 1)
  })

  it('snaps to a boundary between chapters: the end of the earlier one', () => {
    const slot = dropSlot(lay(chapters), NONE, chapters, 2900, 's1710001.mp4')
    assert.equal(slot.chapter, 'r0')
    assert.equal(slot.index, 2)
  })

  it('drops at the start of the next chapter nearer its first clip', () => {
    const slot = dropSlot(lay(chapters), NONE, chapters, 3900, 's1710001.mp4')
    assert.equal(slot.chapter, 'r1')
    assert.equal(slot.index, 1)
    assert.equal(slot.beforeIdentity, 's1710004.mp4')
  })

  it('drops after the last clip of the last chapter and beyond the track', () => {
    for (const ms of [5000, 99999]) {
      const slot = dropSlot(lay(chapters), NONE, chapters, ms, 's1710001.mp4')
      assert.equal(slot.chapter, 'r1')
      assert.equal(slot.index, 2)
      assert.equal(slot.words, 'At the end of Kvällen')
    }
    assert.equal(dropSlot(lay(chapters), NONE, chapters, -500, 's1710003.mp4').index, 0)
  })

  it('offers an empty chapter one boundary where it sits', () => {
    const withEmpty: DrawnChapter[] = [
      chapters[0],
      { key: 'r2', name: 'Empty', identities: [] },
      chapters[1],
    ]
    // The boundary at 3000 is the end of Main, Empty's, and Kvällen's start: the side decides.
    assert.equal(dropSlot(lay(withEmpty), NONE, withEmpty, 2900, 's1710004.mp4').chapter, 'r0')
    assert.equal(dropSlot(lay(withEmpty), NONE, withEmpty, 3100, 's1710001.mp4').chapter, 'r1')
    const solo: DrawnChapter[] = [
      { key: 'a', identities: [] },
      { key: 'b', identities: ['y.mp4', 'x.mp4'] },
    ]
    const s = dropSlot(lay(solo), NONE, solo, -50, 'x.mp4')
    assert.equal(s.chapter, 'a')
    assert.equal(s.index, 0)
    const next = applyDrop(
      new Map([
        ['a', []],
        ['b', ['y.mp4', 'x.mp4']],
      ]),
      { identity: 'x.mp4', chapter: 'b' },
      s,
    )
    assert.deepEqual(next.get('a'), ['x.mp4'])
    assert.deepEqual(next.get('b'), ['y.mp4'])
  })

  it('tells the two sides of a chapter join apart', () => {
    // Kvällen is [s1710004, s1710005] here: the second clip can reach Kvällen's start...
    const k: DrawnChapter[] = [
      chapters[0],
      {
        key: 'r1',
        name: 'Kvällen',
        identities: ['s1710004.mp4', 's1710005.mp4'],
      },
    ]
    for (const ms of [3000, 3100]) {
      const slot = dropSlot(lay(k), NONE, k, ms, 's1710005.mp4')
      assert.equal(slot.chapter, 'r1')
      assert.equal(slot.index, 0)
      assert.equal(slot.beforeIdentity, 's1710004.mp4')
    }
    // ...and the first clip can reach the end of Main.
    for (const ms of [2900, 2999]) {
      const slot = dropSlot(lay(k), NONE, k, ms, 's1710004.mp4')
      assert.equal(slot.chapter, 'r0')
      assert.equal(slot.beforeIdentity, null)
      assert.equal(slot.words, 'At the end of Main')
    }
    // Its own place from the other side.
    assert.equal(dropSlot(lay(k), NONE, k, 3000, 's1710004.mp4').chapter, 'r1')
  })

  it('snaps around a black card between chapters', () => {
    const k: DrawnChapter[] = [
      chapters[0],
      {
        key: 'r1',
        name: 'Kvällen',
        identities: ['s1710004.mp4', 's1710005.mp4'],
      },
    ]
    const l = lay(k)
    const placement: Placement = {
      kind: 'anchored',
      chapter: 1,
      clip: 3,
      atMs: 0,
      background: 'black',
      durationMs: 1000,
      keptMs: 1000,
      widthMs: 1000,
      clamped: false,
    }
    const map = cardMap([placement], l)
    // Main ends at 3000, the card runs 3000..4000, Kvällen starts at 4000.
    assert.equal(dropSlot(l, map, k, 3400, 's1710001.mp4').words, 'At the end of Main')
    const after = dropSlot(l, map, k, 3600, 's1710001.mp4')
    assert.equal(after.chapter, 'r1')
    assert.equal(after.beforeIdentity, 's1710004.mp4')
    assert.equal(dropSlot(l, map, k, 3400, 's1710004.mp4').chapter, 'r0')
  })

  it('resolves a drop by identity when the order holds clips that are not drawn', () => {
    const full: Orders = new Map([['m', ['a.mp4', 'missing.mp4', 'b.mp4', 'c.mp4']]])
    const drawn = new Set(['a.mp4', 'b.mp4', 'c.mp4'])
    const from = { identity: 'b.mp4', chapter: 'm' }
    const view: DrawnChapter[] = [
      { key: 'm', name: 'Main', identities: ['a.mp4', 'b.mp4', 'c.mp4'] },
    ]
    const own = dropSlot(lay(view), NONE, view, 1500, 'b.mp4')
    assert.equal(applyDrop(full, from, own, drawn), full)
    // The hidden clip right after the dragged one is no obstacle either.
    const hiddenAfter: Orders = new Map([['m', ['a.mp4', 'b.mp4', 'missing.mp4', 'c.mp4']]])
    assert.equal(applyDrop(hiddenAfter, from, own, drawn), hiddenAfter)
    const before = dropSlot(lay(view), NONE, view, 0, 'c.mp4')
    assert.equal(before.beforeIdentity, 'a.mp4')
    const moved = applyDrop(full, { identity: 'c.mp4', chapter: 'm' }, before, drawn)
    assert.deepEqual(moved.get('m'), ['c.mp4', 'a.mp4', 'missing.mp4', 'b.mp4'])
    const beforeB = applyDrop(
      full,
      { identity: 'a.mp4', chapter: 'm' },
      { chapter: 'm', beforeIdentity: 'c.mp4' },
      drawn,
    )
    assert.deepEqual(beforeB.get('m'), ['missing.mp4', 'b.mp4', 'a.mp4', 'c.mp4'])
    const end = applyDrop(
      full,
      { identity: 'a.mp4', chapter: 'm' },
      { chapter: 'm', beforeIdentity: null },
      drawn,
    )
    assert.deepEqual(end.get('m'), ['missing.mp4', 'b.mp4', 'c.mp4', 'a.mp4'])
  })

  it('words use the file name of a nested identity', () => {
    const nested: DrawnChapter[] = [{ key: 'a', identities: ['sub/a.mp4', 'sub/b.mp4'] }]
    assert.equal(dropSlot(lay(nested), NONE, nested, 0, 'sub/b.mp4').words, 'Before a.mp4')
  })

  it('refuses a clip that is not drawn and a mismatched lay', () => {
    assert.throws(() => dropSlot(lay(chapters), NONE, chapters, 0, 'nope.mp4'), /no drawn chapter/)
    assert.throws(
      () => dropSlot(lay(chapters.slice(0, 1)), NONE, chapters, 0, 's1710001.mp4'),
      /lay has/,
    )
    assert.throws(() => dropSlot(lay(chapters), NONE, chapters, NaN, 's1710001.mp4'), /finite/)
  })

  it('lays 400 clips and snaps anywhere, with whole-order results', () => {
    const ids = Array.from({ length: 400 }, (_, i) => `c${String(i).padStart(3, '0')}.mp4`)
    const big: DrawnChapter[] = [
      { key: 'a', identities: ids.slice(0, 250) },
      { key: 'b', identities: ids.slice(250) },
    ]
    const l = lay(big, 2000)
    const bigOrders: Orders = new Map(big.map((c) => [c.key, c.identities]))
    const slot = dropSlot(l, NONE, big, 399 * 2000 + 600, 'c000.mp4')
    assert.equal(slot.chapter, 'b')
    assert.equal(slot.beforeIdentity, 'c399.mp4')
    const next = applyDrop(bigOrders, { identity: 'c000.mp4', chapter: 'a' }, slot)
    assert.equal(next.get('a')?.length, 249)
    assert.equal(next.get('b')?.length, 151)
    assert.equal(next.get('b')?.[149], 'c000.mp4')
    const all = [...(next.get('a') ?? []), ...(next.get('b') ?? [])]
    assert.equal(new Set(all).size, 400)
  })
})

describe('applyDrop', () => {
  it('leaves the orders alone for a clip not in the chapter', () => {
    assert.equal(
      applyDrop(
        orders,
        { identity: 'zzz.mp4', chapter: 'r0' },
        { chapter: 'r1', beforeIdentity: 's1710005.mp4' },
      ),
      orders,
    )
  })

  it('does not mutate its input', () => {
    const before = JSON.stringify([...orders])
    applyDrop(
      orders,
      { identity: 's1710001.mp4', chapter: 'r0' },
      { chapter: 'r1', beforeIdentity: 's1710004.mp4' },
    )
    assert.equal(JSON.stringify([...orders]), before)
  })
})
