import type { components } from './schema'

/** Response-reading helpers shared by the reads. */

export type Problem = components['schemas']['ProblemOut']

export function isProblem(body: unknown): body is Problem {
  if (typeof body !== 'object' || body === null) {
    return false
  }
  const fields = body as Record<string, unknown>
  return (
    typeof fields.title === 'string' &&
    typeof fields.status === 'number' &&
    typeof fields.detail === 'string'
  )
}

/** The body as JSON, or `undefined` when it is not JSON. Rethrows `AbortError`. */
export async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    return undefined
  }
}

/** A request with no usable answer: none at all, or one its route does not publish. */
export type Unanswered =
  // no answer at all: fetch rejected (the message is the error)
  | { kind: 'unreachable'; message: string }
  // an answer whose status or body the route does not publish (the message names it)
  | { kind: 'unpublished'; message: string }

/**
 * "GET /api/v1/events answered 500 Internal Server Error": what came back instead,
 * with the request's path as an operator reads it (an event's folder name, not
 * its percent-escapes).
 */
export function unpublishedAnswer(
  method: 'GET' | 'PUT',
  url: string,
  response: Response,
): Extract<Unanswered, { kind: 'unpublished' }> {
  const status = `${response.status} ${response.statusText}`.trimEnd()
  return { kind: 'unpublished', message: `${method} ${readablePath(url)} answered ${status}` }
}

/**
 * A request path with its escapes decoded (`decodeURI` keeps an escaped `/`, `?`
 * or `#` escaped), or as given when an escape is malformed.
 */
function readablePath(url: string): string {
  try {
    return decodeURI(url)
  } catch {
    return url
  }
}
