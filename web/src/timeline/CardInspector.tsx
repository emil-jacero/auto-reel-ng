import { cardDurationMs, cardWords } from './cards'
import type { CardSpec } from './cards'

/*
 * The inspector slot (`title-card-blocks`): in the read view, selecting a card names it in a
 * labelled region and nothing more; it writes nothing and requests nothing. Edit mode fills the
 * slot with the card's inspector instead (`edit/card/Inspector.tsx`, `title-card-inspector`).
 * Its words also go once through a polite status region that is always there, so a selection
 * is announced when it changes.
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

/**
 * `words` is what the slot shows (the draft's length included); `announced` is what the status
 * region says, from the card as the page read it, so a length changed by drag or key is
 * spoken once by its own release words or its handle's value, not again here.
 */
export function CardInspector({
  words,
  announced = words,
}: {
  words: string | null
  announced?: string | null
}) {
  return (
    <>
      {words !== null && (
        <section className="tl-inspector" aria-label="Title card">
          <p className="tl-inspector-card">{words}</p>
        </section>
      )}
      <p className="visually-hidden" role="status">
        {announced ?? ''}
      </p>
    </>
  )
}
