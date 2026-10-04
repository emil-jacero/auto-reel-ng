import { refusalOf } from './model.ts'
import type { CardField, PreviewRequest } from './model.ts'

/*
 * The live preview as a small state machine (`title-card-inspector`), pure: the client, the
 * timers and the image addresses are handed in, so `npm test` drives it with fakes. It waits for
 * a quiet moment before asking, cancels the request it supersedes, drops the answer to one that
 * was superseded, keeps the previous image on show while the next one loads, and says every
 * failure in words by its cause. It never shows an empty box between two images.
 */

/** What the controller needs of the service: one call, abortable, failures as values. */
export type PreviewAnswer =
  | { kind: 'image'; png: Blob }
  | { kind: 'refused'; detail: string }
  | { kind: 'gone'; detail: string }
  | { kind: 'bound'; message: string }
  | { kind: 'failed'; detail: string }
  | { kind: 'busy'; retryAfter: number | null }
  | { kind: 'unreachable' }
  | { kind: 'unpublished'; message: string }

export type PreviewDeps = {
  /** Draw `request`; rejects (any error) when `signal` aborts. */
  draw(request: PreviewRequest, signal: AbortSignal): Promise<PreviewAnswer>
  setTimer(run: () => void, ms: number): unknown
  clearTimer(handle: unknown): void
  makeUrl(png: Blob): string
  revokeUrl(url: string): void
}

/** The quiet time before a request is sent. */
export const DEBOUNCE_MS = 250
/** Seconds waited for a 503 that did not say. */
export const DEFAULT_RETRY_SECONDS = 2

export type PreviewState =
  /** Nothing asked yet. */
  | 'idle'
  /** An edit is waiting out the quiet time, or its request is in flight. */
  | 'updating'
  /** The service is busy; one retry is waiting. */
  | 'busy'
  /** The image shown is the draft's. */
  | 'ready'
  /** A field is over the preview's bound: nothing was sent. */
  | 'skipped'
  | 'error'

export type PreviewView = {
  state: PreviewState
  /** The image on show: the last one that loaded, kept through updating and errors. */
  url: string | null
  /** The failure or the busy note, in words. */
  message: string | null
  /** The card field a refusal names, for the field's own message. */
  field: CardField | null
}

const IDLE: PreviewView = { state: 'idle', url: null, message: null, field: null }

export class PreviewController {
  private view: PreviewView = IDLE
  private readonly listeners = new Set<() => void>()
  private timer: unknown = null
  private abort: AbortController | null = null
  /** Identifies the newest request; an answer for an older one is dropped. */
  private serial = 0
  private lastKey: string | null = null
  private disposed = false

  private readonly deps: PreviewDeps
  private readonly debounceMs: number

  // Plain fields, not parameter properties: `npm test` strips types and runs this as it is.
  constructor(deps: PreviewDeps, debounceMs: number = DEBOUNCE_MS) {
    this.deps = deps
    this.debounceMs = debounceMs
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  snapshot = (): PreviewView => this.view

  /**
   * Show the preview of `request`, or none (`null`: a field is over the bound). The same
   * request again changes nothing.
   */
  show(request: PreviewRequest | null): void {
    if (this.disposed) {
      return
    }
    const key = request === null ? null : JSON.stringify(request)
    if (key === this.lastKey && this.view.state !== 'idle') {
      return
    }
    this.lastKey = key
    this.cancel()
    this.serial += 1
    if (request === null) {
      this.set({ state: 'skipped', message: null, field: null })
      return
    }
    const mine = this.serial
    this.set({ state: 'updating', message: null, field: null })
    this.timer = this.deps.setTimer(() => {
      this.timer = null
      void this.send(request, mine, false)
    }, this.debounceMs)
  }

  dispose(): void {
    this.disposed = true
    this.cancel()
    this.serial += 1
    if (this.view.url !== null) {
      this.deps.revokeUrl(this.view.url)
    }
    this.view = IDLE
    this.listeners.clear()
  }

  private cancel(): void {
    if (this.timer !== null) {
      this.deps.clearTimer(this.timer)
      this.timer = null
    }
    this.abort?.abort()
    this.abort = null
  }

  private set(patch: Partial<PreviewView>): void {
    this.view = { ...this.view, ...patch }
    for (const listener of [...this.listeners]) {
      listener()
    }
  }

  private async send(request: PreviewRequest, mine: number, retried: boolean): Promise<void> {
    const controller = new AbortController()
    this.abort = controller
    let answer: PreviewAnswer
    try {
      answer = await this.deps.draw(request, controller.signal)
    } catch {
      // Aborted by a newer request, or the page left: not an answer.
      return
    }
    if (mine !== this.serial || controller.signal.aborted) {
      return
    }
    this.abort = null
    switch (answer.kind) {
      case 'image': {
        const old = this.view.url
        this.set({ state: 'ready', url: this.deps.makeUrl(answer.png), message: null, field: null })
        if (old !== null) {
          this.deps.revokeUrl(old)
        }
        return
      }
      case 'refused': {
        const refusal = refusalOf(answer.detail)
        this.set({ state: 'error', message: answer.detail, field: refusal.field })
        return
      }
      case 'gone':
        this.set({ state: 'error', message: answer.detail, field: null })
        return
      case 'bound':
        this.set({ state: 'error', message: answer.message, field: null })
        return
      case 'failed':
        this.set({
          state: 'error',
          message: `The preview could not be drawn: ${answer.detail}`,
          field: null,
        })
        return
      case 'busy': {
        if (retried) {
          this.set({
            state: 'error',
            message: 'The service is still busy, so the preview did not update. Edit again to retry.',
            field: null,
          })
          return
        }
        const seconds = answer.retryAfter ?? DEFAULT_RETRY_SECONDS
        this.set({
          state: 'busy',
          message: `The service is busy. Trying again in ${seconds} ${seconds === 1 ? 'second' : 'seconds'}.`,
          field: null,
        })
        this.timer = this.deps.setTimer(() => {
          this.timer = null
          if (mine === this.serial) {
            this.set({ state: 'updating', message: null })
            void this.send(request, mine, true)
          }
        }, seconds * 1000)
        return
      }
      case 'unreachable':
        this.set({ state: 'error', message: 'The service did not answer.', field: null })
        return
      case 'unpublished':
        this.set({ state: 'error', message: answer.message, field: null })
        return
    }
  }
}
