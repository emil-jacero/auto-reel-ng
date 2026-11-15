import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { lengthWords } from './clipLength.ts'

describe('a compact row’s length', () => {
  it('is the whole clip without cuts', () => {
    assert.equal(lengthWords(6.02, []), '0:06.02')
  })

  it('leaves out what the kept cuts cover, overlaps once', () => {
    const cuts = [
      { in: 1, out: 2.5 },
      { in: 2, out: 3 },
    ]
    assert.equal(lengthWords(10, cuts), '0:08')
  })

  it('counts a cut the save removes as kept footage', () => {
    assert.equal(lengthWords(10, [{ in: 0, out: 4, removed: true }]), '0:10')
  })

  it('clips a cut past the end to the clip', () => {
    assert.equal(lengthWords(5, [{ in: 4, out: 9 }]), '0:04')
  })

  it('is a dash when the duration is unknown', () => {
    for (const duration of [null, undefined, 0, -1, Number.NaN]) {
      assert.equal(lengthWords(duration, []), '—')
    }
  })
})
