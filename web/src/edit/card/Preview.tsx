import { useEffect, useRef, useState } from 'react'

import type { Clip } from '../../api/event'
import { ClipThumb } from '../../events/ClipThumb'
import type { Turn } from '../../rotate/turn.ts'
import { Icon } from '../../ui/Icon'
import type { PreviewRequest } from './model.ts'
import { useCardPreview } from './usePreview.ts'
import { BACKDROP_NOTE, NO_BACKDROP } from './specs.ts'

/*
 * The live preview: the service's own drawing of the draft (`POST …/title-card/preview`), shown
 * in a 16:9 stage. A Black card is the image as it is. A Video card is text on transparency,
 * which the page lays over a frame of the clip it sits over (that clip's thumbnail frame, not
 * the exact start); with no clip it lies over a neutral pattern and says so. The previous image
 * stays on show while the next one loads, and a failure is said in words beside it.
 */

/** The clip a video card sits over, with the turn the page shows it with. */
export type Backdrop = { clip: Clip; name: string; turn: Turn }

export function CardPreview({
  eventId,
  request,
  title,
  subtitle,
  video,
  backdrop,
  backdropNote,
  tooLong,
}: {
  eventId: string
  /** The draft as a request, or null when a field is over the preview's bounds. */
  request: PreviewRequest | null
  title: string
  subtitle: string
  /** The card is drawn over video: its image is text on transparency. */
  video: boolean
  backdrop: Backdrop | null
  /** Words in place of the backdrop note, for a card shown over no particular clip. */
  backdropNote?: string
  tooLong: boolean
}) {
  const view = useCardPreview(eventId, request)
  const current = view.state === 'ready' || view.state === 'idle'
  const alt =
    (current ? '' : 'Last drawn preview, which may not show the current text. ') +
    `Preview of the title card: ${title === '' ? 'no title' : title}` +
    (subtitle === '' ? '' : `, subtitle ${subtitle.replace(/\s+/g, ' ')}`)
  const [aspect, setAspect] = useState<string | null>(null)

  // A polite note when the state changes to or from a problem, never for every image.
  const [said, setSaid] = useState('')
  const wasProblem = useRef(false)
  useEffect(() => {
    if (view.state === 'error' || view.state === 'busy') {
      wasProblem.current = true
      setSaid(view.message ?? '')
    } else if (view.state === 'skipped') {
      wasProblem.current = true
      setSaid('Too long to preview. The preview was not updated.')
    } else if (view.state === 'ready' && wasProblem.current) {
      wasProblem.current = false
      setSaid('Preview updated.')
    }
  }, [view.state, view.message])

  const image =
    view.url === null ? null : (
      <img
        className="ci-image"
        src={view.url}
        alt={alt}
        draggable={false}
        onLoad={(event) => {
          const { naturalWidth: w, naturalHeight: h } = event.currentTarget
          if (w > 0 && h > 0) {
            setAspect(`${w} / ${h}`)
          }
        }}
      />
    )
  const over = video && backdrop !== null
  const updating = view.state === 'updating' || view.state === 'busy'
  const problem = view.state === 'error' || view.state === 'busy' ? view.message : null
  const skipped = view.state === 'skipped'

  return (
    <figure className="ci-preview" aria-busy={updating || undefined}>
      <div
        className="ci-stage"
        data-video={video || undefined}
        data-over={over || undefined}
        data-pattern={(video && backdrop === null) || undefined}
        data-state={view.state}
        style={aspect === null ? undefined : { aspectRatio: aspect }}
      >
        {over ? (
          <ClipThumb
            eventId={eventId}
            clip={backdrop.clip}
            name={backdrop.name}
            turn={backdrop.turn}
            overlay={image === null ? null : <span className="ci-layer">{image}</span>}
          />
        ) : (
          image
        )}
        {image === null && (
          <p className="ci-wait" role="presentation">
            {view.state === 'error' ? 'No preview yet' : 'Drawing the preview…'}
          </p>
        )}
        {updating && image !== null && (
          <span className="ci-updating">
            <Icon name="refresh" size={16} />
            Updating
          </span>
        )}
      </div>
      <figcaption className="ci-caption">
        {video && (
          <span className="ci-backdrop-note">
            {backdropNote ?? (backdrop === null ? NO_BACKDROP : BACKDROP_NOTE(backdrop.name))}
          </span>
        )}
        {skipped && (
          <span className="ci-problem" data-tone="warn">
            <Icon name="alert-triangle" size={16} />
            {tooLong
              ? 'Too long to preview, so the picture is not updated. The text is kept and still saves.'
              : 'Not previewed.'}
          </span>
        )}
        {problem !== null && (
          <span className="ci-problem" data-tone={view.state === 'busy' ? 'warn' : 'err'}>
            <Icon name="alert-triangle" size={16} />
            {problem}
          </span>
        )}
      </figcaption>
      <p className="visually-hidden" role="status">
        {said}
      </p>
    </figure>
  )
}
