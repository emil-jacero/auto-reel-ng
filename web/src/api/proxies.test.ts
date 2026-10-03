import assert from 'node:assert/strict'
import { register } from 'node:module'
import { afterEach, before, describe, it } from 'node:test'

/*
 * The filmstrip's address and the proxy enqueue's answers (`api/proxies.ts`), run by
 * `npm test`. `fetch` is a stand-in; the sources import each other without file
 * extensions, which a resolve hook adds for this test only, and `route.ts` reads `window`
 * when it loads, so the test gives it a bare one (as `clipMedia.test.ts`).
 */
type Proxies = typeof import('./proxies.ts')
let proxies: Proxies
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
  proxies = await import('./proxies.ts')
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
const problem = (status: number, extra: Record<string, unknown> = {}) => ({
  title: 'Problem',
  status,
  detail: 'why',
  ...extra,
})

describe('filmstripUrl', () => {
  it('encodes the event id per segment, the identity as the clip query and the tag as v', () => {
    assert.equal(
      proxies.filmstripUrl('2024/05 - Prov, ö #1', { identity: 'a b,c ö.mp4' }, '1a2b-3c4d'),
      '/api/v1/events/2024/05%20-%20Prov%2C%20%C3%B6%20%231/filmstrip?clip=a+b%2Cc+%C3%B6.mp4&v=1a2b-3c4d',
    )
  })

  it('keeps an identity with & and # in the clip value, not in the query structure', () => {
    const url = proxies.filmstripUrl('e', { identity: 'x&v=1#y.mp4' }, 't')
    const query = new URL(url, 'http://h').searchParams
    assert.equal(query.get('clip'), 'x&v=1#y.mp4')
    assert.equal(query.get('v'), 't')
  })
})

describe('enqueueProxies', () => {
  it('POSTs to the event proxies route with the id encoded per segment and no body', async () => {
    const asked = serve(() => json(201, { id: 'j1', kind: 'proxy' }))
    await proxies.enqueueProxies('2024/05 - Prov')
    assert.equal(asked[0].url, '/api/v1/events/2024/05%20-%20Prov/proxies')
    assert.equal(asked[0].init?.method, 'POST')
    assert.equal(asked[0].init?.body, undefined)
  })

  it('answers 201 as enqueued, with the job', async () => {
    serve(() => json(201, { id: 'j1', kind: 'proxy', status: 'queued' }))
    const result = await proxies.enqueueProxies('e')
    assert.equal(result.kind, 'enqueued')
    assert.equal(result.kind === 'enqueued' && result.job.id, 'j1')
  })

  it('answers 200 as ready, with nothing enqueued', async () => {
    serve(() => json(200, { event_id: 'e', status: 'fresh', clip_count: 3 }))
    const result = await proxies.enqueueProxies('e')
    assert.equal(result.kind, 'ready')
    assert.equal(result.kind === 'ready' && result.fresh.clip_count, 3)
  })

  it('answers a 409 active_job as active, with the running job id', async () => {
    serve(() => json(409, problem(409, { conflict: 'active_job', job_id: 'j9' })))
    const result = await proxies.enqueueProxies('e')
    assert.equal(result.kind, 'active')
    assert.equal(result.kind === 'active' && result.jobId, 'j9')
  })

  it('leaves a 409 without its conflict kind or job id unpublished, never active', async () => {
    serve(() => json(409, problem(409)))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'unpublished')
    serve(() => json(409, problem(409, { conflict: 'active_job' })))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'unpublished')
    serve(() => json(409, problem(409, { conflict: 'missing_clips', missing: ['a'] })))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'unpublished')
  })

  it('answers 404 and 502 as problems', async () => {
    serve(() => json(404, problem(404)))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'problem')
    serve(() => json(502, problem(502)))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'problem')
  })

  it('answers a 503 naming the database as database, and any other 503 as unpublished', async () => {
    serve(() => json(503, problem(503, { check: 'database' })))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'database')
    serve(() => json(503, problem(503)))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'unpublished')
    serve(() => new Response('<html>bad gateway</html>', { status: 503 }))
    assert.equal((await proxies.enqueueProxies('e')).kind, 'unpublished')
  })

  it('answers a rejected fetch as unreachable and an unlisted status as unpublished', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('network down')
    }) as typeof fetch
    const down = await proxies.enqueueProxies('e')
    assert.equal(down.kind, 'unreachable')
    serve(() => json(500, problem(500)))
    const odd = await proxies.enqueueProxies('e')
    assert.equal(odd.kind, 'unpublished')
    assert.match(odd.kind === 'unpublished' ? odd.message : '', /POST .*proxies answered 500/)
  })
})
