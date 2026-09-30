import { encodeEventId } from '../route'
import type { Clip } from './event'
import type { paths } from './schema'

/**
 * A clip's thumbnail address: the only module that knows its URL.
 *
 * No fetch: an `<img>` makes the request, and every failure looks the same to it
 * (`events/ClipThumb.tsx`). The route and its query are checked against the
 * generated `paths`, so renaming either in the service fails `tsc --noEmit`.
 */

const THUMBNAIL_PATH = '/api/v1/events/{event_id}/thumbnail' satisfies keyof paths
type ThumbnailQuery = NonNullable<paths[typeof THUMBNAIL_PATH]['get']['parameters']['query']>

/**
 * The event id encoded per segment, the identity as the `clip` query value, and
 * the clip's `mtime` exactly as the detail gives it as `v`: the service ignores
 * `v`, so it only gives a replaced clip a new address.
 */
export function thumbnailUrl(eventId: string, clip: Pick<Clip, 'identity' | 'mtime'>): string {
  const query: Record<string, string> =
    clip.mtime == null
      ? ({ clip: clip.identity } satisfies ThumbnailQuery)
      : ({ clip: clip.identity, v: clip.mtime } satisfies ThumbnailQuery)
  const path = THUMBNAIL_PATH.replace('{event_id}', () => encodeEventId(eventId))
  return `${path}?${new URLSearchParams(query)}`
}
