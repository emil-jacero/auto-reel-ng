import { memo, useSyncExternalStore } from 'react'

import type { CardSpec, Placement } from './cards'
import { cardViewAt } from './cardView'
import type { Playhead } from './playhead'
import type { CardPictures } from './useCardImages'

/**
 * The title card over the Timeline's picture (`timeline-plays-cards`): in a black card the card
 * replaces the picture (an opaque black layer, so the clip loading behind it never shows, and
 * only the image fades on it); over a video card's window the card's image, text on transparency,
 * is laid over the playing video. Same box as the `<video>`, `object-fit: contain`, pointer-inert
 * and hidden from assistive technology: the readout and the slider carry the words. While a
 * card's image is missing its title is shown on black. It reads the playhead's store itself, so
 * a playing card renders this and not the track.
 *
 * It shows the card's fades at every playhead position (played, paused, scrubbed, stepped), as the
 * movie does (`titlecard-scrub-fade`). What to show is decided by the pure `cardView.ts`.
 */
export const CardLayer = memo(function CardLayer({
  playhead,
  placements,
  specs,
  pictures,
}: {
  playhead: Playhead
  placements: readonly Placement[]
  specs: readonly CardSpec[]
  pictures: CardPictures
}) {
  const at = useSyncExternalStore(playhead.subscribe, playhead.get)
  const view = cardViewAt(at, placements, specs, pictures)
  if (view === null) {
    return null
  }
  const { opacity } = view
  return (
    <div
      className="tl-card-layer"
      data-kind={view.kind}
      data-chapter={view.chapter}
      data-opacity={opacity.toFixed(3)}
      aria-hidden="true"
    >
      {view.url !== null ? (
        <img src={view.url} alt="" draggable={false} style={{ opacity }} />
      ) : (
        <p className="tl-card-fallback" style={{ opacity }}>
          {view.title}
        </p>
      )}
    </div>
  )
})
