import { cardDurationMs, cardWords } from './cards'
import type { CardSpec } from './cards'

/*
 * The inspector slot (`title-card-blocks`): selecting a card opens nothing but this labelled
 * region, which says that card editing comes next and names the card. It writes nothing and
 * requests nothing. Its words also go once through a polite status region that is always
 * there, so a selection is announced when it changes.
 */

export const INSPECTOR_NOTE = 'Card editing comes next'

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

export function CardInspector({ words }: { words: string | null }) {
  return (
    <>
      {words !== null && (
        <section className="tl-inspector" aria-label="Title card">
          <p className="tl-inspector-note">{INSPECTOR_NOTE}</p>
          <p className="tl-inspector-card">{words}</p>
        </section>
      )}
      <p className="visually-hidden" role="status">
        {words ?? ''}
      </p>
    </>
  )
}
