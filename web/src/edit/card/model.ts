import type { components } from '../../api/schema'

/*
 * The title-card inspector's model, as pure functions (`title-card-inspector`): a card's nine
 * overrides as the draft holds them, what changed against the card as read, the words an empty
 * field shows, the preview request, the save bar's count and which field a refusal names. No DOM,
 * no React, no network, so `npm test` runs it. The page applies none of the engine's value rules:
 * what was typed is sent, and the service's refusal is shown at the field (Principle I).
 */

type CardBody = components['schemas']['CardBody']

/** The overrides a card can hold, as the `reel.yaml` `card` keys name them. */
export const CARD_FIELDS = [
  'title',
  'subtitle',
  'duration',
  'background',
  'font_family',
  'title_font_size',
  'subtitle_font_size',
  'text_color',
  'position',
] as const

export type CardField = (typeof CARD_FIELDS)[number]

/** The nine overrides; `null` is "not set: follow the event style". */
export type CardDraft = {
  title: string | null
  subtitle: string | null
  duration: number | null
  background: string | null
  font_family: string | null
  title_font_size: number | null
  subtitle_font_size: number | null
  text_color: string | null
  position: string | null
}

export const NO_CARD: CardDraft = Object.freeze({
  title: null,
  subtitle: null,
  duration: null,
  background: null,
  font_family: null,
  title_font_size: null,
  subtitle_font_size: null,
  text_color: null,
  position: null,
})

/** The preview's text bounds (characters), the service's `PreviewCardBody` limits. */
export const TITLE_LIMIT = 200
export const SUBTITLE_LIMIT = 400

/** The fields typed as text; the others are numbers. */
const TEXT_FIELDS: ReadonlySet<CardField> = new Set<CardField>([
  'title',
  'subtitle',
  'background',
  'font_family',
  'text_color',
  'position',
])

function textOf(value: string | null | undefined): string | null {
  return value == null || value === '' ? null : value
}

function numberOf(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** A card as `reel.yaml` holds it (`CardBody`), or none: the overrides it sets. */
export function readCard(card: CardBody | null | undefined): CardDraft {
  if (card == null) {
    return NO_CARD
  }
  return normalise({
    title: card.title ?? null,
    subtitle: card.subtitle ?? null,
    duration: card.duration ?? null,
    background: card.background ?? null,
    font_family: card.font_family ?? null,
    title_font_size: card.title_font_size ?? null,
    subtitle_font_size: card.subtitle_font_size ?? null,
    text_color: card.text_color ?? null,
    position: card.position ?? null,
  })
}

/** An empty text, or a number that is not one, is no override. */
export function normalise(card: CardDraft): CardDraft {
  return {
    title: textOf(card.title),
    subtitle: textOf(card.subtitle),
    duration: numberOf(card.duration),
    background: textOf(card.background),
    font_family: textOf(card.font_family),
    title_font_size: numberOf(card.title_font_size),
    subtitle_font_size: numberOf(card.subtitle_font_size),
    text_color: textOf(card.text_color),
    position: textOf(card.position),
  }
}

/** Whether a card sets nothing: saved, it is `{}`, which removes it. */
export function isUnset(card: CardDraft): boolean {
  const flat = normalise(card)
  return CARD_FIELDS.every((field) => flat[field] === null)
}

/** The fields whose overrides differ between two cards, normalised. */
export function changedFields(read: CardDraft, draft: CardDraft): CardField[] {
  const a = normalise(read)
  const b = normalise(draft)
  return CARD_FIELDS.filter((field) => a[field] !== b[field])
}

/** Whether the draft's overrides differ from the ones read: set back, it is no change. */
export function cardChanged(read: CardDraft, draft: CardDraft): boolean {
  return changedFields(read, draft).length > 0
}

/** The card as the write sends it: the overrides that are set; `{}` for none (removes the card). */
export function cardBody(card: CardDraft): CardBody {
  const flat = normalise(card)
  const body: Record<string, string | number> = {}
  for (const field of CARD_FIELDS) {
    const value = flat[field]
    if (value !== null) {
      body[field] = value
    }
  }
  return body as CardBody
}

/** `card` with one field set (`null` clears it: Use event style). */
export function withField<F extends CardField>(
  card: CardDraft,
  field: F,
  value: CardDraft[F],
): CardDraft {
  return card[field] === value ? card : { ...card, [field]: value }
}

/** Whether a field is typed as text (else a number). */
export function isTextField(field: CardField): boolean {
  return TEXT_FIELDS.has(field)
}

/**
 * How many cards changed: the entries of `drafts` (by chapter key) that differ from their
 * read card, among `keys` (the chapters a save keeps).
 */
export function cardsChangedCount(
  keys: readonly string[],
  drafts: ReadonlyMap<string, CardDraft>,
  readOf: (key: string) => CardDraft,
): number {
  return keys.filter((key) => {
    const draft = drafts.get(key)
    return draft !== undefined && cardChanged(readOf(key), draft)
  }).length
}

/** "1 title card changed", "2 title cards changed"; none for zero. */
export function cardsChangedWords(count: number): string | null {
  if (count <= 0) {
    return null
  }
  return count === 1 ? '1 title card changed' : `${count} title cards changed`
}

// --- what an empty field says -----------------------------------------------------------

/** What an empty title follows, and the words that say so. */
export type TitleFollow = { placeholder: string; follows: string }

export const FOLLOWS_CHAPTER = 'Follows the chapter name'
export const FOLLOWS_EVENT = 'Follows the event title'

/**
 * The placeholder of an empty title, from the draft and not from the detail: the chapter's
 * name now; for the opening card the event's title now (the draft's, else the one read from
 * the folder name, else none).
 */
export function titlePlaceholder(args: {
  opening: boolean
  chapterName: string
  eventTitle: string
  folderTitle: string | null
}): TitleFollow {
  if (!args.opening) {
    return { placeholder: args.chapterName, follows: FOLLOWS_CHAPTER }
  }
  const typed = args.eventTitle.trim() === '' ? null : args.eventTitle
  return { placeholder: typed ?? args.folderTitle ?? '', follows: FOLLOWS_EVENT }
}

// --- the preview request ----------------------------------------------------------------

/** Characters as the service counts them (code points), not UTF-16 units. */
export function lengthOf(text: string): number {
  return Array.from(text).length
}

export type TooLong = { field: 'title' | 'subtitle'; limit: number; length: number }

/** The body of `POST …/title-card/preview`. */
export type PreviewRequest = {
  chapter: string
  card: CardBody
  event_title?: string
}

/** The fields over the preview's bounds, in field order. */
export function overBounds(card: CardDraft): TooLong[] {
  const out: TooLong[] = []
  const title = card.title === null ? 0 : lengthOf(card.title)
  const subtitle = card.subtitle === null ? 0 : lengthOf(card.subtitle)
  if (title > TITLE_LIMIT) {
    out.push({ field: 'title', limit: TITLE_LIMIT, length: title })
  }
  if (subtitle > SUBTITLE_LIMIT) {
    out.push({ field: 'subtitle', limit: SUBTITLE_LIMIT, length: subtitle })
  }
  return out
}

/** "Too long to preview (limit 200)". */
export function tooLongWords(limit: number): string {
  return `Too long to preview (limit ${limit})`
}

/**
 * The request for the draft card: the draft chapter name (the service resolves an empty title
 * to it, so a renamed or added chapter previews as it will render), the set overrides, and for
 * the opening card the draft event title. `null` when a field is over the preview's bounds
 * (nothing is sent; the text is kept and still saves).
 */
export function previewRequest(args: {
  opening: boolean
  chapterName: string
  card: CardDraft
  eventTitle: string
}): PreviewRequest | null {
  const card = normalise(args.card)
  if (overBounds(card).length > 0) {
    return null
  }
  const request: PreviewRequest = { chapter: args.chapterName, card: cardBody(card) }
  if (args.opening && args.eventTitle.trim() !== '') {
    request.event_title = args.eventTitle
  }
  return request
}

// --- a refusal at its field -------------------------------------------------------------

/** A refusal's place: the chapter it names (null: none named) and the card field (null: none). */
export type Refusal = { chapter: string | null; field: CardField | null; message: string }

const QUOTED = String.raw`('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")`
// `chapters[1] ('Dag 2').card.title_font_size …` (the write) and `chapter 'Dag 2': card.font_family …`.
const BY_INDEX = new RegExp(String.raw`chapters\[\d+\] \(${QUOTED}\)\.card\.(\w+)`)
const BY_NAME = new RegExp(String.raw`chapter ${QUOTED}: card\.(\w+)`)
// The preview names the card alone: `card.title_font_size …`.
const BARE = /(?:^|[\s:])card\.(\w+)/

function unquote(repr: string): string {
  return repr.slice(1, -1).replace(/\\(['"\\])/g, '$1')
}

function known(name: string): CardField | null {
  return (CARD_FIELDS as readonly string[]).includes(name) ? (name as CardField) : null
}

/**
 * Which chapter and card field a refusal's `detail` names. The service names the field in
 * its own words (`chapters[1] ('Dag 2').card.title_font_size …`); a message that names none
 * of them has neither and is shown at the top of the card.
 */
export function refusalOf(detail: string): Refusal {
  const byIndex = BY_INDEX.exec(detail)
  if (byIndex !== null) {
    return { chapter: unquote(byIndex[1]), field: known(byIndex[2]), message: detail }
  }
  const byName = BY_NAME.exec(detail)
  if (byName !== null) {
    return { chapter: unquote(byName[1]), field: known(byName[2]), message: detail }
  }
  const bare = BARE.exec(detail)
  if (bare !== null) {
    return { chapter: null, field: known(bare[1]), message: detail }
  }
  return { chapter: null, field: null, message: detail }
}
