import assert from 'node:assert/strict'
import { register } from 'node:module'
import { afterEach, before, describe, it } from 'node:test'

/*
 * The analysis read and its answers (`api/analysis.ts`), run by `npm test`. `fetch` is a
 * stand-in; the sources import each other without file extensions, which a resolve hook
 * adds for this test only, and `route.ts` reads `window` when it loads, so the test gives
 * it a bare one (as `proxies.test.ts`).
 */
type Analysis = typeof import('./analysis.ts')
let analysis: Analysis
const realFetch = globalThis.fetch

before(async () => {
  Object.assign(globalThis, {
    window: { location: { hash: '' }, history: { state: {}, replaceState: () => undefined } },
  })
  register(
    'data:text/javascript,' +
      encodeURIComponent(`
        export async function resolve(specifier, context, next) {
          if (specifier.startsWith('.') && !/\\.[a-z]+$/.test(specifier)) {
            try {
              return await next(specifier + '.ts', context)
            } catch (error) {
              if (error?.code !== 'ERR_MODULE_NOT_FOUND') throw error
            }
          }
          return next(specifier, context)
        }
      `),
  )
  analysis = await import('./analysis.ts')
})

afterEach(() => {
  globalThis.fetch = realFetch
})

type Asked = { url: unknown; init: RequestInit | undefined }

/** `fetch` answers `make()`; the requests it saw are collected. */
function serve(make: () => Response): Asked[] {
  const asked: Asked[] = []
  globalThis.fetch = (async (url: unknown, init?: RequestInit) => {
    asked.push({ url, init })
    return make()
  }) as typeof fetch
  return asked
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const problem = (status: number) => ({ title: 'Problem', status, detail: 'why' })
const read = (eventId = '2024/e') => analysis.fetchAnalysis(eventId, new AbortController().signal)

describe('fetchAnalysis', () => {
  it('returns the segments of an analysed event as read', async () => {
    const body = {
      analyzed: true,
      segments: {
        'a.mp4': [{ start: 0, end: 3.2, kind: 'black', confidence: 1 }],
        'b.mp4': [],
      },
    }
    serve(() => json(200, body))
    assert.deepEqual(await read(), { kind: 'ok', analysis: body })
  })

  it('returns an event that was never analysed as it came', async () => {
    serve(() => json(200, { analyzed: false, segments: {} }))
    assert.deepEqual(await read(), { kind: 'ok', analysis: { analyzed: false, segments: {} } })
  })

  it('keeps a clip analysed with nothing found (an empty list) apart from one with no key', async () => {
    serve(() => json(200, { analyzed: true, segments: { 'a.mp4': [] } }))
    const result = await read()
    assert.equal(result.kind, 'ok')
    if (result.kind === 'ok') {
      assert.deepEqual(result.analysis.segments['a.mp4'], [])
      assert.equal('b.mp4' in result.analysis.segments, false)
    }
  })

  it('asks for the event’s analysis, each segment of its id encoded, never from the cache', async () => {
    const asked = serve(() => json(200, { analyzed: false, segments: {} }))
    await read('2024/Sommar på Öland')
    assert.equal(asked.length, 1)
    assert.equal(asked[0].url, '/api/v1/events/2024/Sommar%20p%C3%A5%20%C3%96land/analysis')
    assert.equal(asked[0].init?.cache, 'no-store')
    assert.equal(asked[0].init?.method, undefined) // a GET: it changes nothing
  })

  it('reads a 404 and a 502 problem body as a problem', async () => {
    serve(() => json(404, problem(404)))
    assert.deepEqual(await read(), { kind: 'problem', problem: problem(404) })
    serve(() => json(502, problem(502)))
    assert.deepEqual(await read(), { kind: 'problem', problem: problem(502) })
  })

  it('reads the job store’s 503 problem body as a problem', async () => {
    const down = { ...problem(503), check: 'database' }
    serve(() => json(503, down))
    assert.deepEqual(await read(), { kind: 'problem', problem: down })
  })

  it('names the request when the answer is a status the route does not publish', async () => {
    serve(() => new Response('boom', { status: 500, statusText: 'Internal Server Error' }))
    const result = await read('2024/Sommar på Öland')
    assert.deepEqual(result, {
      kind: 'unpublished',
      message: 'GET /api/v1/events/2024/Sommar på Öland/analysis answered 500 Internal Server Error',
    })
  })

  it('reads a 502 that is not a problem body as unpublished', async () => {
    serve(() => new Response('<html>Bad Gateway</html>', { status: 502 }))
    assert.equal((await read()).kind, 'unpublished')
  })

  it('reads no answer at all as unreachable', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('Failed to fetch')
    }) as typeof fetch
    assert.deepEqual(await read(), { kind: 'unreachable', message: 'TypeError: Failed to fetch' })
  })

  it('rethrows an aborted request', async () => {
    const controller = new AbortController()
    globalThis.fetch = (async () => {
      controller.abort()
      throw new DOMException('aborted', 'AbortError')
    }) as typeof fetch
    await assert.rejects(analysis.fetchAnalysis('e', controller.signal), { name: 'AbortError' })
  })
})

const enqueue = (eventId = '2024/e', force = true) => analysis.enqueueAnalysis(eventId, { force })

describe('enqueueAnalysis', () => {
  it('POSTs {"force":true} to the event analysis route, each id segment encoded, unabortable', async () => {
    const asked = serve(() => json(201, { id: 'j1', kind: 'analysis' }))
    await enqueue('2024/Sommar på Öland')
    assert.equal(asked.length, 1)
    assert.equal(asked[0].url, '/api/v1/events/2024/Sommar%20p%C3%A5%20%C3%96land/analysis')
    assert.equal(asked[0].init?.method, 'POST')
    assert.equal(asked[0].init?.body, '{"force":true}')
    assert.equal(new Headers(asked[0].init?.headers).get('Content-Type'), 'application/json')
    assert.equal(asked[0].init?.signal, undefined)
  })

  it('sends {"force":false} for an unforced press', async () => {
    const asked = serve(() => json(201, { id: 'j1', kind: 'analysis' }))
    await enqueue('e', false)
    assert.equal(asked[0].init?.body, '{"force":false}')
  })

  it('reads 201 as the queued job', async () => {
    const job = { id: 'j1', kind: 'analysis', status: 'queued' }
    serve(() => json(201, job))
    assert.deepEqual(await enqueue(), { kind: 'enqueued', job })
  })

  it('reads 200 fresh as nothing to analyze', async () => {
    const fresh = { event_id: '2024/e', status: 'fresh', clip_count: 3, failed_count: 0 }
    serve(() => json(200, fresh))
    assert.deepEqual(await enqueue(), { kind: 'fresh', fresh })
  })

  it('reads 409 active_job as the active job, with whether it is forced', async () => {
    const body = problem(409)
    serve(() => json(409, { ...body, conflict: 'active_job', job_id: 'j9', forced: false }))
    const result = await enqueue()
    assert.equal(result.kind, 'active')
    if (result.kind === 'active') {
      assert.equal(result.jobId, 'j9')
      assert.equal(result.forced, false)
    }
    serve(() => json(409, { ...body, conflict: 'active_job', job_id: 'j9' }))
    const unknown = await enqueue()
    assert.equal(unknown.kind === 'active' && unknown.forced, null)
  })

  it('reads a 409 without the active_job kind or its job id as unpublished, never guessed', async () => {
    serve(() => json(409, { ...problem(409), conflict: 'output_collision' }))
    assert.equal((await enqueue()).kind, 'unpublished')
    serve(() => json(409, { ...problem(409), conflict: 'active_job' }))
    assert.equal((await enqueue()).kind, 'unpublished')
  })

  it('reads 404 and 502 problems as problems', async () => {
    serve(() => json(404, problem(404)))
    assert.deepEqual(await enqueue(), { kind: 'problem', problem: problem(404) })
    serve(() => json(502, problem(502)))
    assert.deepEqual(await enqueue(), { kind: 'problem', problem: problem(502) })
  })

  it('reads a 503 as the database only when the problem names it', async () => {
    const down = { ...problem(503), check: 'database' }
    serve(() => json(503, down))
    assert.deepEqual(await enqueue(), { kind: 'database', problem: down })
    serve(() => json(503, problem(503)))
    assert.equal((await enqueue()).kind, 'unpublished')
  })

  it('names the request when the status is one the route does not publish', async () => {
    serve(() => new Response('boom', { status: 500, statusText: 'Internal Server Error' }))
    assert.deepEqual(await enqueue('2024/Sommar på Öland'), {
      kind: 'unpublished',
      message: 'POST /api/v1/events/2024/Sommar på Öland/analysis answered 500 Internal Server Error',
    })
  })

  it('reads no answer at all as unreachable', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('Failed to fetch')
    }) as typeof fetch
    assert.deepEqual(await enqueue(), { kind: 'unreachable', message: 'TypeError: Failed to fetch' })
  })
})

describe('analyzeAll', () => {
  const counts = { queued: 12, fresh: 3, active: 1, unreadable: [] }

  it('POSTs to /api/v1/analysis with no body, unabortable', async () => {
    const asked = serve(() => json(200, counts))
    await analysis.analyzeAll()
    assert.equal(asked.length, 1)
    assert.equal(asked[0].url, '/api/v1/analysis')
    assert.equal(asked[0].init?.method, 'POST')
    assert.equal(asked[0].init?.body, undefined)
    assert.equal(asked[0].init?.signal, undefined)
  })

  it('reads 200 as the counts', async () => {
    const unreadable = [{ event_id: '2024/x', detail: 'Permission denied' }]
    serve(() => json(200, { ...counts, unreadable }))
    assert.deepEqual(await analysis.analyzeAll(), {
      kind: 'counted',
      result: { ...counts, unreadable },
    })
  })

  it('reads a 200 without the counts as unpublished', async () => {
    serve(() => json(200, { queued: 1 }))
    assert.equal((await analysis.analyzeAll()).kind, 'unpublished')
  })

  it('reads 502 as a problem and a 503 naming the database as the database', async () => {
    serve(() => json(502, problem(502)))
    assert.deepEqual(await analysis.analyzeAll(), { kind: 'problem', problem: problem(502) })
    const down = { ...problem(503), check: 'database' }
    serve(() => json(503, down))
    assert.deepEqual(await analysis.analyzeAll(), { kind: 'database', problem: down })
    serve(() => json(503, problem(503)))
    assert.equal((await analysis.analyzeAll()).kind, 'unpublished')
  })

  it('reads no answer as unreachable and a 404 as unpublished', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('Failed to fetch')
    }) as typeof fetch
    assert.equal((await analysis.analyzeAll()).kind, 'unreachable')
    serve(() => json(404, problem(404)))
    assert.deepEqual(await analysis.analyzeAll(), {
      kind: 'unpublished',
      message: 'POST /api/v1/analysis answered 404',
    })
  })
})
