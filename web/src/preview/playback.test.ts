import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  STOP_EDITING,
  changedWords,
  goneWords,
  offersSkip,
  playheadWords,
  staleAdvice,
  timeCells,
  timeWords,
} from './playback.ts'

/*
 * The preview's words and rules that differ between Edit mode and the event page's
 * read view (`playback.ts`), run by `npm test`. The Edit-mode strings are copied here as
 * they were before the read view existed: they must not change by a byte.
 */

const OLD_STOP_EDITING =
  'Stop editing (save first if you want to keep your edits) to read the event again, then open ' +
  'the player anew.'

describe('the advice after a clip that is gone or changed on disk', () => {
  it('is Edit mode’s, byte for byte, unless the player is read-only', () => {
    assert.equal(STOP_EDITING, OLD_STOP_EDITING)
    assert.equal(staleAdvice(false), OLD_STOP_EDITING)
    assert.deepEqual(goneWords('a.mp4', 'Not found.'), {
      title: 'a.mp4 is no longer on disk.',
      detail: `Not found. ${OLD_STOP_EDITING}`,
    })
    assert.deepEqual(changedWords('a.mp4'), {
      title: 'a.mp4 changed on disk since the page was read.',
      detail: OLD_STOP_EDITING,
    })
    // The default is Edit mode's.
    assert.deepEqual(goneWords('a.mp4', 'Not found.', false), goneWords('a.mp4', 'Not found.'))
    assert.deepEqual(changedWords('a.mp4', false), changedWords('a.mp4'))
  })

  it('names Refresh when read-only, and says nothing of editing or saving', () => {
    const advice = staleAdvice(true)
    assert.match(advice, /Refresh/)
    assert.match(advice, /watch the clip anew/)
    for (const word of [/edit/i, /save/i, /Edit mode/i]) {
      assert.doesNotMatch(advice, word)
    }
    const gone = goneWords('a.mp4', 'Not found.', true)
    const changed = changedWords('a.mp4', true)
    assert.equal(gone.detail, `Not found. ${advice}`)
    // The service's detail has no full stop: the read view's advice is a sentence of its own.
    assert.equal(goneWords('a.mp4', 'no clip on disk', true).detail, `no clip on disk. ${advice}`)
    assert.equal(changed.detail, advice)
    assert.equal(gone.title, 'a.mp4 is no longer on disk.')
    for (const words of [gone, changed]) {
      assert.doesNotMatch(`${words.title} ${words.detail}`, /edit|save/i)
    }
  })
})

describe('offersSkip', () => {
  const cut = { in: 0, out: 1.5 }
  const removed = { in: 2, out: 3, removed: true }

  it('is always true in Edit mode, as it was', () => {
    assert.equal(offersSkip(false, []), true)
    assert.equal(offersSkip(false, [cut]), true)
    assert.equal(offersSkip(false, [removed]), true)
  })

  it('is false read-only with no cuts', () => {
    assert.equal(offersSkip(true, []), false)
  })

  it('is true read-only with one cut, or a cut beside a removed one', () => {
    assert.equal(offersSkip(true, [cut]), true)
    assert.equal(offersSkip(true, [removed, cut]), true)
  })

  it('is false read-only when every cut is removed', () => {
    assert.equal(offersSkip(true, [removed]), false)
  })
})

describe('the player\'s visible time', () => {
  it('says the clip, the time in it and its length, to centiseconds', () => {
    assert.equal(timeWords(20476, 20640), 'Clip 0:20.47 of 0:20.64')
    assert.equal(timeWords(20480, 20640), 'Clip 0:20.48 of 0:20.64')
    assert.equal(timeWords(0, 6020), 'Clip 0:00.00 of 0:06.02')
  })

  it('shows dashes of the same width before the length is read, never 0:00', () => {
    assert.equal(timeWords(0, null), 'Clip 0:00.00 of -:--.--')
    for (const unreadable of [0, Number.NaN, -5, Number.POSITIVE_INFINITY]) {
      assert.equal(timeWords(0, unreadable), 'Clip 0:00.00 of -:--.--')
    }
    const before = timeCells(0, null)
    const after = timeCells(0, 6020)
    assert.equal(before.time.ch, after.time.ch)
    assert.equal(before.length.ch, after.length.ch)
  })

  it('has one length for every millisecond of a 20.64 s clip and of a 10-minute one', () => {
    for (const length of [20_640, 600_000]) {
      const lengths = new Set<number>()
      for (let at = 0; at <= length; at += length > 100_000 ? 13 : 1) {
        lengths.add(timeWords(at, length).length)
      }
      assert.equal(lengths.size, 1, `clip of ${length} ms`)
    }
    assert.equal(timeWords(0, 600_000), 'Clip 00:00.00 of 10:00.00')
  })

  it('shows a playhead a millisecond past the length as the length', () => {
    assert.equal(timeWords(20641, 20640), 'Clip 0:20.64 of 0:20.64')
  })

  it('keeps the slider\'s words in the Cuts panel\'s form', () => {
    assert.equal(playheadWords(1234, 6020, []), '0:01.234 of 0:06.02')
  })
})
