import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { cardPlacements } from './cards.ts'
import type { CardClip, CardSpec } from './cards.ts'
import { cardViewAt } from './cardView.ts'
import type { PictureLookup } from './cardView.ts'

/*
 * The card layer's decision (`cardView.ts`, `titlecard-scrub-fade`), against the scenarios of
 * "The playhead can be put in a card, and the readouts count card time": the fades show at every
 * position, not only while playing.
 */

const spec = (chapter: string, seconds: number, background = 'black', title = 't'): CardSpec => ({
  chapter,
  card: {
    duration: seconds,
    background,
    title,
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
const none: PictureLookup = { get: () => null }
const near = (a: number | undefined, b: number) =>
  assert.ok(a !== undefined && Math.abs(a - b) < 1e-9, `${a} vs ${b}`)
const cardAt = (chapter: number, ms: number, lengthMs: number, name = '') => ({
  clip: chapter,
  ms: 0,
  card: { chapter, name, ms, lengthMs },
})

describe('cardViewAt', () => {
  const specs = [spec('', 7)]
  const placements = cardPlacements(specs, [clipOf(0, 20000)], 'on')
  const view = (ms: number, len = 7000, pics = none, s = specs, pl = placements) =>
    cardViewAt(cardAt(0, ms, len), pl, s, pics)

  it('(a) shows a black card at its fades at every position', () => {
    for (const [ms, want] of [
      [0, 0],
      [1000, 0.5],
      [3500, 1],
      [6000, 0.5],
    ] as const) {
      const v = view(ms)
      assert.equal(v?.kind, 'black')
      near(v?.opacity, want)
    }
    // the length-shrink clamp: the card-edit effect holds card.ms to a shortened card's end
    near(view(7000)?.opacity, 0)
  })

  it('(a2) steps back from a clip into the end of its card', () => {
    const s = [spec('', 4)]
    const pl = cardPlacements(s, [clipOf(0, 20000)], 'on')
    near(view(3900, 4000, none, s, pl)?.opacity, 0.05)
  })

  it('(b) keeps the opacity Pause left, not full', () => {
    near(view(1200)?.opacity, 0.6)
  })

  it('(c) is a video card window', () => {
    const s = [spec('', 4, 'video')]
    const clips = [clipOf(0, 20000, [{ from: 0, to: 3000 }])]
    const pl = cardPlacements(s, clips, 'on')
    const at = (ms: number) => cardViewAt({ clip: 0, ms }, pl, s, none)
    assert.equal(at(4000)?.kind, 'video')
    near(at(4000)?.opacity, 0.5)
    near(at(3000)?.opacity, 0)
    near(at(6000)?.opacity, 0.5)
    assert.equal(at(2999), null)
    assert.equal(at(7000), null)
  })

  it('(d) clamps the fades of a short card', () => {
    const s = [spec('', 3)]
    const pl = cardPlacements(s, [clipOf(0, 20000)], 'on')
    near(view(1000, 3000, none, s, pl)?.opacity, 2 / 3)
  })

  it('(e) carries the picture and the title', () => {
    // Key-sensitive: only the card of chapter "Dag 2" has a picture, so a wrong key finds none.
    const keyed: PictureLookup = { get: (c) => (c === 'Dag 2' ? { url: 'blob:x' } : null) }
    const named = [spec('Dag 2', 7, 'black', 'Hello')]
    const v = view(1000, 7000, keyed, named)
    assert.equal(v?.url, 'blob:x')
    assert.equal(v?.title, 'Hello')
    assert.equal(v?.chapter, 'Dag 2')
    near(v?.opacity, 0.5)
    const missing = view(1000, 7000, none, named)
    assert.equal(missing?.url, null)
    assert.equal(missing?.title, 'Hello')
    near(missing?.opacity, 0.5)
    const pending = view(1000, 7000, { get: () => ({ url: null }) }, named)
    assert.equal(pending?.url, null)
    assert.equal(pending?.title, 'Hello')
    near(pending?.opacity, 0.5)
    const nospec = view(1000, 7000, none, [])
    assert.equal(nospec?.chapter, undefined)
    assert.equal(nospec?.title, '')
  })

  it('keeps CardLayer.tsx a plain renderer: no play state, opacity straight from the view', () => {
    const src = readFileSync(new URL('./CardLayer.tsx', import.meta.url), 'utf8')
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    assert.ok(!/\bplaying\b/.test(code), 'CardLayer takes no play state')
    assert.ok(/const \{ opacity \} = view\b/.test(code), 'opacity comes from the view')
    const styles = [...code.matchAll(/style=\{\{([^}]*)\}\}/g)].map((m) => m[1].trim())
    assert.ok(styles.length > 0)
    assert.ok(styles.every((x) => x === 'opacity'), `style is opacity alone: ${styles}`)
  })

  it('(f) draws nothing over a clip under a black card placement', () => {
    const s = [spec('', 3), spec('Dag 2', 4)]
    const pl = cardPlacements(s, [clipOf(0, 20000), clipOf(1, 20000)], 'on')
    assert.equal(cardViewAt({ clip: 0, ms: 500 }, pl, s, none), null)
  })
})
