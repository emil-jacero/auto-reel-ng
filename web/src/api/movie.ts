import { encodeEventId } from '../route'
import { contentRangeSize, dispositionName } from './headers'
import { isProblem, readJson, unpublishedAnswer } from './http'
import type { Problem, Unanswered } from './http'
import type { paths } from './schema'

/**
 * The event's rendered movie: the only module that knows its URL and its statuses.
 *
 * The route and its query are checked against the generated `paths`, so renaming
 * either in the service fails `tsc --noEmit`. The `<video>` makes the playing
 * requests; this module makes only the one-byte probe that names the file.
 */

const MOVIE_PATH = '/api/v1/events/{event_id}/movie' satisfies keyof paths
type MovieQuery = NonNullable<paths[typeof MOVIE_PATH]['get']['parameters']['query']>

/**
 * The movie's address: the event id encoded per segment and, for the player, the
 * file's entity-tag without quotes as `v`. The service ignores `v`; it gives a
 * replaced file a new address, since Chrome fails a replaced file at an address
 * that served the old one. `version` is null for the probe's own address.
 */
export function movieUrl(eventId: string, version: string | null): string {
  const path = MOVIE_PATH.replace('{event_id}', () => encodeEventId(eventId))
  if (version === null) {
    return path
  }
  const query: Record<string, string> = { v: version } satisfies MovieQuery
  return `${path}?${new URLSearchParams(query)}`
}

/** What one byte of the movie told: never a guessed fact (`null` when a header was absent). */
export type MovieFile = { version: string; size: number | null; name: string | null }

export type MovieProbe =
  | { kind: 'ok'; file: MovieFile }
  // 416: the file has no bytes
  | { kind: 'empty' }
  // 404 / 502 in the published ProblemOut shape
  | { kind: 'problem'; problem: Problem }
  | Unanswered

// The failure statuses the route declares with a problem body (see the schema).
const PROBLEM_STATUSES = new Set([404, 502])

/** The entity-tag as the address carries it: no `W/`, no quotes; null when absent. */
function versionOf(etag: string | null): string | null {
  if (etag === null) {
    return null
  }
  const bare = etag.replace(/^W\//, '').replace(/^"(.*)"$/, '$1')
  return bare === '' ? null : bare
}

/**
 * Ask for the movie's first byte, never from or into the browser's cache. It
 * answers with the file's entity-tag, size and name, and proves the movie is
 * served. Rethrows `AbortError`.
 */
export async function probeMovie(eventId: string, signal: AbortSignal): Promise<MovieProbe> {
  const url = movieUrl(eventId, null)
  let response: Response
  try {
    response = await fetch(url, { headers: { Range: 'bytes=0-0' }, cache: 'no-store', signal })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }

  const version = versionOf(response.headers.get('ETag'))
  if ((response.status === 200 || response.status === 206) && version !== null) {
    // One byte asked for; a 200 would be the whole file, which is not read.
    response.body?.cancel().catch(() => undefined)
    const size =
      response.status === 206
        ? contentRangeSize(response.headers.get('Content-Range'))
        : lengthOf(response.headers.get('Content-Length'))
    return {
      kind: 'ok',
      file: { version, size, name: dispositionName(response.headers.get('Content-Disposition')) },
    }
  }
  if (response.status === 416) {
    return { kind: 'empty' }
  }
  if (PROBLEM_STATUSES.has(response.status)) {
    const body = await readJson(response)
    if (isProblem(body)) {
      return { kind: 'problem', problem: body }
    }
  }
  return unpublishedAnswer('GET', url, response)
}

/** A whole-file `Content-Length`, or null when absent or not a byte count. */
function lengthOf(value: string | null): number | null {
  return value !== null && /^\d+$/.test(value) ? Number(value) : null
}
