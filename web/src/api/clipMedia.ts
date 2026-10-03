import { encodeEventId } from '../route'
import type { Clip } from './event'
import type { Problem, Unanswered } from './http'
import { entityVersion } from './headers'
import { probeFirstByte } from './probe'
import type { paths } from './schema'

/**
 * A clip's media: the only module that knows its URL and its statuses.
 *
 * A `<video>` makes the playing requests, and every failure looks the same to it
 * (`MediaError` 4 for a 404, a 502 and an empty file alike). So after a failure the
 * preview asks for the clip's first byte once, to say why (`checkClipMedia`). The
 * route and its query are checked against the generated `paths`, as `thumbnail.ts`
 * does, so renaming either in the service fails `tsc --noEmit`.
 *
 * The same goes for the clip's preview copy (D-21): its address (`proxyUrl`) and the
 * one-byte request that reads its entity tag (`probeProxy`), which the address carries
 * as `v` because Chrome fails a replaced file at an address that served the old one.
 */

const MEDIA_PATH = '/api/v1/events/{event_id}/media' satisfies keyof paths
type MediaQuery = NonNullable<paths[typeof MEDIA_PATH]['get']['parameters']['query']>
const PROXY_PATH = '/api/v1/events/{event_id}/proxy' satisfies keyof paths
type ProxyQuery = NonNullable<paths[typeof PROXY_PATH]['get']['parameters']['query']>

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

/**
 * The clip's preview copy: the event id encoded per segment, the identity as the `clip`
 * query value and, once the copy's entity tag is known, that tag as `v` (the service
 * ignores it; it gives a replaced copy a new address). `version` is null for the probe's
 * own address.
 */
export function proxyUrl(
  eventId: string,
  clip: Pick<Clip, 'identity'>,
  version: string | null,
): string {
  const query: Record<string, string> =
    version === null
      ? ({ clip: clip.identity } satisfies ProxyQuery)
      : ({ clip: clip.identity, v: version } satisfies ProxyQuery)
  const path = PROXY_PATH.replace('{event_id}', () => encodeEventId(eventId))
  return `${path}?${new URLSearchParams(query)}`
}

/** What one byte of the clip's preview copy told. */
export type ProxyProbe =
  // 200 or 206 with an entity tag: the copy is served, at this version
  | { kind: 'ok'; version: string }
  // 416: the copy has no first byte
  | { kind: 'empty' }
  // 404 / 502 in the published problem shape (404: the service has no copy of the clip)
  | { kind: 'problem'; problem: Problem }
  | Unanswered

/**
 * The copy's first byte by the shared table (`probe.ts`), never from or into the
 * browser's cache. A served copy must carry an entity tag: an answer without one is
 * not a usable answer (`unpublished`), as the movie's is. Rethrows `AbortError`.
 */
export async function probeProxy(
  eventId: string,
  identity: string,
  signal: AbortSignal,
): Promise<ProxyProbe> {
  const answer = await probeFirstByte(proxyUrl(eventId, { identity }, null), signal, (response) =>
    entityVersion(response.headers.get('ETag')),
  )
  return answer.kind === 'served' ? { kind: 'ok', version: answer.file } : answer
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

/**
 * The clip's first byte, by the movie's own table (`probe.ts`): any 200 or 206 is the
 * file served, with its `Last-Modified`. Rethrows `AbortError`.
 */
export async function checkClipMedia(src: string, signal: AbortSignal): Promise<MediaCheck> {
  const answer = await probeFirstByte(src, signal, (response) => ({
    lastModified: response.headers.get('Last-Modified'),
  }))
  return answer.kind === 'served' ? { kind: 'served', ...answer.file } : answer
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
