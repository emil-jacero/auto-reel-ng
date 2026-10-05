import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Analysis } from '../api/analysis'
import {
  ANALYSIS_STATE_WORDS,
  UNKNOWN_WORDS,
  badgeOf,
  clipNoteOf,
  failedClips,
  failedNamesWords,
  neverAnalyzed,
} from './badge.ts'
import type { AnalysisRead } from './badge.ts'

/* The analysis badge (`badge.ts`, D2): the published state in words, the live job ahead of it. */

function analysis(
  state: string,
  clips: Record<string, { state: string; detail?: string | null }> = {},
  extra: Partial<Analysis> = {},
): Analysis {
  return { analyzed: true, segments: {}, state, clips, ...extra } as Analysis
}

const ok = (a: Analysis): AnalysisRead => ({ status: 'ok', analysis: a, rereading: false })
const running = (progress: number) => ({ status: 'running' as const, progress })
const queued = { status: 'queued' as const, progress: 0 }

describe('badgeOf: the read’s state', () => {
  it('says "Not analyzed", muted, for never', () => {
    const badge = badgeOf(ok(analysis('never')), null, true)
    assert.equal(badge?.words, 'Not analyzed')
    assert.equal(badge?.tone, 'idle')
    assert.equal(badge?.state, 'never')
    assert.ok(badge?.icon)
  })

  it('says "Analysis out of date" for stale', () => {
    assert.equal(badgeOf(ok(analysis('stale')), null, true)?.words, 'Analysis out of date')
  })

  it('shows no badge when current', () => {
    assert.equal(badgeOf(ok(analysis('current')), null, true), null)
  })

  it('counts the failed clips, 1 vs N, with a warning tone and the names', () => {
    const one = badgeOf(ok(analysis('failed', { 'C0007.MP4': { state: 'failed', detail: 'x' } })), null, true)
    assert.equal(one?.words, 'Analysis failed for 1 clip')
    assert.equal(one?.tone, 'warn')
    assert.equal(one?.icon, 'alert-triangle')
    assert.deepEqual(one?.failed, { names: ['C0007.MP4'], more: 0 })
    const clips = Object.fromEntries(
      ['a', 'b', 'c', 'd', 'e'].map((name) => [`${name}.mp4`, { state: 'failed' }]),
    )
    clips['ok.mp4'] = { state: 'current' }
    const five = badgeOf(ok(analysis('failed', clips)), null, true)
    assert.equal(five?.words, 'Analysis failed for 5 clips')
    assert.deepEqual(five?.failed, { names: ['a.mp4', 'b.mp4', 'c.mp4'], more: 2 })
    assert.equal(failedNamesWords(five!.failed!), 'a.mp4, b.mp4, c.mp4 and 2 more')
    assert.equal(failedNamesWords(one!.failed!), 'C0007.MP4')
  })

  it('takes the read’s own job while it says analyzing and no live job is trusted', () => {
    const a = analysis('analyzing', { 'a.mp4': { state: 'analyzing' } }, {
      job: { status: 'running', progress: 0.5 } as Analysis['job'],
    })
    const badge = badgeOf(ok(a), null, true)
    assert.equal(badge?.words, 'Analyzing 1 clip…')
    assert.deepEqual(badge?.progress, { fraction: 0.5, percent: 50 })
    const waiting = badgeOf(ok(analysis('analyzing')), null, true)
    assert.equal(waiting?.words, 'Waiting to analyze')
    assert.equal(waiting?.progress, null)
  })

  it('says "Analysis state unknown" for a value this build does not know, never its slug', () => {
    const badge = badgeOf(ok(analysis('pondering')), null, true)
    assert.equal(badge?.words, UNKNOWN_WORDS)
    assert.equal(badge?.state, 'unknown')
    assert.ok(!badge?.words.includes('pondering'))
  })

  it('says "Analysis state unknown" with the cause for a failed read', () => {
    const read: AnalysisRead = {
      status: 'failed',
      failure: { cause: 'The service can’t reach its database.', detail: 'down' },
      rereading: false,
    }
    const badge = badgeOf(read, null, true)
    assert.equal(badge?.words, 'Analysis state unknown')
    assert.equal(badge?.tone, 'idle')
    assert.equal(badge?.detail, 'The service can’t reach its database. down')
  })

  it('shows nothing before the first read answers', () => {
    assert.equal(badgeOf({ status: 'reading' }, null, true), null)
  })
})

describe('badgeOf: the live job ahead of the read', () => {
  it('a queued job is "Waiting to analyze" with no value, even when the read said current', () => {
    const badge = badgeOf(ok(analysis('current')), queued, true)
    assert.equal(badge?.words, 'Waiting to analyze')
    assert.equal(badge?.state, 'analyzing')
    assert.equal(badge?.progress, null)
  })

  it('a running job shows its progress and the clips the read reports as analyzing', () => {
    const clips = Object.fromEntries(
      Array.from({ length: 9 }, (_, i) => [`c${i}.mp4`, { state: 'analyzing' }]),
    )
    const badge = badgeOf(ok(analysis('analyzing', clips)), running(0.42), true)
    assert.equal(badge?.words, 'Analyzing 9 clips…')
    assert.deepEqual(badge?.progress, { fraction: 0.42, percent: 42 })
  })

  it('holds a running job at 99%: 0.995 is shown as 99', () => {
    const badge = badgeOf(ok(analysis('never')), running(0.995), true)
    assert.equal(badge?.progress?.percent, 99)
    assert.equal(badge?.progress?.fraction, 0.99)
    assert.equal(badgeOf(ok(analysis('never')), running(1), true)?.progress?.percent, 99)
  })

  it('says "Analyzing…" when the read reports no analyzing clip', () => {
    assert.equal(badgeOf(ok(analysis('never')), running(0.1), true)?.words, 'Analyzing…')
    assert.equal(badgeOf({ status: 'reading' }, running(0.1), true)?.words, 'Analyzing…')
  })

  it('a failed read under a running job still shows the job', () => {
    const read: AnalysisRead = { status: 'failed', failure: { cause: 'x', detail: null }, rereading: false }
    assert.equal(badgeOf(read, running(0.3), true)?.state, 'analyzing')
  })

  it('an ended job, or one from a connection that is not trusted, gives way to the read', () => {
    const ended = { status: 'done' as const, progress: 1 }
    assert.equal(badgeOf(ok(analysis('current')), ended, true), null)
    assert.equal(badgeOf(ok(analysis('stale')), running(0.5), false)?.words, 'Analysis out of date')
  })
})

describe('the per-clip note and the help', () => {
  const a = analysis('stale', {
    'C0001.MP4': { state: 'current' },
    'C0003.MP4': { state: 'stale' },
    'C0004.MP4': { state: 'never' },
    'C0005.MP4': { state: 'analyzing' },
    'C0007.MP4': { state: 'failed', detail: 'ffmpeg exited 1: Invalid data found when processing input' },
    'C0009.MP4': { state: 'later' },
  })

  it('reads each clip’s own state, nothing for a current clip or one the read does not list', () => {
    assert.equal(clipNoteOf(a, 'C0001.MP4'), null)
    assert.equal(clipNoteOf(a, 'gone.mp4'), null)
    assert.equal(clipNoteOf(a, 'C0003.MP4')?.words, 'Analysis out of date')
    assert.equal(clipNoteOf(a, 'C0004.MP4')?.words, 'Not analyzed')
    assert.equal(clipNoteOf(a, 'C0005.MP4')?.words, 'Analyzing…')
    assert.equal(clipNoteOf(a, 'C0007.MP4')?.words, 'Analysis failed')
    assert.equal(clipNoteOf(a, 'C0009.MP4')?.words, UNKNOWN_WORDS)
    assert.ok(clipNoteOf(a, 'C0003.MP4')?.icon)
  })

  it('lists the failed clips with the service’s text', () => {
    assert.deepEqual(failedClips(a), [
      { identity: 'C0007.MP4', detail: 'ffmpeg exited 1: Invalid data found when processing input' },
    ])
  })

  it('says Analyze only while the read says never', () => {
    assert.equal(neverAnalyzed(ok(analysis('never'))), true)
    assert.equal(neverAnalyzed(ok(analysis('stale'))), false)
    assert.equal(neverAnalyzed({ status: 'reading' }), false)
  })

  it('has words, a glyph and a tone for every published state', () => {
    for (const look of Object.values(ANALYSIS_STATE_WORDS)) {
      assert.ok(look.words.length > 0 && look.icon.length > 0 && look.tone.length > 0)
    }
  })
})
