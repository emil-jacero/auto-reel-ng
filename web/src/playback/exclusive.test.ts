import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createExclusive } from './exclusive.ts'

function fake() {
  const el = { paused: 0, pause: () => (el.paused += 1) }
  return el
}

describe('createExclusive', () => {
  it('pauses the element that held playback when another claims it', () => {
    const x = createExclusive()
    const movie = fake()
    const timeline = fake()
    x.claim(movie)
    x.claim(timeline)
    assert.equal(movie.paused, 1)
    assert.equal(timeline.paused, 0)
    x.claim(movie)
    assert.equal(timeline.paused, 1)
    assert.equal(movie.paused, 1)
  })

  it('pauses nothing when the holder claims again', () => {
    const x = createExclusive()
    const movie = fake()
    x.claim(movie)
    x.claim(movie)
    assert.equal(movie.paused, 0)
  })

  it('pauses nothing for a first claim or after the holder released', () => {
    const x = createExclusive()
    const a = fake()
    const b = fake()
    x.claim(a)
    x.release(a)
    x.claim(b)
    assert.equal(a.paused, 0)
    x.release(a) // not the holder: no effect
    x.claim(a)
    assert.equal(b.paused, 1)
  })
})
