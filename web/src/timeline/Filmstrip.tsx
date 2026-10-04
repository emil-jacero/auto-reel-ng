import { useEffect } from 'react'

import { filmstripUrl } from '../api/proxies'
import type { Turn } from '../rotate/turn.ts'
import { FILM_TILE_HEIGHT, filmScale, filmTiles } from './layout'
import type { TrackClip } from './layout'

/**
 * A clip's filmstrip: the sprite's tiles that fall in the window, each a box with the
 * sprite as its background (a picture only, hidden from assistive technology). Mounted
 * only for a clip that is in view, so a clip out of the window requests nothing. One
 * `Image` probes the sprite, because a background cannot report a failed load: a failure
 * is said once for the Timeline (`onFail`), not once per tile.
 *
 * A clip with a turn (`rotate`) shows each tile's frame turned inside the same tile box: the
 * picture is the tile's place (`tileWidth * scale` by `FILM_TILE_HEIGHT`), rotated about its
 * centre and scaled down to lie wholly inside it; the tile's width, place and the lane's
 * geometry do not change, and no other sprite or proxy is asked for.
 */
export function Filmstrip({
  eventId,
  clip,
  pps,
  window,
  turn = 0,
  onFail,
}: {
  eventId: string
  clip: TrackClip
  pps: number
  window: { from: number; to: number }
  /** The clip's editorial turn: its tiles show the frame turned by it. */
  turn?: Turn
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
  const place = film.tileWidth * scale
  // A quarter turn swaps the frame's sides: it is scaled to lie inside the place.
  const fit = turn === 90 || turn === 270 ? Math.min(place / FILM_TILE_HEIGHT, FILM_TILE_HEIGHT / place) : 1
  return (
    <span className="tl-film" aria-hidden="true">
      {tiles.map((tile) => {
        const picture = {
          backgroundImage: image,
          backgroundSize: size,
          backgroundPosition: `${-tile.col * film.tileWidth * scale}px ${-tile.row * FILM_TILE_HEIGHT}px`,
        }
        return turn === 0 ? (
          <span
            key={tile.x}
            className="tl-tile"
            style={{ insetInlineStart: tile.x, inlineSize: tile.width, ...picture }}
          />
        ) : (
          <span
            key={tile.x}
            className="tl-tile"
            data-turn={turn}
            style={{ insetInlineStart: tile.x, inlineSize: tile.width }}
          >
            <span
              className="tl-tile-pic"
              style={{
                inlineSize: place,
                blockSize: FILM_TILE_HEIGHT,
                rotate: `${turn}deg`,
                scale: fit,
                ...picture,
              }}
            />
          </span>
        )
      })}
    </span>
  )
}
