import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { playName } from '../preview/playback.ts'
import { canWatch, thumbControlName, watchedAfterRead } from './watch.ts'

/*
 * What the event page's read view offers Watch for, and what a re-read does to an open
 * player (`watch.ts`), run by `npm test`.
 */

type Status = 'active' | 'new' | 'missing' | 'ignored'
const clip = (identity: string, status: Status) => ({ identity, status })

describe('canWatch', () => {
  it('is true for every clip on disk: active, new, ignored', () => {
    for (const status of ['active', 'new', 'ignored'] as const) {
      assert.equal(canWatch({ status }), true, status)
    }
  })

  it('is true for an excluded clip, which is active or new on disk', () => {
    assert.equal(canWatch({ status: 'active' }), true)
  })

  it('is false for a missing clip: it has no file', () => {
    assert.equal(canWatch({ status: 'missing' }), false)
  })
})

describe('watchedAfterRead', () => {
  const chapters = [
    { clips: [clip('a.mp4', 'active'), clip('b.mp4', 'new')] },
    { clips: [clip('K/c.mp4', 'ignored'), clip('K/d.mp4', 'missing')] },
  ]

  it('keeps an identity that is listed active, new or ignored', () => {
    assert.equal(watchedAfterRead('a.mp4', chapters), 'a.mp4')
    assert.equal(watchedAfterRead('b.mp4', chapters), 'b.mp4')
    assert.equal(watchedAfterRead('K/c.mp4', chapters), 'K/c.mp4')
  })

  it('finds the clip in a later chapter of several', () => {
    assert.equal(watchedAfterRead('K/c.mp4', chapters), 'K/c.mp4')
  })

  it('drops one that became missing', () => {
    assert.equal(watchedAfterRead('K/d.mp4', chapters), null)
  })

  it('drops one no chapter lists', () => {
    assert.equal(watchedAfterRead('gone.mp4', chapters), null)
    assert.equal(watchedAfterRead('a.mp4', []), null)
    assert.equal(watchedAfterRead('a.mp4', [{ clips: [] }]), null)
  })

  it('answers null for null', () => {
    assert.equal(watchedAfterRead(null, chapters), null)
  })

  it('gives equal output for the same input twice', () => {
    assert.equal(watchedAfterRead('b.mp4', chapters), watchedAfterRead('b.mp4', chapters))
  })
})

describe('thumbControlName', () => {
  it('is Play <name> closed and Hide player of <name> open', () => {
    assert.equal(thumbControlName('s1710001.mp4', false), 'Play s1710001.mp4')
    assert.equal(thumbControlName('s1710001.mp4', true), 'Hide player of s1710001.mp4')
  })

  it('never equals the open player\'s own Play or Pause name', () => {
    const names = [
      's1710001.mp4',
      'raw/s1710001.mp4',
      'a-very-long-clip-name-of-forty-characters.mp4',
    ]
    for (const name of names) {
      const own = [playName(name, false), playName(name, true)]
      // Open, the player is on the page: the control must differ from both of its names.
      assert.ok(!own.includes(thumbControlName(name, true)), name)
    }
  })
})
