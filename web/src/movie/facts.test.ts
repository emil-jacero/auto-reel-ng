import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { movieFacts, movieVersionWords } from './facts.ts'

/*
 * What the detail's `movie` says, run by `npm test`: chapters are absent rather than
 * guessed, and the version leaves out what it cannot tell.
 */

const recordedAt = '2026-10-03T14:02:11.250Z'

describe('movieFacts', () => {
  it('has no chapters and no version for a detail without a movie', () => {
    for (const movie of [null, undefined]) {
      assert.deepEqual(movieFacts({ movie }), { chapters: null, version: null })
    }
  })

  it('has no chapters (and never []) when the movie records none or an empty list', () => {
    for (const chapters of [null, undefined, []]) {
      const facts = movieFacts({ movie: { recorded_at: recordedAt, fingerprint: 'abc', chapters } })
      assert.equal(facts.chapters, null)
      assert.deepEqual(facts.version, { recordedAt, fingerprint: 'abc' })
    }
  })

  it('has no chapters for a list that cannot be relied on', () => {
    const chapters = [{ name: 'A', start: 9 }, { name: 'B', start: 2 }]
    assert.equal(movieFacts({ movie: { recorded_at: recordedAt, fingerprint: 'abc', chapters } }).chapters, null)
  })

  it('has no chapters for a movie of one chapter', () => {
    const chapters = [{ name: '', start: 0 }]
    assert.equal(movieFacts({ movie: { recorded_at: recordedAt, fingerprint: 'abc', chapters } }).chapters, null)
  })

  it('gives the recorded list as it is when it is usable', () => {
    const chapters = [{ name: '', start: 0 }, { name: 'Dans', start: 80 }]
    const facts = movieFacts({ movie: { recorded_at: recordedAt, fingerprint: 'abc', chapters } })
    assert.equal(facts.chapters, chapters)
  })
})

describe('movieVersionWords', () => {
  it('gives the time and the fingerprint, with the exact instant kept apart from its words', () => {
    const words = movieVersionWords({ recordedAt, fingerprint: 'a1b2c3d4e5f6' })
    assert.ok(words !== null && words.time !== null)
    assert.equal(words.time.dateTime, recordedAt)
    assert.notEqual(words.time.text, recordedAt)
    assert.equal(words.fingerprint, 'a1b2c3d4e5f6')
  })

  it('gives the fingerprint alone for a time that does not parse, never a made-up time', () => {
    const words = movieVersionWords({ recordedAt: 'not a time', fingerprint: 'a1b2c3d4e5f6' })
    assert.deepEqual(words, { time: null, fingerprint: 'a1b2c3d4e5f6' })
  })

  it('gives the time alone for a blank fingerprint', () => {
    const words = movieVersionWords({ recordedAt, fingerprint: ' ' })
    assert.ok(words !== null)
    assert.equal(words.fingerprint, null)
    assert.equal(words.time?.dateTime, recordedAt)
  })

  it('says nothing for no version, or one with neither part', () => {
    assert.equal(movieVersionWords(null), null)
    assert.equal(movieVersionWords({ recordedAt: '', fingerprint: '' }), null)
  })
})
