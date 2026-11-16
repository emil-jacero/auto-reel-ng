import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Orders } from '../edit/draft.ts'
import { layout } from './model.ts'
import { applyDrop, dropSlot } from './reorder.ts'
import type { DrawnChapter } from './reorder.ts'


/** Clips of `len` ms each, laid in the chapters' order. */
function lay(chapters: readonly DrawnChapter[], len = 1000) {
  const count = chapters.reduce((sum, c) => sum + c.identities.length, 0)
  return layout(Array.from({ length: count }, () => ({ durationMs: len, fps: 25 })))
}

const chapters: DrawnChapter[] = [
  { key: 'r0', name: 'Main', identities: ['s1710001.mp4', 's1710002.mp4', 's1710003.mp4'] },
  { key: 'r1', name: 'Kvällen', identities: ['s1710005.mp4', 's1710004.mp4'] },
]
const orders: Orders = new Map(chapters.map((c) => [c.key, c.identities]))

describe('dropSlot', () => {
  it('reorders inside a chapter', () => {
    // s1710002 spans 1000..2000; its centre is dragged to the boundary at 0.
    const slot = dropSlot(lay(chapters), chapters, 100, 's1710002.mp4')
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
    const slot = dropSlot(lay(chapters), chapters, 3000, 's1710001.mp4')
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
    const slot = dropSlot(lay(chapters), chapters, 2900, 's1710004.mp4')
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
      const slot = dropSlot(lay(chapters), chapters, ms, 's1710002.mp4')
      assert.equal(slot.chapter, 'r0')
      assert.equal(slot.index, 1)
      assert.equal(applyDrop(orders, { identity: 's1710002.mp4', chapter: 'r0' }, slot), orders)
    }
  })

  it('prefers the own place on a tie with another boundary', () => {
    const slot = dropSlot(lay(chapters), chapters, 1500, 's1710002.mp4')
    assert.equal(slot.index, 1)
  })

  it('snaps to a boundary between chapters: the end of the earlier one', () => {
    const slot = dropSlot(lay(chapters), chapters, 3000, 's1710001.mp4')
    assert.equal(slot.chapter, 'r0')
    assert.equal(slot.index, 2)
  })

  it('drops at the start of the next chapter nearer its first clip', () => {
    const slot = dropSlot(lay(chapters), chapters, 3900, 's1710001.mp4')
    assert.equal(slot.chapter, 'r1')
    assert.equal(slot.index, 1)
    assert.equal(slot.beforeIdentity, 's1710004.mp4')
  })

  it('drops after the last clip of the last chapter and beyond the track', () => {
    for (const ms of [5000, 99999]) {
      const slot = dropSlot(lay(chapters), chapters, ms, 's1710001.mp4')
      assert.equal(slot.chapter, 'r1')
      assert.equal(slot.index, 2)
      assert.equal(slot.words, 'At the end of Kvällen')
    }
    assert.equal(dropSlot(lay(chapters), chapters, -500, 's1710003.mp4').index, 0)
  })

  it('offers an empty chapter (a card between chapters) one boundary where it sits', () => {
    const withEmpty: DrawnChapter[] = [
      chapters[0],
      { key: 'r2', name: 'Empty', identities: [] },
      chapters[1],
    ]
    const o: Orders = new Map(withEmpty.map((c) => [c.key, c.identities]))
    // The boundary at 3000 is the end of Main, Empty's, and Kvällen's start: Main wins.
    assert.equal(dropSlot(lay(withEmpty), withEmpty, 2900, 's1710004.mp4').chapter, 'r0')
    // From the first chapter's perspective the tie also keeps the earliest boundary.
    const slot = dropSlot(lay(withEmpty), withEmpty, 3000, 's1710001.mp4')
    assert.equal(slot.chapter, 'r0')
    const solo: DrawnChapter[] = [{ key: 'a', identities: [] }, { key: 'b', identities: ['x.mp4'] }]
    const s = dropSlot(lay(solo), solo, 0, 'x.mp4')
    assert.equal(s.chapter, 'a')
    assert.equal(s.index, 0)
    const next = applyDrop(
      new Map([['a', []], ['b', ['x.mp4']]]),
      { identity: 'x.mp4', chapter: 'b' },
      s,
    )
    assert.deepEqual(next.get('a'), ['x.mp4'])
    assert.deepEqual(next.get('b'), [])
    void o
  })

  it('words use the file name of a nested identity', () => {
    const nested: DrawnChapter[] = [{ key: 'a', identities: ['sub/a.mp4', 'sub/b.mp4'] }]
    assert.equal(dropSlot(lay(nested), nested, 0, 'sub/b.mp4').words, 'Before a.mp4')
  })

  it('refuses a clip that is not drawn and a mismatched lay', () => {
    assert.throws(() => dropSlot(lay(chapters), chapters, 0, 'nope.mp4'), /no drawn chapter/)
    assert.throws(() => dropSlot(lay(chapters.slice(0, 1)), chapters, 0, 's1710001.mp4'), /lay has/)
    assert.throws(() => dropSlot(lay(chapters), chapters, NaN, 's1710001.mp4'), /finite/)
  })

  it('lays 400 clips and snaps anywhere, with whole-order results', () => {
    const ids = Array.from({ length: 400 }, (_, i) => `c${String(i).padStart(3, '0')}.mp4`)
    const big: DrawnChapter[] = [
      { key: 'a', identities: ids.slice(0, 250) },
      { key: 'b', identities: ids.slice(250) },
    ]
    const l = lay(big, 2000)
    const bigOrders: Orders = new Map(big.map((c) => [c.key, c.identities]))
    const slot = dropSlot(l, big, 399 * 2000 + 600, 'c000.mp4')
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
      applyDrop(orders, { identity: 'zzz.mp4', chapter: 'r0' }, { chapter: 'r1', index: 0 }),
      orders,
    )
  })

  it('does not mutate its input', () => {
    const before = JSON.stringify([...orders])
    applyDrop(orders, { identity: 's1710001.mp4', chapter: 'r0' }, { chapter: 'r1', index: 1 })
    assert.equal(JSON.stringify([...orders]), before)
  })
})
