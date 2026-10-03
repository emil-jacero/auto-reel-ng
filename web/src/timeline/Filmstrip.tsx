import { useEffect } from 'react'

import { filmstripUrl } from '../api/proxies'
import { FILM_TILE_HEIGHT, filmScale, filmTiles } from './layout'
import type { TrackClip } from './layout'

/**
 * A clip's filmstrip: the sprite's tiles that fall in the window, each a box with the
 * sprite as its background (a picture only, hidden from assistive technology). Mounted
 * only for a clip that is in view, so a clip out of the window requests nothing. One
 * `Image` probes the sprite, because a background cannot report a failed load: a failure
 * is said once for the Timeline (`onFail`), not once per tile.
 */
export function Filmstrip({
  eventId,
  clip,
  pps,
  window,
  onFail,
}: {
  eventId: string
  clip: TrackClip
  pps: number
  window: { from: number; to: number }
  onFail: (identity: string) => void
}) {
  const { identity, version, film } = clip
  const url = filmstripUrl(eventId, { identity }, version)
  useEffect(() => {
    const probe = new Image()
    probe.onerror = () => onFail(identity)
    probe.src = url
    return () => {
      probe.onerror = null
    }
  }, [url, identity, onFail])

  const scale = filmScale(film)
  const rows = Math.ceil(film.tiles / film.columns)
  const size = `${film.columns * film.tileWidth * scale}px ${rows * FILM_TILE_HEIGHT}px`
  const image = `url(${JSON.stringify(url)})`
  const tiles = filmTiles(film, clip.facts.durationMs, pps, window)
  return (
    <span className="tl-film" aria-hidden="true">
      {tiles.map((tile) => (
        <span
          key={tile.x}
          className="tl-tile"
          style={{
            insetInlineStart: tile.x,
            inlineSize: tile.width,
            backgroundImage: image,
            backgroundSize: size,
            backgroundPosition: `${-tile.col * film.tileWidth * scale}px ${-tile.row * FILM_TILE_HEIGHT}px`,
          }}
        />
      ))}
    </span>
  )
}
