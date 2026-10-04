import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import {
  cardBlockPx,
  cardBlocks,
  cardDurationMs,
  cardsEnabled,
  cardsSource,
  cardSpecs,
  cardMap,
  cardPlacements,
  cardSelection,
  cardWords,
  clipTimeAt,
  movieWithCards,
  trackLayout,
  trackX,
  visibleBlocks,
} from './cards.ts'
import type { CardClip, CardSpec, Placement } from './cards.ts'
import { ModelError, keptExtent, layout } from './model.ts'
import { globalMs } from './position.ts'
import type { Skip } from '../preview/playback.ts'

/*
 * The title cards' pure layer (`cards.ts`), run by `npm test`, against the scenarios of
 * the `timeline` spec: the render's anchor rule, the track map black cards cause, the
 * words and the selection.
 */

const card = (seconds: number, background = 'black'): CardSpec['card'] => ({
  duration: seconds,
  background,
  title: 't',
  subtitle: '',
  defaultSubtitle: '',
  fontFamily: 'Sofia Sans',
})
const spec = (chapter: string, seconds: number, background = 'black'): CardSpec => ({
  chapter,
  card: card(seconds, background),
  error: null,
})
const clip = (chapter: number, durationMs: number, spans: CardClip['spans'] = []): CardClip => ({
  chapter,
  durationMs,
  spans,
})

describe('cardsEnabled', () => {
  it('is the service’s answer; the draft’s switch wins while it differs', () => {
    assert.equal(cardsEnabled({ enabled: true, source: 'default' }), 'on')
    assert.equal(cardsEnabled({ enabled: false, source: 'event' }), 'off')
    assert.equal(cardsEnabled({ enabled: true, source: 'default' }, false), 'off')
    assert.equal(cardsEnabled({ enabled: false, source: 'project' }, true), 'on')
    assert.equal(cardsEnabled({ enabled: false, source: 'project' }, null), 'off')
  })

  it('has no answer for title_cards null, and never guesses one', () => {
    assert.equal(cardsEnabled(null), 'invalid')
    assert.equal(cardsEnabled(undefined), 'invalid')
  })

  it('names the layer that decided, the event once the draft differs', () => {
    assert.equal(cardsSource({ enabled: false, source: 'project' }), 'project')
    assert.equal(cardsSource({ enabled: false, source: 'project' }, false), 'project')
    assert.equal(cardsSource({ enabled: false, source: 'project' }, true), 'event')
    assert.equal(cardsSource(null), null)
  })

  it('the module no longer guesses from reel.yaml', () => {
    for (const file of ['cards.ts', 'labels.ts', 'Timeline.tsx', 'TimelineSection.tsx']) {
      const text = readFileSync(new URL(`./${file}`, import.meta.url), 'utf8')
      assert.doesNotMatch(text, /\bunset\b|titleCardsOn|decoratorsRead|not counted/i, file)
    }
  })
})

describe('cardSpecs', () => {
  it('reads the resolved cards, the chapter error before the event-wide one', () => {
    const detail = {
      title_card_error: 'look.title_card.font_family',
      chapters: [
        { name: '', clips: [], card: null, card_error: null },
        { name: 'B', clips: [], card: null, card_error: 'card.duration' },
        {
          name: 'C',
          clips: [],
          card: {
            duration: 4,
            background: 'video',
            font_family: 'Sofia Sans',
            title_font_size: 1,
            subtitle_font_size: 1,
            text_color: '#fff',
            position: 'center',
            title: 'Dag två',
            subtitle: 'Stranden',
            default_subtitle: '2024-08-20',
          },
        },
      ],
    }
    assert.deepEqual(cardSpecs(detail), [
      { chapter: '', card: null, error: 'look.title_card.font_family' },
      { chapter: 'B', card: null, error: 'card.duration' },
      {
        chapter: 'C',
        card: {
          duration: 4,
          background: 'video',
          title: 'Dag två',
          subtitle: 'Stranden',
          defaultSubtitle: '2024-08-20',
          fontFamily: 'Sofia Sans',
        },
        error: null,
      },
    ])
  })
})

describe('cardPlacements', () => {
  it('anchors plain chapters at their first clip with a start of 0', () => {
    const p = cardPlacements([spec('', 3), spec('Dag 2', 4)], [clip(0, 20000), clip(1, 20000)], 'on')
    assert.deepEqual(
      p.map((x) => x.kind === 'anchored' && [x.chapter, x.clip, x.atMs]),
      [
        [0, 0, 0],
        [1, 1, 0],
      ],
    )
  })

  it('moves the anchor past a wholly cut first clip', () => {
    const p = cardPlacements(
      [spec('A', 3)],
      [clip(0, 5000, [{ from: 0, to: 5000 }]), clip(0, 8000)],
      'on',
    )
    assert.equal(p[0].kind === 'anchored' && p[0].clip, 1)
  })

  it('starts at the end of a leading cut and clamps a video card to the first kept span', () => {
    const p = cardPlacements(
      [spec('A', 7, 'video')],
      [clip(0, 20000, [{ from: 0, to: 3000 }, { from: 6000, to: 9000 }])],
      'on',
    )
    const x = p[0]
    assert.ok(x.kind === 'anchored')
    assert.equal(x.atMs, 3000)
    assert.equal(x.widthMs, 3000)
    assert.equal(x.clamped, true)
    assert.equal(x.durationMs, 7000)
  })

  it('does not clamp a black card, and a cut elsewhere does not move it', () => {
    const p = cardPlacements([spec('A', 7)], [clip(0, 20000, [{ from: 2000, to: 4000 }])], 'on')
    const x = p[0]
    assert.ok(x.kind === 'anchored')
    assert.equal(x.atMs, 0)
    assert.equal(x.widthMs, 7000)
    assert.equal(x.clamped, false)
  })

  it('has no card for a chapter without footage', () => {
    const p = cardPlacements(
      [spec('A', 3), spec('B', 3)],
      [clip(0, 5000, [{ from: 0, to: 5000 }])],
      'on',
    )
    assert.deepEqual(p.map((x) => x.kind), ['no-footage', 'no-footage'])
  })

  it('is off when the decorator is not title, and draws nothing when it is invalid', () => {
    const clips = [clip(0, 20000)]
    assert.equal(cardPlacements([spec('A', 3)], clips, 'off')[0].kind, 'off')
    assert.deepEqual(cardPlacements([spec('A', 3)], clips, 'invalid'), [])
  })

  it('says an unresolved card with the service words and draws no block', () => {
    const p = cardPlacements(
      [{ chapter: '', card: null, error: 'look.title_card.font_family' }],
      [clip(0, 1000)],
      'on',
    )
    assert.deepEqual(p, [
      { kind: 'unresolved', chapter: 0, error: 'look.title_card.font_family' },
    ] satisfies Placement[])
    assert.deepEqual(cardBlocks(p, layout([{ durationMs: 1000, fps: 25 }])), [])
  })

  it('refuses a bad duration with a ModelError naming it, and places nothing for it', () => {
    for (const bad of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      assert.throws(() => cardDurationMs(bad), (e: unknown) => {
        assert.ok(e instanceof ModelError)
        assert.match(e.message, /card duration/)
        return true
      })
      const p = cardPlacements([spec('A', bad)], [clip(0, 1000)], 'on')
      assert.equal(p[0].kind, 'unreadable')
    }
    assert.equal(cardPlacements([spec('A', 3, 'sepia')], [clip(0, 1000)], 'on')[0].kind, 'unreadable')
  })
})

describe('the track map of black cards', () => {
  const clips = [clip(0, 20000), clip(1, 20000)]
  const lay = layout(clips.map((c) => ({ durationMs: c.durationMs, fps: 25 })))
  const placements = cardPlacements([spec('', 3), spec('Dag 2', 4)], clips, 'on')
  const map = cardMap(placements, lay)

  it('shifts the clips by the cards before them (3,000 and 27,000), total 47,000', () => {
    const track = trackLayout(lay, map)
    assert.deepEqual(track.startsMs, [3000, 27000])
    assert.equal(track.totalMs, 47000)
    assert.equal(movieWithCards(40000, map), 47000)
  })

  it('maps a track time inside a card to the card, with no clip time', () => {
    assert.deepEqual(clipTimeAt(map, 1500), { kind: 'card', index: 0, chapter: 0, afterMs: 0 })
    assert.deepEqual(clipTimeAt(map, 24000), { kind: 'card', index: 1, chapter: 1, afterMs: 20000 })
    assert.deepEqual(clipTimeAt(map, 3000), { kind: 'clip', ms: 0 })
  })

  it('round-trips every clip time', () => {
    for (let ms = 0; ms < 40000; ms += 7) {
      assert.deepEqual(clipTimeAt(map, trackX(map, ms)), { kind: 'clip', ms })
    }
  })

  it('counts the black cards once in the movie', () => {
    assert.equal(movieWithCards(0, map), 7000)
    assert.equal(movieWithCards(0, cardMap([], lay)), 0)
  })

  it('moves nothing for a video card or an off card', () => {
    for (const [background, mode] of [
      ['video', 'on'],
      ['black', 'off'],
    ] as const) {
      const m = cardMap(cardPlacements([spec('', 4, background)], clips, mode), lay)
      assert.equal(m.totalMs, 0)
      assert.deepEqual(trackLayout(lay, m).startsMs, [0, 20000])
      assert.equal(trackX(m, 12345), 12345)
    }
  })

  it('places blocks: black before its clip, video on the footage', () => {
    const mixed = cardPlacements(
      [spec('', 3), spec('Dag 2', 4, 'video')],
      [clip(0, 20000, [{ from: 0, to: 1000 }]), clip(1, 20000, [{ from: 0, to: 2000 }])],
      'on',
    )
    const m = cardMap(mixed, lay)
    const blocks = cardBlocks(mixed, trackLayout(lay, m))
    assert.deepEqual(
      blocks.map((b) => [b.chapter, b.startMs, b.widthMs, b.background]),
      [
        [0, 0, 3000, 'black'],
        [1, 23000 + 2000, 4000, 'video'],
      ],
    )
  })

  it('finds the cards in range among 2,000 chapters without visiting each', () => {
    const many = Array.from({ length: 2000 }, (_, i) => clip(i, 1000))
    const big = layout(many.map((c) => ({ durationMs: c.durationMs, fps: 25 })))
    const placed = cardPlacements(
      many.map((_, i) => spec(`c${i}`, 1)),
      many,
      'on',
    )
    const real = cardMap(placed, big)
    let reads = 0
    const counted = new Proxy(real.gaps as unknown[], {
      get(target, key, receiver) {
        if (typeof key === 'string' && /^\d+$/.test(key)) {
          reads += 1
        }
        return Reflect.get(target, key, receiver)
      },
    })
    const probe = { ...real, gaps: counted as typeof real.gaps }
    assert.equal(trackX(probe, 1_000_000), 1_000_000 + 1001 * 1000)
    assert.ok(reads < 60, `read ${reads} gaps`)

    const blocks = cardBlocks(placed, trackLayout(big, real))
    let touched = 0
    const watched = new Proxy(blocks, {
      get(target, key, receiver) {
        if (typeof key === 'string' && /^\d+$/.test(key)) {
          touched += 1
        }
        return Reflect.get(target, key, receiver)
      },
    })
    const range = visibleBlocks(watched, 500_000, 510_000)
    assert.ok(range !== null)
    assert.equal(range[1] - range[0] + 1, 5)
    assert.ok(touched < 80, `touched ${touched} blocks`)
    assert.equal(visibleBlocks(blocks, 9_000_000, 9_100_000), null)
  })
})

describe('cards at a trimmed clip (timeline-ripple-layout)', () => {
  // Clip 0 (8 s) in the opening chapter, clip 1 (20 s, a cut from 0 to 2 s) opens "Dag 2".
  const clips = [clip(0, 8000), clip(1, 20000, [{ from: 0, to: 2000 }])]
  const lay = layout(
    clips.map((c) => ({ durationMs: c.durationMs, fps: 25, ...keptExtent(c.spans as Skip[], c.durationMs) })),
  )

  it('a black card of 3 s spans 8,000 to 11,000 ms and the clip’s 2,000 ms is 11,000 ms on the track', () => {
    const placements = cardPlacements([spec('', 3, 'video'), spec('Dag 2', 3)], clips, 'on')
    const map = cardMap(placements, lay)
    const track = trackLayout(lay, map)
    assert.equal(lay.startsMs[1], 8000)
    const block = cardBlocks(placements, track).find((b) => b.chapter === 1)!
    assert.deepEqual([block.startMs, block.startMs + block.widthMs], [8000, 11000])
    assert.equal(track.startsMs[1], 11000)
    assert.equal(globalMs(track, { clip: 1, ms: 2000 }), 11000)
  })

  it('a video card begins at the left edge of the clip’s block (3.0 s of the clip), no gap', () => {
    const cut = [clip(0, 8000), clip(1, 20000, [{ from: 0, to: 3000 }])]
    const l = layout(
      cut.map((c) => ({ durationMs: c.durationMs, fps: 25, ...keptExtent(c.spans as Skip[], c.durationMs) })),
    )
    const placements = cardPlacements([spec('', 3, 'video'), spec('Dag 2', 4, 'video')], cut, 'on')
    const map = cardMap(placements, l)
    const track = trackLayout(l, map)
    const block = cardBlocks(placements, track).find((b) => b.chapter === 1)!
    assert.equal(block.startMs, track.startsMs[1])
    const place = placements[1]
    assert.ok(place.kind === 'anchored' && place.atMs === 3000)
  })

  it('a video card is held to the first kept span, ending at a trailing cut', () => {
    const placements = cardPlacements(
      [spec('', 7, 'video')],
      [clip(0, 10000, [{ from: 0, to: 4000 }, { from: 7000, to: 10000 }])],
      'on',
    )
    const place = placements[0]
    assert.ok(place.kind === 'anchored')
    assert.equal(place.keptMs, 3000)
    assert.equal(cardWords('', { durationMs: place.durationMs, widthMs: place.widthMs, background: 'video' }), 'Title card for the opening, 3.0 s of 7.0 s, over video')
  })

  it('a chapter whose clips keep nothing has no card', () => {
    const placements = cardPlacements([spec('', 3)], [clip(0, 5050, [{ from: 0, to: 5000 }])], 'on')
    assert.deepEqual(placements, [{ kind: 'no-footage', chapter: 0 }])
  })
})

describe('cardWords', () => {
  it('words black, video, clamped, off and the opening', () => {
    assert.equal(
      cardWords('Dag 2', { durationMs: 4000, background: 'video' }),
      'Title card for Dag 2, 4.0 s, over video',
    )
    assert.equal(
      cardWords('', { durationMs: 3000, background: 'black' }),
      'Title card for the opening, 3.0 s, on black',
    )
    assert.equal(
      cardWords('Dag 2', { durationMs: 7000, widthMs: 3000, background: 'video' }),
      'Title card for Dag 2, 3.0 s of 7.0 s, over video',
    )
    assert.equal(
      cardWords('Dag 2', { durationMs: 4000, background: 'black', off: true }),
      'Title card for Dag 2, 4.0 s, on black, not enabled',
    )
  })
})

describe('cardSelection', () => {
  it('ends with its chapter and keeps the same object otherwise', () => {
    const dag = cardSelection.select(null, 'Dag 2')
    assert.deepEqual(dag, { chapter: 'Dag 2', editing: false })
    assert.equal(cardSelection.select(dag, 'Dag 2'), dag)
    assert.equal(cardSelection.chapters(dag, ['', 'Dag 2']), dag)
    assert.equal(cardSelection.chapters(dag, ['']), null)
    assert.equal(cardSelection.chapters(null, ['']), null)
  })

  it('clear and selectCut end it, and are no-ops when nothing is selected', () => {
    const dag = cardSelection.select(null, 'Dag 2')
    assert.equal(cardSelection.clear(dag), null)
    assert.equal(cardSelection.selectCut(dag), null)
    assert.equal(cardSelection.clear(null), null)
    assert.equal(cardSelection.selectCut(null), null)
  })
})

describe('cardSelection open and dismiss', () => {
  it('open selects and opens, and reopens a selected card', () => {
    const dag = cardSelection.select(null, 'Dag 2')
    const opened = cardSelection.open(dag, 'Dag 2')
    assert.deepEqual(opened, { chapter: 'Dag 2', editing: true })
    assert.equal(cardSelection.open(opened, 'Dag 2'), opened)
    assert.deepEqual(cardSelection.open(null, 'Dag 2'), { chapter: 'Dag 2', editing: true })
    const closed = cardSelection.dismiss(opened)
    assert.deepEqual(closed, { chapter: 'Dag 2', editing: false })
    assert.deepEqual(cardSelection.open(closed, 'Dag 2'), { chapter: 'Dag 2', editing: true })
  })

  it('dismiss keeps the selection and is a no-op when nothing is open', () => {
    const opened = cardSelection.open(null, 'Dag 2')
    assert.equal(cardSelection.dismiss(opened)?.chapter, 'Dag 2')
    const closed = cardSelection.dismiss(opened)
    assert.equal(cardSelection.dismiss(closed), closed)
    assert.equal(cardSelection.dismiss(null), null)
  })

  it('select never opens, and selecting another card closes the dialog', () => {
    const opened = cardSelection.open(null, 'Dag 2')
    assert.equal(cardSelection.select(opened, 'Dag 2'), opened)
    assert.deepEqual(cardSelection.select(opened, 'Dag 3'), { chapter: 'Dag 3', editing: false })
    assert.equal(cardSelection.select(null, 'Dag 3')?.editing, false)
  })

  it('retain and selectCut and clear end the dialog with the selection', () => {
    const opened = cardSelection.open(null, 'Dag 2')
    assert.equal(cardSelection.chapters(opened, ['']), null)
    assert.equal(cardSelection.chapters(opened, ['Dag 2']), opened)
    assert.equal(cardSelection.selectCut(opened), null)
    assert.equal(cardSelection.clear(opened), null)
  })
})

describe('a zoomed-out card stays pressable', () => {
  it('is at least 24 px wide however narrow its span', () => {
    assert.equal(cardBlockPx(12), 24)
    assert.equal(cardBlockPx(2), 24)
    assert.equal(cardBlockPx(160), 160)
  })
})
