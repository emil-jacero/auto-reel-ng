import assert from 'node:assert/strict'
import { register } from 'node:module'
import { afterEach, before, describe, it } from 'node:test'

import { entityVersion } from './headers.ts'

/*
 * The clip's preview copy as the client addresses and probes it (D-21, `proxyUrl` and
 * `probeProxy`), run by `npm test`. `fetch` is a stand-in; the sources import each other
 * without file extensions, which a resolve hook adds for this test only, and `route.ts`
 * reads `window` when it loads, so the test gives it a bare one (as `thumbnail.test.ts`).
 */
type ClipMedia = typeof import('./clipMedia.ts')
let media: ClipMedia
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
  media = await import('./clipMedia.ts')
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

const probe = () => media.probeProxy('e', 'a.mp4', new AbortController().signal)
const problemBody = { title: 'Not Found', status: 404, detail: 'no preview copy of a.mp4' }

describe('proxyUrl', () => {
  it('encodes the event id per segment and the identity as the clip query, v only when given', () => {
    assert.equal(
      media.proxyUrl('2024/05 - Prov #1', { identity: 'a b#c.mp4' }, null),
      '/api/v1/events/2024/05%20-%20Prov%20%231/proxy?clip=a+b%23c.mp4',
    )
    assert.equal(
      media.proxyUrl('2024/e', { identity: 'sub/a.mp4' }, '1a2b-3c4d'),
      '/api/v1/events/2024/e/proxy?clip=sub%2Fa.mp4&v=1a2b-3c4d',
    )
  })
})

describe('entityVersion', () => {
  it('reads a strong and a weak tag alike, and nothing from an empty or absent one', () => {
    assert.equal(entityVersion('"abc"'), 'abc')
    assert.equal(entityVersion('W/"abc"'), 'abc')
    assert.equal(entityVersion('abc'), 'abc')
    assert.equal(entityVersion('""'), null)
    assert.equal(entityVersion(''), null)
    assert.equal(entityVersion(null), null)
  })
})

describe('probeProxy', () => {
  it('asks for the first byte of the unversioned address, never from the cache', async () => {
    const asked = serve(() => new Response('x', { status: 206, headers: { ETag: '"1f-2e"' } }))
    const answer = await probe()
    assert.deepEqual(answer, { kind: 'ok', version: '1f-2e' })
    assert.equal(asked.length, 1)
    assert.equal(asked[0].url, '/api/v1/events/e/proxy?clip=a.mp4')
    assert.deepEqual(asked[0].init?.headers, { Range: 'bytes=0-0' })
    assert.equal(asked[0].init?.cache, 'no-store')
  })

  it('reads a 200 with a tag as served too', async () => {
    serve(() => new Response('x', { status: 200, headers: { ETag: '"9"' } }))
    assert.deepEqual(await probe(), { kind: 'ok', version: '9' })
  })

  it('reads a 206 with no entity tag as an answer the service should not give', async () => {
    serve(() => new Response('x', { status: 206 }))
    const answer = await probe()
    assert.equal(answer.kind, 'unpublished')
  })

  it('maps a 404 problem body, a 416 and a rejected fetch to problem, empty and unreachable', async () => {
    serve(
      () =>
        new Response(JSON.stringify(problemBody), {
          status: 404,
          headers: { 'Content-Type': 'application/problem+json' },
        }),
    )
    assert.deepEqual(await probe(), { kind: 'problem', problem: problemBody })
    serve(() => new Response(null, { status: 416 }))
    assert.deepEqual(await probe(), { kind: 'empty' })
    globalThis.fetch = (async () => {
      throw new TypeError('network down')
    }) as typeof fetch
    const answer = await probe()
    assert.equal(answer.kind, 'unreachable')
  })

  it('reads a 404 that is not a problem body as unpublished', async () => {
    serve(() => new Response('<html>', { status: 404 }))
    assert.equal((await probe()).kind, 'unpublished')
  })

  it('rethrows an aborted request', async () => {
    const controller = new AbortController()
    globalThis.fetch = (async () => {
      controller.abort()
      throw new DOMException('aborted', 'AbortError')
    }) as typeof fetch
    await assert.rejects(media.probeProxy('e', 'a.mp4', controller.signal), { name: 'AbortError' })
  })
})
