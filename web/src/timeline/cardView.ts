import type { CardSpec, Placement } from './cards.ts'
import { shownAt } from './play.ts'
import type { Position } from './position.ts'

/*
 * What the Timeline's card layer shows at a position (`titlecard-scrub-fade`, D-20). The layer
 * shows the card's fades at every playhead position (played, paused, scrubbed, stepped), as the
 * movie does: a card's first instant is at opacity 0. There is deliberately no play-state
 * parameter, so a "full when paused" rule cannot come back without a signature change. Pure: no
 * DOM, no React.
 */

/** What the card layer draws at a position: nothing over a plain clip, else the card at its fade. */
export type CardView = {
  kind: 'black' | 'video'
  /** The chapter's saved name, or undefined when the spec is missing (as today's `spec?.chapter`). */
  chapter: string | undefined
  /** The fades' opacity at the position's time, in [0, 1]. Never a play-state override. */
  opacity: number
  /** The card image's object URL, or null while it is missing (then `title` is drawn on black). */
  url: string | null
  title: string
}

/** The image lookup the layer needs: `CardPictures` (useCardImages.ts) satisfies it structurally. */
export type PictureLookup = { get(chapter: string): { url: string | null } | null }

/** The card to draw at `p`, or null when the picture is the clip alone. */
export function cardViewAt(
  p: Position,
  placements: readonly Placement[],
  specs: readonly CardSpec[],
  pictures: PictureLookup,
): CardView | null {
  const shown = shownAt(p, placements)
  if (shown.kind === 'clip') {
    return null
  }
  const spec = specs[shown.chapter]
  return {
    kind: shown.kind,
    chapter: spec?.chapter,
    opacity: shown.opacity,
    url: pictures.get(spec?.chapter ?? '')?.url ?? null,
    title: spec?.card?.title ?? '',
  }
}
