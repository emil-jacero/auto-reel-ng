import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  NOT_LOADED,
  NO_CLIP_TO_WATCH,
  SHOW_PLAYER,
  showPlayerName,
  STOP_EDITING,
  changedWords,
  closeName,
  frameLookahead,
  frameSeeked,
  frameTick,
  newFrameClock,
  goneWords,
  hidePlayerName,
  offersSkip,
  playFrom,
  regionName,
  skipAt,
  playheadWords,
  staleAdvice,
  timeCells,
  timeWords,
} from './playback.ts'
import type { FrameClock, Skip } from './playback.ts'

/*
 * The preview's words and rules that differ between Edit mode and the event page's
 * read view (`playback.ts`), run by `npm test`. The Edit-mode strings are copied here as
 * they were before the read view existed: they must not change by a byte.
 */

const OLD_STOP_EDITING =
  'Stop editing (save first if you want to keep your edits) to read the event again, then open ' +
  'the player anew.'

describe('the advice after a clip that is gone or changed on disk', () => {
  it('is Edit mode’s, byte for byte, unless the player is read-only', () => {
    assert.equal(STOP_EDITING, OLD_STOP_EDITING)
    assert.equal(staleAdvice(false), OLD_STOP_EDITING)
    assert.deepEqual(goneWords('a.mp4', 'Not found.'), {
      title: 'a.mp4 is no longer on disk.',
      detail: `Not found. ${OLD_STOP_EDITING}`,
    })
    assert.deepEqual(changedWords('a.mp4'), {
      title: 'a.mp4 changed on disk since the page was read.',
      detail: OLD_STOP_EDITING,
    })
    // The default is Edit mode's.
    assert.deepEqual(goneWords('a.mp4', 'Not found.', false), goneWords('a.mp4', 'Not found.'))
    assert.deepEqual(changedWords('a.mp4', false), changedWords('a.mp4'))
  })

  it('names Refresh when read-only, and says nothing of editing or saving', () => {
    const advice = staleAdvice(true)
    assert.match(advice, /Refresh/)
    assert.match(advice, /watch the clip anew/)
    for (const word of [/edit/i, /save/i, /Edit mode/i]) {
      assert.doesNotMatch(advice, word)
    }
    const gone = goneWords('a.mp4', 'Not found.', true)
    const changed = changedWords('a.mp4', true)
    assert.equal(gone.detail, `Not found. ${advice}`)
    // The service's detail has no full stop: the read view's advice is a sentence of its own.
    assert.equal(goneWords('a.mp4', 'no clip on disk', true).detail, `no clip on disk. ${advice}`)
    assert.equal(changed.detail, advice)
    assert.equal(gone.title, 'a.mp4 is no longer on disk.')
    for (const words of [gone, changed]) {
      assert.doesNotMatch(`${words.title} ${words.detail}`, /edit|save/i)
    }
  })
})

describe('offersSkip', () => {
  const cut = { in: 0, out: 1.5 }
  const removed = { in: 2, out: 3, removed: true }

  it('is always true in Edit mode, as it was', () => {
    assert.equal(offersSkip(false, []), true)
    assert.equal(offersSkip(false, [cut]), true)
    assert.equal(offersSkip(false, [removed]), true)
  })

  it('is false read-only with no cuts', () => {
    assert.equal(offersSkip(true, []), false)
  })

  it('is true read-only with one cut, or a cut beside a removed one', () => {
    assert.equal(offersSkip(true, [cut]), true)
    assert.equal(offersSkip(true, [removed, cut]), true)
  })

  it('is false read-only when every cut is removed', () => {
    assert.equal(offersSkip(true, [removed]), false)
  })
})

describe('the player\'s visible time', () => {
  it('says the clip, the time in it and its length, to centiseconds', () => {
    assert.equal(timeWords(20476, 20640), 'Clip 0:20.47 of 0:20.64')
    assert.equal(timeWords(20480, 20640), 'Clip 0:20.48 of 0:20.64')
    assert.equal(timeWords(0, 6020), 'Clip 0:00.00 of 0:06.02')
  })

  it('shows dashes of the same width before the length is read, never 0:00', () => {
    assert.equal(timeWords(0, null), 'Clip 0:00.00 of -:--.--')
    for (const unreadable of [0, Number.NaN, -5, Number.POSITIVE_INFINITY]) {
      assert.equal(timeWords(0, unreadable), 'Clip 0:00.00 of -:--.--')
    }
    const before = timeCells(0, null)
    const after = timeCells(0, 6020)
    assert.equal(before.time.ch, after.time.ch)
    assert.equal(before.length.ch, after.length.ch)
  })

  it('has one length for every millisecond of a 20.64 s clip and of a 10-minute one', () => {
    for (const length of [20_640, 600_000]) {
      const lengths = new Set<number>()
      for (let at = 0; at <= length; at += length > 100_000 ? 13 : 1) {
        lengths.add(timeWords(at, length).length)
      }
      assert.equal(lengths.size, 1, `clip of ${length} ms`)
    }
    assert.equal(timeWords(0, 600_000), 'Clip 00:00.00 of 10:00.00')
  })

  it('shows a playhead a millisecond past the length as the length', () => {
    assert.equal(timeWords(20641, 20640), 'Clip 0:20.64 of 0:20.64')
  })

  it('keeps the slider\'s words in the Cuts panel\'s form', () => {
    assert.equal(playheadWords(1234, 6020, []), '0:01.234 of 0:06.02')
  })
})

describe('the bin player’s words', () => {
  it('name the region, Hide player and Show player as the spec says', () => {
    assert.equal(regionName('s1710001.mp4'), 'Player for s1710001.mp4')
    assert.equal(hidePlayerName('s1710001.mp4'), 'Hide the player of s1710001.mp4')
    assert.equal(SHOW_PLAYER, 'Show player')
    assert.equal(showPlayerName(null), 'Show player')
    assert.equal(showPlayerName('s1710002.mp4'), 'Show player, s1710002.mp4')
    assert.equal(NO_CLIP_TO_WATCH, 'Select a clip to watch it.')
  })

  it('leave the read view’s Close as it was', () => {
    assert.equal(closeName('a.mp4'), 'Close the player of a.mp4')
  })

  it('say under a closed picture that nothing is loaded', () => {
    assert.equal(NOT_LOADED, 'Nothing is loaded until you press Play.')
  })
})

/** A callback: the frame's media time in ms and the frames presented so far. */
type Callback = readonly [mediaMs: number, presented: number]

/** Callbacks every `every`-th frame of a clip with `frameMs` frames, from `from` to `to` ms. */
function cadence(frameMs: number, every: number, from: number, to: number): Callback[] {
  const out: Callback[] = []
  for (let at = from; at <= to; at += frameMs * every) {
    out.push([at, at / frameMs])
  }
  return out
}

/** Callbacks at the given media times of a clip with `frameMs` frames. */
function callbacksAt(frameMs: number, times: readonly number[]): Callback[] {
  return times.map((at): Callback => [at, at / frameMs])
}

interface Replay {
  /** The seeks the loop made: at which callback, to where. */
  seeks: { at: number; to: number }[]
  /** Frames (in ms) the browser presented that lie inside a cut. */
  cutShown: number[]
  /** Kept frames before a cut that went unshown, for each seek. */
  lost: number[]
}

/**
 * Runs the frame loop's per-callback logic (the clock, the lookahead, `skipAt`) over a
 * callback trace of a clip with `frameMs` frames, with every frame the browser presents
 * between two callbacks counted as shown. A seek lands at once, and the trace goes on
 * with the first callback at or after its target (and the clock told of the seek).
 */
function replay(
  trace: readonly Callback[],
  spans: readonly Skip[],
  frameMs: number,
  /** The clock a play resumes with (settling), and the frame already on screen at its start. */
  start: { clock?: FrameClock; shownFrom?: number } = {},
): Replay {
  const out: Replay = { seeks: [], cutShown: [], lost: [] }
  let clock = start.clock === undefined ? newFrameClock() : frameSeeked(start.clock)
  let shownTo = start.shownFrom ?? (trace[0]?.[0] ?? 0) - frameMs
  const show = (upTo: number) => {
    for (let t = shownTo + frameMs; t <= upTo; t += frameMs) {
      if (spans.some((skip) => skip.from <= t && t < skip.to)) {
        out.cutShown.push(t)
      }
    }
    shownTo = Math.max(shownTo, upTo)
  }
  for (let i = 0; i < trace.length; i += 1) {
    const [at, presented] = trace[i] as Callback
    show(at)
    clock = frameTick(clock, at, presented)
    const action = skipAt(spans, at, frameLookahead(clock), 1_000_000)
    if (action === null || !('seek' in action)) {
      continue
    }
    const span = spans.find((skip) => skip.to === action.seek) as Skip
    out.seeks.push({ at, to: action.seek })
    out.lost.push(Math.max(0, (span.from - at) / frameMs - 1))
    clock = frameSeeked(clock)
    shownTo = action.seek - frameMs
    while (i + 1 < trace.length && (trace[i + 1] as Callback)[0] < action.seek) {
      i += 1
    }
  }
  return out
}

/** A clip long enough that nothing in these traces is near its end. */
const LONG = 1_000_000

/** The callback times of a browser's cadence: every `every`-th frame from `from` to `to`. */
const grid = (frameMs: number, every: number, from: number, to: number) =>
  cadence(frameMs, every, from, to).map(([at]) => at)

/** The cadences browsers show: [name, frame ms, calls back every n-th frame]. */
const CADENCES: readonly (readonly [string, number, number])[] = [
  ['Chrome 50 fps', 20, 1],
  ['Chrome 25 fps', 40, 1],
  ['Firefox 50 fps', 20, 2],
  ['Firefox 25 fps', 40, 2],
]

/** The most kept frames a cadence may lose before a cut: one every frame, two every second. */
const bound = (every: number) => every

/** A clock that has learned `frameMs`/`every` from a steady run. */
const learned = (frameMs: number, every: number): FrameClock =>
  callbacksAt(frameMs, grid(frameMs, every, 0, 400)).reduce(
    (c, [at, p]) => frameTick(c, at, p),
    newFrameClock(),
  )

describe('how far ahead the frame loop looks for a cut', () => {
  // A 50 fps clip (20 ms frames) whose cut is [1000, 2000), and one at 25 fps.
  const cut = [{ from: 1000, to: 2000 }]
  const lastCut = [{ from: 2000, to: 3000 }]
  /** The clock after the given callbacks (a step is counted from the third one). */
  const clockAfter = (frameMs: number, times: readonly number[]) =>
    callbacksAt(frameMs, times).reduce((c, [at, p]) => frameTick(c, at, p), newFrameClock())

  it('looks a fixed 125 ms ahead until three steps are counted', () => {
    assert.equal(frameLookahead(newFrameClock()), 125)
    assert.equal(frameLookahead(clockAfter(20, [0, 20])), 125)
    assert.equal(frameLookahead(clockAfter(20, [0, 200])), 125)
    assert.equal(frameLookahead(clockAfter(20, [0, 20, 40, 60])), 125)
    assert.equal(frameLookahead(clockAfter(20, [0, 20, 40, 60, 80])), 40)
  })

  it('does not count the first step after the start or a seek', () => {
    assert.deepEqual(clockAfter(20, [0, 200, 220]).recent, [20])
    const seeked = frameSeeked(clockAfter(20, [0, 20, 40, 60]))
    const after = [500, 700, 720].reduce((c, at) => frameTick(c, at, at / 20), seeked)
    assert.equal(after.recent.length, 3)
    assert.equal(Math.max(...after.recent), 20)
  })

  it('looks two frame intervals ahead when callbacks come on every frame', () => {
    assert.equal(frameLookahead(clockAfter(20, [0, 20, 40, 60, 80])), 40)
    assert.equal(frameLookahead(clockAfter(40, [0, 40, 80, 120, 160])), 80)
  })

  it('looks one callback gap and a frame ahead on every second frame', () => {
    const clock = clockAfter(20, [0, 40, 80, 120, 160])
    assert.equal(clock.interval, 20)
    assert.equal(frameLookahead(clock), 60)
  })

  it('keeps what it learned of the cadence over a seek and over a resumed play', () => {
    const clock = frameSeeked(clockAfter(20, [0, 40, 80, 120, 160]))
    assert.equal(frameLookahead(clock), 60)
    assert.equal(frameLookahead(frameSeeked(learned(20, 1))), 40)
  })

  it('leaves a stall out of the cadence and does not look a stall ahead', () => {
    const clock = clockAfter(20, [0, 20, 40, 60, 80, 380])
    assert.equal(clock.step, 20)
    assert.equal(frameLookahead(clock), 40)
  })

  it('leaves a stall out before any frame interval is known', () => {
    assert.deepEqual(clockAfter(20, [0, 20, 400]).recent, [])
    assert.deepEqual(clockAfter(20, [0, 20, 400, 420]).recent, [20])
  })

  it('looks at most four frame intervals ahead', () => {
    // Steps of five frames are no stall, and are capped.
    const clock = clockAfter(20, [0, 20, 40, 140, 240, 340])
    assert.equal(frameLookahead(clock), 80)
  })

  it('does not let one odd step among the last eight widen it', () => {
    // A dropped frame (40 ms), and an early callback (20 ms of a 40 ms cadence), long ago.
    const chrome = clockAfter(20, [0, 20, 40, 60, 80, 120, 140, 160, 180, 200, 220])
    assert.equal(frameLookahead(chrome), 40)
    const firefox = clockAfter(20, [0, 40, 80, 120, 160, 180, 240, 280, 320, 360])
    assert.equal(frameLookahead(firefox), 60)
  })

  it('does not look less far after an early callback, nor more after a late one on every frame', () => {
    const early = clockAfter(20, [0, 40, 80, 120, 160, 200, 220])
    assert.equal(early.step, 20)
    assert.equal(frameLookahead(early), 60)
    const dropped = clockAfter(20, [0, 20, 40, 60, 80, 120])
    assert.equal(dropped.step, 40)
    assert.equal(frameLookahead(dropped), 40)
  })

  it('does not start from a startup step that dropped frames', () => {
    // 0, 20, then 200 ms with one frame presented, then steady: the interval recovers.
    const clock = callbacksAt(20, [0, 20, 220, 240, 260]).reduce(
      (c, [at], i) => frameTick(c, at, i < 3 ? i : at / 20 - 9),
      newFrameClock(),
    )
    assert.deepEqual(clock.recent, [200, 20, 20])
    assert.equal(frameLookahead(clock), 40)
  })

  describe('skipAt', () => {
    it('looks at the whole window, so a cut narrower than it is not stepped over', () => {
      const narrow = [{ from: 1000, to: 1020 }]
      assert.deepEqual(skipAt(narrow, 980, 40, LONG), { seek: 1020 })
      assert.deepEqual(skipAt(narrow, 960, 40, LONG), { seek: 1020 })
      assert.equal(skipAt(narrow, 940, 40, LONG), null)
      assert.equal(skipAt(narrow, 1020, 40, LONG), null)
    })

    it('leaves the frame that straddles a seek target alone', () => {
      assert.equal(skipAt([{ from: 1000, to: 1010 }], 1010, 40, LONG), null)
    })

    it('stops at the start of a cut that runs to the end', () => {
      assert.deepEqual(skipAt([{ from: 2000, to: 2060 }], 1960, 40, 2060), { stop: 2000 })
    })
  })

  describe('playFrom', () => {
    it('starts where it always did without a lookahead', () => {
      assert.equal(playFrom(cut, 960, LONG), 960)
      assert.equal(playFrom(cut, 1500, LONG), 2000)
    })

    it('jumps a cut that starts within the lookahead of the start', () => {
      assert.equal(playFrom(cut, 960, LONG, 40), 2000)
      assert.equal(playFrom(cut, 940, LONG, 40), 940)
      assert.equal(playFrom(cut, 940, LONG, 125), 2000)
    })

    it('goes on over a second cut that starts within the lookahead of the first one’s end', () => {
      const two = [{ from: 1000, to: 1500 }, { from: 1540, to: 2000 }]
      assert.equal(playFrom(two, 980, LONG, 60), 2000)
    })

    it('starts at the first footage when a cut to the end starts within the lookahead', () => {
      assert.equal(playFrom([{ from: 2000, to: 2060 }], 1960, 2060, 125), 0)
    })

    it('is null when the cuts cover the whole clip', () => {
      assert.equal(playFrom([{ from: 0, to: 2060 }], 1000, 2060, 125), null)
    })
  })

  describe('replaying whole callback traces', () => {
    it('Chrome, a callback on every frame of a 50 fps clip: one kept frame lost', () => {
      const run = replay(cadence(20, 1, 0, 3000), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Chrome, a 25 fps clip: one kept frame lost', () => {
      const run = replay(cadence(40, 1, 0, 3000), cut, 40)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 920, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Firefox, a callback on every second frame: one kept frame lost', () => {
      const run = replay(cadence(20, 2, 0, 3000), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Firefox, a cut on the cycle’s other phase: two kept frames lost, no more', () => {
      const run = replay(cadence(20, 2, 0, 3000), [{ from: 1020, to: 2000 }], 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.equal(run.lost[0], 2)
    })

    it('Firefox, an off-cycle callback at 940 before the cut at 1000 (920, 940, 1000)', () => {
      // Every second frame, but one callback off its cycle: the gap before the cut is 60 ms.
      const times = [...grid(20, 2, 0, 920), 940, 1000, 1040, 1080]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 940, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 2)
    })

    it('Firefox, an early off-cycle callback at 140, then a missing one before the cut', () => {
      // 900, 940, then 1000: the callback at 960 is missing.
      const times = [0, 40, 80, 120, 140, ...grid(20, 2, 180, 920), 940, 1000]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 940, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 2)
    })

    for (const gap of [100, 140, 200]) {
      it(`Chrome, a ${gap} ms gap after the start: one kept frame lost at the first cut`, () => {
        for (const first of [[0, gap], [0, 20, 20 + gap]]) {
          const rest = grid(20, 1, (first.at(-1) as number) + 20, 3000)
          const run = replay(callbacksAt(20, [...first, ...rest]), lastCut, 20)
          assert.deepEqual(run.cutShown, [])
          assert.deepEqual(run.seeks, [{ at: 1960, to: 3000 }])
          assert.ok((run.lost[0] as number) <= 1)
        }
      })
    }

    it('Chrome, a startup gap in which frames were dropped, not presented', () => {
      // 0, 20, then 200 ms with one frame presented: the interval must not become 200.
      const times = [0, 20, 220, ...grid(20, 1, 240, 3000)]
      const trace = callbacksAt(20, times).map(([at, p], i): Callback => [at, i < 3 ? i : p - 9])
      const run = replay(trace, [{ from: 600, to: 1500 }], 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 560, to: 1500 }])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Chrome, a 25 fps clip, a 200 ms gap after the start: one kept frame lost', () => {
      const run = replay(
        callbacksAt(40, [0, 40, 240, ...grid(40, 1, 280, 3000)]),
        lastCut,
        40,
      )
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Firefox, a 200 ms gap after the start: at most two kept frames lost', () => {
      const run = replay(callbacksAt(20, [0, 40, 240, ...grid(20, 2, 280, 3000)]), lastCut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 2)
    })

    it('Chrome, a 300 ms stall in mid-play: no more lost than without one', () => {
      const times = [...grid(20, 1, 0, 500), ...grid(20, 1, 800, 3000)]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Chrome, a stall that ends right before the cut: one kept frame lost', () => {
      // The callback at 960 comes 320 ms after the one before it; the loop does not
      // look 320 ms ahead, it seeks from 960.
      const times = [...grid(20, 1, 0, 640), ...grid(20, 1, 960, 3000)]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Firefox, a stall in mid-play: at most two kept frames lost', () => {
      const times = [...grid(20, 2, 0, 500), ...grid(20, 2, 800, 3000)]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 2)
    })

    it('Chrome, two cuts a frame apart: both jumped, no kept frame lost after the first', () => {
      const spans = [{ from: 1000, to: 1500 }, { from: 1520, to: 2000 }]
      const run = replay(cadence(20, 1, 0, 3000), spans, 20)
      assert.deepEqual(run.cutShown, [])
      assert.equal(run.seeks.length, 2)
      assert.ok((run.lost[0] as number) <= 1)
      assert.equal(run.lost[1], 0)
    })

    it('Firefox, two cuts close together: both jumped, at most two kept frames lost each', () => {
      const spans = [{ from: 1000, to: 1500 }, { from: 1580, to: 2000 }]
      const run = replay(cadence(20, 2, 0, 3000), spans, 20)
      assert.deepEqual(run.cutShown, [])
      assert.equal(run.seeks.length, 2)
      for (const lost of run.lost) {
        assert.ok(lost <= 2)
      }
    })

    for (const [name, frameMs, every] of CADENCES) {
      it(`${name}, a cut of one frame: jumped, not stepped over`, () => {
        for (let phase = 0; phase < every; phase += 1) {
          const from = 1000 + phase * frameMs
          const run = replay(cadence(frameMs, every, 0, 3000), [{ from, to: from + frameMs }], frameMs)
          assert.deepEqual(run.cutShown, [])
          assert.equal(run.seeks.length, 1)
          assert.ok((run.lost[0] as number) <= bound(every))
        }
      })
    }
  })

  describe('one dropped or off-cycle callback within eight callbacks of a cut', () => {
    for (const [name, frameMs, every] of CADENCES) {
      const stride = frameMs * every
      // Every frame-aligned cut position over two callback cycles.
      const cuts = Array.from({ length: 2 * every }, (_, j) => 2000 + j * frameMs)

      it(`${name}: a ${every === 1 ? 'dropped' : 'late'} callback loses at most ${bound(every)} kept frame${every === 1 ? '' : 's'}`, () => {
        for (const from of cuts) {
          for (let before = 0; before <= 9; before += 1) {
            const odd = Math.floor(from / stride) * stride - before * stride
            // Every frame: the callback is missing (a 2-frame step). Every second frame: it
            // comes one frame late (a step of 3 frames, then 1).
            const times = grid(frameMs, every, 0, 4000).flatMap((at) =>
              at !== odd ? [at] : every === 1 ? [] : [at + frameMs],
            )
            const run = replay(callbacksAt(frameMs, times), [{ from, to: from + 1000 }], frameMs)
            assert.deepEqual(run.cutShown, [], `cut ${from}, odd callback ${odd}`)
            assert.equal(run.seeks.length, 1, `cut ${from}, odd callback ${odd}`)
            assert.ok((run.lost[0] as number) <= bound(every), `cut ${from}, odd callback ${odd}`)
          }
        }
      })

      if (every === 1) {
        continue
      }

      it(`${name}: an extra early callback, the next on-cycle one missing (920, 940, 1000)`, () => {
        for (const from of cuts) {
          for (let before = 0; before <= 9; before += 1) {
            const off = Math.floor(from / stride) * stride - before * stride
            const times = [
              ...grid(frameMs, every, 0, off),
              off + frameMs,
              ...grid(frameMs, every, off + 2 * stride, 4000),
            ]
            const run = replay(callbacksAt(frameMs, times), [{ from, to: from + 1000 }], frameMs)
            assert.deepEqual(run.cutShown, [], `cut ${from}, off-cycle after ${off}`)
            assert.equal(run.seeks.length, 1, `cut ${from}, off-cycle after ${off}`)
            assert.ok((run.lost[0] as number) <= 2, `cut ${from}, off-cycle after ${off}`)
          }
        }
      })

      it(`${name}: an extra early callback, the cycle then shifted by a frame`, () => {
        for (const from of cuts) {
          for (let before = 0; before <= 9; before += 1) {
            const off = Math.floor(from / stride) * stride - before * stride
            const times = [
              ...grid(frameMs, every, 0, off),
              off + frameMs,
              ...grid(frameMs, every, off + frameMs + stride, 4000),
            ]
            const run = replay(callbacksAt(frameMs, times), [{ from, to: from + 1000 }], frameMs)
            assert.deepEqual(run.cutShown, [], `cut ${from}, shifted after ${off}`)
            assert.equal(run.seeks.length, 1, `cut ${from}, shifted after ${off}`)
            assert.ok((run.lost[0] as number) <= 2, `cut ${from}, shifted after ${off}`)
          }
        }
      })
    }

    it('Chrome 50 fps: one dropped frame at 860 to 900, the cut at 1000: one kept frame lost', () => {
      const run = replay(callbacksAt(20, [...grid(20, 1, 0, 860), ...grid(20, 1, 900, 3000)]), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.equal(run.lost[0], 1)
    })

    it('Firefox 50 fps: an off-cycle 780, 840 within the window of the cut at 1000: one lost', () => {
      const times = [...grid(20, 2, 0, 760), 780, 840, ...grid(20, 2, 880, 3000)]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.equal(run.lost[0], 1)
    })
  })

  describe('Play started shortly before a cut', () => {
    for (const [name, frameMs, every] of CADENCES) {
      const stride = frameMs * every
      for (const [known, clock] of [
        ['a clip not played before', undefined],
        ['a clip whose cadence is known', learned(frameMs, every)],
      ] as const) {
        it(`${name}, ${known}: no cut frame from 20, 40, 60, 100 or 140 ms before the cut`, () => {
          for (const from of [1000, 1000 + frameMs]) {
            for (const before of [20, 40, 60, 100, 140]) {
              for (const firstAfter of [0, frameMs, stride]) {
                const at = from - before
                const ahead = clock === undefined ? 125 : frameLookahead(clock)
                const begins = playFrom([{ from, to: 2000 }], at, LONG, ahead) as number
                const trace = callbacksAt(frameMs, grid(frameMs, every, begins + firstAfter, 4000))
                const run = replay(trace, [{ from, to: 2000 }], frameMs, {
                  clock,
                  shownFrom: begins,
                })
                const label = `${name}: cut ${from}, play at ${at}, first callback +${firstAfter}`
                assert.deepEqual(run.cutShown, [], label)
              }
            }
          }
        })
      }
    }

    it('keeps the clock over a pause: the callbacks after Play look as far as before', () => {
      const clock = frameSeeked(learned(20, 2))
      assert.equal(frameLookahead(clock), 60)
      const run = replay(callbacksAt(20, grid(20, 2, 940, 3000)), cut, 20, {
        clock: learned(20, 2),
        shownFrom: 940,
      })
      assert.deepEqual(run.cutShown, [])
    })
  })
})
