import { NO_CARD } from './card/model.ts'
import type { CardDraft } from './card/model.ts'
import type { EventStyle } from './card/specs.ts'

/*
 * The event-wide card style (`title-card-event-style`), as pure functions: the seven fields of
 * `look.title_card` the page edits, the draft of them, what changed against the style as read,
 * the `look` a save writes, which fields a card overrides and which value a card field has once
 * the card, the draft style and the project default are laid over each other. No DOM, no React,
 * no network, so `npm test` runs it. The page applies none of the engine's value rules: what was
 * typed is sent, and the service's refusal is shown at the field (Principle I). It imports only `card/model.ts`, which is as pure.
 */

/** The fields of `look.title_card` the page edits, in the panel's order. */
export const STYLE_FIELDS = [
  'font_family',
  'title_font_size',
  'subtitle_font_size',
  'text_color',
  'position',
  'duration',
  'background',
] as const

export type StyleField = (typeof STYLE_FIELDS)[number]

/** A value as typed: text, or a number once it reads as one. */
export type StyleValue = string | number

/** The style's fields as the draft holds them; `null` is "not set: the project default". */
export type StyleDraft = Record<StyleField, StyleValue | null>

export const NO_STYLE: StyleDraft = Object.freeze({
  font_family: null,
  title_font_size: null,
  subtitle_font_size: null,
  text_color: null,
  position: null,
  duration: null,
  background: null,
})

/** The fields typed as numbers; a text that does not read as one is still sent, and refused. */
const NUMERIC: ReadonlySet<StyleField> = new Set<StyleField>([
  'title_font_size',
  'subtitle_font_size',
  'duration',
])

export function isNumericField(field: StyleField): boolean {
  return NUMERIC.has(field)
}

/** A look map as `reel.yaml` holds it. */
export type Look = { [key: string]: unknown }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * A value in the form it is compared and written in: nothing for an empty text or a number
 * that is not one; a number for a numeric field typed as one (80 and "80" are the same), else
 * the text as typed.
 */
export function normaliseValue(field: StyleField, raw: unknown): StyleValue | null {
  if (raw === null || raw === undefined) {
    return null
  }
  if (typeof raw === 'number') {
    return Number.isFinite(raw) ? raw : null
  }
  const text = typeof raw === 'string' ? raw : JSON.stringify(raw)
  if (isNumericField(field)) {
    const trimmed = text.trim()
    if (trimmed === '') {
      return null
    }
    // Only plain decimals read as numbers: '0x50', '0b11' and '1e2' are sent as typed and refused.
    return /^-?\d+(\.\d+)?$/.test(trimmed) ? Number(trimmed) : text
  }
  return text === '' ? null : text
}

/** The style as `look.title_card` holds it: the seven fields, whatever else the map carries left out. */
export function readStyle(look: Look | null | undefined): StyleDraft {
  const map = look?.title_card
  if (!isRecord(map)) {
    return NO_STYLE
  }
  const out = { ...NO_STYLE } as Record<StyleField, StyleValue | null>
  for (const field of STYLE_FIELDS) {
    out[field] = normaliseValue(field, map[field])
  }
  return out
}

/** The fields whose value differs between two styles, normalised, in the panel's order. */
export function changedStyleFields(read: StyleDraft, draft: StyleDraft): StyleField[] {
  return STYLE_FIELDS.filter(
    (field) => normaliseValue(field, read[field]) !== normaliseValue(field, draft[field]),
  )
}

/** Whether the draft style differs from the one read: put back, it is no change. */
export function styleChanged(read: StyleDraft, draft: StyleDraft): boolean {
  return changedStyleFields(read, draft).length > 0
}

/** `style` with one field set; `null` clears it. The same style when nothing changes. */
export function withStyleField(
  style: StyleDraft,
  field: StyleField,
  value: StyleValue | null,
): StyleDraft {
  return style[field] === value ? style : { ...style, [field]: value }
}

/**
 * The `look` a save writes: `readLook` itself when the style is as read (an untouched save is
 * byte-identical); else a copy whose `title_card` has each changed field set or removed. The keys
 * of `title_card` the page does not edit (fades, outline, shadow), every other key of `look` and
 * a field the operator did not change go back as read. `title_card` is removed when its last
 * key goes, never written empty.
 */
export function applyStyle(readLook: Look, draft: StyleDraft | undefined): Look {
  if (draft === undefined) {
    return readLook
  }
  const changed = changedStyleFields(readStyle(readLook), draft)
  if (changed.length === 0) {
    return readLook
  }
  const readMap = isRecord(readLook.title_card) ? readLook.title_card : {}
  const map: Record<string, unknown> = { ...readMap }
  for (const field of changed) {
    const value = normaliseValue(field, draft[field])
    if (value === null) {
      delete map[field]
    } else {
      map[field] = value
    }
  }
  const { title_card: _dropped, ...rest } = readLook
  return Object.keys(map).length === 0 ? rest : { ...rest, title_card: map }
}

/**
 * The preview's `style`: the draft `look.title_card` as the save would write it, or none while
 * the style is as read (the service then uses the saved one). `{}` is a style with nothing set.
 */
export function previewStyle(readLook: Look, draft: StyleDraft | undefined): Look | undefined {
  const look = applyStyle(readLook, draft)
  if (look === readLook) {
    return undefined
  }
  return isRecord(look.title_card) ? look.title_card : {}
}

// --- what a card overrides -----------------------------------------------------------------

/** The names the page uses for the fields of a card that follow the event style. */
export const FIELD_NAMES: Record<StyleField, string> = {
  font_family: 'font',
  title_font_size: 'title size',
  subtitle_font_size: 'subtitle size',
  text_color: 'color',
  position: 'position',
  duration: 'length',
  background: 'background',
}

export const USES_EVENT_STYLE = 'Uses the event style'

/**
 * The event-style fields a card's draft sets, in the panel's order. Read from the draft, not
 * from the resolved card: a value equal to the event style's is still an override. The title
 * and the subtitle are the card's own text, not a style, so they are not listed.
 */
export function overrides(card: CardDraft): StyleField[] {
  return STYLE_FIELDS.filter((field) => card[field] !== null && card[field] !== undefined)
}

/** "Overrides font, color", or "Uses the event style". */
export function overrideWords(card: CardDraft): string {
  const names = overrides(card).map((field) => FIELD_NAMES[field])
  return names.length === 0 ? USES_EVENT_STYLE : `Overrides ${names.join(', ')}`
}

// --- which value a field has -----------------------------------------------------------------

/** Where a card field's value comes from. */
export type Source = 'card' | 'style' | 'default' | 'unknown'

/**
 * The value a card's field has: the card's override, else the draft event style, else the project
 * default (the detail's resolved value, known only while the saved style did not set the field),
 * else unknown. A field the operator cleared although the saved style set it is `unknown`: the
 * layer below is not known to the page and is not guessed.
 */
export function effective(
  field: StyleField,
  card: CardDraft,
  style: StyleDraft,
  read: StyleDraft,
  resolved: EventStyle | null,
): { value: StyleValue | null; source: Source } {
  const own = normaliseValue(field, card[field])
  if (own !== null) {
    return { value: own, source: 'card' }
  }
  const event = normaliseValue(field, style[field])
  if (event !== null) {
    return { value: event, source: 'style' }
  }
  const fallback = normaliseValue(field, read[field]) === null ? resolved?.[field] : undefined
  return fallback === undefined
    ? { value: null, source: 'unknown' }
    : { value: fallback, source: 'default' }
}

/**
 * The event style the cards inherit now: the draft's set fields over the project default, a
 * field the page does not know left out. `null` when it knows nothing of it.
 */
export function draftEventStyle(
  style: StyleDraft,
  read: StyleDraft,
  resolved: EventStyle | null,
): EventStyle | null {
  const out: Record<string, StyleValue> = {}
  for (const field of STYLE_FIELDS) {
    const { value } = effective(field, NO_CARD, style, read, resolved)
    if (value !== null && typeof value === isNumericKind(field)) {
      out[field] = value
    }
  }
  return Object.keys(out).length === 0 ? null : (out as EventStyle)
}

function isNumericKind(field: StyleField): 'number' | 'string' {
  return isNumericField(field) ? 'number' : 'string'
}

// --- a refusal at its field -------------------------------------------------------------------

/** A refusal's place: the style field it names (null: none named) and the service's words. */
export type StyleRefusal = { field: StyleField | null; message: string }

const STYLE_REFUSAL = /look\.title_card\.(\w+)/

/** The style field a refusal's `detail` names, when it names `look.title_card.<field>`; else null. */
export function styleRefusalOf(detail: string): StyleRefusal | null {
  const found = STYLE_REFUSAL.exec(detail)
  if (found === null) {
    return null
  }
  const name = found[1]
  const field = (STYLE_FIELDS as readonly string[]).includes(name) ? (name as StyleField) : null
  return { field, message: detail }
}
