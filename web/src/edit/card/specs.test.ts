import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { CardSpec, Placement } from '../../timeline/cards.ts'
import { NO_CARD, readCard, withField } from './model.ts'
import { backdropOf, draftSpec, effectiveBackground } from './specs.ts'
import type { EventStyle } from './specs.ts'

const style: EventStyle = {
  duration: 3,
  background: 'black',
  font_family: 'DejaVu Sans',
  title_font_size: 80,
  subtitle_font_size: 40,
  text_color: '#ffffff',
  position: 'center',
}
const spec: CardSpec = {
  chapter: 'Dag 2',
  card: { duration: 4, background: 'video', title: 'Dag 2', subtitle: '', defaultSubtitle: '', fontFamily: 'DejaVu Sans' },
  error: null,
}

describe('draftSpec', () => {
  it('an unchanged card is the saved spec itself', () => {
    assert.equal(draftSpec(spec, style, NO_CARD, undefined, 'Dag 2'), spec)
    assert.equal(draftSpec(spec, style, NO_CARD, NO_CARD, 'Dag 2'), spec)
  })

  it('shows the draft title on the block, not the chapter name', () => {
    const draft = withField(NO_CARD, 'title', 'Mottagningen')
    assert.equal(draftSpec(spec, style, NO_CARD, draft, 'Dag 2').card?.title, 'Mottagningen')
    assert.equal(draftSpec(spec, style, NO_CARD, draft, 'Dag 2').chapter, 'Dag 2')
  })

  it('a cleared title follows the chapter name now', () => {
    const read = readCard({ title: 'Old' })
    const draft = withField(read, 'title', null)
    assert.equal(draftSpec(spec, style, read, draft, 'Dag två').card?.title, 'Dag två')
  })

  it('an unset field takes the event style, not the saved card’s override', () => {
    const read = readCard({ background: 'video' })
    const draft = withField(read, 'background', null)
    assert.equal(draftSpec(spec, style, read, draft, 'x').card?.background, 'black')
    assert.equal(draftSpec(spec, style, read, withField(read, 'background', 'black'), 'x').card?.background, 'black')
  })

  it('without an event style it starts from the saved card, and with neither it changes nothing', () => {
    const draft = withField(NO_CARD, 'subtitle', 'S')
    assert.equal(draftSpec(spec, null, NO_CARD, draft, 'x').card?.fontFamily, 'DejaVu Sans')
    const unresolved: CardSpec = { chapter: 'A', card: null, error: 'bad' }
    assert.equal(draftSpec(unresolved, null, NO_CARD, draft, 'A'), unresolved)
    assert.equal(draftSpec(unresolved, style, NO_CARD, draft, 'A').card?.subtitle, 'S')
  })
})

describe('draftSpec and the subtitle default', () => {
  const opening: CardSpec = {
    chapter: '',
    card: {
      duration: 4,
      background: 'black',
      title: 'Midsommar',
      subtitle: '2024-08-20\nPlats: Tjörn',
      defaultSubtitle: '2024-08-20\nPlats: Tjörn',
      fontFamily: 'DejaVu Sans',
    },
    error: null,
  }
  const read = readCard({})

  it('an unset subtitle shows the detail’s default, a typed one replaces it, "" is none', () => {
    const edit = (subtitle: string | null) =>
      draftSpec(opening, style, read, withField(read, 'subtitle', subtitle), 'Midsommar')
    assert.equal(edit(null), opening)
    assert.equal(edit('Hos mormor').card?.subtitle, 'Hos mormor')
    assert.equal(edit('').card?.subtitle, '')
    assert.equal(edit('').card?.defaultSubtitle, '2024-08-20\nPlats: Tjörn')
  })

  it('going back from "" to unset shows the default again', () => {
    const saved = readCard({ subtitle: '' })
    const savedSpec: CardSpec = { ...opening, card: { ...opening.card!, subtitle: '' } }
    const back = draftSpec(savedSpec, style, saved, withField(saved, 'subtitle', null), 'Midsommar')
    assert.equal(back.card?.subtitle, '2024-08-20\nPlats: Tjörn')
  })

  it('a chapter card has no default: unset stays empty', () => {
    const draft = withField(read, 'title', 'X')
    assert.equal(draftSpec(spec, style, read, draft, 'Dag 2').card?.subtitle, '')
  })
})

describe('draftSpec under an edited event style', () => {
  it('draws a card the operator did not touch from the draft style', () => {
    const edited = { ...style, background: 'video', font_family: 'Playfair Display' }
    const next = draftSpec(spec, edited, NO_CARD, undefined, 'Dag 2', true)
    assert.notEqual(next, spec)
    assert.equal(next.card?.fontFamily, 'Playfair Display')
    assert.equal(next.card?.title, 'Dag 2')
  })

  it('keeps a card’s own font over a changed style', () => {
    const read = readCard({ font_family: 'Own Font' })
    const edited = { ...style, font_family: 'Playfair Display' }
    assert.equal(draftSpec(spec, edited, read, read, 'Dag 2', true).card?.fontFamily, 'Own Font')
  })

  it('does not invent a field the page does not know', () => {
    const unresolved: CardSpec = { chapter: 'A', card: null, error: 'bad' }
    const partial: EventStyle = { text_color: '#00FF00' }
    assert.equal(draftSpec(unresolved, partial, NO_CARD, undefined, 'A', true), unresolved)
  })
})

describe('effectiveBackground', () => {
  it('the draft, then the event style, then the saved card', () => {
    assert.equal(effectiveBackground(withField(NO_CARD, 'background', 'video'), style, spec), 'video')
    assert.equal(effectiveBackground(NO_CARD, style, spec), 'black')
    assert.equal(effectiveBackground(NO_CARD, null, spec), 'video')
    assert.equal(effectiveBackground(NO_CARD, null, undefined), null)
  })
})

describe('backdropOf', () => {
  const shown = [
    { identity: 'a.mp4', name: 'a', chapter: 0 },
    { identity: 'b.mp4', name: 'b', chapter: 1 },
    { identity: 'c.mp4', name: 'c', chapter: 1 },
  ]
  const anchored = (chapter: number, clip: number): Placement => ({
    kind: 'anchored',
    chapter,
    clip,
    atMs: 0,
    background: 'video',
    durationMs: 3000,
    keptMs: 5000,
    widthMs: 3000,
    clamped: false,
  })

  it('the clip the Timeline anchors the card on, when it knows (a whole-clip cut moves it)', () => {
    assert.deepEqual(backdropOf(1, shown, [anchored(1, 2)]), { identity: 'c.mp4', name: 'c' })
  })

  it('else the chapter’s first shown clip', () => {
    assert.deepEqual(backdropOf(1, shown, null), { identity: 'b.mp4', name: 'b' })
    assert.deepEqual(backdropOf(1, shown, [{ kind: 'no-footage', chapter: 1 }]), {
      identity: 'b.mp4',
      name: 'b',
    })
  })

  it('none for a chapter that shows no clip', () => {
    assert.equal(backdropOf(2, shown, null), null)
  })
})
