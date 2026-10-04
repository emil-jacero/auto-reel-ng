import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { cardJobs, drawnOf } from './cardRequests.ts'
import { cardPlacements } from './cards.ts'
import type { CardSpec } from './cards.ts'

const spec = (chapter: string, title: string, background = 'black', subtitle = ''): CardSpec => ({
  chapter,
  card: { duration: 3, background, title, subtitle, defaultSubtitle: '', fontFamily: 'Sofia Sans' },
  error: null,
})
const clips = [0, 1, 2].map((chapter) => ({ chapter, durationMs: 10000, spans: [] }))

describe('the Timeline’s card requests', () => {
  const specs = [spec('', 'Midsommar', 'black', '2024-06-21'), spec('Dag 2', 'Dag 2', 'video'), spec('Dag 3', 'Dag 3')]
  const placements = cardPlacements(specs, clips, 'on')

  it('sends the opening card with the draft event title, and every card in play order', () => {
    const jobs = cardJobs(specs, placements)
    assert.deepEqual(jobs.map((j) => j.chapter), ['', 'Dag 2', 'Dag 3'])
    assert.deepEqual(jobs[0].request, {
      chapter: '',
      card: {
        title: 'Midsommar',
        subtitle: '2024-06-21',
        duration: 3,
        background: 'black',
        font_family: 'Sofia Sans',
      },
      event_title: 'Midsommar',
    })
    assert.equal('event_title' in jobs[1].request, false)
    assert.equal(jobs[1].request.card.background, 'video')
  })

  it('sends the style only when it differs from the saved one', () => {
    assert.equal('style' in cardJobs(specs, placements)[0].request, false)
    const style = { background: 'video' }
    assert.deepEqual(cardJobs(specs, placements, style)[2].request.style, style)
  })

  it('draws nothing for a card that is off, unresolved or over the preview’s bounds', () => {
    assert.deepEqual(cardJobs(specs, cardPlacements(specs, clips, 'off')), [])
    assert.deepEqual(cardJobs(specs, cardPlacements(specs, clips, 'invalid')), [])
    const long = [spec('', 'x'.repeat(201))]
    assert.deepEqual(cardJobs(long, cardPlacements(long, clips, 'on')), [])
    const lost: CardSpec[] = [{ chapter: '', card: null, error: 'no font' }]
    assert.deepEqual(cardJobs(lost, cardPlacements(lost, clips, 'on')), [])
  })
})

describe('the preview client’s answers', () => {
  const problem = { type: 'x', title: 't', status: 502, detail: 'the font is missing' }
  it('reads an image, a busy answer and the failures in the service’s words', () => {
    const png = new Blob(['x'])
    assert.deepEqual(drawnOf({ kind: 'image', png }), { kind: 'image', png })
    assert.deepEqual(drawnOf({ kind: 'busy', retryAfter: 3, problem: null }), { kind: 'busy', retryAfter: 3 })
    assert.deepEqual(drawnOf({ kind: 'failed', problem }), { kind: 'failed', message: 'the font is missing' })
    assert.deepEqual(drawnOf({ kind: 'bound', message: 'too long' }), { kind: 'failed', message: 'too long' })
    assert.equal(drawnOf({ kind: 'unreachable', message: 'x' }).kind, 'failed')
  })
})
