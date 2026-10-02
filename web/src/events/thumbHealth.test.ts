import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { THUMB_NOTE_AT, isUnavailable } from './thumbHealth.ts'

/*
 * When the page says previews are unavailable (`isUnavailable`), run by `npm test`:
 * at least three failures that share one cause, and unlike causes never add up.
 */

describe('isUnavailable', () => {
  it('needs three failures of one cause', () => {
    assert.equal(THUMB_NOTE_AT, 3)
    assert.equal(isUnavailable([]), false)
    assert.equal(isUnavailable(['none']), false)
    assert.equal(isUnavailable(['none', 'none']), false)
    assert.equal(isUnavailable(['none', 'none', 'none']), true)
    assert.equal(isUnavailable(['unreadable_disk', 'unreadable_disk', 'unreadable_disk', 'x']), true)
  })

  it('does not add up unlike causes', () => {
    assert.equal(isUnavailable(['unreadable_disk', 'none', 'unreadable_disk', 'none']), false)
    assert.equal(isUnavailable(['a', 'b', 'c', 'd']), false)
  })

  it('counts the threshold it is given', () => {
    assert.equal(isUnavailable(['none', 'none'], 2), true)
  })
})
