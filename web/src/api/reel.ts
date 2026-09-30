import { encodeEventId } from '../route'
import { isProblem, readJson } from './http'
import type { Problem } from './http'
import type { components } from './schema'

/**
 * The editorial document's read and write: the only module that knows their
 * URL, headers and status codes.
 *
 * Aliases into the generated schema, never re-declared shapes (see `events.ts`).
 * The read's `ETag` is kept verbatim and sent back as the write's `If-Match`, so
 * a write never lands on a state its caller did not read.
 */

export type ReelDocument = components['schemas']['EditorialDocumentBody-Output']
export type ReelWriteBody = components['schemas']['EditorialDocumentBody-Input']
export type ReelWriteResult = components['schemas']['EditorialWriteResult']

/** How a read ended; expected failures are values, as in `fetchEvent`. */
export type ReelReadResult =
  | { kind: 'ok'; document: ReelDocument; etag: string }
  // 404/502 in the published ProblemOut shape
  | { kind: 'problem'; problem: Problem }
  // fetch rejected, or a status, body or header that carries no published shape
  | { kind: 'unreachable'; message: string }

/** How a write ended. */
export type ReelSaveResult =
  | { kind: 'saved'; result: ReelWriteResult }
  // 400/404/412/502 in the published ProblemOut shape
  | { kind: 'problem'; problem: Problem }
  // fetch rejected, or a status or body that carries no published shape (a 422 too)
  | { kind: 'unreachable'; message: string }

// The failure statuses the service declares for each (see the schema).
const READ_PROBLEM_STATUSES = new Set([404, 502])
const WRITE_PROBLEM_STATUSES = new Set([400, 404, 412, 502])

function reelUrl(eventId: string): string {
  return `/api/v1/events/${encodeEventId(eventId)}/reel`
}

/** A status or body outside the published answers, read or write alike. */
function unexpected(
  method: 'GET' | 'PUT',
  url: string,
  response: Response,
): Extract<ReelReadResult, { kind: 'unreachable' }> {
  return {
    kind: 'unreachable',
    message: `${method} ${url} answered ${response.status} ${response.statusText}`.trimEnd(),
  }
}

/**
 * Read the event's `reel.yaml` as authored (the empty document when it has
 * none) and its entity tag. Never from a cache: the tag must be the file's
 * current state. Rethrows `AbortError`.
 */
export async function fetchReel(eventId: string, signal: AbortSignal): Promise<ReelReadResult> {
  const url = reelUrl(eventId)
  let response: Response
  try {
    response = await fetch(url, { signal, cache: 'no-store' })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  if (response.status === 200 && typeof body === 'object' && body !== null) {
    const etag = response.headers.get('ETag')
    // Fail loud: without the tag a later write could only be unconditional.
    if (etag === null) {
      return { kind: 'unreachable', message: `GET ${url} answered 200 without an ETag` }
    }
    return { kind: 'ok', document: body as ReelDocument, etag }
  }
  if (READ_PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return unexpected('GET', url, response)
}

/**
 * Write the complete desired document, on condition that the event's state is
 * still the one tagged `ifMatch`. Not abortable: a sent write cannot be recalled.
 */
export async function saveReel(
  eventId: string,
  body: ReelWriteBody,
  ifMatch: string,
): Promise<ReelSaveResult> {
  const url = reelUrl(eventId)
  let response: Response
  try {
    response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': ifMatch },
      body: JSON.stringify(body),
    })
  } catch (error) {
    return { kind: 'unreachable', message: String(error) }
  }

  const answer = await readJson(response)
  if (response.status === 200 && typeof answer === 'object' && answer !== null) {
    return { kind: 'saved', result: answer as ReelWriteResult }
  }
  if (WRITE_PROBLEM_STATUSES.has(response.status) && isProblem(answer)) {
    return { kind: 'problem', problem: answer }
  }
  return unexpected('PUT', url, response)
}
