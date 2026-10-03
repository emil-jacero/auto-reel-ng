import assert from 'node:assert/strict'
import { register } from 'node:module'
import { before, describe, it } from 'node:test'

import type { JobSummary } from '../api/events'
import type { JobOut } from '../api/jobs'

/*
 * Which version of a job the event shows (`choose`), run by `npm test`. The sources import
 * each other without file extensions, which a resolve hook adds for this test only.
 */
type ShownJobModule = typeof import('./shownJob.ts')
let choose: ShownJobModule['choose']

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
  ;({ choose } = await import('./shownJob.ts'))
})

const ID = '11111111-1111-4111-8111-111111111111'

function held(patch: Partial<JobOut> = {}): JobOut {
  return {
    id: ID,
    event_dir: '2024/2024-07-04 - Barbecue',
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

function read(patch: Partial<JobSummary> = {}): JobSummary {
  return {
    id: ID,
    kind: 'render',
    status: 'running',
    progress: 0.4,
    created_at: '2026-10-02T10:00:00Z',
    started_at: '2026-10-02T10:01:00Z',
    finished_at: null,
    cancel_requested: false,
    requeue_count: 0,
    ...patch,
  }
}

describe('a read of the job the store holds as running', () => {
  it('shows a requeue while the connection is down', () => {
    const requeued = read({
      status: 'queued',
      progress: 0,
      started_at: null,
      requeue_count: 1,
    })
    const shown = choose(held(), requeued, false)
    assert.equal(shown?.source, 'refreshed')
    assert.equal(shown?.job.status, 'queued')
    assert.equal(shown?.job.progress, 0)
    assert.equal(shown?.job.started_at, null)
    assert.equal(shown?.job.requeue_count, 1)
  })

  it('keeps what a read does not carry from the held copy', () => {
    const shown = choose(
      held(),
      read({ status: 'queued', progress: 0, started_at: null, requeue_count: 1 }),
      false,
    )
    assert.equal(shown?.source, 'refreshed')
    assert.equal((shown?.job as JobOut).worker_id, 'worker-1')
    assert.equal((shown?.job as JobOut).event_dir, '2024/2024-07-04 - Barbecue')
  })

  it('keeps the held copy when the read has the same requeue count and is not further along', () => {
    const shown = choose(held(), read({ progress: 0.1 }), false)
    assert.equal(shown?.source, 'live')
    assert.equal(shown?.job.progress, 0.4)
  })

  it('brings a read further along forward, as before', () => {
    const shown = choose(held(), read({ progress: 0.7 }), false)
    assert.equal(shown?.source, 'refreshed')
    assert.equal(shown?.job.progress, 0.7)
  })

  it('does not overrule a live connection, whatever the read says', () => {
    const shown = choose(
      held(),
      read({ status: 'queued', progress: 0, started_at: null, requeue_count: 3 }),
      true,
    )
    assert.equal(shown?.source, 'live')
    assert.equal(shown?.job.status, 'running')
  })

  it('never goes back to a read with a lower requeue count, however far along it looks', () => {
    const waiting = held({ requeue_count: 2, status: 'queued', progress: 0, started_at: null })
    const shown = choose(waiting, read({ requeue_count: 1, progress: 0.9 }), false)
    assert.equal(shown?.source, 'live')
    assert.equal(shown?.job.requeue_count, 2)
    assert.equal(shown?.job.status, 'queued')
  })

  it('shows a cancel request the held copy lacks while the connection is down', () => {
    const shown = choose(held(), read({ cancel_requested: true, progress: 0.2 }), false)
    assert.equal(shown?.source, 'refreshed')
    assert.equal(shown?.job.cancel_requested, true)
  })

  it('shows a read that ended the job', () => {
    const shown = choose(held(), read({ status: 'done', progress: 1 }), true)
    assert.equal(shown?.source, 'read')
    assert.equal(shown?.job.status, 'done')
  })
})

describe('a job known only from a read', () => {
  it('carries the read as it is, with its cancel request', () => {
    const shown = choose(undefined, read({ cancel_requested: true }), false)
    assert.equal(shown?.source, 'read')
    assert.equal(shown?.job.cancel_requested, true)
  })
})
