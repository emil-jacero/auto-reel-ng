import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Chapter, Clip } from '../api/event.ts'
import {
  chapterBands,
  cutLabel,
  drawnCuts,
  filmTiles,
  movieMs,
  omittedWords,
  readiness,
  readProxy,
  sectionOpen,
  sectionState,
  shownClips,
  trackClips,
  trackLayout,
} from './layout.ts'
import type { FilmGeometry, ShownClip } from './layout.ts'
import { timeToPx } from './model.ts'

/*
 * The timeline's pure layer (`layout.ts`), run by `npm test`: which clips it shows, when
 * its proxies are ready, the chapter bands, the cuts as drawn, the movie's length and
 * the filmstrip tiles, each against the scenarios of the `event-timeline` spec.
 */

const FILM = { tile_width: 160, tile_height: 90, columns: 10, tiles: 25, interval: 1 }

function facts(duration: number, over: Record<string, unknown> = {}) {
  return {
    duration,
    fps_num: 25,
    fps_den: 1,
    vfr: false,
    width: 960,
    height: 540,
    rotation: null,
    audio_codec: 'aac',
    filmstrip: FILM,
    ...over,
  }
}

function clip(identity: string, over: Partial<Clip> & { proxy?: unknown } = {}): Clip {
  return {
    identity,
    status: 'active',
    excluded: false,
    proxy: { state: 'ready', facts: facts(10), version: 'v1', reason: null },
    ...over,
  } as Clip
}

function chapter(name: string, clips: Clip[]): Chapter {
  return { name, clips }
}

describe('shownClips', () => {
  it('lays out play order across chapters and counts a missing and an excluded clip apart', () => {
    const { clips, omitted } = shownClips({
      chapters: [
        chapter('Dag 1', [
          clip('Dag 1/a.mp4'),
          clip('Dag 1/b.mp4', { status: 'missing', proxy: null }),
          clip('Dag 1/c.mp4'),
        ]),
        chapter('Kvällen', [clip('Kvällen/d.mp4', { excluded: true }), clip('Kvällen/e.mp4')]),
      ],
    })
    assert.deepEqual(
      clips.map((c) => [c.identity, c.name, c.chapter]),
      [
        ['Dag 1/a.mp4', 'a.mp4', 0],
        ['Dag 1/c.mp4', 'c.mp4', 0],
        ['Kvällen/e.mp4', 'e.mp4', 1],
      ],
    )
    assert.deepEqual(omitted, { missing: 1, excluded: 1 })
  })

  it('leaves out clips the event ignores, and counts an excluded missing clip as excluded', () => {
    const { clips, omitted } = shownClips({
      chapters: [
        chapter('', [
          clip('a.mp4'),
          clip('b.mp4', { status: 'ignored' }),
          clip('c.mp4', { status: 'missing', excluded: true, proxy: null }),
        ]),
      ],
    })
    assert.deepEqual(
      clips.map((c) => c.identity),
      ['a.mp4'],
    )
    assert.deepEqual(omitted, { missing: 0, excluded: 1 })
  })

  it('names a clip by its path when its chapter does not hold every clip in its own folder', () => {
    const { clips } = shownClips({ chapters: [chapter('', [clip('a.mp4'), clip('sub/b.mp4')])] })
    assert.deepEqual(
      clips.map((c) => c.name),
      ['a.mp4', 'sub/b.mp4'],
    )
  })

  it('shows nothing for an event whose every clip is missing', () => {
    const { clips, omitted } = shownClips({
      chapters: [chapter('', [clip('a.mp4', { status: 'missing' }), clip('b.mp4', { status: 'missing' })])],
    })
    assert.equal(clips.length, 0)
    assert.equal(omitted.missing, 2)
    assert.equal(sectionState(true, clips), 'none')
  })
})

describe('readProxy', () => {
  it('is ready only with a state ready, a usable duration, rate, geometry and a version', () => {
    const ok = readProxy({ state: 'ready', facts: facts(24.96), version: 'abc' } as Clip['proxy'])
    assert.equal(ok.health, 'ready')
    assert.equal(ok.ready?.facts.durationMs, 24960)
    assert.equal(ok.ready?.facts.fps, 25)
    assert.equal(ok.ready?.version, 'abc')
    assert.equal(ok.ready?.film.tileWidth, 160)
  })

  it('takes the rate as the exact fraction', () => {
    const r = readProxy({
      state: 'ready',
      facts: facts(10, { fps_num: 30000, fps_den: 1001 }),
      version: 'v',
    } as Clip['proxy'])
    assert.ok(Math.abs((r.ready?.facts.fps ?? 0) - 29.97003) < 1e-4)
  })

  it('does not guess for a ready proxy without facts, with a zero length or rate, or without a tag', () => {
    const bad = (proxy: unknown) => readProxy(proxy as Clip['proxy']).health
    assert.equal(bad({ state: 'ready', facts: null, version: 'v' }), 'unusable')
    assert.equal(bad({ state: 'ready', facts: facts(0), version: 'v' }), 'unusable')
    assert.equal(bad({ state: 'ready', facts: facts(10, { fps_den: 0 }), version: 'v' }), 'unusable')
    assert.equal(bad({ state: 'ready', facts: facts(10), version: null }), 'unusable')
    assert.equal(bad({ state: 'ready', facts: facts(10), version: '' }), 'unusable')
    assert.equal(
      bad({ state: 'ready', facts: facts(10, { filmstrip: { ...FILM, columns: 0 } }), version: 'v' }),
      'unusable',
    )
  })

  it('keeps the service states, and treats no proxy or an unknown state as unknown', () => {
    const state = (s: string) => readProxy({ state: s } as Clip['proxy']).health
    assert.equal(state('absent'), 'absent')
    assert.equal(state('stale'), 'stale')
    assert.equal(state('failed'), 'failed')
    assert.equal(state('new-state'), 'unknown')
    assert.equal(readProxy(null).health, 'unknown')
    assert.equal(readProxy(undefined).health, 'unknown')
  })
})

describe('readiness and sectionState', () => {
  const health = (...h: ShownClip['health'][]) => h.map((health) => ({ health }))

  it('counts by state and opens only when every shown clip is ready', () => {
    const r = readiness(health('ready', 'ready', 'failed', 'absent', 'stale', 'unusable'))
    assert.deepEqual(
      [r.total, r.ready, r.failed, r.absent, r.stale, r.unusable, r.unknown, r.open],
      [6, 2, 1, 1, 1, 1, 0, false],
    )
    assert.equal(readiness(health('ready', 'ready')).open, true)
    assert.equal(readiness([]).open, false)
  })

  it('chooses the state: closed wins, no clips is none, one not ready is prepare, all ready is track', () => {
    assert.equal(sectionState(false, health('ready')), 'closed')
    assert.equal(sectionState(false, []), 'closed')
    assert.equal(sectionState(true, []), 'none')
    assert.equal(sectionState(true, health('ready', 'absent')), 'prepare')
    assert.equal(sectionState(true, health('ready', 'ready')), 'track')
  })

  it('treats 24 ready and 1 failed as prepare', () => {
    const clips = [...Array(24).fill('ready'), 'failed'] as ShownClip['health'][]
    const r = readiness(health(...clips))
    assert.equal(r.ready, 24)
    assert.equal(r.failed, 1)
    assert.equal(sectionState(true, health(...clips)), 'prepare')
  })
})

describe('chapterBands', () => {
  it('has one band per chapter with a shown clip, headed by its name', () => {
    const bands = chapterBands(['Dag 1', 'Kvällen'], [{ chapter: 0 }, { chapter: 0 }, { chapter: 1 }])
    assert.deepEqual(bands, [
      { chapter: 0, heading: 'Dag 1', first: 0, last: 1 },
      { chapter: 1, heading: 'Kvällen', first: 2, last: 2 },
    ])
  })

  it('heads an unnamed chapter Main beside named ones and Clips when none is named', () => {
    assert.equal(chapterBands(['', 'Kvällen'], [{ chapter: 0 }])[0].heading, 'Main')
    assert.equal(chapterBands([''], [{ chapter: 0 }, { chapter: 0 }, { chapter: 0 }])[0].heading, 'Clips')
  })

  it('leaves out a chapter whose clips are all not shown', () => {
    const bands = chapterBands(['A', 'B', 'C'], [{ chapter: 0 }, { chapter: 2 }])
    assert.deepEqual(
      bands.map((b) => b.heading),
      ['A', 'C'],
    )
  })
})

describe('the track', () => {
  function shownOf(durations: number[]): ShownClip[] {
    return shownClips({
      chapters: [
        chapter(
          '',
          durations.map((d, i) =>
            clip(`c${i}.mp4`, { proxy: { state: 'ready', facts: facts(d), version: `v${i}` } as Clip['proxy'] }),
          ),
        ),
      ],
    }).clips
  }

  it('is null while any clip is not ready', () => {
    const shown = shownOf([5, 5])
    shown[1] = { ...shown[1], health: 'absent', ready: null }
    assert.equal(trackClips(shown, null), null)
  })

  it('draws 24.96 s, 3.2 s and 0.48 s at 40 px per second as 998, 128 and 19 px', () => {
    const clips = trackClips(shownOf([24.96, 3.2, 0.48]), null)
    assert.ok(clips !== null)
    const l = trackLayout(clips)
    const widths = clips.map((c) => Math.round(timeToPx(c.facts.durationMs, 40)))
    assert.deepEqual(widths, [998, 128, 19])
    assert.deepEqual(l.startsMs, [0, 24960, 28160])
    assert.equal(l.totalMs, 28640)
  })

  it('joins overlapping cuts 2-4 and 3.5-5 into one 3.0 s span with both reasons', () => {
    const cuts = [
      { in: 2, out: 4, reason: 'black' },
      { in: 3.5, out: 5, reason: 'manual' },
    ]
    assert.deepEqual(drawnCuts(cuts, 12000), [{ from: 2000, to: 5000, reasons: ['black', 'manual'] }])
    const clips = trackClips(shownOf([12]), new Map([['c0.mp4', cuts]]))
    assert.ok(clips !== null)
    assert.equal(clips[0].cutCount, 2)
    assert.equal(movieMs(clips, new Map([['c0.mp4', cuts]])), 9000)
  })

  it('clamps a cut past the end to the clip and draws nothing for one wholly past it', () => {
    assert.deepEqual(drawnCuts([{ in: 0, out: 99 }], 12000), [{ from: 0, to: 12000, reasons: [] }])
    assert.deepEqual(drawnCuts([{ in: 13, out: 14 }], 12000), [])
    const cuts = new Map([['c0.mp4', [{ in: 0, out: 99 }]]])
    const clips = trackClips(shownOf([12]), cuts)
    assert.ok(clips !== null)
    assert.equal(movieMs(clips, cuts), 0)
  })

  it('keeps a rotated phone clip\'s cut at its source time', () => {
    const [span] = drawnCuts([{ in: 3, out: 4.5, reason: 'manual' }], 12000)
    assert.deepEqual([span.from, span.to], [3000, 4500])
  })

  it('has no cuts and the footage as the movie without a read of them', () => {
    const clips = trackClips(shownOf([10, 5]), null)
    assert.ok(clips !== null)
    assert.deepEqual(clips.map((c) => c.drawn), [[], []])
    assert.equal(movieMs(clips, null), 15000)
  })

  it('words a cut by its span and reasons', () => {
    assert.equal(cutLabel({ from: 2000, to: 4000, reasons: ['black'] }), 'Cut 0:02 to 0:04, Black frames')
    assert.equal(cutLabel({ from: 2000, to: 5500, reasons: [] }), 'Cut 0:02 to 0:05.5')
    assert.equal(
      cutLabel({ from: 2000, to: 5000, reasons: ['black', 'manual'] }),
      'Cut 0:02 to 0:05, Black frames, Cut by hand',
    )
  })
})

describe('omittedWords', () => {
  it('says how many were left out, each kind apart, singular and plural', () => {
    assert.deepEqual(omittedWords({ missing: 0, excluded: 0 }), [])
    assert.deepEqual(omittedWords({ missing: 1, excluded: 1 }), [
      '1 clip is missing from disk and is not shown',
      '1 clip is excluded and is not shown',
    ])
    assert.deepEqual(omittedWords({ missing: 2, excluded: 0 }), [
      '2 clips are missing from disk and are not shown',
    ])
  })
})

describe('filmTiles', () => {
  const film: FilmGeometry = { tileWidth: 160, tileHeight: 90, columns: 10, tiles: 25, interval: 1 }
  const all = { from: 0, to: Infinity }

  it('draws a 25 s clip at 40 px/s with 96 px tiles from the first second to the last', () => {
    const tiles = filmTiles(film, 25000, 40, all)
    assert.equal(tiles.length, Math.ceil(1000 / 96))
    assert.equal(tiles[0].index, 0)
    assert.equal(tiles[1].index, 2) // 96 px is 2.4 s: the second at the tile's start
    assert.ok(tiles.at(-1)!.index <= 24)
    assert.deepEqual([tiles[3].col, tiles[3].row], [tiles[3].index % 10, Math.floor(tiles[3].index / 10)])
    assert.ok(tiles.every((t, i) => i === 0 || t.x > tiles[i - 1].x))
  })

  it('cuts the last tile to the clip and gives a sub-second clip its one tile', () => {
    const tiles = filmTiles(film, 480, 40, all)
    assert.equal(tiles.length, 1)
    assert.equal(tiles[0].index, 0)
    assert.equal(Math.round(tiles[0].width), 19)
    const long = filmTiles(film, 25000, 40, all)
    assert.ok(long.at(-1)!.x + long.at(-1)!.width <= 1000 + 1e-6)
  })

  it('draws only tiles that touch the window', () => {
    const tiles = filmTiles(film, 25000, 40, { from: 480, to: 770 })
    assert.deepEqual(
      tiles.map((t) => t.x),
      [480, 576, 672, 768],
    )
    assert.equal(filmTiles(film, 25000, 40, { from: 2000, to: 3000 }).length, 0)
  })

  it('leaves tiles out, not squeezed, at a low zoom, and reaches the sprite end at most', () => {
    const tiles = filmTiles(film, 25000, 10, all)
    assert.equal(tiles.length, Math.ceil(250 / 96))
    assert.ok(tiles.every((t) => t.index <= 24))
    // 240 px/s: several 96 px places show the same second
    const near = filmTiles(film, 3000, 240, all)
    assert.deepEqual(
      near.slice(0, 6).map((t) => t.index),
      [0, 0, 0, 1, 1, 2],
    )
  })

  it('reads a clip longer than the sprite per interval seconds per tile', () => {
    const sparse: FilmGeometry = { ...film, tiles: 120, interval: 3 }
    const tiles = filmTiles(sparse, 360000, 40, { from: 0, to: 400 })
    assert.equal(tiles[1].index, Math.floor(96 / 40 / 3)) // second 2.4 is in tile 0
    assert.equal(tiles[4].index, Math.floor(384 / 40 / 3)) // second 9.6: tile 3
    assert.equal(filmTiles(sparse, 360000, 40, { from: 14400 - 96, to: 14400 }).at(-1)!.index, 119)
  })

  it('scales a portrait sprite to a narrow place', () => {
    const portrait: FilmGeometry = { tileWidth: 50, tileHeight: 90, columns: 10, tiles: 5, interval: 1 }
    const [first, second] = filmTiles(portrait, 5000, 40, all)
    assert.equal(Math.round(second.x - first.x), 30)
  })
})

describe('sectionOpen', () => {
  it('the read view is closed until its button opens it, and toggles', () => {
    assert.equal(sectionOpen(false, false), false)
    assert.equal(sectionOpen(false, true), true)
  })

  it('Edit mode is open on entry, with or without a press, and a Refresh keeps it so', () => {
    assert.equal(sectionOpen(true, false), true)
    assert.equal(sectionOpen(true, true), true)
    assert.equal(sectionState(sectionOpen(true, false), [{ health: 'absent' }]), 'prepare')
    assert.equal(sectionState(sectionOpen(true, false), [{ health: 'ready' }]), 'track')
    assert.equal(sectionState(sectionOpen(false, false), [{ health: 'ready' }]), 'closed')
  })
})
