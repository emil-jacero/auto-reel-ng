import { fetchJob, jobsSocketUrl } from '../api/jobs'
import type { JobOut, JobStatus, WsMessage, WsMessageType } from '../api/jobs'
import { markEventsChanged } from '../events/changes'
import { eventHref } from '../route'
import { toast } from '../ui/toast'
import { etaMs, nextSample } from './eta'
import type { Sample } from './eta'

/*
 * This tab's live view of the render jobs: one WebSocket to `WS /api/v1/ws/jobs`,
 * shared by the header, the event page and every list row through
 * `useSyncExternalStore` (D-8: "one WebSocket hook holding a Map<job_id, JobOut>
 * with reconnect backoff", no library).
 *
 * - The first subscriber opens the socket. The last one's release is deferred by
 *   a tick, so StrictMode's mount, cleanup, mount reuses one socket.
 * - Any close the store did not start itself reconnects after a full-jitter
 *   delay capped at 30 s; the attempt count resets only when a valid frame
 *   arrives, so a service that accepts and then closes backs off instead of
 *   spinning. `online` reconnects at once when no socket is open or connecting.
 * - A socket that delivers no frame for 40 s (counted from its creation and from
 *   each frame) is lost: a connection that died without a close can stay open to
 *   the browser for minutes. The store drops it itself and takes the same path.
 *   The service sends a `heartbeat` frame after 15 s of silence, which changes
 *   nothing on screen and only proves the connection alive.
 * - A snapshot replaces the active set. A job the store knew as active that the
 *   snapshot lacks ended while the socket was down: it is kept as last known and
 *   read once, so its real ending replaces it — never guessed, never shown as
 *   running forever. Ended jobs are final and are kept.
 * - A delta merges; an unchanged job keeps its object, so a row selecting it sees
 *   no change.
 *
 * Side effects of an ending (toasts, `markEventsChanged()`) run here, in the frame
 * and read handlers: once per change, never twice under StrictMode, and whether or
 * not a screen for that event is mounted.
 */

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting'

export type JobsState = {
  readonly connection: ConnectionStatus
  /** Every job this tab learned of, by id: the active ones and, as last known, the ended ones. */
  readonly jobs: ReadonlyMap<string, JobOut>
  /** Job id → milliseconds left, only for running jobs whose estimate is shown (`eta.ts`). */
  readonly eta: ReadonlyMap<string, number>
}

export type LoadOptions = {
  /** Read even if this id was read before. */
  force?: boolean
  /** A screen showed the job queued or running: an ended answer is a reconciled end. */
  knownActive?: boolean
}

// Whether a status is active (queued or running); the other statuses are final.
// A `Record` over the generated union, so a new status fails `tsc --noEmit` here.
const ACTIVE: Record<JobStatus, boolean> = {
  queued: true,
  running: true,
  done: false,
  failed: false,
  canceled: false,
}

// The frame types this client applies; a `Record`, so a new type fails `tsc` here.
const FRAME_TYPES: Record<WsMessageType, true> = { snapshot: true, delta: true, heartbeat: true }

const RETRY_BASE_MS = 500
const RETRY_CAP_MS = 30_000
// A socket must deliver a frame within this window; the service sends one at
// least every 15 s (`_HEARTBEAT_INTERVAL_S` in `api/ws.py`).
const SILENCE_MS = 40_000

/** Queued or running: not yet ended. */
export function isActive(status: JobStatus): boolean {
  return ACTIVE[status]
}

let state: JobsState = { connection: 'connecting', jobs: new Map(), eta: new Map() }
const listeners = new Set<() => void>()

let running = false
let socket: WebSocket | null = null
let attempt = 0
let retryTimer: number | undefined
let releaseTimer: number | undefined
let watchdog: number | undefined

/** Ids `load` has read; without `force` it never reads one again. */
const requested = new Set<string>()
/** Jobs this tab started or attached to → their event's name: a live end raises a toast. */
const tracked = new Map<string, string>()
/** Jobs whose end the operator was already told of. */
const announced = new Set<string>()
const samples = new Map<string, Sample>()

/**
 * Where an absorbed version came from: `live` from the socket or a read the
 * operator's own action caused; `reconciled` from a read of a job a screen or
 * the last snapshot still showed as active.
 */
type Source = 'live' | 'reconciled'

function notify(): void {
  for (const listener of [...listeners]) {
    listener()
  }
}

/** Subscribe to every change; the first subscriber opens the connection. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  if (releaseTimer !== undefined) {
    window.clearTimeout(releaseTimer)
    releaseTimer = undefined
  }
  start()
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      releaseTimer = window.setTimeout(stop, 0)
    }
  }
}

/** The state now: the same object until something changes. */
export function getState(): JobsState {
  return state
}

function start(): void {
  if (running) {
    return
  }
  running = true
  setConnection('connecting')
  window.addEventListener('online', onOnline)
  connect()
}

function stop(): void {
  releaseTimer = undefined
  if (!running || listeners.size > 0) {
    return
  }
  running = false
  window.removeEventListener('online', onOnline)
  window.clearTimeout(retryTimer)
  retryTimer = undefined
  window.clearTimeout(watchdog)
  watchdog = undefined
  const open = socket
  // Cleared first: the guard then drops this socket's close event, so nothing reconnects.
  socket = null
  open?.close()
  attempt = 0
}

function connect(): void {
  retryTimer = undefined
  const opened = new WebSocket(jobsSocketUrl())
  socket = opened
  armWatchdog(opened)
  opened.addEventListener('message', (event: MessageEvent) => {
    if (opened === socket) {
      onFrame(opened, event.data)
    }
  })
  opened.addEventListener('close', () => {
    if (opened !== socket) {
      return // closed by the store, or replaced by a newer socket
    }
    lost()
  })
  opened.addEventListener('error', () => {
    if (opened === socket) {
      opened.close()
    }
  })
}

/** The current socket is gone: say so and schedule the next attempt. */
function lost(): void {
  window.clearTimeout(watchdog)
  watchdog = undefined
  socket = null
  setConnection('reconnecting')
  // Full jitter: anywhere between now and the attempt's ceiling.
  const ceiling = Math.min(RETRY_CAP_MS, RETRY_BASE_MS * 2 ** attempt)
  attempt += 1
  retryTimer = window.setTimeout(connect, Math.random() * ceiling)
}

/** Give `opened` another `SILENCE_MS` to deliver a frame, then drop it as lost. */
function armWatchdog(opened: WebSocket): void {
  window.clearTimeout(watchdog)
  watchdog = window.setTimeout(() => {
    if (opened !== socket) {
      return
    }
    console.warn('jobs WebSocket: silent; reconnecting')
    // `lost` first: the guard then drops the dying socket's own close event, which a
    // peer that is gone may never deliver, or deliver late.
    lost()
    opened.close()
  }, SILENCE_MS)
}

function onOnline(): void {
  // A socket that is open or still connecting is kept: a tab never holds two.
  if (socket !== null) {
    return
  }
  window.clearTimeout(retryTimer)
  connect()
}

function setConnection(connection: ConnectionStatus): void {
  if (state.connection !== connection) {
    state = { ...state, connection }
    notify()
  }
}

function isJob(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const job = value as Record<string, unknown>
  return (
    typeof job.id === 'string' &&
    typeof job.event_dir === 'string' &&
    typeof job.status === 'string' &&
    Object.hasOwn(ACTIVE, job.status) &&
    typeof job.progress === 'number' &&
    typeof job.cancel_requested === 'boolean' &&
    typeof job.created_at === 'string'
  )
}

/** A frame as the published `WsMessage`, or null when it is not one. */
function parseFrame(data: unknown): WsMessage | null {
  if (typeof data !== 'string') {
    return null
  }
  let body: unknown
  try {
    body = JSON.parse(data)
  } catch {
    return null
  }
  if (typeof body !== 'object' || body === null) {
    return null
  }
  const { type, jobs } = body as { type?: unknown; jobs?: unknown }
  if (typeof type !== 'string' || !Object.hasOwn(FRAME_TYPES, type)) {
    return null
  }
  if (!Array.isArray(jobs) || !jobs.every(isJob)) {
    return null
  }
  return { type: type as WsMessageType, jobs: jobs as JobOut[] }
}

function onFrame(opened: WebSocket, data: unknown): void {
  const frame = parseFrame(data)
  if (frame === null) {
    // A protocol error, never half-applied. Closing runs the reconnect path, and
    // the backoff keeps growing: only a valid frame resets it.
    console.error('jobs WebSocket: malformed frame; reconnecting', data)
    opened.close()
    return
  }
  attempt = 0
  armWatchdog(opened)
  switch (frame.type) {
    case 'snapshot':
      applySnapshot(frame.jobs)
      break
    case 'delta':
      absorb(frame.jobs, 'live')
      break
    case 'heartbeat':
      break // proof of life only: no commit, no notify, nothing on screen changes
    default: {
      const unhandled: never = frame.type
      throw new Error(`unhandled frame type ${String(unhandled)}`)
    }
  }
}

function sameJob(a: JobOut, b: JobOut): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<keyof JobOut>
  for (const key of keys) {
    if (a[key] !== b[key]) {
      return false
    }
  }
  return true
}

/**
 * The version to hold: an ended job is never replaced by an active copy of it
 * (a frame read before the end can arrive after it), and an unchanged job keeps
 * its object.
 */
function keep(current: JobOut | undefined, incoming: JobOut): JobOut {
  if (current === undefined) {
    return incoming
  }
  if (!isActive(current.status) && isActive(incoming.status)) {
    return current
  }
  return sameJob(current, incoming) ? current : incoming
}

/** Publish `jobs`, sampling the estimate of every job whose version changed. */
function commit(
  connection: ConnectionStatus,
  jobs: ReadonlyMap<string, JobOut>,
  changed: readonly JobOut[],
): void {
  const now = performance.now()
  let eta: Map<string, number> | null = null
  for (const job of changed) {
    const sample = nextSample(samples.get(job.id), job, now)
    if (sample === undefined) {
      samples.delete(job.id)
    } else {
      samples.set(job.id, sample)
    }
    const left = sample === undefined ? null : etaMs(sample, job)
    if (left !== ((eta ?? state.eta).get(job.id) ?? null)) {
      eta ??= new Map(state.eta)
      if (left === null) {
        eta.delete(job.id)
      } else {
        eta.set(job.id, left)
      }
    }
  }
  state = { connection, jobs, eta: eta ?? state.eta }
  notify()
}

/**
 * The jobs a snapshot leaves the store with (pure): every job in it, every ended
 * job already known (ended states are final), and every job known as active that
 * the snapshot lacks — it ended while the socket was down, so it is kept as last
 * known and listed in `endedMeanwhile`, for a read to replace it with its ending.
 */
function reconcile(
  previous: ReadonlyMap<string, JobOut>,
  snapshot: readonly JobOut[],
): { jobs: Map<string, JobOut>; changed: JobOut[]; endedMeanwhile: string[] } {
  const jobs = new Map<string, JobOut>()
  const changed: JobOut[] = []
  for (const job of snapshot) {
    const held = keep(previous.get(job.id), job)
    jobs.set(job.id, held)
    if (held !== previous.get(job.id)) {
      changed.push(held)
    }
  }
  const endedMeanwhile: string[] = []
  for (const [id, job] of previous) {
    if (!jobs.has(id)) {
      jobs.set(id, job)
      if (isActive(job.status)) {
        endedMeanwhile.push(id)
      }
    }
  }
  return { jobs, changed, endedMeanwhile }
}

/** An ending a merge found: an ended version, and whether an active one came before it. */
type Ending = { job: JobOut; wasActive: boolean }

/**
 * `incoming` versions merged into `before` by id (pure): null when nothing
 * changed, else the new map, the changed jobs and the endings among them.
 */
function mergeVersions(
  before: ReadonlyMap<string, JobOut>,
  incoming: readonly JobOut[],
): { jobs: Map<string, JobOut>; changed: JobOut[]; endings: Ending[] } | null {
  let jobs: Map<string, JobOut> | null = null
  const changed: JobOut[] = []
  const endings: Ending[] = []
  for (const job of incoming) {
    const current = (jobs ?? before).get(job.id)
    const held = keep(current, job)
    if (held === current) {
      continue
    }
    jobs ??= new Map(before)
    jobs.set(job.id, held)
    changed.push(held)
    if (!isActive(held.status) && (current === undefined || isActive(current.status))) {
      endings.push({ job: held, wasActive: current !== undefined })
    }
  }
  return jobs === null ? null : { jobs, changed, endings }
}

function applySnapshot(snapshot: readonly JobOut[]): void {
  const { jobs, changed, endedMeanwhile } = reconcile(state.jobs, snapshot)
  commit('live', jobs, changed)
  for (const id of endedMeanwhile) {
    load(id, { force: true, knownActive: true })
  }
}

/** Merge versions of jobs from a delta or a read, then run the effects of their endings. */
function absorb(incoming: readonly JobOut[], source: Source): void {
  const merged = mergeVersions(state.jobs, incoming)
  if (merged === null) {
    return
  }
  commit(state.connection, merged.jobs, merged.changed)
  for (const { job, wasActive } of merged.endings) {
    onEnded(job, wasActive, source)
  }
}

/**
 * An ending the store learned of. Every `done` marks the events changed — live,
 * reconciled, or first seen already ended. A toast is raised only for a live end
 * of an active version this tab followed, once: a reconciled end, or an ended row
 * with no active version before it, has nothing live to announce.
 */
function onEnded(job: JobOut, wasActive: boolean, source: Source): void {
  if (job.status === 'done') {
    markEventsChanged()
  }
  const name = tracked.get(job.id)
  if (!wasActive || source !== 'live' || name === undefined || announced.has(job.id)) {
    return
  }
  announced.add(job.id)
  const options = { action: { label: 'Open', href: eventHref(job.event_dir) } }
  switch (job.status) {
    case 'done':
      toast.success(`Rendered ${name}`, options)
      break
    case 'failed':
      toast.error(`Render failed: ${name}`, options)
      break
    case 'canceled':
      toast.info(`Render canceled: ${name}`, options)
      break
    case 'queued':
    case 'running':
      break
    default: {
      const unhandled: never = job.status
      throw new Error(`unhandled job status ${String(unhandled)}`)
    }
  }
}

/** Drop a job the service no longer has (a 404); its id stays requested. */
function forget(jobId: string): void {
  if (!state.jobs.has(jobId)) {
    return
  }
  const jobs = new Map(state.jobs)
  jobs.delete(jobId)
  samples.delete(jobId)
  let eta = state.eta
  if (eta.has(jobId)) {
    const kept = new Map(eta)
    kept.delete(jobId)
    eta = kept
  }
  state = { ...state, jobs, eta }
  notify()
}

/** Adopt a job an answer carried (an enqueue's 201). */
export function merge(job: JobOut): void {
  absorb([job], 'live')
}

/**
 * A job this tab started or attached to: its live end raises a toast that names
 * the event `name` (`eventName`; the store knows only the event's id).
 */
export function track(jobId: string, name: string): void {
  tracked.set(jobId, name)
}

/**
 * Record that the operator was told how the job ended (a cancel's answer), so its
 * ending raises no second toast. False when the store had already told it.
 */
export function markAnnounced(jobId: string): boolean {
  if (announced.has(jobId)) {
    return false
  }
  announced.add(jobId)
  return true
}

/**
 * Read one job and merge the answer. Without `force`, an id read before is not
 * read again, so an effect can never loop on a job that keeps failing. A 404
 * drops the job; an unanswered read (including a 503 naming the database) keeps the
 * last known copy, retried only by a later forced load — never on a timer.
 */
export function load(jobId: string, options: LoadOptions = {}): void {
  if (requested.has(jobId) && options.force !== true) {
    return
  }
  requested.add(jobId)
  const source: Source = options.knownActive === true ? 'reconciled' : 'live'
  fetchJob(jobId)
    .then((result) => {
      switch (result.kind) {
        case 'ok':
          absorb([result.job], source)
          break
        case 'problem':
          forget(jobId)
          break
        case 'database':
        case 'unreachable':
        case 'unpublished':
          break
      }
    })
    .catch((error: unknown) => {
      console.error(`jobs: reading job ${jobId} failed`, error)
    })
}
