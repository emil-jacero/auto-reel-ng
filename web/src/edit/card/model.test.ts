import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  NO_CARD,
  SUBTITLE_LIMIT,
  TITLE_LIMIT,
  cardBody,
  cardChanged,
  cardsChangedCount,
  cardsChangedWords,
  changedFields,
  isUnset,
  normalise,
  openingSubtitleFollows,
  openingSubtitlePlaceholder,
  overBounds,
  previewRequest,
  readCard,
  refusalOf,
  titlePlaceholder,
  tooLongWords,
  withField,
} from './model.ts'

describe('readCard and change detection', () => {
  it('reads absent and null cards as no overrides', () => {
    assert.deepEqual(readCard(undefined), NO_CARD)
    assert.deepEqual(readCard(null), NO_CARD)
    assert.deepEqual(readCard({}), NO_CARD)
  })

  it('setting a field back to the read value is no change', () => {
    const read = readCard({ position: 'top', title: 'Hej' })
    const edited = withField(read, 'position', 'bottom')
    assert.equal(cardChanged(read, edited), true)
    assert.deepEqual(changedFields(read, edited), ['position'])
    const back = withField(edited, 'position', 'top')
    assert.equal(cardChanged(read, back), false)
  })

  it('an empty text is no override, so clearing a read title is a change and typing then erasing is not', () => {
    const none = readCard({})
    assert.equal(cardChanged(none, withField(none, 'title', '')), false)
    assert.equal(cardChanged(none, withField(none, 'title', 'x')), true)
    const read = readCard({ subtitle: 'Sub' })
    assert.equal(cardChanged(read, withField(read, 'subtitle', null)), true)
  })

  it('a number that is not finite is no override', () => {
    assert.equal(normalise({ ...NO_CARD, title_font_size: Number.NaN }).title_font_size, null)
    assert.equal(normalise({ ...NO_CARD, title_font_size: 12 }).title_font_size, 12)
  })

  it('the duration the draft does not touch passes through', () => {
    const read = readCard({ duration: 4, title: 'A' })
    const body = cardBody(withField(read, 'title', 'B'))
    assert.deepEqual(body, { duration: 4, title: 'B' })
  })
})

describe('cardBody', () => {
  it('sends only the set overrides, and {} for none (removes the card)', () => {
    assert.deepEqual(cardBody(NO_CARD), {})
    assert.equal(isUnset(NO_CARD), true)
    const card = withField(withField(NO_CARD, 'font_family', 'DejaVu Sans'), 'title_font_size', 80)
    assert.deepEqual(cardBody(card), { font_family: 'DejaVu Sans', title_font_size: 80 })
    assert.equal(isUnset(card), false)
  })

  it('keeps line breaks in a subtitle', () => {
    assert.deepEqual(cardBody(withField(NO_CARD, 'subtitle', 'a\nb')), { subtitle: 'a\nb' })
  })
})

describe('the subtitle keeps "" and unset apart', () => {
  it('"" round-trips as "", unset as absent', () => {
    assert.equal(readCard({ subtitle: '' }).subtitle, '')
    assert.equal(readCard({}).subtitle, null)
    assert.deepEqual(cardBody(readCard({ subtitle: '' })), { subtitle: '' })
    assert.deepEqual(cardBody(readCard({})), {})
  })

  it('is a change between "" and unset, in both directions, and "" is a card that saves', () => {
    const none = readCard({})
    const empty = withField(none, 'subtitle', '')
    assert.equal(cardChanged(none, empty), true)
    assert.equal(cardChanged(empty, none), true)
    assert.equal(cardChanged(empty, readCard({ subtitle: '' })), false)
    assert.equal(isUnset(empty), false)
    assert.deepEqual(changedFields(none, empty), ['subtitle'])
  })

  it('the other text fields still treat "" as unset', () => {
    assert.equal(normalise(withField(NO_CARD, 'title', '')).title, null)
    assert.equal(normalise(withField(NO_CARD, 'text_color', '')).text_color, null)
  })

  it('the preview request carries subtitle "" and none when unset', () => {
    const request = (subtitle: string | null) =>
      previewRequest({
        opening: true,
        chapterName: '',
        card: withField(NO_CARD, 'subtitle', subtitle),
        eventTitle: 'T',
      })
    assert.deepEqual(request('')?.card, { subtitle: '' })
    assert.deepEqual(request(null)?.card, {})
  })
})

describe('the opening subtitle placeholder', () => {
  it('shows the engine’s default on one line while unset, and never composes one', () => {
    assert.equal(
      openingSubtitlePlaceholder(null, '2024-08-20\nPlats: Tjörn'),
      'Default: 2024-08-20 / Plats: Tjörn',
    )
    assert.equal(openingSubtitleFollows('2024-08-20\nPlats: Tjörn'), '2024-08-20 / Plats: Tjörn')
    assert.equal(openingSubtitlePlaceholder(null, ''), 'No subtitle')
  })

  it('says No subtitle once the subtitle is "" or typed', () => {
    assert.equal(openingSubtitlePlaceholder('', '2024-08-20'), 'No subtitle')
    assert.equal(openingSubtitlePlaceholder('Hej', '2024-08-20'), 'No subtitle')
  })
})

describe('titlePlaceholder', () => {
  it('a chapter follows its name in the draft', () => {
    assert.deepEqual(
      titlePlaceholder({ opening: false, chapterName: 'Dag två', eventTitle: 'X', folderTitle: 'F' }),
      { placeholder: 'Dag två', follows: 'Follows the chapter name' },
    )
  })

  it('the opening card follows the draft event title, else the folder title', () => {
    const base = { opening: true, chapterName: '', folderTitle: 'Från mappen' }
    assert.deepEqual(titlePlaceholder({ ...base, eventTitle: 'Sommaren' }), {
      placeholder: 'Sommaren',
      follows: 'Follows the event title',
    })
    assert.equal(titlePlaceholder({ ...base, eventTitle: '  ' }).placeholder, 'Från mappen')
    assert.equal(titlePlaceholder({ ...base, eventTitle: '', folderTitle: null }).placeholder, '')
  })
})

describe('previewRequest, the draft event style', () => {
  const base = { opening: false, chapterName: 'A', eventTitle: '' }
  it('carries the draft look.title_card as the body’s style, whole', () => {
    const style = { text_color: '#00FF00', fade_in: 0.5 }
    assert.deepEqual(previewRequest({ ...base, card: NO_CARD, style })?.style, style)
  })
  it('sends no style key while the style is as saved', () => {
    assert.equal('style' in (previewRequest({ ...base, card: NO_CARD }) ?? {}), false)
  })
  it('keeps an empty style: a cleared one is not the saved one', () => {
    assert.deepEqual(previewRequest({ ...base, card: NO_CARD, style: {} })?.style, {})
  })
})

describe('previewRequest', () => {
  const base = { opening: false, chapterName: 'Dag 2', eventTitle: 'Ev' }

  it('carries the draft chapter name and the set overrides', () => {
    const request = previewRequest({ ...base, card: withField(NO_CARD, 'position', 'top') })
    assert.deepEqual(request, { chapter: 'Dag 2', card: { position: 'top' } })
  })

  it('the opening card carries the draft event title', () => {
    const request = previewRequest({ ...base, opening: true, chapterName: '', card: NO_CARD })
    assert.deepEqual(request, { chapter: '', card: {}, event_title: 'Ev' })
  })

  it('a chapter that is not the opening sends no event title', () => {
    assert.equal(previewRequest({ ...base, card: NO_CARD })?.event_title, undefined)
  })

  it('the title bound: 200 is sent, 201 is not', () => {
    const at = (n: number) => withField(NO_CARD, 'title', 'x'.repeat(n))
    assert.notEqual(previewRequest({ ...base, card: at(TITLE_LIMIT) }), null)
    assert.equal(previewRequest({ ...base, card: at(TITLE_LIMIT + 1) }), null)
    assert.deepEqual(overBounds(at(TITLE_LIMIT + 1)), [{ field: 'title', limit: 200, length: 201 }])
  })

  it('the subtitle bound: 400 is sent, 401 is not', () => {
    const at = (n: number) => withField(NO_CARD, 'subtitle', 'y'.repeat(n))
    assert.notEqual(previewRequest({ ...base, card: at(SUBTITLE_LIMIT) }), null)
    assert.equal(previewRequest({ ...base, card: at(SUBTITLE_LIMIT + 1) }), null)
    assert.equal(tooLongWords(400), 'Too long to preview (limit 400)')
  })

  it('counts characters, not UTF-16 units', () => {
    const emoji = withField(NO_CARD, 'title', '😀'.repeat(TITLE_LIMIT))
    assert.notEqual(previewRequest({ ...base, card: emoji }), null)
  })
})

describe('the save bar count', () => {
  const read = (key: string) => (key === 'r1' ? readCard({ position: 'top' }) : NO_CARD)

  it('counts the changed cards among the kept chapters', () => {
    const drafts = new Map([
      ['r0', withField(NO_CARD, 'subtitle', 'S')],
      ['r1', withField(readCard({ position: 'top' }), 'font_family', 'F')],
      ['r2', NO_CARD],
    ])
    assert.equal(cardsChangedCount(['r0', 'r1', 'r2'], drafts, read), 2)
    assert.equal(cardsChangedCount(['r0', 'r2'], drafts, read), 1)
  })

  it('an entry equal to its read card counts nothing', () => {
    assert.equal(cardsChangedCount(['r1'], new Map([['r1', readCard({ position: 'top' })]]), read), 0)
  })

  it('says 1, 2 and nothing for 0', () => {
    assert.equal(cardsChangedWords(1), '1 title card changed')
    assert.equal(cardsChangedWords(2), '2 title cards changed')
    assert.equal(cardsChangedWords(0), null)
  })
})

describe('refusalOf', () => {
  it('maps a write refusal to the chapter and field it names', () => {
    const detail =
      "reel.yaml: chapters[1] ('Dag 2').card.title_font_size must be a positive integer, got -3"
    assert.deepEqual(refusalOf(detail), { chapter: 'Dag 2', field: 'title_font_size', message: detail })
  })

  it('maps the opening chapter and a quoted name', () => {
    assert.equal(refusalOf("chapters[0] ('').card.position must be one of x").chapter, '')
    assert.equal(refusalOf('chapters[2] ("It\'s").card.text_color bad').chapter, "It's")
  })

  it('maps the font registry refusal', () => {
    const r = refusalOf("chapter 'Dag 2': card.font_family 'Comic' is not a bundled font family; use one of: A")
    assert.deepEqual([r.chapter, r.field], ['Dag 2', 'font_family'])
  })

  it('maps a preview refusal, which names the card alone', () => {
    const r = refusalOf('card.background must be one of [black, video], got "x"')
    assert.deepEqual([r.chapter, r.field], [null, 'background'])
  })

  it('a message that names no known field has none', () => {
    assert.deepEqual(refusalOf('something else'), { chapter: null, field: null, message: 'something else' })
    assert.equal(refusalOf("chapters[0] ('A').card.nope bad").field, null)
  })
})
