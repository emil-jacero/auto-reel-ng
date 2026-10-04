import { cardDurationMs, cardWords } from './cards'
import type { CardSpec } from './cards'

/*
 * The selected card's announcement (`title-card-blocks`, `help-text-declutter`): selecting a card
 * block shows no text panel. Its words go once through a polite, visually hidden status region
 * that is always there, so a selection is announced when it changes; the block's own accessible
 * name says the same. A card's editor is a dialog (`edit/card/Inspector.tsx`).
 */

/** The selected card in words, or null when nothing is selected. */
export function inspectorWords(spec: CardSpec | undefined): string | null {
  if (spec === undefined) {
    return null
  }
  const who = spec.chapter === '' ? 'the opening' : spec.chapter
  if (spec.card === null) {
    return `Title card for ${who} could not be resolved${spec.error === null ? '' : `: ${spec.error}`}`
  }
  try {
    const background = spec.card.background === 'video' ? 'video' : 'black'
    return cardWords(spec.chapter, { durationMs: cardDurationMs(spec.card.duration), background })
  } catch (error) {
    return `Title card for ${who} cannot be read: ${(error as Error).message}`
  }
}

/** The always-present, visually hidden polite status region; `announced` is what it says. */
export function CardInspector({ announced }: { announced: string | null }) {
  return (
    <p className="visually-hidden" role="status">
      {announced ?? ''}
    </p>
  )
}
