import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createVerdictFlight } from './verdictFlight.ts'

/*
 * Edit mode's verdict reads, run by `npm test`: a burst gives one read in flight and one
 * after it, and leaving Edit mode drops the answer of the read on its way.
 */

describe('createVerdictFlight', () => {
  it('gives one read in flight and one after it for a burst', () => {
    const flight = createVerdictFlight()
    const first = flight.request()
    assert.notEqual(first, null)
    assert.equal(flight.request(), null)
    assert.equal(flight.request(), null)
    assert.equal(flight.finish(first as AbortController), true)
    const second = flight.request()
    assert.notEqual(second, null)
    assert.equal(flight.finish(second as AbortController), false)
  })

  it('asks for no further read when nothing was requested meanwhile', () => {
    const flight = createVerdictFlight()
    const first = flight.request() as AbortController
    assert.equal(flight.finish(first), false)
    assert.notEqual(flight.request(), null)
  })

  it('drops the answer of an aborted read and the request waiting behind it', () => {
    const flight = createVerdictFlight()
    const first = flight.request() as AbortController
    assert.equal(flight.request(), null)
    flight.abort()
    assert.equal(first.signal.aborted, true)
    assert.equal(flight.finish(first), false)
  })

  it('starts fresh after an abort, and the aborted read cannot end the new one', () => {
    const flight = createVerdictFlight()
    const first = flight.request() as AbortController
    flight.abort()
    const second = flight.request() as AbortController
    assert.notEqual(second, first)
    assert.equal(second.signal.aborted, false)
    assert.equal(flight.finish(first), false)
    assert.equal(flight.request(), null)
    assert.equal(flight.finish(second), true)
  })
})
