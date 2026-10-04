import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  atPlayhead,
  bareMousePress,
  handleRows,
  keyOutcome,
  nearestHandle,
  selectionStands,
  snapWords,
  stepEdge,
} from './handles.ts'
import { cutSpans, frameMs, keptExtent, nearestFrame, trimLimits, clipFacts } from './model.ts'

const clip = clipFacts(6.02, 25)
const RANGE = [0, 2360] as const

describe('stepEdge', () => {
  it('three Rights from 1.0 s at 25 fps give 1.12 s', () => {
    let at = 1000
    for (let i = 0; i < 3; i += 1) {
      at = stepEdge('ArrowRight', false, at, [0, 5000], 25) ?? -1
    }
    assert.equal(at, 1120)
  })

  it('a typed time off the grid moves to the next frame in each direction', () => {
    assert.equal(stepEdge('ArrowRight', false, 1234, [0, 5000], 25), 1240)
    assert.equal(stepEdge('ArrowLeft', false, 1234, [0, 5000], 25), 1200)
  })

  it('an edge between frames goes to the frame before it, not to a frame a step away', () => {
    // 1215 ms is 30.4 frames at 25 fps: Left is frame 30 (1200), not the nearest of 1175 (1160)
    assert.equal(stepEdge('ArrowLeft', false, 1215, [0, 5000], 25), 1200)
    assert.equal(stepEdge('ArrowRight', false, 1215, [0, 5000], 25), 1240)
    // exactly on a frame, a step is one frame
    assert.equal(stepEdge('ArrowLeft', false, 1200, [0, 5000], 25), 1160)
  })

  it('a frame step is exact at 29.97 fps, where frame times are rounded', () => {
    const times = [0, 1, 2, 3, 4].map((n) => frameMs(n, 29.97))
    for (let i = 1; i < times.length; i += 1) {
      assert.equal(stepEdge('ArrowRight', false, times[i - 1], [0, 5000], 29.97), times[i])
      assert.equal(stepEdge('ArrowLeft', false, times[i], [0, 5000], 29.97), times[i - 1])
    }
  })

  it('Shift gives one second and Page keys five, then the nearest frame', () => {
    assert.equal(stepEdge('ArrowRight', true, 2480, [0, 9000], 25), 3480)
    assert.equal(stepEdge('ArrowLeft', true, 2480, [0, 9000], 25), 1480)
    // 2.5 s is half a frame off the 25 fps grid: one second on is the frame nearest 3.5 s
    assert.equal(stepEdge('ArrowRight', true, 2500, [0, 9000], 25), 3520)
    assert.equal(stepEdge('PageUp', false, 1000, [0, 9000], 25), 6000)
    assert.equal(stepEdge('PageDown', false, 6000, [0, 9000], 25), 1000)
    assert.equal(stepEdge('ArrowRight', true, 1234, [0, 9000], 25), nearestFrame(2234, 25))
    assert.equal(stepEdge('PageUp', false, 1234, [0, 9000], 25), nearestFrame(6234, 25))
    // at 29.97 fps the result is a frame time, not the raw second
    const up = stepEdge('PageUp', false, 0, [0, 90000], 29.97) ?? -1
    assert.equal(up, nearestFrame(5000, 29.97))
    assert.notEqual(up, 5000)
  })

  it('Home and End give the range ends, on frame times at 25 and 29.97 fps', () => {
    for (const fps of [25, 29.97]) {
      const facts = clipFacts(6.02, fps)
      const cuts = [
        { in: 1, out: 2.5 },
        { in: 4, out: 5 },
      ]
      const [low, high] = trimLimits(cuts, 0, 'in', facts)
      assert.equal(stepEdge('Home', false, 1000, [low, high], fps), low)
      assert.equal(stepEdge('End', false, 1000, [low, high], fps), high)
      assert.equal(nearestFrame(high, fps), high)
    }
    // Home and End on the model's own range for the spec's cut: 0 and 2.36 s
    const [low, high] = trimLimits([{ in: 1, out: 2.5 }, { in: 4, out: 5 }], 0, 'in', clip)
    assert.deepEqual([low, high], [0, 2360])
    assert.equal(stepEdge('End', false, 1000, [low, high], 25), 2360)
  })

  it('a key at a limit returns the limit, and a key that would pass it stops there', () => {
    assert.equal(stepEdge('Home', false, 0, RANGE, 25), 0)
    assert.equal(stepEdge('ArrowLeft', false, 0, RANGE, 25), 0)
    assert.equal(stepEdge('ArrowRight', false, 2360, RANGE, 25), 2360)
    assert.equal(stepEdge('PageUp', false, 1000, RANGE, 25), 2360)
    assert.equal(stepEdge('ArrowLeft', true, 500, RANGE, 25), 0)
  })

  it('a range that holds a value off the grid still moves from it', () => {
    // a cut past the clip's end: the end 7 s, range up to 7 s; Left is one frame earlier
    assert.equal(stepEdge('ArrowLeft', false, 7000, [5120, 7000], 25), 6960)
    // a cut shorter than three frames: Left on its end changes nothing
    assert.equal(stepEdge('ArrowLeft', false, 5050, [5050, 6020], 25), 5050)
  })

  it('returns null for a key that is not a handle’s', () => {
    for (const key of ['a', 'Tab', 'Escape', 'Enter', ' ', 'ArrowUp', 'ArrowDown']) {
      assert.equal(stepEdge(key, false, 1000, RANGE, 25), null)
    }
  })
})

describe('atPlayhead', () => {
  it('sets the edge at the playhead’s nearest frame within the range', () => {
    assert.deepEqual(atPlayhead(1600, 6020, [0, 5000], 25), { ms: 1600 })
    assert.deepEqual(atPlayhead(1610, 6020, [0, 5000], 25), { ms: 1600 })
    assert.deepEqual(atPlayhead(3000, 6020, [0, 2360], 25), { ms: 2360 })
  })

  it('counts the playhead’s end of the clip as inside it', () => {
    assert.deepEqual(atPlayhead(6020, 6020, [0, 6020], 25), { ms: 6020 })
    assert.deepEqual(atPlayhead(6020, 6020, [0, 6000], 25), { ms: 6000 })
    assert.deepEqual(atPlayhead(0, 6020, [0, 6020], 25), { ms: 0 })
  })

  it('refuses a playhead in another clip or outside this one', () => {
    assert.deepEqual(atPlayhead(null, 6020, [0, 5000], 25), { refused: 'not-in-clip' })
    assert.deepEqual(atPlayhead(6021, 6020, [0, 5000], 25), { refused: 'not-in-clip' })
    assert.deepEqual(atPlayhead(-1, 6020, [0, 5000], 25), { refused: 'not-in-clip' })
  })
})

describe('nearestHandle', () => {
  const handles = [
    { id: 'a-end', px: 100 },
    { id: 'b-start', px: 104 },
  ]

  it('takes the nearer of two edges 4 px apart', () => {
    assert.equal(nearestHandle(103, handles, 22), 'b-start')
    assert.equal(nearestHandle(101, handles, 22), 'a-end')
  })

  it('a press 3 px right of the first edge goes to the first (the spec’s two neighbours)', () => {
    assert.equal(nearestHandle(103 - 1, handles, 22), 'a-end')
    assert.equal(nearestHandle(100 + 1.5, handles, 22), 'a-end')
  })

  it('takes the earlier of a tie', () => {
    assert.equal(nearestHandle(102, handles, 22), 'a-end')
    assert.equal(nearestHandle(102, [...handles].reverse(), 22), 'a-end')
  })

  it('is null when no edge is within reach', () => {
    assert.equal(nearestHandle(300, handles, 22), null)
    assert.equal(nearestHandle(127, handles, 22), null)
    assert.equal(nearestHandle(10, [], 22), null)
  })
})

describe('snapWords', () => {
  const ctx = {
    playheadMs: 1600,
    durationMs: 6020,
    others: [
      { n: 2, inMs: 4000, outMs: 5000 },
      { n: 3, inMs: 5500, outMs: 6020 },
    ],
  }

  it('names the playhead, the clip’s ends and a cut’s edge by the panel’s number', () => {
    assert.equal(snapWords(1600, ctx), 'Snapped to the playhead')
    assert.equal(snapWords(0, ctx), 'Snapped to the clip’s start')
    assert.equal(snapWords(4000, ctx), 'Snapped to cut 2 start')
    assert.equal(snapWords(5000, ctx), 'Snapped to cut 2 end')
  })

  it('names the playhead before the clip’s end before a cut’s edge', () => {
    assert.equal(snapWords(6020, { ...ctx, playheadMs: 6020 }), 'Snapped to the playhead')
    assert.equal(snapWords(6020, ctx), 'Snapped to the clip’s end')
    assert.equal(snapWords(4000, { ...ctx, playheadMs: 4000 }), 'Snapped to the playhead')
  })

  it('has no words for a place that is not a snapping place', () => {
    assert.equal(snapWords(1234, ctx), '')
    assert.equal(snapWords(1600, { ...ctx, playheadMs: null }), '')
  })
})

describe('keyOutcome', () => {
  const at = (key: string, now: number, playhead: number | null = null, shift = false) =>
    keyOutcome(key, shift, now, [0, 2360], 25, 6020, playhead)

  it('a key that moves the edge sets it', () => {
    assert.deepEqual(at('ArrowRight', 1000), { kind: 'set', ms: 1040, stopped: false })
    assert.deepEqual(at('Home', 1000), { kind: 'set', ms: 0, stopped: false })
  })

  it('a key at a limit changes nothing: the second Home is a stay', () => {
    assert.deepEqual(at('Home', 0), { kind: 'stay' })
    assert.deepEqual(at('ArrowRight', 2360), { kind: 'stay' })
    assert.deepEqual(at('End', 2360), { kind: 'stay' })
  })

  it('a key that is not a handle’s is left alone', () => {
    for (const key of ['Tab', 'a', 'Escape', 'ArrowUp', ' ']) {
      assert.deepEqual(at(key, 1000), { kind: 'ignore' })
    }
  })

  it('Enter sets the edge at the playhead when it is in the clip', () => {
    assert.deepEqual(at('Enter', 2000, 1600), { kind: 'set', ms: 1600, stopped: false })
    assert.deepEqual(at('Enter', 1600, 1600), { kind: 'stay' })
  })

  it('Enter with the playhead in another clip is refused and changes nothing', () => {
    assert.deepEqual(at('Enter', 2000, null), { kind: 'refused' })
  })

  it('Enter stopped by a limit says so', () => {
    assert.deepEqual(at('Enter', 2000, 4000), { kind: 'set', ms: 2360, stopped: true })
    assert.deepEqual(at('Enter', 2360, 4000), { kind: 'set', ms: 2360, stopped: true })
  })
})

describe('bareMousePress', () => {
  it('is a main-button mousedown that no pointerdown came before', () => {
    assert.equal(bareMousePress(false, 0), true)
  })

  it('is not one that follows a pointer press, which the handle’s own press handled', () => {
    assert.equal(bareMousePress(true, 0), false)
  })

  it('is not a secondary or middle button, which the browser keeps', () => {
    assert.equal(bareMousePress(false, 1), false)
    assert.equal(bareMousePress(false, 2), false)
  })

  it('hands the Firefox press to the nearer edge: the order that failed, two edges 4 px apart', () => {
    // Cut 1's end at 120.6 px and cut 2's start at 124.6 px; a press at 121.6 lands on cut 2's
    // start (on top) and belongs to cut 1's end. A bare mousedown asks for that hand-over.
    const edges = [
      { id: 'a1:out', px: 120.6 },
      { id: 'a2:in', px: 124.6 },
    ]
    assert.equal(bareMousePress(false, 0), true)
    assert.equal(nearestHandle(121.6, edges, 24), 'a1:out')
  })
})

describe('handleRows (timeline-ripple-layout)', () => {
  it('a leading or a trailing cut has no handle; interior and removed-number order kept', () => {
    const listed = [
      { in: 4, out: 5 },
      { in: 0, out: 1 },
      { in: 2, out: 3, removed: true },
      { in: 5.5, out: 7 },
      { in: 2.5, out: 3 },
    ]
    const kept = keptExtent(cutSpans(listed, 6020), 6020)
    assert.deepEqual(kept, { inMs: 1000, outMs: 5500 })
    assert.deepEqual(
      handleRows(listed, kept, 6020).map((row) => row.index),
      [4, 0],
    )
  })

  it('a handle taken to the clip’s start makes a leading cut: its handles are gone', () => {
    const before = [{ in: 1, out: 2.5 }]
    const after = [{ in: 0, out: 2.5 }]
    const keptOf = (l: typeof before) => keptExtent(cutSpans(l, 6020), 6020)
    assert.equal(handleRows(before, keptOf(before), 6020).length, 1)
    assert.equal(handleRows(after, keptOf(after), 6020).length, 0)
  })

  it('without edge cuts every cut that is not removed has handles', () => {
    const listed = [{ in: 1, out: 2 }, { in: 3, out: 4 }]
    assert.equal(handleRows(listed, { inMs: 0, outMs: 6020 }, 6020).length, 2)
  })
})

describe('selectionStands (timeline-ripple-layout)', () => {
  it('ends when the selected cut became part of a leading cut, or was removed', () => {
    const listed = [{ key: 'a', in: 0, out: 2.5 }, { key: 'b', in: 4, out: 5 }, { key: 'c', in: 3, out: 3.5, removed: true }]
    const kept = keptExtent(cutSpans(listed, 6020), 6020)
    assert.equal(selectionStands(listed, 'a', kept, 6020), false)
    assert.equal(selectionStands(listed, 'b', kept, 6020), true)
    assert.equal(selectionStands(listed, 'c', kept, 6020), false)
    assert.equal(selectionStands(listed, 'z', kept, 6020), false)
    assert.equal(selectionStands(listed, 'a', null, 6020), true)
  })
})
