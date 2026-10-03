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
