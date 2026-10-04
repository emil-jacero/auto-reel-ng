import { cardDurationMs, cardWords } from '../timeline/cards.ts'
import type { CardSpec } from '../timeline/cards.ts'
import { USES_EVENT_STYLE } from './cardStyle.ts'
import { oneLine } from './card/model.ts'

/*
 * The card row at the head of each chapter in Edit mode (`title-card-blocks`), as data: what
 * the row says about the chapter's saved card, matched by the chapter's saved name. Read
 * only. Pure, so `npm test` checks the words.
 */

export type CardRowInfo =
  /** A chapter added in this session: no saved card yet. */
  | { kind: 'added' }
  /** The card could not be resolved (or read): no values are shown. */
  | { kind: 'unresolved'; chapter: string; error: string; savedName: string | null }
  | {
      kind: 'card'
      /** The saved name: what the card is selected by. */
      chapter: string
      title: string
      subtitle: string
      length: string
      look: 'Black' | 'Video'
      font: string
      /** Which style fields the draft card overrides, or that it uses the event style. */
      overrides: string
      /** Whether the render draws the card (`title_cards.enabled`); null: the service gave no answer. */
      enabled: boolean | null
      /** The row's accessible name. */
      words: string
      /** The draft's name when it differs from the saved one. */
      savedName: string | null
    }

export const NO_SUBTITLE = 'No subtitle'
export const ADDED_WORDS = 'Its title card is drawn after Save.'

/**
 * The row for a draft chapter: `readName` is the name it was read with (null: added) and
 * `name` its name now; `overrides` says which style fields its draft card overrides. A renamed chapter shows its saved card and says the saved name.
 */
export function cardRowInfo(
  chapter: { readName: string | null; name: string },
  specs: readonly CardSpec[],
  overrides: string = USES_EVENT_STYLE,
  enabled: boolean | null = null,
): CardRowInfo | null {
  if (chapter.readName === null) {
    return { kind: 'added' }
  }
  const spec = specs.find((candidate) => candidate.chapter === chapter.readName)
  if (spec === undefined) {
    return null
  }
  const savedName = chapter.name !== chapter.readName ? chapter.readName : null
  if (spec.card === null) {
    return {
      kind: 'unresolved',
      chapter: spec.chapter,
      error: spec.error ?? 'The card was not resolved.',
      savedName,
    }
  }
  const background = spec.card.background
  try {
    const durationMs = cardDurationMs(spec.card.duration)
    if (background !== 'black' && background !== 'video') {
      throw new Error(`card background must be "black" or "video", got ${JSON.stringify(background)}`)
    }
    return {
      kind: 'card',
      chapter: spec.chapter,
      title: spec.card.title,
      subtitle: spec.card.subtitle === '' ? NO_SUBTITLE : oneLine(spec.card.subtitle),
      length: `${(durationMs / 1000).toFixed(1)} s`,
      look: background === 'video' ? 'Video' : 'Black',
      font: spec.card.fontFamily,
      overrides,
      enabled,
      words: cardWords(spec.chapter, { durationMs, background, off: enabled === false }),
      savedName,
    }
  } catch (error) {
    return { kind: 'unresolved', chapter: spec.chapter, error: (error as Error).message, savedName }
  }
}
