import assert from 'node:assert/strict'
import { register } from 'node:module'
import { afterEach, before, beforeEach, describe, it, mock } from 'node:test'

/*
 * The jobs store's connection rules (silence watchdog, reconnect), run by `npm test`
 * under Node's built-in runner. The store's sources import each other without file
 * extensions (the bundler resolves them), which Node does not; a resolve hook adds
 * them for this test only. `WebSocket` is a stand-in, timers are `mock.timers`.
 */
type Store = typeof import('./store.ts')
let store: Store

class FakeSocket {
  static all: FakeSocket[] = []
  closed = false
  private readonly listeners = new Map<string, Array<(event: unknown) => void>>()

  readonly url: string

  constructor(url: string) {
    this.url = url
    FakeSocket.all.push(this)
  }

  addEventListener(type: string, listener: (event: unknown) => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }

  /** A real socket reports its close later; delivering it at once is the strictest order. */
  close(): void {
    this.closed = true
    this.emit('close')
  }

  emit(type: string, event: unknown = {}): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event)
    }
  }

  frame(type: string): void {
    this.emit('message', { data: JSON.stringify({ type, jobs: [] }) })
  }
}

const SILENCE_MS = 40_000

before(async () => {
  register(
    'data:text/javascript,' +
      encodeURIComponent(`
        const tryNext = async (specifier, context, next, suffixes) => {
          for (const suffix of suffixes) {
            try {
              return await next(specifier + suffix, context)
            } catch (error) {
              if (error?.code !== 'ERR_MODULE_NOT_FOUND') throw error
            }
          }
          return next(specifier, context)
        }
        export function resolve(specifier, context, next) {
          if (specifier.startsWith('.') && !/\\.[a-z]+$/.test(specifier)) {
            return tryNext(specifier, context, next, ['.ts', '.tsx', '/index.ts'])
          }
          return next(specifier, context)
        }
      `),
  )
  Object.assign(globalThis, {
    window: globalThis,
    WebSocket: FakeSocket,
    // `route.ts` (imported for `eventHref`) reads the address and history when it loads.
    location: { protocol: 'http:', host: 'localhost:8080', hash: '' },
    addEventListener: () => {},
    removeEventListener: () => {},
    history: { state: { autoReelIndex: 0 }, replaceState: () => {} },
  })
  store = await import('./store.ts')
})

let release: () => void

beforeEach(() => {
  FakeSocket.all = []
  mock.timers.enable({ apis: ['setTimeout'] })
  // Full jitter at 0: a reconnect is due at once, so a test steps to it with `tick(0)`.
  mock.method(Math, 'random', () => 0)
  mock.method(console, 'warn', () => {})
  release = store.subscribe(() => {})
})

afterEach(() => {
  release()
  mock.timers.tick(0) // the deferred release runs `stop`
  mock.timers.reset()
  mock.restoreAll()
})

describe('the silence watchdog', () => {
  it('drops a socket that delivers no frame for 40 s and reconnects once', () => {
    const [first] = FakeSocket.all
    assert.equal(FakeSocket.all.length, 1)
    first.frame('snapshot')
    assert.equal(store.getState().connection, 'live')

    mock.timers.tick(SILENCE_MS - 1)
    assert.equal(store.getState().connection, 'live')
    assert.equal(first.closed, false)

    mock.timers.tick(1)
    assert.equal(store.getState().connection, 'reconnecting')
    assert.equal(first.closed, true, 'the dead socket was closed by the store')

    mock.timers.tick(0)
    assert.equal(FakeSocket.all.length, 2, 'one new socket')

    // The close the store's own `close()` caused, and one a gone peer delivers late, must
    // not schedule a second reconnect.
    first.emit('close')
    mock.timers.tick(0)
    assert.equal(FakeSocket.all.length, 2)
  })

  it('counts the first window from the socket creation, not from a first frame', () => {
    const [first] = FakeSocket.all
    mock.timers.tick(SILENCE_MS)
    assert.equal(store.getState().connection, 'reconnecting')
    assert.equal(first.closed, true)
  })

  it('is re-armed by each heartbeat, which changes nothing the store publishes', () => {
    const [first] = FakeSocket.all
    first.frame('snapshot')
    const before = store.getState()

    mock.timers.tick(30_000)
    first.frame('heartbeat')
    mock.timers.tick(30_000) // 60 s since the snapshot, 30 s since the heartbeat
    first.frame('heartbeat')
    mock.timers.tick(30_000)
    assert.equal(store.getState(), before, 'a heartbeat commits no state')
    assert.equal(store.getState().connection, 'live')
    assert.equal(first.closed, false)

    mock.timers.tick(10_000) // 40 s with no frame at all
    assert.equal(store.getState().connection, 'reconnecting')
    assert.equal(first.closed, true)
  })

  it('does not fire for a socket the store closed on a real close event', () => {
    const [first] = FakeSocket.all
    first.frame('snapshot')
    first.emit('close')
    assert.equal(store.getState().connection, 'reconnecting')
    mock.timers.tick(0)
    assert.equal(FakeSocket.all.length, 2)
    const [, second] = FakeSocket.all
    second.frame('snapshot')
    mock.timers.tick(SILENCE_MS - 1)
    assert.equal(first.closed, false, 'the old socket was not closed again')
    assert.equal(store.getState().connection, 'live')
  })
})

describe('how an end was learned', () => {
  const analysisJob = (id: string, status: string) => ({
    id,
    kind: 'analysis',
    event_dir: '2024/e',
    status,
    progress: status === 'done' ? 1 : 0.3,
    created_at: '2026-10-05T10:00:00Z',
    started_at: null,
    finished_at: null,
    cancel_requested: false,
    requeue_count: 0,
    worker_id: null,
    error: null,
  })
  const send = (socket: FakeSocket, type: string, jobs: unknown[]) =>
    socket.emit('message', { data: JSON.stringify({ type, jobs }) })
  const realFetch = globalThis.fetch

  afterEach(() => {
    globalThis.fetch = realFetch
  })

  it('marks an end read after a lost connection as reconciled, and a live delta’s as not', async () => {
    const [first] = FakeSocket.all
    send(first, 'snapshot', [analysisJob('rec-1', 'running'), analysisJob('live-1', 'running')])
    send(first, 'delta', [analysisJob('live-1', 'done')])
    assert.equal(store.getState().jobs.get('live-1')?.status, 'done')
    assert.equal(store.wasReconciled('live-1'), false)

    globalThis.fetch = (async () =>
      new Response(JSON.stringify(analysisJob('rec-1', 'done')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })) as typeof fetch
    first.close()
    mock.timers.tick(0)
    const second = FakeSocket.all[FakeSocket.all.length - 1]
    send(second, 'snapshot', [])
    // The read of the job the snapshot lacks answers on a later turn.
    for (let i = 0; i < 10 && store.getState().jobs.get('rec-1')?.status !== 'done'; i += 1) {
      await new Promise((resolve) => setImmediate(resolve))
    }
    assert.equal(store.getState().jobs.get('rec-1')?.status, 'done')
    assert.equal(store.wasReconciled('rec-1'), true)
    assert.equal(store.wasReconciled('live-1'), false)
  })
})
