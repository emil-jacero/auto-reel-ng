/*
 * The cards' images on the Timeline (D-20, `timeline-plays-cards`): every card's preview is
 * fetched once when the Timeline opens, one request at a time in play order (the endpoint allows
 * two at once and answers 503 `Retry-After` beyond that), kept as object URLs keyed by the draft
 * card and style, and only an edited card is fetched again after the quiet time. Pure: the
 * request, the timer and the URL functions are passed in, so `npm test` runs it with stand-ins.
 * Nothing is guessed (Principle I): a card that cannot be drawn is said, not retried by itself.
 */

/** What one request came to, as the queue reads it. */
export type Drawn =
  | { kind: 'image'; png: Blob }
  /** 503: busy; `retryAfter` is the seconds the service asked for, when it said. */
  | { kind: 'busy'; retryAfter: number | null }
  /** Any other failure, in the service's words. */
  | { kind: 'failed'; message: string }

export type ImagesIo<Request> = {
  draw(request: Request, signal: AbortSignal): Promise<Drawn>
  setTimer(run: () => void, ms: number): unknown
  clearTimer(handle: unknown): void
  makeUrl(png: Blob): string
  revokeUrl(url: string): void
}

/** One card to have an image for, in play order. */
export type CardJob<Request> = {
  /** The chapter's saved name: the card's identity. */
  chapter: string
  request: Request
}

export type CardImage =
  /** Asked for (or waiting its turn), with no image yet. */
  | { state: 'pending'; url: string | null }
  | { state: 'ready'; url: string }
  /** Could not be drawn: the words, and the previous image if there was one. */
  | { state: 'failed'; url: string | null; message: string }

/** Seconds waited for a 503 that did not say, and the bounds of what is waited. */
export const DEFAULT_RETRY_SECONDS = 2
export const MIN_RETRY_SECONDS = 1
export const MAX_RETRY_SECONDS = 30
/** The tries a card gets against 503. */
export const TRIES = 3
/** The quiet time before an edited card is asked for again (the inspector's own). */
export const QUIET_MS = 250

/** The wait for a 503: its `Retry-After`, from 1 to 30 s. */
export function waitSeconds(retryAfter: number | null): number {
  const seconds = retryAfter ?? DEFAULT_RETRY_SECONDS
  return Math.min(MAX_RETRY_SECONDS, Math.max(MIN_RETRY_SECONDS, seconds))
}

/** The key of a card's request: the same body and style give the same image. */
export function imageKey(request: unknown): string {
  return JSON.stringify(request)
}

type Entry<Request> = {
  key: string
  request: Request
  url: string | null
  state: CardImage['state']
  message: string
  /** Waiting for the quiet time before it is queued. */
  quiet: unknown
}

export type CardImages<Request> = {
  /**
   * The cards the Timeline draws now, in play order. A card not seen before is queued at once, a
   * card whose request changed after the quiet time, a card no longer listed is let go.
   */
  sync(jobs: readonly CardJob<Request>[]): void
  /** The image of a chapter's card, or null when it is not listed. */
  get(chapter: string): CardImage | null
  /** Counts every change, for `useSyncExternalStore`. */
  version(): number
  /** The failures to say, once each: chapter and words. */
  failures(): readonly { chapter: string; message: string }[]
  subscribe(listener: () => void): () => void
  /** Let go: abort what is in flight, revoke every URL, ask for nothing more. */
  dispose(): void
}

export function createCardImages<Request>(io: ImagesIo<Request>): CardImages<Request> {
  const entries = new Map<string, Entry<Request>>()
  const queue: string[] = []
  const listeners = new Set<() => void>()
  let order: string[] = []
  let current: { chapter: string; abort: AbortController } | null = null
  let waiting: unknown = null
  let disposed = false
  let version = 0

  const emit = () => {
    version += 1
    for (const listener of [...listeners]) {
      listener()
    }
  }

  const release = (entry: Entry<Request>) => {
    if (entry.quiet !== null) {
      io.clearTimer(entry.quiet)
      entry.quiet = null
    }
    if (entry.url !== null) {
      io.revokeUrl(entry.url)
      entry.url = null
    }
  }

  function enqueue(chapter: string): void {
    if (!queue.includes(chapter)) {
      queue.push(chapter)
      // Play order, so the opening card is drawn first even when an edit queued a later one.
      queue.sort((a, b) => order.indexOf(a) - order.indexOf(b))
    }
    pump()
  }

  function pump(): void {
    if (disposed || current !== null || waiting !== null) {
      return
    }
    const chapter = queue.shift()
    if (chapter === undefined) {
      return
    }
    const entry = entries.get(chapter)
    if (entry === undefined) {
      pump()
      return
    }
    void run(chapter, entry, TRIES)
  }

  async function run(chapter: string, entry: Entry<Request>, tries: number): Promise<void> {
    const abort = new AbortController()
    current = { chapter, abort }
    const key = entry.key
    let drawn: Drawn
    try {
      drawn = await io.draw(entry.request, abort.signal)
    } catch (error) {
      current = null
      if (abort.signal.aborted) {
        pump()
        return
      }
      drawn = { kind: 'failed', message: String(error) }
    }
    current = null
    if (disposed || entries.get(chapter) !== entry || entry.key !== key) {
      // Superseded or let go while it was in flight: the answer is dropped.
      pump()
      return
    }
    if (drawn.kind === 'busy') {
      if (tries <= 1) {
        entry.state = 'failed'
        entry.message = 'The service was busy and did not draw this card.'
        emit()
        pump()
        return
      }
      waiting = io.setTimer(() => {
        waiting = null
        if (!disposed && entries.get(chapter) === entry && entry.key === key) {
          void run(chapter, entry, tries - 1)
        } else {
          pump()
        }
      }, waitSeconds(drawn.retryAfter) * 1000)
      return
    }
    if (drawn.kind === 'failed') {
      entry.state = 'failed'
      entry.message = drawn.message
      emit()
      pump()
      return
    }
    const url = io.makeUrl(drawn.png)
    if (entry.url !== null) {
      io.revokeUrl(entry.url)
    }
    entry.url = url
    entry.state = 'ready'
    entry.message = ''
    emit()
    pump()
  }

  return {
    sync(jobs) {
      if (disposed) {
        return
      }
      order = jobs.map((job) => job.chapter)
      const listed = new Set(order)
      let changed = false
      for (const [chapter, entry] of [...entries]) {
        if (!listed.has(chapter)) {
          release(entry)
          entries.delete(chapter)
          const at = queue.indexOf(chapter)
          if (at !== -1) {
            queue.splice(at, 1)
          }
          if (current?.chapter === chapter) {
            current.abort.abort()
          }
          changed = true
        }
      }
      for (const job of jobs) {
        const key = imageKey(job.request)
        const entry = entries.get(job.chapter)
        if (entry === undefined) {
          entries.set(job.chapter, {
            key,
            request: job.request,
            url: null,
            state: 'pending',
            message: '',
            quiet: null,
          })
          changed = true
          enqueue(job.chapter)
        } else if (entry.key !== key) {
          // An edit: only this card is asked for again, after the quiet time; the old image stays until the new one arrives.
          entry.key = key
          entry.request = job.request
          entry.state = 'pending'
          entry.message = ''
          if (entry.quiet !== null) {
            io.clearTimer(entry.quiet)
          }
          const chapter = job.chapter
          entry.quiet = io.setTimer(() => {
            entry.quiet = null
            if (current?.chapter === chapter) {
              current.abort.abort()
            }
            enqueue(chapter)
          }, QUIET_MS)
          changed = true
        }
      }
      if (changed) {
        emit()
      }
    },
    get(chapter) {
      const entry = entries.get(chapter)
      if (entry === undefined) {
        return null
      }
      return entry.state === 'ready'
        ? { state: 'ready', url: entry.url as string }
        : entry.state === 'failed'
          ? { state: 'failed', url: entry.url, message: entry.message }
          : { state: 'pending', url: entry.url }
    },
    failures() {
      const out: { chapter: string; message: string }[] = []
      for (const chapter of order) {
        const entry = entries.get(chapter)
        if (entry !== undefined && entry.state === 'failed') {
          out.push({ chapter, message: entry.message })
        }
      }
      return out
    },
    version: () => version,
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    dispose() {
      disposed = true
      current?.abort.abort()
      if (waiting !== null) {
        io.clearTimer(waiting)
        waiting = null
      }
      for (const entry of entries.values()) {
        release(entry)
      }
      entries.clear()
      queue.length = 0
      listeners.clear()
    },
  }
}
