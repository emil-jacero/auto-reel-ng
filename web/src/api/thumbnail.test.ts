import assert from 'node:assert/strict'
import { register } from 'node:module'
import { afterEach, before, describe, it } from 'node:test'

/*
 * How the client reads why a thumbnail failed (`readFailedThumbnail`), run by `npm test`:
 * a clip's own failure, the service's, or neither. `fetch` is a stand-in; the sources import
 * each other without file extensions, which a resolve hook adds for this test only, and
 * `route.ts` reads `window` when it loads, so the test gives it a bare one.
 */
type Thumbnail = typeof import('./thumbnail.ts')
let thumbnail: Thumbnail
const realFetch = globalThis.fetch
const URL_OF_CLIP = '/api/v1/events/e/thumbnail?clip=a.mp4'

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
  thumbnail = await import('./thumbnail.ts')
})

afterEach(() => {
  globalThis.fetch = realFetch
})

function answer(status: number, body: Record<string, unknown> | string | null): void {
  globalThis.fetch = (async () =>
    new Response(typeof body === 'string' || body === null ? body : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/problem+json' },
    })) as typeof fetch
}

function problem(extra: Record<string, unknown>): Record<string, unknown> {
  return { title: 'Bad Gateway', status: 502, detail: 'could not', ...extra }
}

const read = () => thumbnail.readFailedThumbnail(URL_OF_CLIP, new AbortController().signal)

describe('readFailedThumbnail', () => {
  it('asks again for the same address, uncached', async () => {
    let asked: { url: unknown; cache: unknown; priority: unknown } | null = null
    globalThis.fetch = (async (url: unknown, init?: RequestInit) => {
      asked = { url, cache: init?.cache, priority: init?.priority }
      return new Response(null, { status: 404 })
    }) as typeof fetch
    await read()
    assert.deepEqual(asked, { url: URL_OF_CLIP, cache: 'no-store', priority: 'low' })
  })

  it('reads a 502 with the thumbnail failure kind as the clip’s own', async () => {
    answer(502, problem({ thumbnail_failure: 'thumbnail_failed' }))
    assert.deepEqual(await read(), { kind: 'clip' })
  })

  it('reads a 502 with no thumbnail kind and no event failure as the service’s', async () => {
    answer(502, problem({}))
    assert.deepEqual(await read(), { kind: 'service' })
  })

  it('reads a 502 that says the event could not be read as neither', async () => {
    answer(502, problem({ failure: 'unusable_metadata' }))
    assert.deepEqual(await read(), { kind: 'unknown' })
  })

  it('reads every other answer as unknown', async () => {
    answer(404, problem({ status: 404 }))
    assert.deepEqual(await read(), { kind: 'unknown' })
    answer(503, problem({ status: 503 }))
    assert.deepEqual(await read(), { kind: 'unknown' })
    answer(200, null)
    assert.deepEqual(await read(), { kind: 'unknown' })
  })

  it('reads a 502 that is not a problem body as unknown', async () => {
    answer(502, '<html>Bad Gateway</html>')
    assert.deepEqual(await read(), { kind: 'unknown' })
    answer(502, { message: 'no problem fields' })
    assert.deepEqual(await read(), { kind: 'unknown' })
  })

  it('reads no answer at all as unknown, but rethrows an abort', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('network down')
    }) as typeof fetch
    assert.deepEqual(await read(), { kind: 'unknown' })

    const controller = new AbortController()
    globalThis.fetch = (async () => {
      controller.abort()
      throw new DOMException('aborted', 'AbortError')
    }) as typeof fetch
    await assert.rejects(thumbnail.readFailedThumbnail(URL_OF_CLIP, controller.signal), {
      name: 'AbortError',
    })
  })
})
