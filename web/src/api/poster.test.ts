import assert from 'node:assert/strict'
import { register } from 'node:module'
import { before, describe, it } from 'node:test'

/* `route.ts` reads `window` when it loads and the sources import each other without file
 * extensions: the same stand-ins as `thumbnail.test.ts` give. */
type Poster = typeof import('./poster.ts')
let poster: Poster

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
  poster = await import('./poster.ts')
})

describe('the poster address', () => {
  it('encodes each segment of the event id and adds no query without a version', () => {
    assert.equal(
      poster.posterUrl('2024/2024-07-04 - Kalas åäö'),
      '/api/v1/events/2024/2024-07-04%20-%20Kalas%20%C3%A5%C3%A4%C3%B6/poster.jpg',
    )
  })

  it('carries the version as v', () => {
    assert.equal(
      poster.posterUrl('2024/Kalas', 'event:a b.mp4@1.5'),
      '/api/v1/events/2024/Kalas/poster.jpg?v=event%3Aa+b.mp4%401.5',
    )
  })

  it('versions by source, clip and time', () => {
    assert.equal(poster.posterVersion(null), null)
    assert.equal(poster.posterVersion({ clip: 'a.mp4', at: null, source: 'default' }), 'default:a.mp4@')
    assert.equal(poster.posterVersion({ clip: 'a.mp4', at: 2.5, source: 'event' }), 'event:a.mp4@2.5')
  })
})
