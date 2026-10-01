import { encodeEventId } from '../route'
import type { Clip } from './event'
import { isProblem, readJson, unpublishedAnswer } from './http'
import type { Problem, Unanswered } from './http'
import type { paths } from './schema'

/**
 * A clip's media: the only module that knows its URL and its statuses.
 *
 * A `<video>` makes the playing requests, and every failure looks the same to it
 * (`MediaError` 4 for a 404, a 502 and an empty file alike). So after a failure the
 * preview asks for the clip's first byte once, to say why (`checkClipMedia`). The
 * route and its query are checked against the generated `paths`, as `thumbnail.ts`
 * does, so renaming either in the service fails `tsc --noEmit`.
 */

const MEDIA_PATH = '/api/v1/events/{event_id}/media' satisfies keyof paths
type MediaQuery = NonNullable<paths[typeof MEDIA_PATH]['get']['parameters']['query']>

/**
 * The event id encoded per segment, the identity as the `clip` query value, and the
 * clip's `mtime` exactly as the detail gives it as `v`: the service ignores `v`, so it
 * only gives a replaced clip a new address (and, in the preview, a new length key).
 */
export function clipMediaUrl(eventId: string, clip: Pick<Clip, 'identity' | 'mtime'>): string {
  const query: Record<string, string> =
    clip.mtime == null
      ? ({ clip: clip.identity } satisfies MediaQuery)
      : ({ clip: clip.identity, v: clip.mtime } satisfies MediaQuery)
  const path = MEDIA_PATH.replace('{event_id}', () => encodeEventId(eventId))
  return `${path}?${new URLSearchParams(query)}`
}

/** What one byte of the clip told. */
export type MediaCheck =
  // 206 or 200: the file is served; its `Last-Modified` (null when absent)
  | { kind: 'served'; lastModified: string | null }
  // 416: no first byte (a zero-byte file)
  | { kind: 'empty' }
  // 404 / 502 in the published problem shape
  | { kind: 'problem'; problem: Problem }
  | Unanswered

// The failure statuses the route declares with a problem body (see the schema).
const PROBLEM_STATUSES = new Set([404, 502])

/**
 * One `GET` with `Range: bytes=0-0` and `cache: 'no-store'`: no `If-None-Match`, so
 * never a 304. The body is cancelled unread. Rethrows `AbortError`.
 */
export async function checkClipMedia(src: string, signal: AbortSignal): Promise<MediaCheck> {
  let response: Response
  try {
    response = await fetch(src, { headers: { Range: 'bytes=0-0' }, cache: 'no-store', signal })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }
  if (response.status === 206 || response.status === 200) {
    void response.body?.cancel().catch(() => undefined)
    return { kind: 'served', lastModified: response.headers.get('Last-Modified') }
  }
  if (response.status === 416) {
    return { kind: 'empty' }
  }
  const body = await readJson(response)
  if (PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return unpublishedAnswer('GET', src, response)
}

/**
 * Whether the file the service serves is not the one the page read: true when both
 * times are present and differ in whole seconds. The detail's `mtime` (a UTC instant
 * with microseconds, `…Z`) is read from its first 19 characters, and `Last-Modified`
 * (whole seconds, HTTP date) with `Date.parse`. Both follow a symbolic link.
 */
export function changedSince(mtime: string | null, lastModified: string | null): boolean {
  if (mtime === null || lastModified === null) {
    return false
  }
  const read = Date.parse(`${mtime.slice(0, 19)}Z`)
  const served = Date.parse(lastModified)
  if (Number.isNaN(read) || Number.isNaN(served)) {
    return false
  }
  return Math.floor(read / 1000) !== Math.floor(served / 1000)
}
