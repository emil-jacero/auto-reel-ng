import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Analysis } from '../api/analysis'
import type { AnalysisRead } from './badge.ts'
import { clearsDismissals, endWords, onJobChange, recheckKey, startKey } from './refresh.ts'

/* When the page reads its analysis again by itself (`refresh.ts`, D3). */

const job = (id: string, status: 'queued' | 'running' | 'done' | 'failed' | 'canceled') => ({ id, status })

describe('onJobChange', () => {
  it('reloads and announces when a job seen active ends live', () => {
    assert.deepEqual(onJobChange(job('a', 'running'), job('a', 'done'), false), {
      reload: true,
      announce: true,
      endedAs: 'done',
    })
    assert.deepEqual(onJobChange(job('a', 'queued'), job('a', 'canceled'), false), {
      reload: true,
      announce: true,
      endedAs: 'canceled',
    })
  })

  it('reloads without the announcement when the end was reconciled', () => {
    assert.deepEqual(onJobChange(job('a', 'running'), job('a', 'failed'), true), {
      reload: true,
      announce: false,
      endedAs: 'failed',
    })
  })

  it('does not reload for a job first seen ended, a job that starts, or progress', () => {
    assert.deepEqual(onJobChange(null, job('a', 'done'), false), { reload: false })
    assert.deepEqual(onJobChange(null, job('a', 'queued'), false), { reload: false })
    assert.deepEqual(onJobChange(job('a', 'queued'), job('a', 'running'), false), { reload: false })
    assert.deepEqual(onJobChange(job('a', 'running'), job('a', 'running'), false), { reload: false })
    assert.deepEqual(onJobChange(job('a', 'done'), job('b', 'queued'), false), { reload: false })
    assert.deepEqual(onJobChange(job('a', 'done'), job('a', 'done'), false), { reload: false })
  })

  it('reloads when an active job gives way to a newer one already ended', () => {
    assert.equal(onJobChange(job('a', 'running'), job('b', 'done'), false).reload, true)
    assert.equal(onJobChange(job('a', 'running'), job('b', 'queued'), false).reload, false)
  })
})

function read(state: string, jobId: string | null): AnalysisRead {
  const analysis = {
    analyzed: true,
    segments: {},
    state,
    clips: {},
    job: jobId === null ? null : { id: jobId, status: 'running', progress: 0.1 },
  } as unknown as Analysis
  return { status: 'ok', analysis, rereading: false }
}

describe('recheckKey', () => {
  it('re-reads once when the read says analyzing and the live connection has no active job', () => {
    const r = read('analyzing', 'j1')
    assert.equal(recheckKey(r, false, true, null), 'j1')
    // The read that answers names the same job: never a second time.
    assert.equal(recheckKey(read('analyzing', 'j1'), false, true, 'j1'), null)
    // A read naming a newer job is checked once more.
    assert.equal(recheckKey(read('analyzing', 'j2'), false, true, 'j1'), 'j2')
    assert.equal(recheckKey(read('analyzing', null), false, true, null), '')
    assert.equal(recheckKey(read('analyzing', null), false, true, ''), null)
  })

  it('does not re-read while the job is live, the connection is not, or the read is not analyzing', () => {
    assert.equal(recheckKey(read('analyzing', 'j1'), true, true, null), null)
    assert.equal(recheckKey(read('analyzing', 'j1'), false, false, null), null)
    assert.equal(recheckKey(read('current', null), false, true, null), null)
    assert.equal(recheckKey({ status: 'reading' }, false, true, null), null)
  })
})

describe('clearsDismissals', () => {
  it('forgets the dismissals when a job seen active ends, live or reconciled', () => {
    // A forced re-analysis of unchanged clips finds the very same spans: without this, every
    // dismissal would survive `dropGone`, and Re-analyze would not bring them back.
    assert.equal(clearsDismissals(onJobChange(job('a', 'running'), job('a', 'done'), false)), true)
    assert.equal(clearsDismissals(onJobChange(job('a', 'running'), job('a', 'done'), true)), true)
    assert.equal(clearsDismissals(onJobChange(job('a', 'running'), job('a', 'failed'), false)), true)
  })

  it('keeps them for a cancel, a start, progress, or a job first seen ended', () => {
    assert.equal(clearsDismissals(onJobChange(job('a', 'running'), job('a', 'canceled'), false)), false)
    assert.equal(clearsDismissals(onJobChange(null, job('a', 'queued'), false)), false)
    assert.equal(clearsDismissals(onJobChange(job('a', 'queued'), job('a', 'running'), false)), false)
    assert.equal(clearsDismissals(onJobChange(null, job('a', 'done'), false)), false)
  })
})

describe('startKey', () => {
  const before = read('never', null)

  it('re-reads once when a trusted job starts after the shown read', () => {
    assert.equal(startKey(before, job('j1', 'queued'), true, null), 'j1')
    assert.equal(startKey(before, job('j1', 'running'), true, null), 'j1')
    // A read naming an older job predates this one too.
    assert.equal(startKey(read('stale', 'j0'), job('j1', 'running'), true, null), 'j1')
    // Never twice for one job, whatever the read that answers says.
    assert.equal(startKey(before, job('j1', 'running'), true, 'j1'), null)
    // A newer job is read for once more.
    assert.equal(startKey(before, job('j2', 'queued'), true, 'j1'), 'j2')
  })

  it('does not re-read when the read knows the job, it is not trusted or not active', () => {
    assert.equal(startKey(read('analyzing', 'j1'), job('j1', 'running'), true, null), null)
    assert.equal(startKey(before, job('j1', 'running'), false, null), null)
    assert.equal(startKey(before, job('j1', 'done'), true, null), null)
    assert.equal(startKey(before, null, true, null), null)
    assert.equal(startKey({ status: 'reading' }, job('j1', 'running'), true, null), null)
  })
})

describe('endWords', () => {
  const answer = (clips: Record<string, { state: string }>) =>
    ({ analyzed: true, segments: {}, state: 'failed', clips }) as unknown as Analysis

  it('says finished, or how many clips failed, from the new read', () => {
    assert.equal(endWords('done', answer({ a: { state: 'current' } })), 'Analysis finished.')
    assert.equal(endWords('done', answer({ a: { state: 'failed' } })), 'Analysis failed for 1 clip.')
    assert.equal(
      endWords('done', answer({ a: { state: 'failed' }, b: { state: 'failed' } })),
      'Analysis failed for 2 clips.',
    )
    assert.equal(endWords('done', null), 'Analysis finished.')
  })

  it('says a failed or canceled job as such', () => {
    assert.equal(endWords('failed', null), 'Analysis failed.')
    assert.equal(endWords('canceled', null), 'Analysis canceled.')
  })

  it('names the failed clips of a job that failed because every clip did', () => {
    assert.equal(endWords('failed', answer({ a: { state: 'failed' } })), 'Analysis failed for 1 clip.')
  })
})
