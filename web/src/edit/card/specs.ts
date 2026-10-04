import type { CardSpec, Placement } from '../../timeline/cards.ts'
import { cardChanged } from './model.ts'
import type { CardDraft } from './model.ts'

/*
 * What the draft card shows on the Timeline's blocks and the chapter rows, and which clip the
 * preview lays a video card over: pure rules (`title-card-inspector`). Nothing is guessed: with
 * no event style and no saved card to start from, the saved spec stays as it is.
 */

/** The event-wide resolved style (`title_card` of the detail): what an unset field inherits. */
export type EventStyle = {
  duration: number
  background: string
  font_family: string
  title_font_size: number
  subtitle_font_size: number
  text_color: string
  position: string
}

/**
 * The card as the render would draw it with the draft's overrides: the event style under the
 * set overrides, the title as `titleNow` says while unset (the chapter's name now; the event's
 * title for the opening card), the subtitle empty while unset. An unchanged card is the saved
 * spec itself, so a block and a row keep their identity.
 */
export function draftSpec(
  spec: CardSpec,
  style: EventStyle | null,
  read: CardDraft,
  draft: CardDraft | undefined,
  titleNow: string,
): CardSpec {
  if (draft === undefined || !cardChanged(read, draft)) {
    return spec
  }
  const base = spec.card
  if (style === null && base === null) {
    return spec
  }
  const card = {
    duration: draft.duration ?? style?.duration ?? base?.duration ?? 0,
    background: draft.background ?? style?.background ?? base?.background ?? '',
    title: draft.title ?? titleNow,
    subtitle: draft.subtitle ?? '',
    fontFamily: draft.font_family ?? style?.font_family ?? base?.fontFamily ?? '',
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
