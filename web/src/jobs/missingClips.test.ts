import assert from 'node:assert/strict'
import { register } from 'node:module'
import { afterEach, before, describe, it } from 'node:test'

/*
 * The client's reading of the `missing_clips` refusal of `POST /api/v1/jobs` and the way
 * it names the clips, run by `npm test`. `fetch` is a stand-in; the sources import each
 * other without file extensions, which a resolve hook adds for this test only.
 */
type Jobs = typeof import('../api/jobs.ts')
type ClipNames = typeof import('./clipNames.ts')
let jobs: Jobs
let clipNames: ClipNames
const realFetch = globalThis.fetch

before(async () => {
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
  jobs = await import('../api/jobs.ts')
  clipNames = await import('./clipNames.ts')
})

afterEach(() => {
  globalThis.fetch = realFetch
})

function answer409(body: Record<string, unknown>): void {
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        type: 'about:blank',
        title: 'Conflict',
        status: 409,
        detail: 'refused',
        ...body,
      }),
      { status: 409, headers: { 'Content-Type': 'application/problem+json' } },
    )) as typeof fetch
}

describe('enqueueJob on a missing_clips 409', () => {
  it('answers the missing identities', async () => {
    answer409({ conflict: 'missing_clips', missing: ['a.mp4', 'b.mp4'] })
    const result = await jobs.enqueueJob('2024/e', false)
    assert.equal(result.kind, 'missingClips')
    assert.deepEqual(result.kind === 'missingClips' && result.missing, ['a.mp4', 'b.mp4'])
  })

  it('is unpublished, never missingClips, when the list is empty', async () => {
    answer409({ conflict: 'missing_clips', missing: [] })
    assert.equal((await jobs.enqueueJob('2024/e', true)).kind, 'unpublished')
  })

  it('is unpublished when the list is absent or not all strings', async () => {
    answer409({ conflict: 'missing_clips' })
    assert.equal((await jobs.enqueueJob('2024/e', false)).kind, 'unpublished')
    answer409({ conflict: 'missing_clips', missing: ['a.mp4', 3] })
    assert.equal((await jobs.enqueueJob('2024/e', false)).kind, 'unpublished')
    answer409({ conflict: 'missing_clips', missing: 'a.mp4' })
    assert.equal((await jobs.enqueueJob('2024/e', false)).kind, 'unpublished')
  })
})

describe('missingClipNames', () => {
  const clips = ['a.mp4', 'b.mp4', 'c.mp4', 'd.mp4', 'e.mp4', 'f.mp4']

  it('names every clip by default', () => {
    assert.equal(clipNames.missingClipNames(clips.slice(0, 2)), 'a.mp4, b.mp4')
    assert.equal(clipNames.missingClipNames(clips), clips.join(', '))
  })

  it('names every clip up to the limit', () => {
    assert.equal(clipNames.missingClipNames(clips.slice(0, 3), 3), 'a.mp4, b.mp4, c.mp4')
  })

  it('names the one clip over the limit rather than "and 1 more"', () => {
    assert.equal(clipNames.missingClipNames(clips.slice(0, 4), 3), 'a.mp4, b.mp4, c.mp4, d.mp4')
  })

  it('counts the rest once two or more are over the limit', () => {
    assert.equal(clipNames.missingClipNames(clips.slice(0, 5), 3), 'a.mp4, b.mp4, c.mp4 and 2 more')
    assert.equal(clipNames.missingClipNames(clips, 3), 'a.mp4, b.mp4, c.mp4 and 3 more')
  })
})
