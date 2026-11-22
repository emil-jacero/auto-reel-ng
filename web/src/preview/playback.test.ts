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
  regionName,
  skipAt,
  playheadWords,
  staleAdvice,
  timeCells,
  timeWords,
} from './playback.ts'
import type { Skip } from './playback.ts'

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
function replay(trace: readonly Callback[], spans: readonly Skip[], frameMs: number): Replay {
  const out: Replay = { seeks: [], cutShown: [], lost: [] }
  let clock = newFrameClock()
  let shownTo = (trace[0]?.[0] ?? 0) - frameMs
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

describe('how far ahead the frame loop looks for a cut', () => {
  // A 50 fps clip (20 ms frames) whose cut is [1000, 2000), and one at 25 fps.
  const cut = [{ from: 1000, to: 2000 }]
  const lastCut = [{ from: 2000, to: 3000 }]
  /** The clock after the given callbacks (a step is counted from the third one). */
  const clockAfter = (frameMs: number, times: readonly number[]) =>
    callbacksAt(frameMs, times).reduce((c, [at, p]) => frameTick(c, at, p), newFrameClock())

  it('looks nowhere while no step is known', () => {
    assert.equal(frameLookahead(newFrameClock()), 0)
    assert.equal(frameLookahead(clockAfter(20, [0, 20])), 0)
  })

  it('does not count the first step after the start or a seek', () => {
    assert.equal(frameLookahead(clockAfter(20, [0, 200])), 0)
    assert.deepEqual(clockAfter(20, [0, 200, 220]).recent, [20])
    const seeked = frameSeeked(clockAfter(20, [0, 20, 40, 60]))
    const after = [500, 700, 720].reduce(
      (c, at) => frameTick(c, at, at / 20),
      seeked,
    )
    assert.equal(after.recent.length, 3)
    assert.equal(Math.max(...after.recent), 20)
  })

  it('looks two frame intervals ahead when callbacks come on every frame', () => {
    assert.equal(frameLookahead(clockAfter(20, [0, 20, 40, 60])), 40)
    assert.equal(frameLookahead(clockAfter(40, [0, 40, 80, 120])), 80)
  })

  it('reads the frame interval from the frames presented between callbacks', () => {
    const clock = clockAfter(20, [0, 40, 80, 120])
    assert.equal(clock.interval, 20)
    assert.equal(frameLookahead(clock), 60)
  })

  it('keeps what it learned of the cadence over a seek', () => {
    const clock = frameSeeked(clockAfter(20, [0, 40, 80, 120]))
    assert.equal(frameLookahead(clock), 60)
  })

  it('leaves a stall out of the cadence and does not look a stall ahead', () => {
    const clock = clockAfter(20, [0, 20, 40, 60, 360])
    assert.equal(clock.step, 20)
    assert.equal(frameLookahead(clock), 40)
  })

  it('looks at most four frame intervals ahead', () => {
    // Steps of five frames are no stall, and are capped.
    const clock = clockAfter(20, [0, 20, 40, 140, 240, 340])
    assert.equal(frameLookahead(clock), 80)
  })

  it('forgets a gap after eight steps', () => {
    const times = [0, 20, 40, 100, ...Array.from({ length: 8 }, (_, i) => 120 + i * 20)]
    assert.equal(frameLookahead(clockAfter(20, times)), 40)
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

    it('Firefox, a callback on every second frame: at most one callback gap lost', () => {
      const run = replay(cadence(20, 2, 0, 3000), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.equal(run.seeks.length, 1)
      assert.ok((run.lost[0] as number) <= 2)
    })

    it('Firefox, an off-cycle callback at 940 before the cut at 1000 (920, 940, 1000)', () => {
      // Every second frame, but one callback off its cycle: the gap before the cut is 60 ms.
      const times = [...cadence(20, 2, 0, 920).map(([at]) => at), 940, 1000, 1040, 1080]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 940, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 2)
    })

    it('Firefox, the same trace after an early off-cycle callback showed the frame interval', () => {
      // Before 8139edaf's rule the lookahead was max(step, 2 * interval): 40 ms here, so the
      // cut's first frame (1000) came through after the callback at 940.
      const times = [0, 40, 80, 120, 140, ...cadence(20, 2, 180, 920).map(([at]) => at), 940, 1000]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 2)
    })

    for (const gap of [100, 140, 200]) {
      it(`Chrome, a ${gap} ms gap after the start: one kept frame lost at the first cut`, () => {
        for (const first of [[0, gap], [0, 20, 20 + gap]]) {
          const rest = cadence(20, 1, (first.at(-1) as number) + 20, 3000).map(([at]) => at)
          const run = replay(callbacksAt(20, [...first, ...rest]), lastCut, 20)
          assert.deepEqual(run.cutShown, [])
          assert.deepEqual(run.seeks, [{ at: 1960, to: 3000 }])
          assert.ok((run.lost[0] as number) <= 1)
        }
      })
    }

    it('Chrome, a 25 fps clip, a 200 ms gap after the start: one kept frame lost', () => {
      const run = replay(
        callbacksAt(40, [0, 40, 240, ...cadence(40, 1, 280, 3000).map(([at]) => at)]),
        lastCut,
        40,
      )
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Firefox, a 200 ms gap after the start: at most one callback gap lost', () => {
      const times = [0, 40, 240, ...cadence(20, 2, 280, 3000).map(([at]) => at)]
      const run = replay(callbacksAt(20, times), lastCut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 2)
    })

    it('Chrome, a 300 ms stall in mid-play: no more lost than without one', () => {
      const times = [...cadence(20, 1, 0, 500).map(([at]) => at), ...cadence(20, 1, 800, 3000).map(([at]) => at)]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Chrome, a stall that ends right before the cut: one kept frame lost', () => {
      // The callback at 960 comes 320 ms after the one before it; the loop does not
      // look 320 ms ahead, it seeks from 960.
      const times = [...cadence(20, 1, 0, 640).map(([at]) => at), ...cadence(20, 1, 960, 3000).map(([at]) => at)]
      const run = replay(callbacksAt(20, times), cut, 20)
      assert.deepEqual(run.cutShown, [])
      assert.deepEqual(run.seeks, [{ at: 960, to: 2000 }])
      assert.ok((run.lost[0] as number) <= 1)
    })

    it('Firefox, a stall in mid-play: at most one callback gap lost', () => {
      const times = [...cadence(20, 2, 0, 500).map(([at]) => at), ...cadence(20, 2, 800, 3000).map(([at]) => at)]
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

    it('Firefox, two cuts close together: both jumped, at most one callback gap lost', () => {
      const spans = [{ from: 1000, to: 1500 }, { from: 1580, to: 2000 }]
      const run = replay(cadence(20, 2, 0, 3000), spans, 20)
      assert.deepEqual(run.cutShown, [])
      assert.equal(run.seeks.length, 2)
      for (const lost of run.lost) {
        assert.ok(lost <= 2)
      }
    })
  })
})
