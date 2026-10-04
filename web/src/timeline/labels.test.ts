import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { EnqueueProxiesResult } from '../api/proxies.ts'
import {
  cardsNotes,
  clipDescription,
  jobAnnouncement,
  jobEndWords,
  movieWords,
  noticeFor,
  notReadyWords,
  playbackNote,
  playheadAnnouncement,
  playheadValueText,
  PROXY_STATUS_LABEL,
  readyCountWords,
} from './labels.ts'
import { readiness } from './layout.ts'
import type { Placement } from './cards.ts'
import type { ProxyHealth } from './layout.ts'
import { createPlayhead } from './playhead.ts'

const counts = (...h: ProxyHealth[]) => readiness(h.map((health) => ({ health })))
const problem = (status: number, detail = 'why') => ({ title: 'T', status, detail })

describe('the counts', () => {
  it('says 0 of 25, 24 of 25 and the singular', () => {
    const none = counts(...Array<ProxyHealth>(25).fill('absent'))
    assert.equal(readyCountWords(none), '0 of 25 clips are ready')
    assert.deepEqual(notReadyWords(none), ['25 not prepared'])
    const one = counts(...Array<ProxyHealth>(24).fill('ready'), 'failed')
    assert.equal(readyCountWords(one), '24 of 25 clips are ready')
    assert.deepEqual(notReadyWords(one), ['1 failed'])
    assert.equal(readyCountWords(counts('absent')), '0 of 1 clip is ready')
  })

  it('counts each state apart, in a fixed order', () => {
    const r = counts('absent', 'stale', 'stale', 'failed', 'unusable', 'unknown', 'ready')
    assert.deepEqual(notReadyWords(r), [
      '1 not prepared',
      '2 damaged',
      '1 failed',
      '1 with no usable length',
      '1 not known',
    ])
    assert.deepEqual(notReadyWords(counts('ready')), [])
  })
})

describe('the answers to Prepare proxies', () => {
  const job = { id: 'j' } as never
  const answers: EnqueueProxiesResult[] = [
    { kind: 'enqueued', job },
    { kind: 'ready', fresh: { event_id: 'e', status: 'fresh', clip_count: 2 } },
    { kind: 'active', jobId: 'j', problem: problem(409) },
    { kind: 'problem', problem: problem(404) },
    { kind: 'problem', problem: problem(502, 'cache unreadable') },
    { kind: 'database', problem: problem(503) },
    { kind: 'unreachable', message: 'x' },
    { kind: 'unpublished', message: 'POST /x answered 500' },
  ]

  it('has words for every answer but a created job, and a 409 is not an error', () => {
    const notices = answers.map(noticeFor)
    assert.equal(notices[0], null)
    assert.ok(notices.slice(1).every((n) => n !== null && n.title !== ''))
    assert.equal(notices[2]?.tone, 'info')
    assert.equal(notices[1]?.tone, 'ok')
  })

  it('says why from the answer: 404, 502 and the database by cause', () => {
    assert.match(noticeFor(answers[3])?.title ?? '', /no longer there/)
    assert.equal(noticeFor(answers[4])?.detail, 'cache unreadable')
    assert.match(noticeFor(answers[5])?.title ?? '', /database/)
    assert.match(noticeFor(answers[6])?.title ?? '', /did not answer/)
    assert.match(noticeFor(answers[7])?.detail ?? '', /answered 500/)
  })

  it('words a failed job with the recorded error and a canceled one neutrally', () => {
    assert.deepEqual(jobEndWords('failed', 'ffmpeg exited 1'), {
      tone: 'err',
      title: 'Preparing the proxies failed.',
      detail: 'ffmpeg exited 1',
    })
    assert.equal(jobEndWords('failed', null).detail, null)
    assert.equal(jobEndWords('canceled', 'x').tone, 'info')
  })

  it('names every job status without the render words', () => {
    for (const words of Object.values(PROXY_STATUS_LABEL)) {
      assert.doesNotMatch(words, /render/i)
    }
    assert.equal(PROXY_STATUS_LABEL.running, 'Preparing proxies')
    assert.equal(jobAnnouncement('queued', false), 'Proxy job queued. Waiting for a worker')
    assert.equal(jobAnnouncement('running', true), 'Cancelling the proxy job')
    assert.equal(jobAnnouncement('done', false), 'Proxies ready')
  })
})

describe('the playhead\'s words', () => {
  it('builds the slider\'s value text with the clip and the time in it and in all', () => {
    assert.equal(
      playheadValueText('Harbour', 12400, 24960, 72000, 192000),
      'Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12',
    )
    assert.equal(playheadAnnouncement('Harbour', 12400), 'Playhead at Harbour, 0:12.4')
  })

  it('says the spoken slider text in the Cuts panel\'s form, not padded', () => {
    assert.equal(
      playheadValueText('s1710002.mp4', 100, 40000, 9100, 55020),
      's1710002.mp4, clip 0:00.1 of 0:40; event 0:09.1 of 0:55.02',
    )
  })

  it('writes the movie line to the footage\'s scale so it never changes width', () => {
    assert.equal(movieWords(0, 225000), 'Movie 0:00.00 of 3:45.00 of footage')
    assert.equal(movieWords(225000, 225000).length, movieWords(9990, 225000).length)
    // a 70-minute footage has hours in both numbers
    assert.equal(movieWords(3_600_000, 4_200_000), 'Movie 1:00:00.00 of 1:10:00.00 of footage')
    assert.equal(movieWords(59_000, 4_200_000), 'Movie 0:00:59.00 of 1:10:00.00 of footage')
  })

  it('says the movie, the clip and a clip without cuts', () => {
    assert.equal(movieWords(192000, 225000), 'Movie 3:12.00 of 3:45.00 of footage')
    assert.equal(clipDescription(24960, 2), '0:24.96 long, 2 cuts')
    assert.equal(clipDescription(3200, 0), '0:03.2 long, no cuts')
    assert.equal(clipDescription(3200, 1), '0:03.2 long, 1 cut')
  })
})

describe('a proxy that does not play', () => {
  it('tells a gone proxy (and offers Prepare) from a service fault and a browser refusal', () => {
    const gone = playbackNote('a.mp4', { kind: 'problem', problem: problem(404, 'no proxy of a.mp4') }, '')
    assert.equal(gone.gone, true)
    assert.match(gone.title, /no longer there/)
    assert.match(gone.detail ?? '', /Prepare the proxies again/)
    const unreadable = playbackNote('a.mp4', { kind: 'problem', problem: problem(502, 'disk') }, '')
    assert.equal(unreadable.gone, false)
    const refused = playbackNote('a.mp4', { kind: 'ok', version: 'v' }, 'The browser does not support the file')
    assert.equal(refused.gone, false)
    assert.equal(refused.detail, 'The browser does not support the file')
    assert.equal(playbackNote('a.mp4', { kind: 'empty' }, '').gone, true)
    assert.match(playbackNote('a.mp4', { kind: 'unreachable', message: 'x' }, '').title, /did not answer/)
    assert.match(playbackNote('a.mp4', { kind: 'unpublished', message: 'GET answered 500' }, '').detail ?? '', /500/)
  })
})

describe('createPlayhead', () => {
  it('notifies only when the playhead moved, and stops notifying after unsubscribe', () => {
    const p = createPlayhead({ clip: 0, ms: 0 })
    let n = 0
    const off = p.subscribe(() => (n += 1))
    p.set({ clip: 0, ms: 0 })
    assert.equal(n, 0)
    p.set({ clip: 0, ms: 40 })
    p.set({ clip: 1, ms: 40 })
    assert.equal(n, 2)
    assert.deepEqual(p.get(), { clip: 1, ms: 40 })
    off()
    p.set({ clip: 2, ms: 0 })
    assert.equal(n, 2)
  })

  it('returns the same object until the position changes (a stable snapshot)', () => {
    const p = createPlayhead({ clip: 0, ms: 0 })
    const a = p.get()
    p.set({ clip: 0, ms: 0 })
    assert.equal(p.get(), a)
  })
})

describe('title cards in the words', () => {
  it('says the time black cards add to the movie, and nothing without them', () => {
    assert.equal(
      movieWords(200000, 225000, 'with 8 s of title cards'),
      'Movie 3:20.00 of 3:45.00 of footage, with 8 s of title cards',
    )
    assert.equal(movieWords(200000, 225000, ''), 'Movie 3:20.00 of 3:45.00 of footage')
    // Longer than the footage (cards add time): the movie is written whole, not cut to the footage.
    assert.equal(
      movieWords(52650, 47650, 'with 8 s of title cards'),
      'Movie 0:52.65 of 0:47.65 of footage, with 8 s of title cards',
    )
  })

  it('says once what cannot be drawn, in the service’s words', () => {
    const specs = [{ chapter: '' }, { chapter: 'Dag 2' }]
    const unresolved: Placement[] = [
      { kind: 'unresolved', chapter: 0, error: 'look.title_card.font_family' },
      { kind: 'unresolved', chapter: 1, error: 'look.title_card.font_family' },
    ]
    assert.deepEqual(cardsNotes(specs, unresolved, 'on'), [
      {
        title: 'A title card could not be resolved: look.title_card.font_family',
        detail: 'Not drawn for the opening, Dag 2.',
      },
    ])
    const off: Placement[] = [
      { kind: 'off', chapter: 0, clip: 0, atMs: 0, background: 'black', durationMs: 1, keptMs: 1, widthMs: 1, clamped: false },
    ]
    assert.deepEqual(cardsNotes(specs, off, 'off'), [
      { title: 'Title cards are off for this event; the render draws none' },
    ])
    assert.match(cardsNotes(specs, off, 'unset')[0].detail ?? '', /project default/)
    assert.equal(cardsNotes(specs, [], 'invalid').length, 1)
    assert.equal(cardsNotes(specs, [], 'unreadable').length, 1)
    assert.deepEqual(cardsNotes(specs, [], 'on'), [])
    const bad: Placement[] = [{ kind: 'unreadable', chapter: 1, error: 'card duration must be positive' }]
    assert.equal(cardsNotes(specs, bad, 'on')[0].detail, 'Dag 2: card duration must be positive')
  })
})
