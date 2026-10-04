import { encodeEventId } from '../route.ts'
import { isProblem, readJson } from './http.ts'
import type { Problem } from './http.ts'
import type { paths } from './schema'

/**
 * The title-card preview (`POST /api/v1/events/{event_id}/title-card/preview`): the only module
 * that knows its URL and its statuses. The request body is checked against the generated
 * `paths`, so renaming a key in the service fails `tsc --noEmit`. A failure is a value by its
 * status; only an abort is thrown (the caller superseded the request).
 */

const PREVIEW_PATH = '/api/v1/events/{event_id}/title-card/preview' satisfies keyof paths

export type PreviewBody = NonNullable<
  paths[typeof PREVIEW_PATH]['post']['requestBody']
>['content']['application/json']

/** How a preview ended. */
export type PreviewResult =
  | { kind: 'image'; png: Blob }
  /** 400: the draft is refused, the detail names the field. */
  | { kind: 'refused'; problem: Problem }
  /** 404: no such event. */
  | { kind: 'gone'; problem: Problem }
  /** 422: a value over the preview's bounds (the service's validation message). */
  | { kind: 'bound'; message: string }
  /** 502: the preview could not be drawn (its cause is the service's words). */
  | { kind: 'failed'; problem: Problem }
  /** 503: busy; `retryAfter` is the seconds the service asked to wait, when it said. */
  | { kind: 'busy'; retryAfter: number | null; problem: Problem | null }
  | { kind: 'unreachable'; message: string }
  | { kind: 'unpublished'; message: string }

/** The address of an event's preview route. */
export function previewUrl(eventId: string): string {
  return PREVIEW_PATH.replace('{event_id}', () => encodeEventId(eventId))
}

/** FastAPI's 422 body: `{detail: [{loc, msg}]}`, reduced to the first message with its field. */
function boundMessage(body: unknown): string {
  const detail = (body as { detail?: unknown } | undefined)?.detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown; msg?: unknown }
    const where = Array.isArray(first.loc) ? first.loc.filter((part) => part !== 'body').join('.') : ''
    const msg = typeof first.msg === 'string' ? first.msg : 'a value is out of bounds'
    return where === '' ? msg : `${where}: ${msg}`
  }
  return typeof detail === 'string' ? detail : 'A value is out of the preview’s bounds.'
}

function retryAfterOf(response: Response): number | null {
  const raw = response.headers.get('Retry-After')
  if (raw === null) {
    return null
  }
  const seconds = Number(raw)
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null
}

/** Draw `body` for `eventId`. Rethrows `AbortError`. */
export async function previewCard(
  eventId: string,
  body: PreviewBody,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<PreviewResult> {
  const url = previewUrl(eventId)
  let response: Response
  try {
    response = await fetcher(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
      cache: 'no-store',
    })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }
  if (response.status === 200) {
    const type = response.headers.get('Content-Type') ?? ''
    if (!type.startsWith('image/png')) {
      return { kind: 'unpublished', message: `POST ${url} answered 200 with ${type || 'no type'}` }
    }
    try {
      return { kind: 'image', png: await response.blob() }
    } catch (error) {
      if (signal.aborted) {
        throw error
      }
      return { kind: 'unreachable', message: String(error) }
    }
  }
  const answer = await readJson(response)
  switch (response.status) {
    case 400:
      return isProblem(answer) ? { kind: 'refused', problem: answer } : unpublished(url, response)
    case 404:
      return isProblem(answer) ? { kind: 'gone', problem: answer } : unpublished(url, response)
    case 422:
      return { kind: 'bound', message: boundMessage(answer) }
    case 502:
      return isProblem(answer) ? { kind: 'failed', problem: answer } : unpublished(url, response)
    case 503:
      return {
        kind: 'busy',
        retryAfter: retryAfterOf(response),
        problem: isProblem(answer) ? answer : null,
      }
    default:
      return unpublished(url, response)
  }
}

function unpublished(url: string, response: Response): PreviewResult {
  return {
    kind: 'unpublished',
    message: `POST ${url} answered ${`${response.status} ${response.statusText}`.trimEnd()}`,
  }
}
