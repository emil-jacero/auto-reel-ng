import { encodeEventId } from '../route'
import type { Clip } from './event'
import { isProblem, readJson } from './http'
import type { paths } from './schema'

/**
 * A clip's thumbnail address: the only module that knows its URL.
 *
 * An `<img>` makes the request, and every failure looks the same to it
 * (`events/ClipThumb.tsx`); only a box that has already failed asks again, through
 * `readFailedThumbnail`, to read the service's answer. The route and its query are
 * checked against the generated `paths`, so renaming either in the service fails
 * `tsc --noEmit`.
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

/**
 * Why a thumbnail the browser could not show failed, by who is at fault:
 * the clip's own failure (the service answers a 502 with `thumbnail_failure`), the
 * service's (a 502 with none: its thumbnail cache or `config.yaml`, so that no clip could
 * have a preview, named by the problem's `failure` when it has one, `none` otherwise), or
 * anything else (another status, no answer, or an answer that works now).
 */
export type FailedThumbnail =
  | { kind: 'clip' }
  | { kind: 'service'; failure: string }
  | { kind: 'unknown' }

/**
 * One further request for the address of a thumbnail that failed to show, only to read
 * the answer. It never throws except `AbortError` (a box that left the page, not an
 * answer), and its body is never shown. The kind the service gives a clip's own failure
 * is the one the engine's failure marker replays, so this stays cheap for a broken clip.
 */
export async function readFailedThumbnail(
  url: string,
  signal: AbortSignal,
): Promise<FailedThumbnail> {
  let response: Response
  try {
    response = await fetch(url, { cache: 'no-store', signal })
  } catch (error) {
    if (signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
      throw error
    }
    return { kind: 'unknown' }
  }
  if (response.status !== 502) {
    await response.body?.cancel().catch(() => undefined)
    return { kind: 'unknown' }
  }
  const body = await readJson(response)
  if (!isProblem(body) || body.status !== 502) {
    return { kind: 'unknown' }
  }
  if (body.thumbnail_failure === 'thumbnail_failed') {
    return { kind: 'clip' }
  }
  if (body.thumbnail_failure == null) {
    return { kind: 'service', failure: body.failure ?? 'none' }
  }
  return { kind: 'unknown' }
}
