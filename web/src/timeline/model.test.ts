import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { playheadWords, skipSpans, toMs } from '../preview/playback.ts'
import {
  clampPps,
  clipAt,
  clipToLayout,
  clipFacts,
  cutRects,
  cutSpans,
  DEFAULT_PPS,
  edgeCut,
  fitPps,
  frameMs,
  interiorSpans,
  keptExtent,
  layout,
  layoutToClip,
  MAX_PPS,
  minCutMs,
  MIN_PPS,
  ModelError,
  movieLengthMs,
  nearestFrame,
  pxToTime,
  tickStepMs,
  timeToPx,
  visibleClips,
  visibleTicks,
  zoomAt,
  anchorFor,
  canvasWidth,
  fitCanvas,
  ppsToSlider,
  SLIDER_STEPS,
  sliderToPps,
  wheelFactor,
  ZOOM_STEP,
} from './model.ts'
import type { ClipFacts, KeptFacts, Layout, Ms, View } from './model.ts'

/** A small deterministic generator, so a property loop fails the same way twice. */
function random(seed: number): () => number {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const RATES = [23.976, 24, 25, 29.97, 30, 50, 59.94]

/** `count` clips of `seconds` each, at 25 fps. */
function clips(count: number, seconds: number): ClipFacts[] {
  return Array.from({ length: count }, () => clipFacts(seconds, 25))
}

describe('units and frames', () => {
  it('rounds to the clip’s own frames: 29.97 fps gives 1,001 ms, 50 fps 1,020 ms', () => {
    assert.equal(nearestFrame(1015, 29.97), 1001)
    assert.equal(nearestFrame(1015, 50), 1020)
    assert.equal(nearestFrame(1015, 25), 1000)
  })

  it('a frame time is rounded to the millisecond: frame 1 at 29.97 fps is 33 ms', () => {
    assert.equal(frameMs(1, 29.97), 33)
    assert.equal(frameMs(30, 29.97), 1001)
    assert.equal(frameMs(0, 25), 0)
  })

  it('returns whole milliseconds on every common rate for 0 to 10,000 ms', () => {
    for (const fps of RATES) {
      for (let ms = 0; ms <= 10000; ms += 7) {
        const frame = nearestFrame(ms, fps)
        assert.ok(Number.isInteger(frame), `${ms} ms at ${fps} fps gave ${frame}`)
        assert.equal(nearestFrame(frame, fps), frame, `a frame time stays on its frame at ${fps}`)
      }
    }
  })

  it('the shortest cut is three frames, itself a whole number of ms', () => {
    assert.equal(minCutMs(25), 120)
    assert.equal(minCutMs(29.97), 100)
    assert.equal(minCutMs(50), 60)
  })

  it('refuses a duration or a rate that is not above zero, naming it', () => {
    for (const bad of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      assert.throws(() => clipFacts(bad, 25), (e) => e instanceof ModelError && /duration/.test(e.message))
      assert.throws(() => clipFacts(6, bad), (e) => e instanceof ModelError && /fps/.test(e.message))
    }
    assert.throws(() => clipFacts(0.0001, 25), ModelError)
    assert.throws(() => nearestFrame(100, 0), /fps/)
    assert.throws(() => frameMs(3, -25), /fps/)
    assert.throws(() => minCutMs(Number.NaN), /fps/)
  })

  it('builds a clip’s facts from seconds, once, to the millisecond', () => {
    assert.deepEqual(clipFacts(24.96, 25), { durationMs: 24960, fps: 25 })
    assert.deepEqual(clipFacts(6.0833333, 29.97), { durationMs: 6083, fps: 29.97 })
  })
})

describe('layout and pixels', () => {
  const mixed = layout([clipFacts(24.96, 25), clipFacts(6.08, 25), clipFacts(0.48, 25)])

  it('lays clips of mixed durations end to end', () => {
    assert.deepEqual(mixed, { startsMs: [0, 24960, 31040], totalMs: 31520, inMs: [0, 0, 0] })
  })

  it('an empty list has no length and no clip at any time', () => {
    const none = layout([])
    assert.deepEqual(none, { startsMs: [], totalMs: 0, inMs: [] })
    assert.equal(clipAt(none, 0), null)
    assert.equal(clipAt(none, 5000), null)
  })

  it('refuses a clip without a usable duration', () => {
    assert.throws(() => layout([{ durationMs: 0, fps: 25 }]), /durationMs/)
    assert.throws(() => layout([{ durationMs: Number.NaN, fps: 25 }]), /durationMs/)
    assert.throws(() => layout([{ durationMs: 1000.5, fps: 25 }]), /whole milliseconds/)
  })

  it('finds the clip that holds a time: a boundary is the later clip', () => {
    assert.equal(clipAt(mixed, -5), 0)
    assert.equal(clipAt(mixed, 0), 0)
    assert.equal(clipAt(mixed, 24959), 0)
    assert.equal(clipAt(mixed, 24960), 1)
    assert.equal(clipAt(mixed, 31039), 1)
    assert.equal(clipAt(mixed, 31040), 2)
    assert.equal(clipAt(mixed, mixed.totalMs), 2)
    assert.equal(clipAt(mixed, 40000), 2)
  })

  it('maps pixels to a whole millisecond, not clamped', () => {
    assert.equal(pxToTime(137, 40), 3425)
    assert.equal(pxToTime(10, 7), 1429)
    assert.equal(pxToTime(-40, 40), -1000)
    assert.equal(pxToTime(1e9, 40), 25e9)
    assert.equal(timeToPx(3425, 40), 137)
    assert.equal(timeToPx(-1000, 40), -40)
  })

  it('refuses a scale that is not above zero', () => {
    for (const pps of [0, -3, Number.NaN]) {
      assert.throws(() => pxToTime(10, pps), /pps/)
      assert.throws(() => timeToPx(10, pps), /pps/)
    }
  })
})

/** A clip of `durationMs` at 25 fps with its cuts (seconds) and the extent they leave. */
function kept(durationMs: Ms, cuts: { in: number; out: number }[]): KeptFacts & { cuts: typeof cuts } {
  return { durationMs, fps: 25, ...keptExtent(cutSpans(cuts, durationMs), durationMs), cuts }
}

describe('the kept extent (timeline-ripple-layout)', () => {
  // "Edge cuts shorten the layout": A has a leading cut, B a trailing one, C an interior one.
  const A = kept(10000, [{ in: 0, out: 2 }])
  const B = kept(8000, [{ in: 6, out: 8 }])
  const C = kept(5000, [{ in: 1, out: 2 }])
  const lay = layout([A, B, C])

  it('edge cuts shorten the layout: starts 0, 8,000 and 14,000 ms, total 19,000 ms', () => {
    assert.deepEqual(lay, { startsMs: [0, 8000, 14000], totalMs: 19000, inMs: [2000, 0, 0] })
  })

  it('a wholly cut clip takes no length, and its start is held by the next clip', () => {
    const three = layout([kept(4000, []), kept(4000, [{ in: 0, out: 4 }]), kept(4000, [])])
    assert.deepEqual(three.startsMs, [0, 4000, 4000])
    assert.equal(three.totalMs, 8000)
    assert.equal(clipAt(three, 4000), 2)
    assert.equal(clipAt(three, 3999), 0)
  })

  it('never gives a clip of no length: wholly cut first, middle and last clips', () => {
    const none = (d: Ms) => kept(d, [{ in: 0, out: d / 1000 }])
    const first = layout([none(3000), kept(4000, []), kept(4000, [])])
    assert.deepEqual(first.startsMs, [0, 0, 4000])
    assert.equal(clipAt(first, -5), 1)
    assert.equal(clipAt(first, 0), 1)
    const last = layout([kept(4000, []), kept(4000, []), none(3000)])
    assert.deepEqual(last.startsMs, [0, 4000, 8000])
    assert.equal(clipAt(last, 8000), 1)
    assert.equal(clipAt(last, 50000), 1)
  })

  it('extents from edge cuts: joined leading spans, and a trailing cut with an interior one', () => {
    const one = [
      { in: 0, out: 2 },
      { in: 1.5, out: 3 },
    ]
    const spansOne = cutSpans(one, 10000)
    const extentOne = keptExtent(spansOne, 10000)
    assert.deepEqual(extentOne, { inMs: 3000, outMs: 10000 })
    assert.deepEqual(interiorSpans(spansOne, extentOne), [])
    assert.ok(one.every((cut) => edgeCut(cut, extentOne, 10000)))
    const two = [
      { in: 9.95, out: 10 },
      { in: 4, out: 5 },
    ]
    const spansTwo = cutSpans(two, 10000)
    const extentTwo = keptExtent(spansTwo, 10000)
    assert.deepEqual(extentTwo, { inMs: 0, outMs: 9950 })
    assert.deepEqual(interiorSpans(spansTwo, extentTwo), [{ from: 4000, to: 5000 }])
    assert.deepEqual(
      two.map((cut) => edgeCut(cut, extentTwo, 10000)),
      [true, false],
    )
  })

  it('a cut ending just short of the end, or past it, is a trailing cut', () => {
    assert.deepEqual(keptExtent(cutSpans([{ in: 5, out: 5.95 }], 6020), 6020), { inMs: 0, outMs: 5000 })
    assert.deepEqual(keptExtent(cutSpans([{ in: 5, out: 7 }], 6020), 6020), { inMs: 0, outMs: 5000 })
    // 100 ms short is footage Play shows: not a trailing cut.
    assert.deepEqual(keptExtent(cutSpans([{ in: 5, out: 5.92 }], 6020), 6020), { inMs: 0, outMs: 6020 })
  })

  it('the trailing cut is the first span Play ends the clip at', () => {
    // Both spans end within 0.1 s of the end; Play stops at the first (`skipAt`).
    const spans = cutSpans(
      [
        { in: 5.91, out: 5.93 },
        { in: 5.95, out: 6 },
      ],
      6000,
    )
    const extent = keptExtent(spans, 6000)
    assert.deepEqual(extent, { inMs: 0, outMs: 5910 })
    assert.deepEqual(interiorSpans(spans, extent), [])
  })

  it('a span that is both leading and trailing leaves the extent empty', () => {
    assert.deepEqual(keptExtent(cutSpans([{ in: 0, out: 5 }], 5050), 5050), { inMs: 0, outMs: 0 })
    assert.deepEqual(keptExtent(cutSpans([{ in: 0, out: 9 }], 5050), 5050), { inMs: 0, outMs: 0 })
    assert.equal(edgeCut({ in: 1, out: 2 }, { inMs: 0, outMs: 0 }, 5050), true)
  })

  it('no cut keeps the whole clip; a removed or empty cut is no edge cut', () => {
    assert.deepEqual(keptExtent([], 7000), { inMs: 0, outMs: 7000 })
    assert.equal(edgeCut({ in: 0, out: 2, removed: true }, { inMs: 2000, outMs: 7000 }, 7000), false)
    assert.equal(edgeCut({ in: 8, out: 9 }, { inMs: 0, outMs: 7000 }, 7000), false)
  })

  it('round trip: every kept time maps to the layout and back to itself', () => {
    const all = [A, B, C]
    all.forEach((clip, index) => {
      for (let ms = clip.inMs ?? 0; ms < (clip.outMs ?? clip.durationMs); ms += 1) {
        const t = clipToLayout(lay, index, ms)
        assert.deepEqual(layoutToClip(lay, t), { clip: index, ms })
      }
    })
    assert.equal(clipToLayout(lay, 0, 5000), 3000)
    assert.deepEqual(layoutToClip(lay, 3000), { clip: 0, ms: 5000 })
  })

  it('the movie keeps the render’s arithmetic: 18 s of the 19 s track here', () => {
    assert.equal(movieLengthMs([A, B, C]), 18000)
  })

  it('handle rectangles leave out edge cuts and start at the block’s left edge', () => {
    const cuts = [
      { in: 0, out: 2 },
      { in: 4, out: 5 },
      { in: 9, out: 10 },
    ]
    const extent = keptExtent(cutSpans(cuts, 10000), 10000)
    assert.deepEqual(cutRects(cuts, 10000, 40, extent), [{ index: 1, left: 80, width: 40 }])
  })
})

describe('zoom', () => {
  it('zooms about the pointer: 17.5 s stays under x = 300 and the scroll is 1,100', () => {
    const view: View = { pps: 40, scrollLeft: 400, width: 800 }
    const zoomed = zoomAt(view, 2, 300, 120000)
    assert.deepEqual(zoomed, { pps: 80, scrollLeft: 1100, width: 800 })
    assert.equal((view.scrollLeft + 300) / view.pps, 17.5)
    assert.equal((zoomed.scrollLeft + 300) / zoomed.pps, 17.5)
  })

  it('holds the scale between 4 and 240', () => {
    assert.equal(zoomAt({ pps: 200, scrollLeft: 0, width: 800 }, 10, 0, 120000).pps, MAX_PPS)
    assert.equal(zoomAt({ pps: 5, scrollLeft: 0, width: 800 }, 0.1, 0, 120000).pps, MIN_PPS)
    assert.equal(clampPps(1000), 240)
    assert.equal(clampPps(0.5), 4)
    assert.equal(clampPps(40), 40)
  })

  it('never scrolls below zero or past the end', () => {
    // 5 s at 20 px/s is 100 px, in an 800 px view: nothing to scroll.
    assert.equal(zoomAt({ pps: 40, scrollLeft: 100, width: 800 }, 0.5, 0, 5000).scrollLeft, 0)
    // 120 s at 80 px/s is 9,600 px: the furthest scroll is 8,800.
    const far = zoomAt({ pps: 40, scrollLeft: 4700, width: 800 }, 2, 700, 120000)
    assert.equal(far.scrollLeft, 8800)
    assert.equal(zoomAt({ pps: 40, scrollLeft: 0, width: 800 }, 2, 300, 120000).scrollLeft, 300)
    assert.equal(zoomAt({ pps: 80, scrollLeft: 0, width: 800 }, 0.5, 300, 120000).scrollLeft, 0)
  })

  it('keeps the time under the anchor within a pixel, unless a bound applied', () => {
    const next = random(7)
    let kept = 0
    for (let i = 0; i < 200; i += 1) {
      const totalMs = Math.round(next() * 600000) + 1000
      const width = 300 + Math.round(next() * 1200)
      const pps = MIN_PPS + next() * (MAX_PPS - MIN_PPS)
      const factor = 0.25 + next() * 4
      const longest = Math.max(0, (totalMs * pps) / 1000 - width)
      const view: View = { pps, scrollLeft: next() * longest, width }
      const anchorX = next() * width
      const zoomed = zoomAt(view, factor, anchorX, totalMs)
      assert.ok(zoomed.scrollLeft >= 0)
      assert.ok(zoomed.scrollLeft <= Math.max(0, (totalMs * zoomed.pps) / 1000 - width) + 1e-9)
      const before = (view.scrollLeft + anchorX) / view.pps
      const after = (zoomed.scrollLeft + anchorX) / zoomed.pps
      const raw = (before * zoomed.pps - anchorX)
      const clamped = zoomed.pps !== pps * factor || raw < 0 || raw > longest
      if (!clamped) {
        kept += 1
        assert.ok(Math.abs(after - before) < 1 / zoomed.pps, `moved ${after - before} s`)
      }
    }
    assert.ok(kept > 20, `only ${kept} of 200 cases were free of a bound`)
  })

  it('fits the whole timeline to the width, within the bounds', () => {
    assert.equal(fitPps(60000, 1200), 20)
    assert.equal(fitPps(3000, 1200), 240)
    assert.equal(fitPps(10 * 3600 * 1000, 1200), 4)
    assert.equal(fitPps(0, 1200), DEFAULT_PPS)
    assert.equal(DEFAULT_PPS, 40)
  })

  it('picks the first tick step at least 70 px wide', () => {
    assert.equal(tickStepMs(80), 1000)
    assert.equal(tickStepMs(240), 500)
    assert.equal(tickStepMs(60), 2000)
    assert.equal(tickStepMs(70), 1000)
    assert.equal(tickStepMs(40), 2000)
    assert.equal(tickStepMs(20), 5000)
    // At the slowest allowed scale 30 s is 120 px wide: the first step that is 70 px or more.
    assert.equal(tickStepMs(MIN_PPS), 30000)
    // Only a scale below the allowed range leaves no step wide enough.
    assert.equal(tickStepMs(0.1), 600000)
  })

  it('refuses a scale, width, factor or length that cannot be used', () => {
    const view: View = { pps: 40, scrollLeft: 0, width: 800 }
    assert.throws(() => zoomAt({ ...view, pps: 0 }, 2, 0, 1000), /pps/)
    assert.throws(() => zoomAt({ ...view, width: 0 }, 2, 0, 1000), /width/)
    assert.throws(() => zoomAt({ ...view, width: Number.NaN }, 2, 0, 1000), /width/)
    assert.throws(() => zoomAt(view, 0, 0, 1000), /factor/)
    assert.throws(() => zoomAt(view, 2, Number.NaN, 1000), /anchorX/)
    assert.throws(() => zoomAt(view, 2, 0, -1), /totalMs/)
    assert.throws(() => fitPps(1000, 0), /width/)
    assert.throws(() => fitPps(Number.NaN, 800), /totalMs/)
    assert.throws(() => clampPps(-1), /pps/)
    assert.throws(() => tickStepMs(0), /pps/)
  })
})

/** A layout whose `startsMs` counts the reads of its elements. */
function counted(l: Layout): { layout: Layout; reads: () => number } {
  let reads = 0
  const startsMs = new Proxy(l.startsMs as Ms[], {
    get(target, key, receiver) {
      if (typeof key === 'string' && /^\d+$/.test(key)) {
        reads += 1
      }
      return Reflect.get(target, key, receiver)
    },
  })
  return { layout: { startsMs, totalMs: l.totalMs, inMs: l.inMs }, reads: () => reads }
}
describe('windowing', () => {
  const big = layout(clips(5000, 25))

  it('5,000 clips at 40 px/s: a view at 600,000 px holds clips 599 and 600, not 601', () => {
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 600000, width: 800 }, 200), [599, 600])
  })

  it('a clip that only meets the margin’s edge is out, one a pixel inside is in', () => {
    // Clip 601 starts at 601,000 px: the margin ends there.
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 600000, width: 800 }, 200)?.[1], 600)
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 600001, width: 800 }, 200), [599, 601])
    // Clip 598 ends at 599,000 px, the margin's other edge.
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 599200, width: 800 }, 200)?.[0], 599)
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 599199, width: 800 }, 200)?.[0], 598)
  })

  it('one clip wider than the view is the whole range', () => {
    const one = layout([clipFacts(600, 25)])
    assert.deepEqual(visibleClips(one, { pps: 240, scrollLeft: 50000, width: 800 }, 200), [0, 0])
  })

  it('a view past the end, or an empty layout, gives no clip', () => {
    const one = layout([clipFacts(600, 25)])
    assert.equal(visibleClips(one, { pps: 240, scrollLeft: 144000 + 201, width: 800 }, 200), null)
    assert.equal(visibleClips(big, { pps: 40, scrollLeft: 5000 * 1000 + 300, width: 800 }, 200), null)
    assert.equal(visibleClips(layout([]), { pps: 40, scrollLeft: 0, width: 800 }, 200), null)
  })

  it('the first and last clip at the two ends', () => {
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 0, width: 800 }, 200), [0, 0])
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 0, width: 1801 }, 200), [0, 2])
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: 0, width: 1800 }, 200), [0, 1])
    const end = 5000 * 1000 - 800
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: end, width: 800 }, 200), [4999, 4999])
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: end - 1000, width: 801 }, 0), [4998, 4999])
  })

  it('a view scrolled before the start is clipped to the first clips', () => {
    assert.deepEqual(visibleClips(big, { pps: 40, scrollLeft: -500, width: 800 }, 200), [0, 0])
    assert.equal(visibleClips(big, { pps: 40, scrollLeft: -1500, width: 800 }, 200), null)
  })

  it('agrees with a plain filter over every clip', () => {
    const next = random(3)
    const some = layout(Array.from({ length: 300 }, () => clipFacts(0.2 + next() * 30, 25)))
    for (let i = 0; i < 300; i += 1) {
      const view: View = {
        pps: MIN_PPS + next() * (MAX_PPS - MIN_PPS),
        scrollLeft: next() * ((some.totalMs / 1000) * 100),
        width: 200 + next() * 1500,
      }
      const overscan = next() * 300
      const lo = view.scrollLeft - overscan
      const hi = view.scrollLeft + view.width + overscan
      const want = some.startsMs
        .map((start, at) => ({ at, from: (start * view.pps) / 1000, to: (((some.startsMs[at + 1] ?? some.totalMs)) * view.pps) / 1000 }))
        .filter(({ from, to }) => from < hi && to > lo)
        .map(({ at }) => at)
      const got = visibleClips(some, view, overscan)
      if (want.length === 0) {
        assert.equal(got, null)
      } else {
        assert.deepEqual(got, [want[0], want[want.length - 1]])
      }
    }
  })

  it('reads a bounded number of clips: 5,000 or 50,000 cost about the same', () => {
    const view: View = { pps: 40, scrollLeft: 600000, width: 800 }
    const small = counted(big)
    visibleClips(small.layout, view, 200)
    assert.ok(small.reads() <= 40, `${small.reads()} reads for 5,000 clips`)
    const huge = counted(layout(clips(50000, 25)))
    visibleClips(huge.layout, view, 200)
    assert.ok(huge.reads() <= small.reads() + 4, `${huge.reads()} reads for 50,000, ${small.reads()} for 5,000`)
  })

  it('ticks near the view only, within the timeline', () => {
    const view: View = { pps: 40, scrollLeft: 10000, width: 800 }
    // 40 px/s ticks every 2 s; the view and margin run 245 s to 275 s.
    assert.deepEqual(visibleTicks(big, view, 200), { stepMs: 2000, first: 123, last: 137 })
    // At the start, none before zero.
    assert.deepEqual(visibleTicks(big, { ...view, scrollLeft: 0 }, 200), { stepMs: 2000, first: 0, last: 12 })
    // Past the end of a short timeline there are none to draw.
    const short = layout(clips(1, 10))
    assert.deepEqual(visibleTicks(short, { ...view, scrollLeft: 0 }, 200), { stepMs: 2000, first: 0, last: 5 })
    const gone = visibleTicks(short, { ...view, scrollLeft: 5000 }, 0)
    assert.ok(gone.last < gone.first)
  })
})

describe('cut spans and rectangles', () => {
  it('imports playback.ts under Node (the extensions on its imports)', () => {
    assert.deepEqual(skipSpans([{ in: 1, out: 2 }], 10000), [{ from: 1000, to: 2000 }])
    assert.equal(toMs(0.96), 960)
  })

  it('overlapping cuts form one span, count once, and keep two rectangles', () => {
    const cuts = [
      { in: 1, out: 3 },
      { in: 2, out: 4 },
    ]
    assert.deepEqual(cutSpans(cuts, 10000), [{ from: 1000, to: 4000 }])
    assert.equal(movieLengthMs([{ durationMs: 10000, fps: 25, cuts }]), 7000)
    assert.deepEqual(cutRects(cuts, 10000, 40), [
      { index: 0, left: 40, width: 80 },
      { index: 1, left: 80, width: 80 },
    ])
  })

  it('draws a cut past the end up to the end', () => {
    assert.deepEqual(cutRects([{ in: 5, out: 7 }], 6080, 100), [{ index: 0, left: 500, width: 108 }])
  })

  it('a cut wholly past the end, an empty cut and a removed cut have no rectangle', () => {
    const cuts = [
      { in: 7, out: 8 },
      { in: 2, out: 2 },
      { in: 1, out: 2, removed: true },
      { in: 3, out: 4 },
    ]
    assert.deepEqual(cutRects(cuts, 6080, 100), [{ index: 3, left: 300, width: 100 }])
  })

  it('a cut that starts before the clip is drawn from its start', () => {
    assert.deepEqual(cutRects([{ in: -1, out: 1 }], 6080, 100), [{ index: 0, left: 0, width: 100 }])
  })

  it('the movie is the clips less their spans, over several clips', () => {
    const movie = movieLengthMs([
      { durationMs: 24960, fps: 25, cuts: [{ in: 0, out: 2.4 }, { in: 14, out: 17.2 }] },
      { durationMs: 6080, fps: 25, cuts: [{ in: 5, out: 7 }, { in: 1, out: 2, removed: true }] },
      { durationMs: 480, fps: 25, cuts: [] },
    ])
    assert.equal(movie, 24960 - 2400 - 3200 + (6080 - 1080) + 480)
    assert.equal(movieLengthMs([]), 0)
  })

  it('a cut over the whole clip takes the clip out of the movie', () => {
    assert.equal(movieLengthMs([{ durationMs: 6080, fps: 25, cuts: [{ in: 0, out: 9 }] }]), 0)
  })

  it('a handle is named by the Cuts panel number: its place in the list, plus one', () => {
    // Listed 14 to 17.2 s then 0 to 2.4 s: the rectangles carry the list place, so the
    // two cuts are "cut 1" and "cut 2" as the panel and playheadWords call them, and
    // no two share a name whatever the order in the file.
    const cuts = [
      { in: 14, out: 17.2 },
      { in: 0, out: 2.4 },
    ]
    const rects = cutRects(cuts, 24960, 40)
    assert.deepEqual(
      rects.map((rect) => rect.index + 1),
      [1, 2],
    )
    assert.match(playheadWords(1000, 24960, cuts), /in cut 2$/)
    assert.match(playheadWords(15000, 24960, cuts), /in cut 1$/)
  })

  it('a removed cut has no rectangle and the others keep their list number', () => {
    const cuts = [
      { in: 0, out: 1, removed: true },
      { in: 5, out: 6 },
      { in: 2, out: 3 },
    ]
    assert.deepEqual(
      cutRects(cuts, 24960, 40).map((rect) => rect.index + 1),
      [2, 3],
    )
  })

  it('refuses a scale that is not above zero', () => {
    assert.throws(() => cutRects([{ in: 0, out: 1 }], 1000, 0), /pps/)
  })

  it('refuses a duration that is not a finite number above zero, never replaces it', () => {
    for (const bad of [Number.NaN, 0, -5, Infinity, undefined as unknown as number]) {
      assert.throws(() => cutRects([{ in: 1, out: 2 }], bad, 40), ModelError)
      assert.throws(() => cutSpans([{ in: 1, out: 2 }], bad), ModelError)
      assert.throws(() => movieLengthMs([{ durationMs: bad, fps: 25, cuts: [] }]), /durationMs/)
    }
  })

  it('movieLengthMs refuses a clip whose rate is not a finite number above zero', () => {
    for (const bad of [Number.NaN, 0, -25, Infinity]) {
      assert.throws(() => movieLengthMs([{ durationMs: 1000, fps: bad, cuts: [] }]), /fps/)
    }
  })

  it('clipAt refuses a time that is not finite', () => {
    const l = layout([{ durationMs: 1000, fps: 25 }])
    assert.throws(() => clipAt(l, Number.NaN), ModelError)
    assert.throws(() => clipAt(l, Infinity), ModelError)
  })
})

describe('purity and dependencies', () => {
  const root = new URL('../../', import.meta.url)

  it('the dependencies stay React, React DOM and the three dnd-kit packages', () => {
    const pkg = JSON.parse(readFileSync(new URL('package.json', root), 'utf8')) as {
      dependencies: Record<string, string>
    }
    assert.deepEqual(Object.keys(pkg.dependencies).sort(), [
      '@dnd-kit/core',
      '@dnd-kit/sortable',
      '@dnd-kit/utilities',
      'react',
      'react-dom',
    ])
  })

  it('the model imports only the repo’s own pure modules', () => {
    const source = readFileSync(new URL('src/timeline/model.ts', root), 'utf8')
    const specifiers = [...source.matchAll(/^(?:import|export)\b[^'"]*?from\s+['"]([^'"]+)['"]/gms)].map(
      (match) => match[1],
    )
    assert.deepEqual([...new Set(specifiers)].sort(), ['../cuts/times.ts', '../preview/playback.ts'])
    assert.doesNotMatch(source, /^import\s+['"]/m, 'no bare side-effect import')
    assert.doesNotMatch(source, /\b(document|window|fetch|localStorage|require)\b\s*[.(]/)
  })
})

describe('the zoom slider', () => {
  it('keeps the maximum at 240 px per second', () => {
    assert.equal(MAX_PPS, 240)
  })

  it('puts Fit at position 0 and the maximum at the last step, exactly', () => {
    for (const fit of [4, 7.3, 40, 239]) {
      assert.equal(sliderToPps(0, fit), fit)
      assert.equal(sliderToPps(SLIDER_STEPS, fit), MAX_PPS)
      assert.equal(ppsToSlider(fit, fit), 0)
      assert.equal(ppsToSlider(MAX_PPS, fit), SLIDER_STEPS)
    }
  })

  it('round-trips a scale through a position to within one step', () => {
    const next = random(7)
    for (let i = 0; i < 500; i += 1) {
      const fit = MIN_PPS + next() * (MAX_PPS - MIN_PPS - 1)
      const pps = fit + next() * (MAX_PPS - fit)
      const back = sliderToPps(ppsToSlider(pps, fit), fit)
      const step = (MAX_PPS / fit) ** (1 / SLIDER_STEPS)
      assert.ok(back / pps <= step && pps / back <= step, `${pps} -> ${back} at fit ${fit}`)
    }
  })

  it('is logarithmic: the middle is the geometric mean of Fit and the maximum', () => {
    assert.ok(Math.abs(sliderToPps(SLIDER_STEPS / 2, 15) - Math.sqrt(15 * 240)) < 1e-9)
    assert.equal(ppsToSlider(Math.sqrt(15 * 240), 15), SLIDER_STEPS / 2)
  })

  it('clamps outside its range', () => {
    assert.equal(sliderToPps(-5, 20), 20)
    assert.equal(sliderToPps(SLIDER_STEPS + 50, 20), MAX_PPS)
    assert.equal(ppsToSlider(10, 20), 0)
    assert.equal(ppsToSlider(500, 20), SLIDER_STEPS)
  })

  it('has nothing to move when Fit is already the maximum', () => {
    assert.equal(ppsToSlider(MAX_PPS, MAX_PPS), 0)
    assert.equal(sliderToPps(120, MAX_PPS), MAX_PPS)
  })

  it('refuses values that are not numbers', () => {
    assert.throws(() => ppsToSlider(Number.NaN, 20), /pps/)
    assert.throws(() => sliderToPps(Number.NaN, 20), /position/)
    assert.throws(() => sliderToPps(10, 0), /fit/)
  })
})

describe('anchorFor', () => {
  it('anchors on the playhead while it is in view', () => {
    assert.equal(anchorFor(300, 800), 300)
    assert.equal(anchorFor(0, 800), 0)
    assert.equal(anchorFor(800, 800), 800)
  })

  it('anchors on the centre when the playhead is out of view', () => {
    assert.equal(anchorFor(-1, 800), 400)
    assert.equal(anchorFor(801, 800), 400)
  })

  it('anchors on the pointer when one is given, held to the view', () => {
    assert.equal(anchorFor(300, 800, 650), 650)
    assert.equal(anchorFor(-50, 800, 120), 120)
    assert.equal(anchorFor(300, 800, -10), 0)
    assert.equal(anchorFor(300, 800, 900), 800)
  })

  it('keeps the anchored time in place through zoomAt', () => {
    const view: View = { pps: 20, scrollLeft: 1000, width: 800 }
    const x = anchorFor(250, view.width)
    const before = (view.scrollLeft + x) / view.pps
    const zoomed = zoomAt(view, 3, x, 600000)
    assert.ok(Math.abs((zoomed.scrollLeft + x) / zoomed.pps - before) < 1e-9)
  })
})

describe('wheelFactor', () => {
  it('zooms in on a wheel turned up and out on one turned down', () => {
    assert.ok(wheelFactor(-50, 0, 600) > 1)
    assert.ok(wheelFactor(50, 0, 600) < 1)
    assert.equal(wheelFactor(0, 0, 600), 1)
    assert.ok(Math.abs(wheelFactor(-100, 0, 600) - ZOOM_STEP) < 1e-9)
  })

  it('holds one event to one 1.5x step', () => {
    assert.equal(wheelFactor(-5000, 0, 600), ZOOM_STEP)
    assert.equal(wheelFactor(5000, 0, 600), 1 / ZOOM_STEP)
  })

  it('turns lines and pages into px', () => {
    assert.equal(wheelFactor(-3, 1, 600), wheelFactor(-48, 0, 600))
    assert.equal(wheelFactor(0.1, 2, 600), wheelFactor(60, 0, 600))
  })
})

describe('fitCanvas', () => {
  it('is never wider than the view, gutter included, at any length and width', () => {
    const next = random(11)
    for (let i = 0; i < 1000; i += 1) {
      const width = 200 + Math.floor(next() * 2000)
      const gutter = [0, 12, 22][i % 3]
      const totalMs = 1 + Math.floor(next() * 3_600_000)
      const { pps, canvasPx } = fitCanvas(totalMs, width, gutter)
      if (pps > MIN_PPS) {
        assert.ok(canvasPx <= width, `${totalMs} ms in ${width} px: ${canvasPx}`)
      }
      // The last moment's line, and the grip around it, are inside the canvas.
      assert.ok(timeToPx(totalMs, pps) + gutter <= canvasPx + 1)
    }
  })

  it('keeps the 4 px/s floor for an event too long to fit', () => {
    const { pps, canvasPx } = fitCanvas(10 * 3600 * 1000, 1200, 12)
    assert.equal(pps, MIN_PPS)
    assert.equal(canvasPx, 144000 + 12)
  })

  it('adds the gutter to the track\'s whole pixels when zoomed in', () => {
    assert.equal(canvasWidth(10_000, 40.05, 12), 400 + 12)
    assert.equal(canvasWidth(10_000, 40, 0), 400)
  })
})
