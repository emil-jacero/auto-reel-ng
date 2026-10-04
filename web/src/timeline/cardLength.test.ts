import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import {
  CARD_MAX_TENTHS,
  CARD_MIN_TENTHS,
  cardCell,
  cardKey,
  cardLimits,
  cardTenthsAt,
  cardValueText,
  releasedWords,
  secondsToTenths,
  tenthsToSeconds,
} from './cardLength.ts'
import { cardBlocks, cardHandles, cardMap, cardPlacements, trackLayout, withDurations } from './cards.ts'
import type { CardClip, CardSpec } from './cards.ts'
import { ModelError, layout } from './model.ts'

/* The `timeline` delta of `title-card-duration-drag`, scenario by scenario. */

describe('cardLimits', () => {
  it('a black card runs 0.5 s to 60 s', () => {
    assert.deepEqual(cardLimits({ background: 'black', currentTenths: 40, keptMs: 1000 }), {
      adjustable: true,
      min: 5,
      max: 600,
    })
  })

  it('a video card is held to its first kept span, cut to a tenth, and keeps its current value', () => {
    const range = cardLimits({ background: 'video', currentTenths: 30, keptMs: 2450 })
    assert.deepEqual(range, { adjustable: true, min: 5, max: 30 })
    // With room to grow the footage is the limit.
    assert.deepEqual(cardLimits({ background: 'video', currentTenths: 20, keptMs: 2450 }), {
      adjustable: true,
      min: 5,
      max: 24,
    })
  })

  it('a video card longer than its footage can only go down: its value is inside the range', () => {
    assert.deepEqual(cardLimits({ background: 'video', currentTenths: 50, keptMs: 3000 }), {
      adjustable: true,
      min: 5,
      max: 50,
    })
  })

  it('a span too short for a card, and a chapter with no footage, are not adjustable, with the reason', () => {
    const short = cardLimits({ background: 'video', currentTenths: 40, keptMs: 400 })
    assert.equal(short.adjustable, false)
    assert.match((short as { reason: string }).reason, /0\.4 s/)
    const none = cardLimits({ background: 'video', currentTenths: 40, keptMs: null })
    assert.equal(none.adjustable, false)
    assert.match((none as { reason: string }).reason, /no footage/)
  })

  it('refuses a non-finite or negative input by name', () => {
    assert.throws(() => cardLimits({ background: 'black', currentTenths: Number.NaN, keptMs: 1 }), ModelError)
    assert.throws(() => cardLimits({ background: 'video', currentTenths: 4, keptMs: -1 }), /footage length/)
    assert.throws(() => secondsToTenths(-1), /card duration in seconds/)
    assert.throws(() => tenthsToSeconds(Number.POSITIVE_INFINITY), ModelError)
  })

  it('the mirrored constants match the engine', () => {
    const source = readFileSync(new URL('../../../auto_reel_ng/reel/card.py', import.meta.url), 'utf8')
    const read = (name: string) => {
      const found = new RegExp(`^${name}\\s*=\\s*([0-9.]+)`, 'm').exec(source)
      assert.ok(found, `${name} is in reel/card.py`)
      return Number(found[1])
    }
    const min = read('CARD_MIN_DURATION')
    const max = read('CARD_MAX_DURATION')
    assert.equal(secondsToTenths(min), CARD_MIN_TENTHS, `engine minimum ${min} s vs web ${CARD_MIN_TENTHS / 10} s`)
    assert.equal(secondsToTenths(max), CARD_MAX_TENTHS, `engine maximum ${max} s vs web ${CARD_MAX_TENTHS / 10} s`)
  })
})

describe('cardTenthsAt', () => {
  const full = { min: 5, max: 600 }

  it('a pointer between tenths lands on a tenth, and a near whole second snaps', () => {
    assert.deepEqual(cardTenthsAt(4040, 40, full), { tenths: 40, snapped: true })
  })

  it('a zoomed-out view takes the whole second within 8 px', () => {
    assert.deepEqual(cardTenthsAt(4900, 4, full), { tenths: 50, snapped: true })
  })

  it('no snap away from a whole second', () => {
    assert.deepEqual(cardTenthsAt(4460, 240, full), { tenths: 45, snapped: false })
  })

  it('a snap the limits refuse is not taken', () => {
    assert.deepEqual(cardTenthsAt(2600, 20, { min: 5, max: 24 }), { tenths: 24, snapped: false })
  })

  it('stops at the limits whatever the pointer does', () => {
    assert.deepEqual(cardTenthsAt(0, 40, full), { tenths: 5, snapped: false })
    assert.deepEqual(cardTenthsAt(90_000, 40, full), { tenths: 600, snapped: false })
  })

  it('of two equally near whole seconds the earlier is taken', () => {
    // 4.5 s at 4 px/s: 4 s and 5 s are both 2 px away.
    assert.deepEqual(cardTenthsAt(4500, 4, full), { tenths: 40, snapped: true })
  })

  it('never produces a value with a float error', () => {
    for (let ms = 0; ms < 61_000; ms += 37) {
      const { tenths } = cardTenthsAt(ms, 40, full)
      assert.ok(Number.isInteger(tenths))
      assert.equal(String(tenthsToSeconds(tenths)).replace(/^\d+\.?/, '').length <= 1, true)
    }
  })

  it('refuses a position or zoom that is not a number', () => {
    assert.throws(() => cardTenthsAt(-1, 40, full), ModelError)
    assert.throws(() => cardTenthsAt(1000, 0, full), /pixels per second/)
  })
})

describe('cardKey', () => {
  const range = { min: 5, max: 600 }

  it('steps a tenth, and with Shift to the nearest whole second in that direction, with no float error', () => {
    assert.equal(cardKey('ArrowRight', false, 7, range), 8)
    assert.equal(tenthsToSeconds(8), 0.8)
    assert.equal(cardKey('ArrowRight', true, 43, range), 50)
    assert.equal(cardKey('ArrowRight', true, 50, range), 60)
    assert.equal(cardKey('ArrowLeft', true, 43, range), 40)
    assert.equal(cardKey('ArrowDown', true, 40, range), 30)
    assert.equal(cardKey('ArrowUp', false, 43, range), 44)
  })

  it('Home and End are the limits; keys stop at them and change nothing there', () => {
    assert.equal(cardKey('Home', false, 40, range), 5)
    assert.equal(cardKey('End', false, 40, range), 600)
    assert.equal(cardKey('ArrowLeft', false, 5, range), 5)
    assert.equal(cardKey('ArrowLeft', true, 8, range), 5)
    assert.equal(cardKey('ArrowRight', false, 600, range), 600)
    assert.equal(cardKey('ArrowRight', true, 595, range), 600)
  })

  it('a card above its range can only go down', () => {
    assert.equal(cardKey('ArrowRight', false, 50, { min: 5, max: 50 }), 50)
    assert.equal(cardKey('ArrowLeft', false, 50, { min: 5, max: 50 }), 49)
  })

  it('refuses a value that is not a length, by name', () => {
    assert.throws(() => cardKey('ArrowRight', false, Number.NaN, range), /card length/)
    assert.throws(() => cardKey('Home', false, -1, range), ModelError)
  })

  it('is null for a key that is not the handle’s', () => {
    assert.equal(cardKey('a', false, 40, range), null)
    assert.equal(cardKey('Tab', false, 40, range), null)
  })
})

describe('the words', () => {
  it('writes the value text and a cell that keeps its width from 0.5 to 60.0', () => {
    assert.equal(cardValueText(40), 'Card 4.0 s')
    const widths = new Set<number>()
    for (let t = CARD_MIN_TENTHS; t <= CARD_MAX_TENTHS; t += 1) {
      widths.add(cardCell(t).ch)
    }
    assert.deepEqual([...widths], [4])
    assert.equal(cardCell(600).text, '60.0')
    assert.equal(cardCell(5).text, '0.5')
  })

  it('says a release once, with the movie’s change for a black card only', () => {
    assert.equal(
      releasedWords('Reception', 60, 40, 'black'),
      'Title card for Reception now 6.0 s. The movie is 2.0 s longer.',
    )
    assert.equal(
      releasedWords('the opening', 25, 40, 'black'),
      'Title card for the opening now 2.5 s. The movie is 1.5 s shorter.',
    )
    assert.equal(releasedWords('Reception', 30, 20, 'video'), 'Title card for Reception now 3.0 s.')
  })
})

describe('the layout follows a card’s duration (withDurations)', () => {
  const spec = (chapter: string, seconds: number, background = 'black'): CardSpec => ({
    chapter,
    card: { duration: seconds, background, title: 't', subtitle: '', fontFamily: 'f' },
    error: null,
  })
  const specs = [spec('', 4), spec('B', 4), spec('C', 4)]
  const clips: CardClip[] = [0, 1, 2].map((chapter) => ({ chapter, durationMs: 10_000, spans: [] }))
  const lay = layout(clips.map((clip) => ({ durationMs: clip.durationMs, fps: 25, frames: 250 }) as never))
  const track = (using: readonly CardSpec[]) => {
    const placements = cardPlacements(using, clips, 'on')
    const map = cardMap(placements, lay)
    return { placements, map, track: trackLayout(lay, map) }
  }

  it('a longer black card moves everything after it and not itself', () => {
    const before = track(specs)
    const after = track(withDurations(specs, new Map([['', 6]])))
    assert.deepEqual(
      after.track.startsMs.map((start, i) => start - before.track.startsMs[i]),
      [2000, 2000, 2000],
    )
    assert.equal(after.track.totalMs - before.track.totalMs, 2000)
    const blocks = cardBlocks(after.placements, after.track)
    assert.equal(blocks[0].startMs, 0)
    assert.equal(blocks[0].widthMs, 6000)
  })

  it('a shorter black card never overlaps: the next span starts where the card ends', () => {
    const { placements, track: t } = track(withDurations(specs, new Map([['B', 0.5]])))
    const blocks = cardBlocks(placements, t)
    assert.equal(blocks[1].startMs + blocks[1].widthMs, t.startsMs[1])
  })

  it('a video card shifts nothing', () => {
    const video = [spec('', 4, 'video'), spec('B', 4), spec('C', 4)]
    const before = track(video)
    const after = track(withDurations(video, new Map([['', 6]])))
    assert.deepEqual(after.track, before.track)
  })

  it('a moment keeps its content: clip time maps to the shifted start plus the same offset', () => {
    const before = track(specs)
    const after = track(withDurations(specs, new Map([['B', 6]])))
    const moment = 3000
    assert.equal(after.track.startsMs[1] + moment - (before.track.startsMs[1] + moment), 2000)
  })

  it('returns the same array when nothing differs, so memos hold', () => {
    assert.equal(withDurations(specs, new Map()), specs)
    assert.equal(withDurations(specs, new Map([['B', 4]])), specs)
    assert.equal(withDurations(specs, null), specs)
  })

  it('handles carry each card’s limits from the footage after the cuts', () => {
    const cut: CardClip[] = [{ chapter: 0, durationMs: 12_000, spans: [{ from: 2450, to: 12_000 }] }]
    const one = [spec('', 3, 'video')]
    const placements = cardPlacements(one, cut, 'on')
    const lone = layout(cut.map((c) => ({ durationMs: c.durationMs, fps: 25, frames: 300 }) as never))
    const blocks = cardBlocks(placements, trackLayout(lone, cardMap(placements, lone)))
    const [handle] = cardHandles(placements, blocks, one)
    assert.deepEqual(handle.range, { adjustable: true, min: 5, max: 30 })
    assert.equal(handle.chapter, '')
    assert.equal(handle.tenths, 30)
  })
})
