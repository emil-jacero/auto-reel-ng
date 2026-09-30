import './thumbs.css'

import { useState } from 'react'

import type { Clip } from '../api/event'
import { thumbnailUrl } from '../api/thumbnail'
import { Icon } from '../ui/Icon'
import { fileName } from './common'

/*
 * A clip's thumbnail: the frame the service extracts, in a fixed 16:9 box that
 * its screen sizes by the column it sits in. The component decides its own
 * states; the screens decide only where it sits and how wide it is.
 *
 * It never gets in the page's way: the image is requested only near the view
 * (native lazy loading), behind the page's own requests (low fetch priority),
 * and the box has its final size before any byte arrives. Any failure shows one
 * neutral "No preview" box, with no alert and no retry: the clip's real
 * problems are reported where they already are (its status, its job).
 */

/** The thumbnail of one clip row; a missing clip requests nothing. */
export function ClipThumb({ eventId, clip }: { eventId: string; clip: Clip }) {
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
      name={fileName(clip.identity)}
      dimmed={clip.status === 'ignored'}
    />
  )
}

type ThumbState = 'loading' | 'loaded' | 'failed'

/**
 * The box and its image. No effect and no ref: React sets `loading` and
 * `fetchpriority` before `src`, and a load from the memory cache still reaches
 * `onLoad`. No fade-in, so a remounted row (Refresh, Edit mode) never flickers.
 */
function LoadingThumb({ src, name, dimmed }: { src: string; name: string; dimmed: boolean }) {
  const [state, setState] = useState<ThumbState>('loading')
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
    </span>
  )
}
