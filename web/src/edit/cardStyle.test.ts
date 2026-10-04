import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { NO_CARD } from './card/model.ts'
import {
  NO_STYLE,
  applyStyle,
  changedStyleFields,
  draftEventStyle,
  effective,
  normaliseValue,
  overrideWords,
  overrides,
  previewStyle,
  readStyle,
  styleChanged,
  styleRefusalOf,
  withStyleField,
} from './cardStyle.ts'

const resolved = {
  duration: 3,
  background: 'black',
  font_family: 'DejaVu Sans',
  title_font_size: 72,
  subtitle_font_size: 40,
  text_color: '#FFFFFF',
  position: 'center',
}

describe('readStyle', () => {
  it('reads the seven fields and leaves the rest of the map out', () => {
    const read = readStyle({ title_card: { text_color: '#FF0000', fade_in: 0.5, title_font_size: '80' } })
    assert.equal(read.text_color, '#FF0000')
    assert.equal(read.title_font_size, 80)
    assert.equal('fade_in' in read, false)
  })
  it('is no style for a look without title_card or with one that is not a map', () => {
    assert.deepEqual(readStyle({}), NO_STYLE)
    assert.deepEqual(readStyle({ title_card: 'x' }), NO_STYLE)
  })
  it('keeps a hand-written bad value as written', () => {
    assert.equal(readStyle({ title_card: { position: 'middle' } }).position, 'middle')
  })
})

describe('styleChanged', () => {
  it('compares numbers as numbers: 80 and "80" are no change', () => {
    const read = readStyle({ title_card: { title_font_size: 80 } })
    assert.equal(styleChanged(read, { ...read, title_font_size: '80' }), false)
    assert.equal(styleChanged(read, { ...read, title_font_size: '90' }), true)
  })
  it('lists the changed fields in the panel order', () => {
    const changed = changedStyleFields(NO_STYLE, { ...NO_STYLE, background: 'video', font_family: 'X' })
    assert.deepEqual(changed, ['font_family', 'background'])
  })
  it('counts an empty text as unset', () => {
    assert.equal(styleChanged(NO_STYLE, { ...NO_STYLE, text_color: '' }), false)
  })
})

describe('applyStyle', () => {
  it('is the read look itself when the style is untouched or put back', () => {
    const look = { title_card: { font_family: 'A' }, other: 1 }
    assert.equal(applyStyle(look, undefined), look)
    assert.equal(applyStyle(look, readStyle(look)), look)
    assert.equal(applyStyle(look, withStyleField(readStyle(look), 'font_family', 'A')), look)
  })
  it('keeps fade_in and every other look key through a colour edit', () => {
    const look = { title_card: { fade_in: 0.5, outline: { width: 2 } }, other: { a: 1 } }
    const next = applyStyle(look, withStyleField(readStyle(look), 'text_color', '#FFFFFF'))
    assert.deepEqual(next, {
      title_card: { fade_in: 0.5, outline: { width: 2 }, text_color: '#FFFFFF' },
      other: { a: 1 },
    })
    assert.deepEqual(look.title_card, { fade_in: 0.5, outline: { width: 2 } })
  })
  it('removes a cleared field and leaves an unchanged one as read', () => {
    const look = { title_card: { title_font_size: '80', text_color: '#111111' } }
    const next = applyStyle(look, withStyleField(readStyle(look), 'text_color', null))
    assert.deepEqual(next, { title_card: { title_font_size: '80' } })
  })
  it('removes title_card when its last key is cleared', () => {
    const look = { title_card: { font_family: 'A' }, keep: true }
    const next = applyStyle(look, withStyleField(readStyle(look), 'font_family', null))
    assert.deepEqual(next, { keep: true })
  })
  it('adds title_card to a look without one, numbers as numbers', () => {
    const next = applyStyle({}, withStyleField(NO_STYLE, 'title_font_size', '90'))
    assert.deepEqual(next, { title_card: { title_font_size: 90 } })
  })
  it('sends a number typed as text as typed, for the engine to refuse', () => {
    const next = applyStyle({}, withStyleField(NO_STYLE, 'title_font_size', 'big'))
    assert.deepEqual(next, { title_card: { title_font_size: 'big' } })
  })
})

describe('previewStyle', () => {
  it('sends nothing while the style is as read, the whole draft map after', () => {
    const look = { title_card: { fade_in: 1 } }
    assert.equal(previewStyle(look, undefined), undefined)
    const draft = withStyleField(readStyle(look), 'font_family', 'Playfair Display')
    assert.deepEqual(previewStyle(look, draft), { fade_in: 1, font_family: 'Playfair Display' })
  })
  it('sends an empty map for a style cleared of everything', () => {
    const look = { title_card: { font_family: 'A' } }
    assert.deepEqual(previewStyle(look, withStyleField(readStyle(look), 'font_family', null)), {})
  })
})

describe('what a card overrides', () => {
  it('names the style fields it sets, in the panel order', () => {
    const card = { ...NO_CARD, text_color: '#FF0000', font_family: 'X' }
    assert.deepEqual(overrides(card), ['font_family', 'text_color'])
    assert.equal(overrideWords(card), 'Overrides font, color')
  })
  it('uses the event style when it sets none, title and subtitle being its own text', () => {
    assert.equal(overrideWords(NO_CARD), 'Uses the event style')
    assert.equal(overrideWords({ ...NO_CARD, title: 'Hej', subtitle: 'x' }), 'Uses the event style')
  })
  it('counts a value equal to the event style as an override', () => {
    const card = { ...NO_CARD, position: 'center' }
    assert.equal(overrideWords(card), 'Overrides position')
  })
})

describe('effective', () => {
  const read = readStyle({ title_card: { title_font_size: 80 } })
  it('lets the card beat the draft style, and the style the default', () => {
    const style = { ...read, font_family: 'Event Font' }
    const card = { ...NO_CARD, font_family: 'Card Font' }
    assert.deepEqual(effective('font_family', card, style, read, resolved), { value: 'Card Font', source: 'card' })
    assert.deepEqual(effective('font_family', NO_CARD, style, read, resolved), { value: 'Event Font', source: 'style' })
    assert.deepEqual(effective('text_color', NO_CARD, style, read, resolved), { value: '#FFFFFF', source: 'default' })
  })
  it('is unknown for a cleared field the saved style set, not a number', () => {
    const cleared = { ...read, title_font_size: null }
    assert.deepEqual(effective('title_font_size', NO_CARD, cleared, read, resolved), { value: null, source: 'unknown' })
  })
  it('is unknown without a resolved style', () => {
    assert.equal(effective('position', NO_CARD, NO_STYLE, NO_STYLE, null).source, 'unknown')
  })
})

describe('draftEventStyle', () => {
  it('lays the draft over the default and leaves a cleared saved field out', () => {
    const read = readStyle({ title_card: { title_font_size: 80 } })
    const draft = { ...read, title_font_size: null, text_color: '#00FF00' }
    const style = draftEventStyle(draft, read, resolved)
    assert.equal(style?.text_color, '#00FF00')
    assert.equal(style?.position, 'center')
    assert.equal(style !== null && 'title_font_size' in style, false)
  })
  it('keeps a typed non-number out of a numeric field', () => {
    const style = draftEventStyle({ ...NO_STYLE, title_font_size: 'big' }, NO_STYLE, null)
    assert.equal(style, null)
  })
})

describe('styleRefusalOf', () => {
  it('names the field of a look.title_card refusal', () => {
    const found = styleRefusalOf('look.title_card.title_font_size must be a number, got "big"')
    assert.equal(found?.field, 'title_font_size')
  })
  it('names none for a card refusal or an unknown key', () => {
    assert.equal(styleRefusalOf("chapters[1] ('A').card.title_font_size must be an integer"), null)
    assert.equal(styleRefusalOf('look.title_card.fade_in must be a number')?.field, null)
  })
})

describe('normaliseValue', () => {
  it('reads 80, "80" and " 80 " as 80 and "big" as text', () => {
    assert.equal(normaliseValue('title_font_size', 80), 80)
    assert.equal(normaliseValue('title_font_size', ' 80 '), 80)
    assert.equal(normaliseValue('title_font_size', 'big'), 'big')
    assert.equal(normaliseValue('title_font_size', ' '), null)
    assert.equal(normaliseValue('font_family', ''), null)
  })
})
