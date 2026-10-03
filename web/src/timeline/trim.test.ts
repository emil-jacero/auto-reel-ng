import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { clipFacts, frameMs, minCutMs, ModelError, nearestFrame, snapCandidates, snapTo, SNAP_PX, trimEdge, trimLimits } from './model.ts'

const RATES = [23.976, 24, 25, 29.97, 30, 50, 59.94]

function random(seed: number): () => number {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clip = clipFacts(24.96, 25)

describe('trim limits', () => {
  it('prototype defect 1: the lowest end of 0 to 2.4 s is three frames, on a frame', () => {
    const cuts = [{ in: 0, out: 2.4 }]
    assert.equal(trimLimits(cuts, 0, 'out', clipFacts(24.96, 25))[0], 120)
    assert.equal(trimLimits(cuts, 0, 'out', clipFacts(24.96, 29.97))[0], 100)
    assert.equal(trimLimits(cuts, 0, 'out', clipFacts(24.96, 25))[0], minCutMs(25))
    assert.equal(trimLimits(cuts, 0, 'out', clipFacts(24.96, 29.97))[0], frameMs(3, 29.97))
    // 100 ms is 2.5 frames at 25 fps: never offered.
    assert.notEqual(trimLimits(cuts, 0, 'out', clip)[0], 100)
  })

  it('the highest start of a cut is three frames before its end, on a frame', () => {
    const cuts = [{ in: 0, out: 2.4 }]
    assert.equal(trimLimits(cuts, 0, 'in', clip)[1], 2280)
    assert.equal(trimLimits(cuts, 0, 'in', clipFacts(24.96, 29.97))[1], 2269)
  })

  it('a minimum-length limit is on the grid and keeps three frames, at every rate', () => {
    const next = random(5)
    for (const fps of RATES) {
      const facts = clipFacts(600, fps)
      const frames = Math.round((facts.durationMs * fps) / 1000)
      for (let i = 0; i < 100; i += 1) {
        const k = 4 + Math.floor(next() * (frames - 8))
        const at = frameMs(k, fps)
        const later = frameMs(k + 10 + Math.floor(next() * 50), fps)
        const [, highest] = trimLimits([{ in: at / 1000, out: later / 1000 }], 0, 'in', facts)
        const [lowest] = trimLimits([{ in: at / 1000, out: later / 1000 }], 0, 'out', facts)
        assert.equal(nearestFrame(highest, fps), highest, `start limit ${highest} at ${fps}`)
        assert.equal(nearestFrame(lowest, fps), lowest, `end limit ${lowest} at ${fps}`)
        assert.ok(later - highest >= minCutMs(fps), `${later} - ${highest} at ${fps}`)
        assert.ok(lowest - at >= minCutMs(fps), `${lowest} - ${at} at ${fps}`)
      }
    }
  })

  it('a neighbour limits the edge', () => {
    const cuts = [
      { in: 0, out: 2.4 },
      { in: 14, out: 17.2 },
    ]
    assert.deepEqual(trimLimits(cuts, 1, 'in', clip), [2400, 17080])
    assert.deepEqual(trimLimits(cuts, 1, 'out', clip), [14120, 24960])
    assert.deepEqual(trimLimits(cuts, 0, 'out', clip), [120, 14000])
    assert.deepEqual(trimLimits(cuts, 0, 'in', clip), [0, 2280])
  })

  it('the order the cuts are listed in does not matter', () => {
    const cuts = [
      { in: 14, out: 17.2 },
      { in: 0, out: 2.4 },
    ]
    assert.deepEqual(trimLimits(cuts, 0, 'in', clip), [2400, 17080])
  })

  it('overlapping cuts from disk are not neighbours and no range is inverted', () => {
    const cuts = [
      { in: 1, out: 3 },
      { in: 2, out: 4 },
    ]
    assert.deepEqual(trimLimits(cuts, 0, 'out', clip), [1120, 24960])
    assert.deepEqual(trimLimits(cuts, 0, 'in', clip), [0, 2880])
    assert.deepEqual(trimLimits(cuts, 1, 'in', clip), [0, 3880])
    assert.deepEqual(trimLimits(cuts, 1, 'out', clip), [2120, 24960])
    for (const index of [0, 1]) {
      for (const edge of ['in', 'out'] as const) {
        const [lowest, highest] = trimLimits(cuts, index, edge, clip)
        const current = toMs(cuts[index][edge])
        assert.ok(lowest <= current && current <= highest && lowest <= highest)
      }
    }
  })

  it('a cut shorter than three frames keeps its end where it is', () => {
    const cuts = [{ in: 5, out: 5.05 }]
    const [lowest, highest] = trimLimits(cuts, 0, 'out', clip)
    assert.equal(lowest, 5050)
    assert.ok(highest >= 5050)
    assert.equal(trimLimits(cuts, 0, 'in', clip)[1], 5000)
    assert.equal(trimEdge(cuts, 0, 'out', 5050, clip, 40, []).ms, 5050)
    assert.equal(trimEdge(cuts, 0, 'out', 5030, clip, 40, []).ms, 5050)
  })

  it('a clip shorter than three frames gives each edge its current value alone', () => {
    const tiny = clipFacts(0.08, 25)
    const cuts = [{ in: 0, out: 0.08 }]
    assert.deepEqual(trimLimits(cuts, 0, 'in', tiny), [0, 0])
    assert.deepEqual(trimLimits(cuts, 0, 'out', tiny), [80, 80])
  })

  it('a cut running past the clip’s end keeps its end', () => {
    const cuts = [{ in: 20, out: 30 }]
    const [lowest, highest] = trimLimits(cuts, 0, 'out', clip)
    assert.ok(lowest <= 30000 && highest >= 30000)
    assert.equal(trimLimits(cuts, 0, 'in', clip)[1], 24840)
  })

  it('removed cuts are not neighbours', () => {
    const cuts = [
      { in: 0, out: 2.4, removed: true },
      { in: 14, out: 17.2 },
      { in: 20, out: 21, removed: true },
    ]
    assert.deepEqual(trimLimits(cuts, 1, 'in', clip), [0, 17080])
    assert.deepEqual(trimLimits(cuts, 1, 'out', clip), [14120, 24960])
  })

  it('touching cuts limit each other exactly at the shared time', () => {
    const cuts = [
      { in: 1, out: 3 },
      { in: 3, out: 5 },
    ]
    assert.equal(trimLimits(cuts, 0, 'out', clip)[1], 3000)
    assert.equal(trimLimits(cuts, 1, 'in', clip)[0], 3000)
  })

  it('refuses a position outside the list and facts that are not usable', () => {
    const cuts = [{ in: 0, out: 1 }]
    assert.throws(() => trimLimits(cuts, 1, 'in', clip), ModelError)
    assert.throws(() => trimLimits(cuts, -1, 'in', clip), ModelError)
    assert.throws(() => trimLimits(cuts, 0.5, 'in', clip), ModelError)
    assert.throws(() => trimLimits(cuts, 0, 'in', { durationMs: 1000, fps: 0 }), /fps/)
    assert.throws(() => trimLimits(cuts, 0, 'in', { durationMs: Number.NaN, fps: 25 }), /durationMs/)
  })
})

function toMs(seconds: number): number {
  return Math.round(seconds * 1000)
}

describe('snapping', () => {
  it('snaps to a candidate within 8 px: 7,900 ms to 8,000 at 40 px/s', () => {
    assert.deepEqual(snapTo(7900, [8000], 40), { ms: 8000, target: 8000 })
  })

  it('takes a snap at exactly 8 px and not at 8.01 px', () => {
    assert.equal(SNAP_PX, 8)
    assert.equal(snapTo(1000, [1200], 40).target, 1200)
    assert.equal(snapTo(1000, [1200], 40.05).target, null)
    assert.equal(snapTo(1000, [800], 40).target, 800)
  })

  it('does not snap to a candidate out of reach', () => {
    assert.deepEqual(snapTo(5317, [5717], 40), { ms: 5317, target: null })
    assert.deepEqual(snapTo(5317, [], 40), { ms: 5317, target: null })
  })

  it('two equally near candidates give the earlier, in either order', () => {
    assert.equal(snapTo(8050, [8000, 8100], 80).ms, 8000)
    assert.equal(snapTo(8050, [8100, 8000], 80).ms, 8000)
    assert.equal(snapTo(8050, [8100, 8000], 80).target, 8000)
  })

  it('takes the nearest of several in reach', () => {
    assert.equal(snapTo(8040, [8000, 8030, 8100], 40).ms, 8030)
  })

  it('candidates: the clip’s ends, other cuts’ edges, the playhead, extras; sorted, once', () => {
    const cuts = [
      { in: 1, out: 2 },
      { in: 5, out: 6 },
      { in: 8, out: 9, removed: true },
      { in: 2, out: 3 },
    ]
    assert.deepEqual(snapCandidates(cuts, 1, clip, 2500, [4000, 2000, 6000]), [
      0, 1000, 2000, 2500, 3000, 4000, 6000, 24960,
    ])
  })

  it('the playhead counts only inside the clip; extras outside it are dropped', () => {
    const cuts = [{ in: 1, out: 2 }]
    assert.deepEqual(snapCandidates(cuts, 0, clip, null, []), [0, 24960])
    assert.deepEqual(snapCandidates(cuts, 0, clip, 30000, [-5, 99999]), [0, 24960])
    assert.deepEqual(snapCandidates(cuts, 0, clip, 24960, []), [0, 24960])
  })

  it('refuses a position outside the list', () => {
    assert.throws(() => snapCandidates([], 0, clip, null, []), ModelError)
  })
})

describe('trimEdge', () => {
  const cuts = [{ in: 8, out: 12 }]

  it('snaps a start dragged to 7,900 ms onto a candidate at 8,000', () => {
    const lone = [{ in: 9, out: 12 }]
    assert.deepEqual(trimEdge(lone, 0, 'in', 7900, clip, 40, [8000]), { ms: 8000, snappedTo: 8000 })
  })

  it('a candidate beyond the limit gives the limit and no snap', () => {
    const near = [{ in: 7.8, out: 12 }, { in: 5, out: 7.7 }]
    // Cut 0's start may not go below 7,700 (a neighbour's end): dragging to 7,400 with a
    // candidate at 7,300 at 10 px/s snaps to it, then is held at 7,700.
    assert.deepEqual(trimEdge(near, 0, 'in', 7400, clip, 10, [7300]), { ms: 7700, snappedTo: null })
    // A highest limit of 7,800, a candidate at 8,000 and a drag to 7,900.
    const cut = [{ in: 5, out: 6 }, { in: 7.8, out: 9 }]
    assert.deepEqual(trimEdge(cut, 0, 'out', 7900, clip, 10, [8000]), { ms: 7800, snappedTo: null })
  })

  it('with no candidate in reach the edge lands on the nearest frame', () => {
    assert.deepEqual(trimEdge(cuts, 0, 'out', 5317 + 7000, clip, 40, [5717]), { ms: 12320, snappedTo: null })
    const early = [{ in: 1, out: 6 }]
    assert.deepEqual(trimEdge(early, 0, 'out', 5317, clip, 40, [5717]), { ms: 5320, snappedTo: null })
  })

  it('a limit reached is returned exactly, not moved to the grid', () => {
    const next = [{ in: 1, out: 2 }, { in: 3.007, out: 4 }]
    assert.deepEqual(trimEdge(next, 0, 'out', 3500, clip, 40, []), { ms: 3007, snappedTo: null })
    assert.deepEqual(trimEdge(next, 1, 'in', 1500, clip, 40, []), { ms: 2000, snappedTo: null })
  })

  it('reports a snap when the clamped result is the candidate', () => {
    const next = [{ in: 1, out: 2 }, { in: 3.007, out: 4 }]
    assert.deepEqual(trimEdge(next, 0, 'out', 3500, clip, 40, [3007]), { ms: 3007, snappedTo: 3007 })
  })

  it('moving an edge to the place it holds returns that place', () => {
    const typed = [{ in: 1.003, out: 5.0071 }]
    assert.deepEqual(trimEdge(typed, 0, 'in', 1003, clip, 40, [1000]), { ms: 1003, snappedTo: null })
    assert.deepEqual(trimEdge(typed, 0, 'out', 5007, clip, 40, []), { ms: 5007, snappedTo: null })
    assert.deepEqual(trimEdge(typed, 0, 'in', 1003, clip, 40, [1003]), { ms: 1003, snappedTo: 1003 })
  })

  it('applied to the cut, a drag’s result is where the edge stays (200 random drags)', () => {
    const next = random(9)
    const facts = clipFacts(60, 29.97)
    const start = [
      { in: 3.2, out: 9.5 },
      { in: 14.003, out: 20 },
      { in: 30, out: 40.5 },
    ]
    for (let i = 0; i < 200; i += 1) {
      const index = Math.floor(next() * start.length)
      const edge = next() < 0.5 ? 'in' : 'out'
      const pps = 4 + next() * 236
      const wanted = Math.round(next() * facts.durationMs)
      const candidates = snapCandidates(start, index, facts, next() < 0.5 ? Math.round(next() * 60000) : null, [])
      const first = trimEdge(start, index, edge, wanted, facts, pps, candidates)
      const [lowest, highest] = trimLimits(start, index, edge, facts)
      assert.ok(first.ms >= lowest && first.ms <= highest, `${first.ms} outside ${lowest}..${highest}`)
      assert.ok(Number.isInteger(first.ms))
      if (first.snappedTo !== null) {
        assert.equal(first.snappedTo, first.ms)
      }
      const moved = start.map((cut, at) => (at === index ? { ...cut, [edge]: first.ms / 1000 } : cut))
      const again = trimEdge(moved, index, edge, first.ms, facts, pps, candidates)
      assert.equal(again.ms, first.ms)
      // Same arguments, same answer.
      assert.deepEqual(trimEdge(start, index, edge, wanted, facts, pps, candidates), first)
    }
  })

  it('a time it returns is one the Cuts panel reads back unchanged', () => {
    const next = random(21)
    for (const fps of RATES) {
      const facts = clipFacts(60, fps)
      const cut = [{ in: 10, out: 20 }]
      for (let i = 0; i < 40; i += 1) {
        const { ms } = trimEdge(cut, 0, 'out', Math.round(next() * 60000), facts, 40, [])
        assert.equal(toMs(ms / 1000), ms)
      }
    }
  })

  it('refuses a position outside the list and a scale that is not above zero', () => {
    assert.throws(() => trimEdge(cuts, 3, 'in', 1000, clip, 40, []), ModelError)
    assert.throws(() => trimEdge(cuts, 0, 'in', 1000, clip, 0, []), /pps/)
    assert.throws(() => trimEdge(cuts, 0, 'in', Number.NaN, clip, 40, []), /wantedMs/)
  })
})
