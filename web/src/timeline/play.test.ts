import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { cardMap, cardPlacements, trackLayout } from './cards.ts'
import type { CardClip, CardSpec } from './cards.ts'
import { ModelError, layout } from './model.ts'
import {
  createCardClock,
  fadesOf,
  handOverMs,
  handOverReady,
  opacityAt,
  positionOnTrack,
  shownAt,
  stagesOf,
  stepFramesOnTrack,
  trackStart,
  videoTarget,
} from './play.ts'
import { globalMs } from './position.ts'

/*
 * The play clock of the Timeline (`play.ts`, `timeline-plays-cards`), against the scenarios of
 * "The model plays a movie of clips and cards on one clock".
 */

const spec = (chapter: string, seconds: number, background = 'black'): CardSpec => ({
  chapter,
  card: {
    duration: seconds,
    background,
    title: 't',
    subtitle: '',
    defaultSubtitle: '',
    fontFamily: 'Sofia Sans',
  },
  error: null,
})
const clipOf = (chapter: number, durationMs: number, spans: CardClip['spans'] = []): CardClip => ({
  chapter,
  durationMs,
  spans,
})
const names = ['', 'Dag 2']

/** Two chapters of one 20 s clip each, black cards of 3 s and 4 s: card, clip, card, clip. */
function movie(specs = [spec('', 3), spec('Dag 2', 4)], clips = [clipOf(0, 20000), clipOf(1, 20000)]) {
  const placements = cardPlacements(specs, clips, 'on')
  const facts = clips.map((c) => ({ durationMs: c.durationMs, fps: 25 }))
  const lay = layout(facts)
  const map = cardMap(placements, lay)
  return { placements, facts, lay, map, track: trackLayout(lay, map) }
}

describe('stages', () => {
  it('add up to the track', () => {
    const { map, lay } = movie()
    const stages = stagesOf(map, lay)
    assert.deepEqual(
      stages.map((s) => [s.kind, s.startMs, s.lengthMs]),
      [
        ['card', 0, 3000],
        ['clip', 3000, 20000],
        ['card', 23000, 4000],
        ['clip', 27000, 20000],
      ],
    )
    const last = stages[stages.length - 1]
    assert.equal(last.startMs + last.lengthMs, 47000)
    assert.equal(lay.totalMs + map.totalMs, 47000)
  })

  it('has no card stage for a video card', () => {
    const { map, lay } = movie([spec('', 3, 'video'), spec('Dag 2', 4)])
    assert.deepEqual(stagesOf(map, lay).map((s) => s.kind), ['clip', 'card', 'clip'])
  })
})

describe('a position on the track', () => {
  const { map, lay, facts, track } = movie()

  it('is in the card at the elapsed time, with the anchor clip at clip time 0', () => {
    const p = positionOnTrack(map, lay, facts, names, 1500)
    assert.equal(p.clip, 0)
    assert.equal(p.ms, 0)
    assert.deepEqual(p.card, { chapter: 0, name: '', ms: 1500, lengthMs: 3000 })
    assert.equal(globalMs(track, p), 1500)
  })

  it('round-trips every whole second', () => {
    for (let t = 0; t < 47000; t += 1000) {
      assert.equal(globalMs(track, positionOnTrack(map, lay, facts, names, t)), t, `at ${t}`)
    }
  })

  it('takes a boundary as the later stage’s start', () => {
    assert.equal(positionOnTrack(map, lay, facts, names, 3000).card, undefined)
    assert.equal(positionOnTrack(map, lay, facts, names, 3000).clip, 0)
    const into = positionOnTrack(map, lay, facts, names, 23000)
    assert.equal(into.card?.chapter, 1)
    assert.equal(into.card?.ms, 0)
    assert.equal(into.clip, 1)
  })

  it('holds a time before zero to the first instant and past the end to the last frame', () => {
    assert.deepEqual(positionOnTrack(map, lay, facts, names, -500).card?.ms, 0)
    const end = positionOnTrack(map, lay, facts, names, 99999)
    assert.equal(end.clip, 1)
    assert.equal(end.card, undefined)
    assert.equal(end.ms, 19960)
  })

  it('maps a press inside a card, at both of its edges, and a drag across it', () => {
    const at = (ms: number) => positionOnTrack(map, lay, facts, names, ms)
    // The second card spans 23,000 to 27,000 ms of the track.
    assert.equal(at(23000).card?.ms, 0)
    assert.equal(at(24000).card?.ms, 1000)
    assert.equal(at(26999).card?.ms, 3999)
    assert.equal(at(27000).card, undefined)
    assert.equal(at(27000).clip, 1)
    assert.equal(at(27000).ms, 0)
    // A drag from the end of clip 1 through the card to the next clip never goes backwards and stays one card.
    const path = [22960, 23000, 24500, 26999, 27000].map(at)
    assert.deepEqual(path.map((p) => p.card?.ms ?? null), [null, 0, 1500, 3999, null])
    assert.deepEqual(path.map((p) => p.clip), [0, 1, 1, 1, 1])
  })

  it('starts the track in the opening card when it is black, else on the first frame', () => {
    assert.equal(trackStart(map, lay, facts, names).card?.chapter, 0)
    const plain = movie([spec('', 3, 'video'), spec('Dag 2', 4)])
    assert.equal(trackStart(plain.map, plain.lay, plain.facts, names).card, undefined)
  })
})

describe('opacity', () => {
  it('follows the 2 s fades of a 7 s card', () => {
    const at = [0, 1000, 2000, 3500, 5000, 6000, 7000].map((ms) => opacityAt(ms, 7000))
    assert.deepEqual(at, [0, 0.5, 1, 1, 1, 0.5, 0])
  })

  it('clamps the fades together in a short card', () => {
    assert.deepEqual(fadesOf(2000), { inMs: 1000, outMs: 1000 })
    assert.equal(opacityAt(500, 2000), 0.5)
    assert.equal(opacityAt(1000, 2000), 1)
  })

  it('refuses a bad length, naming the card', () => {
    for (const bad of [0, Number.NaN, -1, Number.POSITIVE_INFINITY]) {
      assert.throws(() => opacityAt(0, bad), ModelError)
      assert.throws(() => createCardClock().start(0, 0, bad), (e: Error) => /title card/.test(e.message))
    }
  })
})

describe('what is shown', () => {
  it('is a black card with its opacity inside it', () => {
    const { placements, map, lay, facts } = movie()
    const p = positionOnTrack(map, lay, facts, names, 1000)
    // A 3 s card fades 1.5 s each way (the 2 s fades, clamped together).
    const shown = shownAt(p, placements)
    assert.equal(shown.kind, 'black')
    assert.ok(Math.abs((shown as { opacity: number }).opacity - 1000 / 1500) < 1e-9)
  })

  it('is a video card’s window over the clip and nowhere else', () => {
    const specs = [spec('', 4, 'video')]
    const clips = [clipOf(0, 13000, [{ from: 0, to: 3000 }])]
    const { placements } = movie(specs, clips)
    const at = (ms: number) => shownAt({ clip: 0, ms }, placements)
    assert.equal(at(2999).kind, 'clip')
    assert.deepEqual(at(3000), { kind: 'video', chapter: 0, opacity: 0 })
    assert.equal((at(5000) as { opacity: number }).opacity, 1)
    assert.equal((at(4000) as { opacity: number }).opacity, 0.5)
    assert.equal(at(6999).kind, 'video')
    assert.equal(at(7000).kind, 'clip')
  })

  it('shows nothing over a clip with a black card or no card', () => {
    const { placements } = movie()
    assert.equal(shownAt({ clip: 0, ms: 500 }, placements).kind, 'clip')
  })
})

describe('the hand-over', () => {
  it('is the anchor clip’s start, or the end of a cut that begins at zero', () => {
    assert.equal(handOverMs([]), 0)
    assert.equal(handOverMs([{ from: 0, to: 3000 }]), 3000)
    assert.equal(handOverMs([{ from: 1000, to: 3000 }]), 0)
    assert.deepEqual(
      videoTarget({ clip: 1, ms: 0, card: { chapter: 1, name: 'x', ms: 500, lengthMs: 4000 } }, () => [
        { from: 0, to: 3000 },
      ]),
      { clip: 1, ms: 3000 },
    )
    assert.deepEqual(videoTarget({ clip: 1, ms: 700 }, () => []), { clip: 1, ms: 700 })
  })

  it('waits for the seek: the clip must be loaded and settled', () => {
    assert.equal(handOverReady({ busy: false, loadedClip: 1, anchor: 1 }), true)
    assert.equal(handOverReady({ busy: true, loadedClip: 1, anchor: 1 }), false)
    assert.equal(handOverReady({ busy: false, loadedClip: 0, anchor: 1 }), false)
    assert.equal(handOverReady({ busy: false, loadedClip: null, anchor: 1 }), false)
  })
})

describe('the card clock', () => {
  it('is held to the length and says when the hand-over is due', () => {
    const clock = createCardClock()
    clock.start(1000, 0, 7000)
    assert.deepEqual(clock.read(1000 + 9000), { ms: 7000, due: true })
    assert.deepEqual(clock.read(1000 + 3000), { ms: 3000, due: false })
  })

  it('counts elapsed time, not frames: a slow frame does not stretch the card', () => {
    const clock = createCardClock()
    clock.start(0, 0, 7000)
    // Frames at 16 ms, then nothing for 500 ms, then on.
    for (const now of [16, 32, 48]) {
      assert.equal(clock.read(now).due, false)
    }
    assert.equal(clock.read(548).ms, 548)
    assert.equal(clock.read(6999).due, false)
    assert.equal(clock.read(7000).due, true)
  })

  it('pauses at 1.2 s and ends the card 5.8 s after Play', () => {
    const clock = createCardClock()
    clock.start(0, 0, 7000)
    assert.equal(clock.stop(1200), 1200)
    assert.equal(clock.running(), false)
    assert.equal(clock.read(60000).ms, 1200)
    clock.start(60000, 1200, 7000)
    assert.equal(clock.read(60000 + 5799).due, false)
    assert.equal(clock.read(60000 + 5800).due, true)
  })
})

describe('steps across cards', () => {
  const { map, lay, facts } = movie()
  const first = () => 0
  const step = (p: Parameters<typeof stepFramesOnTrack>[4], n: number) =>
    stepFramesOnTrack(map, facts, names, first, p, n)

  it('skips nothing: a step into a card lands on its first instant', () => {
    const next = step({ clip: 0, ms: 19960 }, 1)
    assert.equal(next.card?.chapter, 1)
    assert.equal(next.card?.ms, 0)
  })

  it('moves by 0.1 s inside a card, and leaves it on the clip’s first frame', () => {
    const inside = positionOnTrack(map, lay, facts, names, 1000)
    assert.equal(step(inside, 1).card?.ms, 1100)
    assert.equal(step(inside, -1).card?.ms, 900)
    const last = positionOnTrack(map, lay, facts, names, 2950)
    assert.deepEqual(step(last, 1), { clip: 0, ms: 0 })
  })

  it('leaves a card backwards onto the last frame of the clip before it, and holds at the very start', () => {
    const second = positionOnTrack(map, lay, facts, names, 23010)
    assert.deepEqual(step(second, -1), { clip: 0, ms: 19960 })
    const open = positionOnTrack(map, lay, facts, names, 20)
    assert.equal(step(open, -1).card?.ms, 0)
  })

  it('steps back from a clip’s first frame into the end of its card', () => {
    const back = step({ clip: 1, ms: 0 }, -1)
    assert.equal(back.card?.chapter, 1)
    assert.equal(back.card?.ms, 3900)
  })
})
