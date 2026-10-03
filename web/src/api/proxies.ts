import { encodeEventId } from '../route'
import type { Clip } from './event'
import { isProblem, readJson } from './http'
import type { Problem } from './http'
import type { JobOut } from './jobs'
import type { components, paths } from './schema'

/**
 * The event's proxies: the filmstrip sprite's address and the proxy job's enqueue. The
 * only module that knows `POST …/proxies` and its status codes. The proxy's own address
 * is `clipMedia.ts`'s `proxyUrl`; both carry the proxy file's entity tag as `v` (D-15).
 *
 * Aliases into the generated schema, never re-declared shapes (see `events.ts`).
 */

export type ProxiesFreshResult = components['schemas']['ProxiesFreshResult']
export type ClipProxy = NonNullable<Clip['proxy']>
export type ProxyState = components['schemas']['ProxyState']

const FILMSTRIP_PATH = '/api/v1/events/{event_id}/filmstrip' satisfies keyof paths
type FilmstripQuery = NonNullable<
  paths[typeof FILMSTRIP_PATH]['get']['parameters']['query']
>
const PROXIES_PATH = '/api/v1/events/{event_id}/proxies' satisfies keyof paths

/**
 * The clip's filmstrip sprite: the event id encoded per segment, the identity as the
 * `clip` query value and the proxy's entity tag as `v` (the service ignores it; it gives
 * a proxy made again a new address).
 */
export function filmstripUrl(
  eventId: string,
  clip: Pick<Clip, 'identity'>,
  version: string,
): string {
  const query: Record<string, string> = {
    clip: clip.identity,
    v: version,
  } satisfies FilmstripQuery
  const path = FILMSTRIP_PATH.replace('{event_id}', () => encodeEventId(eventId))
  return `${path}?${new URLSearchParams(query)}`
}

/** How an enqueue ended: one kind per answer `POST …/proxies` publishes. */
export type EnqueueProxiesResult =
  // 201: the proxy job was created
  | { kind: 'enqueued'; job: JobOut }
  // 200: every clip's proxy is ready, nothing was enqueued
  | { kind: 'ready'; fresh: ProxiesFreshResult }
  // 409 `active_job`: a proxy job for the event is already queued or running
  | { kind: 'active'; jobId: string; problem: Problem }
  // 404 (unknown event) or 502 (the folder or the proxy cache cannot be read)
  | { kind: 'problem'; problem: Problem }
  // 503 naming the database as the failing dependency: the job's creation was not confirmed
  | { kind: 'database'; problem: Problem }
  // no answer at all: fetch rejected (the message is the error)
  | { kind: 'unreachable'; message: string }
  // an answer whose status or body the route does not publish (the message names it)
  | { kind: 'unpublished'; message: string }

const PROBLEM_STATUSES = new Set([404, 502])

/**
 * Ask the service to prepare the event's proxies. A write, so not abortable: its answer
 * still matters after the caller leaves. A 503 is a `database` answer only when its
 * problem names the database; any other stays `unpublished`, never a guessed cause.
 */
export async function enqueueProxies(eventId: string): Promise<EnqueueProxiesResult> {
  const url = PROXIES_PATH.replace('{event_id}', () => encodeEventId(eventId))
  let response: Response
  try {
    response = await fetch(url, { method: 'POST' })
  } catch (error) {
    return { kind: 'unreachable', message: String(error) }
  }
  const body = await readJson(response)
  const isObject = typeof body === 'object' && body !== null
  if (response.status === 201 && isObject) {
    return { kind: 'enqueued', job: body as JobOut }
  }
  if (response.status === 200 && isObject) {
    return { kind: 'ready', fresh: body as ProxiesFreshResult }
  }
  if (response.status === 503 && isProblem(body) && body.check === 'database') {
    return { kind: 'database', problem: body }
  }
  if (response.status === 409 && isProblem(body)) {
    // A 409 means only what its conflict kind says, and the job id it promises.
    if (body.conflict === 'active_job' && typeof body.job_id === 'string') {
      return { kind: 'active', jobId: body.job_id, problem: body }
    }
  } else if (PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return {
    kind: 'unpublished',
    message: `POST ${url} answered ${response.status} ${response.statusText}`.trimEnd(),
  }
}
