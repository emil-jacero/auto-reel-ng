import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { currentChapterIndex, jumpLabel, listedChapters, usableChapters } from './chapters.ts'

/*
 * Which chapter list may be relied on, which chapter a position is in, and how a jump is
 * named, run by `npm test`: the list is correct or absent, and no start is ever derived.
 */

const three = [
  { name: 'Förberedelser', start: 0 },
  { name: 'Majstången', start: 74 },
  { name: 'Dans', start: 301 },
]

describe('usableChapters', () => {
  it('gives the same array back for a valid list, and never reorders or drops a row', () => {
    assert.equal(usableChapters(three), three)
    assert.deepEqual(three.map((c) => c.name), ['Förberedelser', 'Majstången', 'Dans'])
  })

  it('does not need the first start to be 0', () => {
    const later = [{ name: 'A', start: 4 }, { name: 'B', start: 9.5 }]
    assert.equal(usableChapters(later), later)
  })

  it('accepts the empty name, the default chapter as the render recorded it', () => {
    const list = [{ name: '', start: 0 }, { name: 'Kvällen', start: 6.02 }]
    assert.equal(usableChapters(list), list)
  })

  it('is null for nothing, an empty list and a value that is not a list', () => {
    for (const raw of [null, undefined, [], {}, 'x', 3]) {
      assert.equal(usableChapters(raw), null, String(raw))
    }
  })

  it('is null for starts that do not strictly increase', () => {
    assert.equal(usableChapters([{ name: 'A', start: 5 }, { name: 'B', start: 4 }]), null)
    assert.equal(usableChapters([{ name: 'A', start: 5 }, { name: 'B', start: 5 }]), null)
    assert.equal(
      usableChapters([{ name: 'A', start: 1 }, { name: 'B', start: 9 }, { name: 'C', start: 3 }]),
      null,
    )
  })

  it('is null for a start that is not a finite, non-negative number', () => {
    for (const start of [-1, -0.001, NaN, Infinity, -Infinity, '5', null, undefined]) {
      assert.equal(usableChapters([{ name: 'A', start }]), null, String(start))
    }
  })

  it('is null for a name that is only spaces or not text', () => {
    for (const name of [' ', '   ', '\t', '\n', null, undefined, 3, {}]) {
      assert.equal(usableChapters([{ name, start: 0 }]), null, JSON.stringify(name))
    }
  })

  it('is null for a row that is not an object, and shows no part of a list with one bad row', () => {
    assert.equal(usableChapters([null]), null)
    assert.equal(usableChapters(['A']), null)
    assert.equal(usableChapters([{ name: 'A', start: 0 }, { name: ' ', start: 9 }]), null)
  })
})

describe('listedChapters', () => {
  it('is null for one usable chapter: nothing to jump between', () => {
    assert.equal(listedChapters([{ name: '', start: 0 }]), null)
  })

  it('is the array for two', () => {
    const two = three.slice(0, 2)
    assert.equal(listedChapters(two), two)
  })

  it('is null for a list that cannot be relied on, whatever its length', () => {
    assert.equal(listedChapters([{ name: 'A', start: 4 }, { name: 'B', start: 4 }]), null)
    assert.equal(listedChapters(null), null)
  })
})

describe('currentChapterIndex', () => {
  it('is null before the first start less the slack', () => {
    const later = [{ name: 'A', start: 4 }, { name: 'B', start: 9 }]
    assert.equal(currentChapterIndex(later, 0), null)
    assert.equal(currentChapterIndex(later, 3.93), null)
    assert.equal(currentChapterIndex(later, 3.94), 0)
  })

  it('is the first chapter at exactly 0 and at 0.5', () => {
    assert.equal(currentChapterIndex(three, 0), 0)
    assert.equal(currentChapterIndex(three, 0.5), 0)
  })

  it('changes at the start, and a frame short of it (60 ms) already counts as at it', () => {
    assert.equal(currentChapterIndex(three, 74), 1)
    assert.equal(currentChapterIndex(three, 74 - 0.06), 1)
    assert.equal(currentChapterIndex(three, 74 - 0.061), 0)
  })

  it('is exact for starts a float cannot hold', () => {
    const odd = [{ name: 'A', start: 0 }, { name: 'B', start: 6.02 }]
    assert.equal(currentChapterIndex(odd, 6.02 - 0.06), 1)
    assert.equal(currentChapterIndex(odd, 6.02 - 0.061), 0)
    // 0.062 - 0.06 is 0.0020000000000000018 in floating point: a position of 0.002 is still at the start
    const near = [{ name: 'A', start: 0 }, { name: 'B', start: 0.062 }]
    assert.equal(currentChapterIndex(near, 0.002), 1)
    assert.equal(currentChapterIndex(near, 0.001), 0)
  })

  it('is the last chapter past the end of the movie', () => {
    assert.equal(currentChapterIndex(three, 301), 2)
    assert.equal(currentChapterIndex(three, 99999), 2)
  })

  it('works for a single chapter and for a slack of 0', () => {
    assert.equal(currentChapterIndex([{ name: '', start: 0 }], 12), 0)
    assert.equal(currentChapterIndex(three, 73.99, 0), 0)
    assert.equal(currentChapterIndex(three, 74, 0), 1)
  })

  it('is null for a position that is not a number', () => {
    assert.equal(currentChapterIndex(three, NaN), null)
    assert.equal(currentChapterIndex(three, Infinity), null)
  })
})

describe('jumpLabel', () => {
  it('names the chapter by number, name and start', () => {
    assert.equal(jumpLabel(1, 'Majstången', 74), 'Jump to chapter 2, Majstången, at 1:14')
  })

  it('writes an hour-long start as h:mm:ss', () => {
    assert.equal(jumpLabel(3, 'Sent', 3675), 'Jump to chapter 4, Sent, at 1:01:15')
  })

  it('keeps a fraction of a second and leaves a comma in a name as it is', () => {
    assert.equal(jumpLabel(1, 'Kvällen, sent', 6.02), 'Jump to chapter 2, Kvällen, sent, at 0:06.02')
  })
})
