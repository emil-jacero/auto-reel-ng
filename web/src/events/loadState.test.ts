import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { EventDetail } from '../api/event'
import { movieOf, readingState } from './loadState.ts'
import type { LoadState } from './loadState.ts'

/*
 * What a read does to the event page's state, run by `npm test`: a Refresh carries the
 * event whose Movie section stays, so its player is the same element; a first read, a
 * read on leaving Edit mode and a failure's retry carry none.
 */

const EVENT = { id: '2024/Kalas', title: 'Kalas' } as unknown as EventDetail
const READY: LoadState = { status: 'ready', event: EVENT, fetchedAt: new Date(0) }

describe('readingState', () => {
  it('carries the event through a Refresh, and Edit’s place', () => {
    const state = readingState(READY, { keepMovie: true })
    assert.deepEqual(state, { status: 'loading', editPlace: true, movie: EVENT })
    assert.equal(movieOf(state), EVENT)
  })

  it('keeps carrying it when a Refresh supersedes a Refresh still reading', () => {
    const reading = readingState(READY, { keepMovie: true })
    const again = readingState(reading, { keepMovie: true })
    assert.equal(movieOf(again), EVENT)
  })

  it('carries none for a read on leaving Edit mode, or the first one', () => {
    assert.equal(movieOf(readingState(READY, {})), undefined)
    assert.equal(movieOf(readingState({ status: 'loading', editPlace: true }, {})), undefined)
  })

  it('carries none from a failure, which has no player', () => {
    const failed: LoadState = { status: 'failed', cause: 'x', detail: null }
    const state = readingState(failed, { keepMovie: true })
    assert.deepEqual(state, { status: 'loading', editPlace: false, movie: undefined })
  })

  it('keeps the content for a quiet read, marked as updating', () => {
    assert.deepEqual(readingState(READY, { quiet: true }), { ...READY, updating: true })
  })

  it('shows placeholders for a quiet read of a failure', () => {
    const failed: LoadState = { status: 'failed', cause: 'x', detail: null }
    assert.equal(readingState(failed, { quiet: true }).status, 'loading')
  })
})

describe('movieOf', () => {
  it('is the event of a ready page, and of a loading one that carries it', () => {
    assert.equal(movieOf(READY), EVENT)
    assert.equal(movieOf({ status: 'loading', editPlace: false, movie: EVENT }), EVENT)
    assert.equal(movieOf({ status: 'failed', cause: 'x', detail: null }), undefined)
  })
})
