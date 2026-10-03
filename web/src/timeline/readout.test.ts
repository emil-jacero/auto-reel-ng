import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { layout } from './model.ts'
import { readoutOf, readoutWords, tipOf } from './readout.ts'

const clips = (...seconds: number[]) =>
  seconds.map((s, i) => ({
    name: `s17100${String(i + 1).padStart(2, '0')}.mp4`,
    facts: { durationMs: Math.round(s * 1000), fps: 25 },
  }))

describe('the Timeline readout', () => {
  const c = clips(9, 40, 6.02)
  const lay = layout(c.map((x) => x.facts))

  it('says each number by its noun, at the same width on both sides of a boundary', () => {
    const before = readoutOf({ clip: 0, ms: 8200 }, c, lay)
    const after = readoutOf({ clip: 1, ms: 100 }, c, lay)
    assert.equal(readoutWords(before), 'Clip 0:08.20 of 0:09.00 · Event 0:08.20 of 0:55.02')
    assert.equal(readoutWords(after), 'Clip 0:00.10 of 0:40.00 · Event 0:09.10 of 0:55.02')
    for (const key of ['clip', 'event'] as const) {
      assert.equal(before[key].time.ch, after[key].time.ch)
      assert.equal(before[key].length.ch, after[key].length.ch)
    }
    assert.equal(before.name, 's1710001.mp4')
    assert.equal(after.name, 's1710002.mp4')
  })

  it('has the cell width in ch equal to the text it holds, for every position', () => {
    for (let clip = 0; clip < c.length; clip += 1) {
      for (let ms = 0; ms <= c[clip].facts.durationMs; ms += 20) {
        const r = readoutOf({ clip, ms }, c, lay)
        for (const cell of [r.clip.time, r.clip.length, r.event.time, r.event.length]) {
          assert.equal(cell.text.length, cell.ch)
        }
      }
    }
  })

  it('keeps the whole name, however long, for the tooltip', () => {
    const long = [{ name: 'IMG_20240627_201530_BURST042_final_v2.mp4', facts: { durationMs: 5000, fps: 25 } }]
    const r = readoutOf({ clip: 0, ms: 0 }, long, layout(long.map((x) => x.facts)))
    assert.equal(r.name, 'IMG_20240627_201530_BURST042_final_v2.mp4')
  })

  it('works for one clip, and holds a playhead past the end to the end', () => {
    const one = clips(12)
    const l = layout(one.map((x) => x.facts))
    assert.equal(readoutWords(readoutOf({ clip: 0, ms: 9990 }, one, l)), 'Clip 0:09.99 of 0:12.00 · Event 0:09.99 of 0:12.00')
    assert.equal(readoutWords(readoutOf({ clip: 0, ms: 10000 }, one, l)), 'Clip 0:10.00 of 0:12.00 · Event 0:10.00 of 0:12.00')
    assert.equal(readoutWords(readoutOf({ clip: 0, ms: 99999 }, one, l)), 'Clip 0:12.00 of 0:12.00 · Event 0:12.00 of 0:12.00')
  })

  it('reserves a wider clip pair for a clip of twelve minutes', () => {
    const big = clips(750, 9)
    const l = layout(big.map((x) => x.facts))
    const r = readoutOf({ clip: 1, ms: 0 }, big, l)
    assert.equal(r.clip.time.ch, 8)
    assert.equal(r.clip.time.text, '00:00.00')
    assert.equal(r.clip.length.text, '00:09.00')
    assert.equal(r.event.time.ch, 8)
  })

  it('does not trip on a playhead for a clip that is gone: it reads the start', () => {
    const r = readoutOf({ clip: 7, ms: 3000 }, c, lay)
    assert.equal(r.name, 's1710001.mp4')
    assert.equal(r.clip.time.text, '0:00.00')
  })
})

describe('the trim tip', () => {
  it('writes the edge to the millisecond at one width for 1.250 and 1.300 s of a 6.02 s clip', () => {
    const a = tipOf(1250, 6020)
    const b = tipOf(1300, 6020)
    assert.equal(a.text, '0:01.250')
    assert.equal(b.text, '0:01.300')
    assert.equal(a.text.length, b.text.length)
    assert.equal(a.ch, b.ch)
    assert.equal(a.ch, a.text.length)
  })

  it('holds an edge past the clip to the clip\'s end', () => {
    assert.equal(tipOf(7000, 6020).text, '0:06.020')
  })
})
