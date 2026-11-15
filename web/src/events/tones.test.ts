import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { CLIP_STATUS_LOOK, EXCLUDED_LOOK } from './tones.ts'

describe('the clip status looks', () => {
  it('give Included, New, Missing, Ignored and Excluded five different icons', () => {
    // The bin's rows show the status as its icon alone (State is never shown by color alone).
    const icons = [...Object.values(CLIP_STATUS_LOOK), EXCLUDED_LOOK].map((look) => look.icon)
    assert.equal(icons.length, 5)
    assert.equal(new Set(icons).size, 5)
  })
})
