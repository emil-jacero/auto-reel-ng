import type { Font } from '../../api/fonts.ts'
import type { CardSpec, Placement } from '../../timeline/cards.ts'
import { cardChanged } from './model.ts'
import type { CardDraft } from './model.ts'

/*
 * What the draft card shows on the Timeline's blocks and the chapter rows, and which clip the
 * preview lays a video card over: pure rules (`title-card-inspector`). Nothing is guessed: with
 * no event style and no saved card to start from, the saved spec stays as it is.
 */

/**
 * The event-wide style an unset card field inherits: the detail's resolved `title_card`, under the
 * draft's edits of `look.title_card` (`cardStyle.ts`). A field the page does not know (the operator
 * cleared a value the saved style set, so the lower layer is not known) is absent, never guessed.
 */
export type EventStyle = {
  duration?: number
  background?: string
  font_family?: string
  title_font_size?: number
  subtitle_font_size?: number
  text_color?: string
  position?: string
}

/**
 * The card as the render would draw it with the draft's overrides: the event style under the
 * set overrides, the title as `titleNow` says while unset (the chapter's name now; the event's
 * title for the opening card), the subtitle the detail's default while unset (empty for a chapter card; never composed here). A card the draft did not change,
 * under an event style that is as saved, is the saved spec itself, so a block and a row keep
 * their identity. `styleEdited`: the draft changed the event style, so every card is drawn
 * from `read` (the card as read) and `style`. A field the page does not know (no style, no
 * saved card) keeps the saved spec: nothing is guessed.
 */
export function draftSpec(
  spec: CardSpec,
  style: EventStyle | null,
  read: CardDraft,
  draft: CardDraft | undefined,
  titleNow: string,
  styleEdited = false,
): CardSpec {
  const own = draft ?? read
  if (!styleEdited && (draft === undefined || !cardChanged(read, draft))) {
    return spec
  }
  const base = spec.card
  const duration = own.duration ?? style?.duration ?? base?.duration
  const background = own.background ?? style?.background ?? base?.background
  const fontFamily = own.font_family ?? style?.font_family ?? base?.fontFamily
  if (duration === undefined || background === undefined || fontFamily === undefined) {
    return spec
  }
  const defaultSubtitle = base?.defaultSubtitle ?? ''
  const card = {
    duration,
    background,
    title: own.title ?? titleNow,
    subtitle: own.subtitle ?? defaultSubtitle,
    defaultSubtitle,
    fontFamily,
  }
  return { ...spec, card, error: null }
}

/**
 * The background the card is drawn with, as far as the page knows it: the draft's override,
 * else the event style's, else the saved card's; null when none is known.
 */
export function effectiveBackground(
  draft: CardDraft,
  style: EventStyle | null,
  spec: CardSpec | undefined,
): string | null {
  return draft.background ?? style?.background ?? spec?.card?.background ?? null
}

/** The shown clip a video card sits over: its identity and the name the page gives it. */
export type Backdrop = { identity: string; name: string }

/**
 * The clip the chapter's card sits over: the one the Timeline anchors it on when the
 * placements are known (honouring exclusion and whole-clip cuts), else the chapter's first
 * shown clip. Null when the chapter shows no clip.
 */
export function backdropOf(
  chapter: number,
  shown: readonly { identity: string; name: string; chapter: number }[],
  placements: readonly Placement[] | null,
): Backdrop | null {
  const placed = placements?.find(
    (place) => place.chapter === chapter && (place.kind === 'anchored' || place.kind === 'off'),
  )
  const clip =
    placed !== undefined && 'clip' in placed ? shown[placed.clip] : shown.find((c) => c.chapter === chapter)
  return clip === undefined ? null : { identity: clip.identity, name: clip.name }
}

export const BACKDROP_NOTE = (name: string) => `Backdrop: a frame from ${name}, not the exact start.`
export const NO_BACKDROP = 'No clip frame to show it over.'

/** A style value as words (`Black`, a font's display name, the number), or empty when the value is not known. */
export function styleWords(
  field: string,
  value: string | number | undefined,
  fonts: readonly Font[],
): string {
  if (value === undefined || value === '') {
    return ''
  }
  if (field === 'font_family') {
    return fonts.find((font) => font.family === value)?.display_name ?? String(value)
  }
  if (field === 'background' || field === 'position') {
    const text = String(value)
    return text.charAt(0).toUpperCase() + text.slice(1)
  }
  return String(value)
}
