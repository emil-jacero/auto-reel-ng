import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { cutSpans, keptExtent, layout } from './model.ts'
import { readoutOf, readoutScales, readoutWords, tipOf } from './readout.ts'

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

describe('held readout scales', () => {
  it('give the same readout as scales worked out each time', () => {
    const c = clips(8, 12)
    const lay = layout(c.map((x) => x.facts))
    const at = { clip: 1, ms: 4321 }
    assert.deepEqual(readoutOf(at, c, lay, readoutScales(c, lay)), readoutOf(at, c, lay))
  })
})

describe('the readout in a title card', () => {
  const c = clips(60, 40)
  const lay = layout(c.map((x) => x.facts))
  // 3 s of black card before the first clip: the track is 3 s longer than the footage.
  const track = { ...lay, startsMs: [3000, 63000], totalMs: lay.totalMs + 3000 }
  const card = { chapter: 0, name: '', ms: 1200, lengthMs: 3000 }

  it('reads Card time of length and counts the card in the Event time', () => {
    const r = readoutOf({ clip: 0, ms: 0, card }, c, track)
    assert.equal(readoutWords(r), 'Card 0:01.20 of 0:03.00 · Event 0:01.20 of 1:43.00')
    assert.equal(r.name, 'Opening')
    assert.equal(r.label, 'Card')
  })

  it('counts three seconds into the opening card as Event 0:03.00', () => {
    const r = readoutOf({ clip: 0, ms: 0, card: { ...card, ms: 3000 } }, c, track)
    assert.match(readoutWords(r), /Event 0:03\.00 of 1:43\.00$/)
  })

  it('keeps the width of its cells between a card and a clip', () => {
    const inCard = readoutOf({ clip: 0, ms: 0, card }, c, track)
    const inClip = readoutOf({ clip: 0, ms: 500 }, c, track)
    assert.equal(inCard.clip.time.ch, inClip.clip.time.ch)
    assert.equal(inCard.clip.length.ch, inClip.clip.length.ch)
    assert.equal(inClip.label, 'Clip')
    assert.equal(readoutOf({ clip: 1, ms: 0, card: { ...card, chapter: 1, name: 'Dag 2' } }, c, track).name, 'Dag 2')
  })

  it('holds a card longer than every clip to its own scale', () => {
    const short = clips(2)
    const l = { startsMs: [75000], totalMs: 77000, inMs: [0] }
    const scales = readoutScales(short, l, 75000)
    const r = readoutOf({ clip: 0, ms: 0, card: { chapter: 0, name: '', ms: 70000, lengthMs: 75000 } }, short, l, scales)
    assert.equal(r.clip.length.text, '1:15.00')
  })
})

describe('the readout on a rippled track (timeline-ripple-layout)', () => {
  const trimmed = (name: string, durationMs: number, cuts: { in: number; out: number }[]) => {
    const facts = { durationMs, fps: 25 }
    return { name, facts, kept: keptExtent(cutSpans(cuts, durationMs), durationMs) }
  }
  const c = [
    trimmed('A', 10000, [{ in: 0, out: 2 }]),
    trimmed('B', 8000, [{ in: 6, out: 8 }]),
    trimmed('C', 5000, [{ in: 1, out: 2 }]),
  ]
  const lay = layout(c.map((x) => ({ ...x.facts, ...x.kept })))

  it('says the clip’s own time and full length, and the rippled event time', () => {
    assert.equal(readoutWords(readoutOf({ clip: 0, ms: 2000 }, c, lay)), 'Clip 0:02.00 of 0:10.00 · Event 0:00.00 of 0:19.00')
    assert.equal(readoutWords(readoutOf({ clip: 0, ms: 5000 }, c, lay)), 'Clip 0:05.00 of 0:10.00 · Event 0:03.00 of 0:19.00')
    assert.equal(readoutWords(readoutOf({ clip: 1, ms: 5960 }, c, lay)), 'Clip 0:05.96 of 0:08.00 · Event 0:13.96 of 0:19.00')
  })

  it('reads a playhead left inside a leading cut as the clip’s first kept frame', () => {
    assert.equal(readoutWords(readoutOf({ clip: 0, ms: 1000 }, c, lay)), 'Clip 0:02.00 of 0:10.00 · Event 0:00.00 of 0:19.00')
  })
})
