import { isProblem, readJson, unpublishedAnswer } from './http'
import type { Problem, Unanswered } from './http'

/**
 * One byte of a media route: the response-to-kind table the movie's probe
 * (`movie.ts`) and a clip's check (`clipMedia.ts`) share, so the two players read
 * the service's answers alike (designs of `movie-player-screen` and
 * `clip-preview-screen`, "one-byte checks").
 *
 * - 200 or 206 that the caller can read → `served`, with what it read (the body is
 *   cancelled unread)
 * - 416 → `empty`: the file has no first byte
 * - 404 or 502 with a problem body → `problem`
 * - a rejected fetch → `unreachable`; any other answer → `unpublished`
 */
export type ByteAnswer<T> =
  | { kind: 'served'; file: T }
  | { kind: 'empty' }
  | { kind: 'problem'; problem: Problem }
  | Unanswered

// The failure statuses the media routes declare with a problem body (see the schema).
const PROBLEM_STATUSES = new Set([404, 502])

/**
 * A `GET` of `url` with `Range: bytes=0-0`, never from or into the browser's cache (no
 * `If-None-Match`, so never a 304). `read` takes from a 200 or 206 the facts its caller
 * needs, or null when they are not there (the movie requires its entity-tag): such an
 * answer reads as an unpublished one. Rethrows `AbortError`.
 */
export async function probeFirstByte<T>(
  url: string,
  signal: AbortSignal,
  read: (response: Response) => T | null,
): Promise<ByteAnswer<T>> {
  let response: Response
  try {
    response = await fetch(url, { headers: { Range: 'bytes=0-0' }, cache: 'no-store', signal })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }
  const file = response.status === 200 || response.status === 206 ? read(response) : null
  if (file !== null) {
    // One byte asked for; a 200 would be the whole file, which is not read.
    response.body?.cancel().catch(() => undefined)
    return { kind: 'served', file }
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
