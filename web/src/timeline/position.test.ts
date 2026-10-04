import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { layout } from './model.ts'
import {
  clampPosition,
  endPosition,
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
  const track = { startsMs: [7000, 9000, 10000], totalMs: 10480 }

  it('keeps the anchor clip and counts card time in the timeline’s time', () => {
    assert.equal(globalMs(track, { clip: 0, ms: 0, card }), 1200)
    assert.equal(globalMs(track, { clip: 0, ms: 0 }), 7000)
  })

  it('never reads a time before zero when the cards were switched off under the playhead', () => {
    const off = { startsMs: [0, 2000, 3000], totalMs: 3480 }
    assert.equal(globalMs(off, { clip: 0, ms: 0, card }), 0)
  })

  it('is a clip position unchanged by the card field', () => {
    assert.deepEqual(clampPosition([{ facts: { durationMs: 2000 } }], { clip: 0, ms: 5000 }), {
      clip: 0,
      ms: 2000,
    })
    const there = { clip: 0, ms: 0, card }
    assert.equal(clampPosition([{ facts: { durationMs: 2000 } }], there), there)
  })

  it('tells two places in a card apart', () => {
    assert.equal(samePosition({ clip: 0, ms: 0, card }, { clip: 0, ms: 0, card: { ...card } }), true)
    assert.equal(samePosition({ clip: 0, ms: 0, card }, { clip: 0, ms: 0, card: { ...card, ms: 1300 } }), false)
    assert.equal(samePosition({ clip: 0, ms: 0, card }, { clip: 0, ms: 0 }), false)
    assert.equal(samePosition({ clip: 0, ms: 0 }, { clip: 0, ms: 0, card: null }), true)
  })
})
