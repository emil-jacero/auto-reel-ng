import type { PreviewResult } from '../api/titleCard.ts'
import { NO_CARD, previewRequest } from '../edit/card/model.ts'
import type { PreviewRequest } from '../edit/card/model.ts'
import type { Drawn, CardJob } from './cardImages.ts'
import type { CardSpec, Placement } from './cards.ts'

/*
 * What the Timeline asks the title-card preview for (`timeline-plays-cards`): one request per
 * card the lane draws as playing, built from the card as the detail resolved it (the draft's in
 * Edit mode) through the inspector's own `previewRequest`, and the answer of the client read as
 * the queue reads it. Pure: no DOM, no network.
 */

/**
 * The jobs for the cards that play, in play order. A card is sent as its resolved text,
 * background, length and font, so the image is the card the render draws; the opening card also
 * carries the (draft) event title, and the event's draft style goes along only when it differs
 * from the saved one (`style`). A card over the preview's text bounds gets no job: nothing is
 * sent, and its block and span show the title on black.
 */
export function cardJobs(
  specs: readonly CardSpec[],
  placements: readonly Placement[],
  style?: { [key: string]: unknown },
): CardJob<PreviewRequest>[] {
  const jobs: CardJob<PreviewRequest>[] = []
  for (const place of placements) {
    if (place.kind !== 'anchored') {
      continue
    }
    const spec = specs[place.chapter]
    const card = spec?.card
    if (card == null) {
      continue
    }
    const opening = spec.chapter === ''
    const request = previewRequest({
      opening,
      chapterName: spec.chapter,
      card: {
        ...NO_CARD,
        title: card.title,
        subtitle: card.subtitle,
        duration: card.duration,
        background: card.background,
        font_family: card.fontFamily,
      },
      eventTitle: opening ? card.title : '',
      style,
    })
    if (request !== null) {
      jobs.push({ chapter: spec.chapter, request })
    }
  }
  return jobs
}

/** The client's result as the queue reads it: a problem becomes its words. */
export function drawnOf(result: PreviewResult): Drawn {
  switch (result.kind) {
    case 'image':
      return { kind: 'image', png: result.png }
    case 'busy':
      return { kind: 'busy', retryAfter: result.retryAfter }
    case 'refused':
    case 'gone':
    case 'failed':
      return { kind: 'failed', message: result.problem.detail }
    case 'bound':
    case 'unpublished':
      return { kind: 'failed', message: result.message }
    case 'unreachable':
      return { kind: 'failed', message: 'The service did not answer.' }
    default: {
      const unhandled: never = result
      throw new Error(`unhandled preview answer ${String(unhandled)}`)
    }
  }
}
