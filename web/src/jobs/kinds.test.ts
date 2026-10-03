import assert from 'node:assert/strict'
import { register } from 'node:module'
import { before, describe, it } from 'node:test'

import type { JobOut } from '../api/jobs'

/*
 * The store holds jobs of every kind; the screens about renders must not see a proxy job
 * (`kinds.ts`), run by `npm test`. The sources import each other without file extensions,
 * which a resolve hook adds for this test only.
 */
type Kinds = typeof import('./kinds.ts')
let kinds: Kinds

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
  kinds = await import('./kinds.ts')
})

const EVENT = '2024/Blandat'

function job(id: string, patch: Partial<JobOut> = {}): JobOut {
  return {
    id,
    kind: 'render',
    event_dir: EVENT,
    status: 'running',
    progress: 0.4,
    created_at: '2026-10-02T10:00:00Z',
    started_at: '2026-10-02T10:01:00Z',
    finished_at: null,
    cancel_requested: false,
    requeue_count: 0,
    worker_id: 'worker-1',
    error: null,
    ...patch,
  } as JobOut
}

describe('the newest render per event', () => {
  it('is not replaced by a newer proxy job of the same event', () => {
    const render = job('render', { status: 'failed', progress: 0.3 })
    const proxy = job('proxy', { kind: 'proxy', created_at: '2026-10-02T10:05:00Z' })
    const index = kinds.newestRenderByEvent([render, proxy])
    assert.equal(index.get(EVENT)?.id, 'render')
    assert.equal(index.get(EVENT)?.status, 'failed')
  })

  it('holds nothing for an event whose only job is a proxy job', () => {
    const index = kinds.newestRenderByEvent([job('proxy', { kind: 'proxy' })])
    assert.equal(index.has(EVENT), false)
  })

  it('still picks the newer of two renders, in either order', () => {
    const older = job('older', { status: 'done', created_at: '2026-10-02T09:00:00Z' })
    const newer = job('newer', { created_at: '2026-10-02T10:00:00Z' })
    assert.equal(kinds.newestRenderByEvent([older, newer]).get(EVENT)?.id, 'newer')
    assert.equal(kinds.newestRenderByEvent([newer, older]).get(EVENT)?.id, 'newer')
  })

  it('skips a kind this build does not know', () => {
    const future = job('future', { kind: 'future' as JobOut['kind'] })
    assert.equal(kinds.newestRenderByEvent([future]).size, 0)
  })
})

describe('the header count', () => {
  it('counts renders that run and wait, and no proxy job', () => {
    const counted = kinds.countRenders([
      job('a'),
      job('b', { status: 'queued' }),
      job('c', { status: 'done' }),
      job('p1', { kind: 'proxy' }),
      job('p2', { kind: 'proxy', status: 'queued' }),
    ])
    assert.deepEqual(counted, { rendering: 1, queued: 1 })
  })
})

describe('the newest proxy job per event', () => {
  it('is the proxy job, whichever of the event\'s jobs is newer', () => {
    const render = job('render', { created_at: '2026-10-02T10:05:00Z' })
    const proxy = job('proxy', { kind: 'proxy', created_at: '2026-10-02T10:00:00Z' })
    assert.equal(kinds.newestProxyByEvent([render, proxy]).get(EVENT)?.id, 'proxy')
    assert.equal(kinds.newestRenderByEvent([render, proxy]).get(EVENT)?.id, 'render')
  })

  it('picks the newer of two proxy jobs and holds nothing for an event with only renders', () => {
    const older = job('older', { kind: 'proxy', status: 'failed', created_at: '2026-10-02T09:00:00Z' })
    const newer = job('newer', { kind: 'proxy', created_at: '2026-10-02T10:00:00Z' })
    assert.equal(kinds.newestProxyByEvent([newer, older]).get(EVENT)?.id, 'newer')
    assert.equal(kinds.newestProxyByEvent([job('r')]).size, 0)
    assert.equal(kinds.isProxy(job('future', { kind: 'future' as JobOut['kind'] })), false)
  })
})

describe('a running proxy job and the render screens', () => {
  it('gives the header counts of zero and the event no render', () => {
    const jobs = [job('p', { kind: 'proxy' })]
    assert.deepEqual(kinds.countRenders(jobs), { rendering: 0, queued: 0 })
    assert.equal(kinds.newestRenderByEvent(jobs).has(EVENT), false)
  })
})
