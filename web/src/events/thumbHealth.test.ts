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
    assert.equal(isUnavailable(['service']), false)
    assert.equal(isUnavailable(['service', 'service']), false)
    assert.equal(isUnavailable(['service', 'service', 'service']), true)
    assert.equal(isUnavailable(['other', 'other', 'other', 'x']), true)
  })

  it('does not add up unlike causes', () => {
    assert.equal(isUnavailable(['other', 'service', 'other', 'service']), false)
    assert.equal(isUnavailable(['a', 'b', 'c', 'd']), false)
  })

  it('counts the threshold it is given', () => {
    assert.equal(isUnavailable(['service', 'service'], 2), true)
  })
})
