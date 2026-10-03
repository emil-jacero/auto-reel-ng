import './thumbs.css'

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import type { Clip } from '../api/event'
import { readFailedThumbnail, thumbnailUrl } from '../api/thumbnail'
import { Icon } from '../ui/Icon'
import { fileName } from './common'
import { SERVICE_CAUSE, useThumbReporter } from './thumbHealth'

/*
 * A clip's thumbnail: the frame the service extracts, in a fixed 16:9 box that
 * its screen sizes by the column it sits in. The component decides its own
 * states; the screens decide only where it sits and how wide it is.
 *
 * It never gets in the page's way: the image is requested only near the view
 * (native lazy loading), behind the page's own requests (low fetch priority),
 * and the box has its final size before any byte arrives. Any failure shows one
 * neutral "No preview" box, with no alert and no retry of the image: the clip's real
 * problems are reported where they already are (its status, its job).
 *
 * A failed box asks once, for the same address, why it failed, and tells the page when
 * the cause is the service's and not the clip's (`thumbHealth.ts`), so that a page of
 * "No preview" boxes can say once that previews are unavailable. The box shows nothing
 * of that answer.
 */

/**
 * The thumbnail of one clip row; a missing clip requests nothing. `name` is the
 * clip's name as its row shows it (`clipNames`), for "Frame from …" and
 * "No preview for …"; it defaults to the file name. `overlay` is laid inside the box, over
 * the image or the "No preview" placeholder (the read view's play control); a missing
 * clip has no box to lay it in and ignores it.
 */
export function ClipThumb({
  eventId,
  clip,
  name = fileName(clip.identity),
  overlay = null,
}: {
  eventId: string
  clip: Clip
  name?: string
  overlay?: ReactNode
}) {
  // No file, no frame: an empty outline, hidden, since the row's status says why.
  if (clip.status === 'missing') {
    return <span className="clip-thumb" data-state="missing" aria-hidden="true" />
  }
  const src = thumbnailUrl(eventId, clip)
  // Keyed by address: a clip replaced on disk (a new `mtime`) starts loading afresh.
  return (
    <LoadingThumb
      key={src}
      src={src}
      name={name}
      dimmed={clip.status === 'ignored'}
      overlay={overlay}
    />
  )
}

type ThumbState = 'loading' | 'loaded' | 'failed'

/**
 * The box and its image. No effect or ref on the image itself (the effect below runs
 * only once it has failed): React sets `loading` and `fetchpriority` before `src`,
 * and a load from the memory cache still reaches `onLoad`. No fade-in, so a remounted row
 * (Refresh, Edit mode) never flickers.
 */
function LoadingThumb({
  src,
  name,
  dimmed,
  overlay,
}: {
  src: string
  name: string
  dimmed: boolean
  overlay: ReactNode
}) {
  const [state, setState] = useState<ThumbState>('loading')
  const { report, clear } = useThumbReporter()
  const failed = state === 'failed'
  useEffect(() => {
    if (!failed) {
      return
    }
    const controller = new AbortController()
    readFailedThumbnail(src, controller.signal)
      .then((why) => {
        if (why.kind === 'service' && !controller.signal.aborted) {
          report(src, SERVICE_CAUSE)
        }
      })
      .catch(() => undefined)
    return () => {
      controller.abort()
      clear(src)
    }
  }, [failed, src, report, clear])
  return (
    <span className="clip-thumb" data-state={state} data-dimmed={dimmed || undefined}>
      {state === 'failed' ? (
        <span className="clip-thumb-none" role="img" aria-label={`No preview for ${name}`}>
          <Icon name="film" />
          <span aria-hidden="true">No preview</span>
        </span>
      ) : (
        // Only the handle drags a row: the image never starts a native drag.
        <img
          src={src}
          width={320}
          height={180}
          alt={`Frame from ${name}`}
          loading="lazy"
          decoding="async"
          fetchPriority="low"
          draggable={false}
          onLoad={() => setState('loaded')}
          onError={() => setState('failed')}
        />
      )}
      {overlay}
    </span>
  )
}
