import { useSyncExternalStore } from 'react'

import type { CardSpec, Placement } from './cards'
import { shownAt } from './play'
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
 */
export function CardLayer({
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
  const shown = shownAt(at, placements)
  if (shown.kind === 'clip') {
    return null
  }
  const spec = specs[shown.chapter]
  const url = pictures.get(spec?.chapter ?? '')?.url ?? null
  const title = spec?.card?.title ?? ''
  return (
    <div
      className="tl-card-layer"
      data-kind={shown.kind}
      data-chapter={spec?.chapter}
      data-opacity={shown.opacity.toFixed(3)}
      aria-hidden="true"
    >
      {url !== null ? (
        <img src={url} alt="" draggable={false} style={{ opacity: shown.opacity }} />
      ) : (
        <p className="tl-card-fallback" style={{ opacity: shown.opacity }}>
          {title}
        </p>
      )}
    </div>
  )
}
