import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { cutSpans, keptExtent, layout } from './model.ts'
import type { Ms } from './model.ts'
import {
  clampPosition,
  endPosition,
  firstKeptMs,
  hasKeptFrame,
  keptPosition,
  lastKeptMs,
  globalMs,
  lastFrame,
  lastFrameMs,
  onGrid,
  positionAt,
  samePosition,
  seekSeconds,
  startPosition,
  stepFrames,
  stepMs,
} from './position.ts'

/*
 * The playhead's arithmetic (`position.ts`), run by `npm test`: frames in whole ms on the
 * clip's grid, steps across clip boundaries, and the position of a time on the timeline.
 */

const A = { durationMs: 2000, fps: 25 } // 50 frames: 0 .. 1960
const B = { durationMs: 1000, fps: 30 } // 30 frames: 0 .. 967
const C = { durationMs: 480, fps: 25 } // 12 frames: 0 .. 440
const clips = [A, B, C]
const l = layout(clips)

describe('frames', () => {
  it('finds a clip\'s last frame before its end', () => {
    assert.equal(lastFrame(A), 49)
    assert.equal(lastFrameMs(A), 1960)
    assert.equal(lastFrame(B), 29)
    assert.equal(lastFrameMs(B), 967)
    assert.equal(lastFrame(C), 11)
    // 29.97 fps over 1.001 s: frames 0..29, the 30th at 1001 ms is not before the end
    assert.equal(lastFrame({ durationMs: 1001, fps: 30000 / 1001 }), 29)
  })

  it('holds a time to the nearest frame, no later than the last', () => {
    assert.equal(onGrid(A, 1005), 1000)
    assert.equal(onGrid(A, 1021), 1040)
    assert.equal(onGrid(A, 1999), 1960)
    assert.equal(onGrid(A, -50), 0)
  })
})

describe('positionAt', () => {
  it('finds the clip that holds a time and the frame in it', () => {
    assert.deepEqual(positionAt(l, clips, 0), { clip: 0, ms: 0 })
    assert.deepEqual(positionAt(l, clips, 1000), { clip: 0, ms: 1000 })
    assert.deepEqual(positionAt(l, clips, 2000), { clip: 1, ms: 0 })
    assert.deepEqual(positionAt(l, clips, 2500), { clip: 1, ms: 500 })
    assert.equal(globalMs(l, { clip: 1, ms: 500 }), 2500)
  })

  it('holds a time before the start and past the end to the first and the last frame', () => {
    assert.deepEqual(positionAt(l, clips, -100), { clip: 0, ms: 0 })
    assert.deepEqual(positionAt(l, clips, 99999), { clip: 2, ms: 440 })
    assert.deepEqual(positionAt(l, clips, l.totalMs), endPosition(clips))
    assert.deepEqual(startPosition(), { clip: 0, ms: 0 })
  })

  it('puts a time in the last half frame of a clip on its last frame, not the next clip', () => {
    assert.deepEqual(positionAt(l, clips, 1995), { clip: 0, ms: 1960 })
  })
})

describe('stepFrames', () => {
  it('steps back three frames from 1.00 s at 25 fps to exactly 0.88 s', () => {
    assert.deepEqual(stepFrames([A], { clip: 0, ms: 1000 }, -3), { clip: 0, ms: 880 })
  })

  it('goes from a clip\'s last frame to the next clip\'s first, and back, skipping none', () => {
    assert.deepEqual(stepFrames(clips, { clip: 0, ms: 1960 }, 1), { clip: 1, ms: 0 })
    assert.deepEqual(stepFrames(clips, { clip: 1, ms: 0 }, -1), { clip: 0, ms: 1960 })
    assert.deepEqual(stepFrames(clips, { clip: 1, ms: 967 }, 1), { clip: 2, ms: 0 })
    assert.deepEqual(stepFrames(clips, { clip: 0, ms: 1920 }, 3), { clip: 1, ms: 33 })
  })

  it('walks every frame of the timeline once, in order', () => {
    let p = startPosition()
    let seen = 1
    for (;;) {
      const next = stepFrames(clips, p, 1)
      if (next.clip === p.clip && next.ms === p.ms) {
        break
      }
      p = next
      seen += 1
    }
    assert.equal(seen, 50 + 30 + 12)
    assert.deepEqual(p, endPosition(clips))
  })

  it('stays on the first and the last frame at the ends', () => {
    assert.deepEqual(stepFrames(clips, startPosition(), -1), { clip: 0, ms: 0 })
    assert.deepEqual(stepFrames(clips, endPosition(clips), 1), endPosition(clips))
    assert.deepEqual(stepFrames(clips, { clip: 0, ms: 0 }, 500), endPosition(clips))
  })
})

describe('stepMs', () => {
  it('moves along the whole timeline and lands on a frame', () => {
    assert.deepEqual(stepMs(l, clips, { clip: 0, ms: 1500 }, 1000), { clip: 1, ms: 500 })
    assert.deepEqual(stepMs(l, clips, { clip: 1, ms: 100 }, -1000), { clip: 0, ms: 1120 })
    assert.deepEqual(stepMs(l, clips, { clip: 0, ms: 0 }, -5000), { clip: 0, ms: 0 })
    assert.deepEqual(stepMs(l, clips, { clip: 2, ms: 0 }, 5000), endPosition(clips))
  })
})

describe('seekSeconds', () => {
  it('seeks a quarter frame into the frame, so a rounded frame time never falls in the one before', () => {
    // 29.97 fps: frame 1 starts at 33.37 ms but is listed at 33 ms
    const fps = 30000 / 1001
    const t = seekSeconds(33, fps)
    assert.ok(t * fps >= 1 && t * fps < 2)
    assert.ok(Math.abs(seekSeconds(880, 25) - 0.89) < 1e-9)
  })

  it('stays inside every frame of a run at common rates', () => {
    for (const fps of [24, 25, 30000 / 1001, 30, 50, 60000 / 1001, 60]) {
      for (let n = 0; n < 500; n += 1) {
        const t = seekSeconds(frameMsOf(n, fps), fps) * fps
        assert.ok(t >= n && t < n + 1, `fps ${fps} frame ${n}: ${t}`)
      }
    }
  })
})

describe('clampPosition', () => {
  const clips = [{ facts: A }, { facts: B }, { facts: C }]

  it('leaves a position the clips still hold as it is', () => {
    const p = { clip: 2, ms: 440 }
    assert.equal(clampPosition(clips, p), p)
    assert.deepEqual(clampPosition(clips, { clip: 1, ms: B.durationMs }), { clip: 1, ms: B.durationMs })
  })

  it('moves a position past the last clip to the start, where the playhead goes next', () => {
    assert.deepEqual(clampPosition(clips.slice(0, 2), { clip: 2, ms: 300 }), startPosition())
    assert.deepEqual(clampPosition(clips, { clip: 9, ms: 0 }), startPosition())
    assert.deepEqual(clampPosition(clips, { clip: -1, ms: 0 }), startPosition())
    assert.deepEqual(clampPosition([], { clip: 0, ms: 0 }), startPosition())
  })

  it('holds a time past a shortened clip to its end', () => {
    assert.deepEqual(clampPosition([{ facts: { ...A, durationMs: 800 } }], { clip: 0, ms: 1960 }), {
      clip: 0,
      ms: 800,
    })
  })
})

function frameMsOf(n: number, fps: number): number {
  return Math.round((n * 1000) / fps)
}

describe('a place in a card', () => {
  const card = { chapter: 0, name: '', ms: 1200, lengthMs: 7000 }
  // The track layout puts the clip after its 7 s card.
  const track = { startsMs: [7000, 9000, 10000], totalMs: 10480, inMs: [0, 0, 0] }

  it('keeps the anchor clip and counts card time in the timeline’s time', () => {
    assert.equal(globalMs(track, { clip: 0, ms: 0, card }), 1200)
    assert.equal(globalMs(track, { clip: 0, ms: 0 }), 7000)
  })

  it('never reads a time before zero when the cards were switched off under the playhead', () => {
    const off = { startsMs: [0, 2000, 3000], totalMs: 3480, inMs: [0, 0, 0] }
    assert.equal(globalMs(off, { clip: 0, ms: 0, card }), 0)
  })

  it('is a clip position unchanged by the card field', () => {
    assert.deepEqual(clampPosition([{ facts: { durationMs: 2000, fps: 25 } }], { clip: 0, ms: 5000 }), {
      clip: 0,
      ms: 2000,
    })
    const there = { clip: 0, ms: 0, card }
    assert.equal(clampPosition([{ facts: { durationMs: 2000, fps: 25 } }], there), there)
  })

  it('tells two places in a card apart', () => {
    assert.equal(samePosition({ clip: 0, ms: 0, card }, { clip: 0, ms: 0, card: { ...card } }), true)
    assert.equal(samePosition({ clip: 0, ms: 0, card }, { clip: 0, ms: 0, card: { ...card, ms: 1300 } }), false)
    assert.equal(samePosition({ clip: 0, ms: 0, card }, { clip: 0, ms: 0 }), false)
    assert.equal(samePosition({ clip: 0, ms: 0 }, { clip: 0, ms: 0, card: null }), true)
  })
})

/** A 25 fps clip of `durationMs` with its kept extent from cuts given in seconds. */
function trimmed(durationMs: Ms, cuts: { in: number; out: number }[] = []) {
  return { durationMs, fps: 25, ...keptExtent(cutSpans(cuts, durationMs), durationMs) }
}

describe('the playhead on kept frames (timeline-ripple-layout)', () => {
  // A (10 s, cut 0..2 s), B (8 s, cut 6..8 s), C (5 s, cut 1..2 s): starts 0, 8,000, 14,000.
  const A2 = trimmed(10000, [{ in: 0, out: 2 }])
  const B2 = trimmed(8000, [{ in: 6, out: 8 }])
  const C2 = trimmed(5000, [{ in: 1, out: 2 }])
  const abc = [A2, B2, C2]
  const lay = layout(abc)

  it('positions are held to kept frames: -5, 13,975 and 19,500 ms', () => {
    assert.deepEqual(positionAt(lay, abc, -5), { clip: 0, ms: 2000 })
    assert.deepEqual(positionAt(lay, abc, 13975), { clip: 1, ms: 5960 })
    assert.deepEqual(positionAt(lay, abc, 19500), { clip: 2, ms: 4960 })
  })

  it('a press at 0 and 120 px (40 px/s) is A 2.00 s and A 5.00 s; at 559 px B 5.96 s', () => {
    assert.deepEqual(positionAt(lay, abc, 0), { clip: 0, ms: 2000 })
    assert.deepEqual(positionAt(lay, abc, 3000), { clip: 0, ms: 5000 })
    assert.deepEqual(positionAt(lay, abc, 13975), { clip: 1, ms: 5960 })
    assert.equal(globalMs(lay, { clip: 0, ms: 5000 }), 3000)
    assert.equal(globalMs(lay, { clip: 1, ms: 5960 }), 13960)
  })

  it('steps cross the edges: B 5.96 s +1 is C 0, B 0 -1 is A 9.96 s', () => {
    assert.deepEqual(stepFrames(abc, { clip: 1, ms: 5960 }, 1), { clip: 2, ms: 0 })
    assert.deepEqual(stepFrames(abc, { clip: 1, ms: 0 }, -1), { clip: 0, ms: 9960 })
    assert.deepEqual(stepFrames(abc, { clip: 2, ms: 0 }, -1), { clip: 1, ms: 5960 })
    assert.deepEqual(stepFrames(abc, { clip: 1, ms: 5960 }, -1), { clip: 1, ms: 5920 })
  })

  it('Home and End are the first and last kept frames of the timeline', () => {
    assert.deepEqual(startPosition(abc), { clip: 0, ms: 2000 })
    assert.deepEqual(endPosition(abc), { clip: 2, ms: 4960 })
    assert.deepEqual(endPosition([A2, B2]), { clip: 1, ms: 5960 })
    assert.deepEqual(stepFrames(abc, { clip: 0, ms: 2000 }, -1), { clip: 0, ms: 2000 })
  })

  it('a few frames kept: 4,000, 4,040 and 4,080 ms, then on into the next clip', () => {
    const few = trimmed(10000, [
      { in: 0, out: 4 },
      { in: 4.12, out: 10 },
    ])
    assert.deepEqual([few.inMs, few.outMs], [4000, 4120])
    const two = [few, trimmed(3000)]
    let p = { clip: 0, ms: firstKeptMs(few) }
    const seen = [p.ms]
    for (let i = 0; i < 3; i += 1) {
      p = stepFrames(two, p, 1)
      seen.push(p.clip === 0 ? p.ms : -1)
    }
    assert.deepEqual(seen, [4000, 4040, 4080, -1])
    assert.deepEqual(p, { clip: 1, ms: 0 })
    assert.equal(lastKeptMs(few), 4080)
  })

  it('a clip with no kept frame is passed over by steps and lookups', () => {
    const none = { durationMs: 3000, fps: 25, inMs: 1001, outMs: 1030 }
    assert.equal(hasKeptFrame(none), false)
    const three = [trimmed(2000), none, trimmed(2000)]
    const l3 = layout(three)
    assert.deepEqual(stepFrames(three, { clip: 0, ms: 1960 }, 1), { clip: 2, ms: 0 })
    assert.deepEqual(stepFrames(three, { clip: 2, ms: 0 }, -1), { clip: 0, ms: 1960 })
    assert.deepEqual(positionAt(l3, three, 2010), { clip: 2, ms: 0 })
  })

  it('a wholly cut middle clip: Right on the first clip’s last kept frame lands on the third', () => {
    const three = [trimmed(2000), trimmed(2000, [{ in: 0, out: 2 }]), trimmed(2000)]
    const l3 = layout(three)
    assert.deepEqual(l3.startsMs, [0, 2000, 2000])
    assert.deepEqual(stepFrames(three, { clip: 0, ms: 1960 }, 1), { clip: 2, ms: 0 })
    assert.deepEqual(positionAt(l3, three, 2000), { clip: 2, ms: 0 })
  })

  it('a time no longer kept goes to the nearest kept frame of its clip', () => {
    const track = abc.map((facts) => ({ facts }))
    assert.deepEqual(clampPosition(track, { clip: 0, ms: 1000 }), { clip: 0, ms: 2000 })
    assert.deepEqual(clampPosition(track, { clip: 1, ms: 7000 }), { clip: 1, ms: 5960 })
    const at = { clip: 2, ms: 1500 } // inside an interior cut: kept as it is
    assert.equal(clampPosition(track, at), at)
    assert.deepEqual(keptPosition(abc, 0, 1000), { clip: 0, ms: 2000 })
  })

  it('a new leading cut moves a playhead at A 1.00 s to A 2.00 s', () => {
    const before = [{ facts: trimmed(10000) }]
    const after = [{ facts: trimmed(10000, [{ in: 0, out: 2 }]) }]
    assert.deepEqual(clampPosition(before, { clip: 0, ms: 1000 }), { clip: 0, ms: 1000 })
    assert.deepEqual(clampPosition(after, { clip: 0, ms: 1000 }), { clip: 0, ms: 2000 })
  })

  it('a clip given with `kept` beside its facts is held the same way', () => {
    const facts = { durationMs: 10000, fps: 25 }
    assert.deepEqual(clampPosition([{ facts, kept: { inMs: 2000, outMs: 10000 } }], { clip: 0, ms: 0 }), {
      clip: 0,
      ms: 2000,
    })
  })
})
