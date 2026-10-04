import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { EnqueueProxiesResult } from '../api/proxies.ts'
import {
  cardsNotes,
  clipDescription,
  jobAnnouncement,
  jobEndWords,
  movieStat,
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

  it('writes the movie stat to one clock scale so it never changes width', () => {
    assert.equal(movieStat(0, 225000), 'Movie 0:00.00 \u00b7 footage 3:45.00 \u00b7 cuts \u22123:45.00')
    // Same terms, a different time: the same width (the playhead or a trim drag moves the numbers).
    assert.equal(movieStat(224000, 225000).length, movieStat(100000, 225000).length)
    // 9.99 s to 10.00 s on a one-hour scale: the digits grow, the line does not.
    assert.equal(movieStat(9990, 3_600_000, 1000).length, movieStat(10000, 3_600_000, 1000).length)
    // a 70-minute footage has hours in every number
    assert.equal(
      movieStat(3_600_000, 4_200_000),
      'Movie 1:00:00.00 \u00b7 footage 1:10:00.00 \u00b7 cuts \u22120:10:00.00',
    )
  })

  it('leaves out the cuts term for no cuts and the cards term for no cards', () => {
    assert.equal(movieStat(225000, 225000), 'Movie 3:45.00 \u00b7 footage 3:45.00')
    assert.equal(movieStat(225000, 225000, 0), 'Movie 3:45.00 \u00b7 footage 3:45.00')
    assert.equal(
      movieStat(225000, 225000, 8000),
      'Movie 3:53.00 \u00b7 footage 3:45.00 \u00b7 cards +0:08.00',
    )
  })

  it('keeps movie = footage \u2212 cuts + cards', () => {
    assert.equal(
      movieStat(200000, 225000, 8000),
      'Movie 3:28.00 \u00b7 footage 3:45.00 \u00b7 cuts \u22120:25.00 \u00b7 cards +0:08.00',
    )
    // Cards can make the movie longer than the footage: the scale holds both.
    assert.equal(
      movieStat(47650, 47650, 5000),
      'Movie 0:52.65 \u00b7 footage 0:47.65 \u00b7 cards +0:05.00',
    )
  })

  it('says the movie, the clip and a clip without cuts', () => {
        assert.equal(clipDescription(24960, 2), '0:24.96 long, 2 cuts')
    assert.equal(clipDescription(3200, 0), '0:03.2 long, no cuts')
    assert.equal(clipDescription(3200, 1), '0:03.2 long, 1 cut')
    // timeline-ripple-layout: edge cuts leave less of the clip on the track.
    assert.equal(clipDescription(10000, 1, 8000), '0:08 of 0:10 kept, 1 cut')
    assert.equal(clipDescription(10000, 1, 10000), '0:10 long, 1 cut')
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
    assert.deepEqual(cardsNotes(specs, off, 'off', 'project'), [
      { title: 'Title cards are off for this event; the render draws none', detail: 'Set by the project’s config.yaml.' },
    ])
    assert.deepEqual(cardsNotes(specs, [], 'invalid', null, 'look.decorators is not a list'), [
      { title: 'look.decorators is not a list', detail: 'No title card is drawn here.' },
    ])
    assert.equal(cardsNotes(specs, [], 'invalid').length, 1)
    for (const note of [...cardsNotes(specs, off, 'off', 'default'), ...cardsNotes(specs, [], 'invalid')]) {
      assert.doesNotMatch(`${note.title} ${note.detail ?? ''}`, /unset|not counted|project default/)
    }
    assert.deepEqual(cardsNotes(specs, [], 'on'), [])
    const bad: Placement[] = [{ kind: 'unreadable', chapter: 1, error: 'card duration must be positive' }]
    assert.equal(cardsNotes(specs, bad, 'on')[0].detail, 'Dag 2: card duration must be positive')
  })
})

describe('the slider and the announcement in a title card', () => {
  it('names the title card and the event time including cards', () => {
    const card = { name: '', ms: 1200, lengthMs: 7000 }
    assert.equal(
      playheadValueText('s1.mp4', 0, 40000, 1200, 163760, card),
      'title card for the opening, 1.2 s of 7.0 s; event 0:01.2 of 2:43.76',
    )
    assert.equal(playheadAnnouncement('s1.mp4', 0, card), 'Playhead at title card for the opening, 0:01.2')
    assert.match(playheadValueText('s1.mp4', 0, 40000, 1200, 163760, { ...card, name: 'Dag 2' }), /^title card for Dag 2,/)
  })
})
