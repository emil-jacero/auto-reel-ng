import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { EventDetail } from '../api/event'
import {
  liveOf,
  movieOf,
  readingState,
  verdictOf,
  withVerdict,
  withVerdictUnread,
} from './loadState.ts'
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

/*
 * The render region's verdict while Edit mode is open: a newer read changes the verdict and
 * latest job and nothing the editor's baseline or the page's header stands on.
 */

const STALE = { stale: true, reasons: [{ kind: 'x' }] }
const FRESH = { stale: false, reasons: [] }
const RUNNING = { id: 'j1', status: 'running' }
const DONE = { id: 'j1', status: 'done' }
const BEFORE = { ...EVENT, staleness: STALE, latest_job: RUNNING } as unknown as EventDetail
// A newer read, which differs in everything the editor and the page's header show.
const AFTER = {
  id: '2024/Kalas',
  title: 'Other title',
  date: '2020-01-01',
  chapters: [{ name: 'Elsewhere', clips: [] }],
  missing: ['gone.mp4'],
  staleness: FRESH,
  latest_job: DONE,
} as unknown as EventDetail
const EDITED: LoadState = { status: 'ready', event: BEFORE, fetchedAt: new Date(5) }

describe('verdictOf', () => {
  it('is the last read’s verdict until a newer one is taken', () => {
    assert.deepEqual(verdictOf(EDITED as never), BEFORE)
    const newer = withVerdict(EDITED, AFTER)
    assert.deepEqual(verdictOf(newer as never), { staleness: FRESH, latest_job: DONE })
  })
})

describe('withVerdict', () => {
  it('takes the verdict and the latest job and nothing else', () => {
    const state = withVerdict(EDITED, AFTER)
    assert.equal(state.status, 'ready')
    if (state.status !== 'ready') {
      return
    }
    assert.equal(state.event, BEFORE)
    assert.equal(state.fetchedAt, EDITED.status === 'ready' ? EDITED.fetchedAt : undefined)
    assert.equal(state.updating, undefined)
    assert.equal(state.verdict?.staleness, FRESH)
    assert.equal(state.verdict?.latest_job, DONE)
  })

  it('keeps the event as read for the Edit-mode Timeline, apart from the baseline', () => {
    const state = withVerdict(EDITED, AFTER)
    assert.equal(state.status === 'ready' ? liveOf(state) : null, AFTER)
    assert.equal(state.status === 'ready' ? state.event : null, BEFORE)
    // before any newer read the live event is the one the page shows
    assert.equal(liveOf(EDITED as never), BEFORE)
  })

  it('removes the note that an earlier read got no answer', () => {
    const unread = withVerdictUnread(EDITED, { cause: 'The service is not reachable.', detail: null })
    const state = withVerdict(unread, AFTER)
    assert.equal(state.status === 'ready' && 'verdictUnread' in state, false)
  })

  it('leaves a page that is not ready as it is', () => {
    const loading: LoadState = { status: 'loading', editPlace: true }
    const failed: LoadState = { status: 'failed', cause: 'x', detail: null }
    assert.equal(withVerdict(loading, AFTER), loading)
    assert.equal(withVerdict(failed, AFTER), failed)
  })
})

describe('withVerdictUnread', () => {
  it('adds the note and keeps the verdict, the event and the time', () => {
    const newer = withVerdict(EDITED, AFTER)
    const state = withVerdictUnread(newer, { cause: 'c', detail: 'd' })
    assert.deepEqual(state, { ...newer, verdictUnread: { cause: 'c', detail: 'd' } })
    assert.equal(state.status === 'ready' ? state.event : null, BEFORE)
  })

  it('leaves a page that is not ready as it is', () => {
    const failed: LoadState = { status: 'failed', cause: 'x', detail: null }
    assert.equal(withVerdictUnread(failed, { cause: 'c', detail: null }), failed)
  })

  it('does not outlive the read that leaving Edit mode makes', () => {
    const state = withVerdictUnread(withVerdict(EDITED, AFTER), { cause: 'c', detail: null })
    assert.equal(readingState(state, {}).status, 'loading')
  })
})
