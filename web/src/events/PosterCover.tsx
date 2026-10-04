import './poster.css'
import './thumbs.css'

import { useState } from 'react'

import '../rotate/rotate.css'
import { turnAttr } from '../rotate/turn.ts'
import type { Turn } from '../rotate/turn.ts'
import { Icon } from '../ui/Icon'

/*
 * An event's poster as a cover image: a 16:9 box as wide as the place it is given, reserved
 * before the image arrives so nothing shifts, the frame shown whole inside it. Requested
 * only near the view (native lazy loading) and behind the page's own requests. Any failure
 * (the event plays no clip, the frame cannot be made, the service is away) shows the same
 * neutral "No poster" box, with no alert: the row's real problems are said where they are.
 * `turn` is a snapshot's editorial turn (`rotate`), shown the way the Timeline shows it.
 */

type CoverState = 'loading' | 'loaded' | 'failed'

export function PosterCover({
  src,
  alt,
  none,
  turn = 0,
  eager = false,
}: {
  /** `null`: there is nothing to request (the event plays no clip); the placeholder shows. */
  src: string | null
  /** The image's alternative text: names the event (and the page's cover, which frame). */
  alt: string
  /** The placeholder's accessible name: names the event. */
  none: string
  turn?: Turn
  /** The page's own cover is above the fold: not lazy. */
  eager?: boolean
}) {
  // Keyed by address: another poster starts loading afresh.
  return <Box key={src ?? ''} src={src} alt={alt} none={none} turn={turn} eager={eager} />
}

function Box({
  src,
  alt,
  none,
  turn,
  eager,
}: {
  src: string | null
  alt: string
  none: string
  turn: Turn
  eager: boolean
}) {
  const [state, setState] = useState<CoverState>(src === null ? 'failed' : 'loading')
  return (
    <span
      className="clip-thumb poster-cover"
      data-state={state}
      data-turned={(state !== 'failed' && turn !== 0) || undefined}
    >
      {state === 'failed' || src === null ? (
        <span className="clip-thumb-none" role="img" aria-label={none}>
          <Icon name="film" />
          <span aria-hidden="true">No poster</span>
        </span>
      ) : (
        <img
          src={src}
          width={640}
          height={360}
          alt={alt}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          fetchPriority="low"
          draggable={false}
          data-turn={turnAttr(turn)}
          onLoad={() => setState('loaded')}
          onError={() => setState('failed')}
        />
      )}
    </span>
  )
}
