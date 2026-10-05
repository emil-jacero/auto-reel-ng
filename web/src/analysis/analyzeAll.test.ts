import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { NOTHING_TO_ANALYZE, analyzeAllWords } from './analyzeAll.ts'

/* Analyze all's answer in words (`analyzeAll.ts`). */

const counts = (queued: number, active: number, unreadable = 0, fresh = 0) => ({
  queued,
  fresh,
  active,
  unreadable: Array.from({ length: unreadable }, (_, i) => ({ event_id: `e${i}`, detail: 'x' })),
})

describe('analyzeAllWords', () => {
  it('says how many were queued and how many already were', () => {
    assert.equal(analyzeAllWords(counts(12, 1)), 'Queued 12 events. 1 already queued.')
    assert.equal(analyzeAllWords(counts(1, 0)), 'Queued 1 event.')
  })

  it('says how many could not be read', () => {
    assert.equal(analyzeAllWords(counts(2, 0, 3)), 'Queued 2 events. 3 could not be read.')
    assert.equal(analyzeAllWords(counts(0, 0, 1)), 'Queued no events. 1 could not be read.')
  })

  it('says there is nothing to analyze when it queued none and read every event', () => {
    assert.equal(analyzeAllWords(counts(0, 0, 0, 40)), NOTHING_TO_ANALYZE)
    assert.equal(analyzeAllWords(counts(0, 4)), NOTHING_TO_ANALYZE)
    assert.equal(NOTHING_TO_ANALYZE, 'Nothing to analyze: every event is analyzed or already queued.')
  })
})
