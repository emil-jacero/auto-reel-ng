import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { NO_POSTER, pageCoverWords, rowCoverWords } from './cover.ts'

describe('the cover words', () => {
  it('names the event in a row cover and its placeholder', () => {
    assert.deepEqual(rowCoverWords('Kalas'), {
      alt: 'Poster of Kalas',
      none: 'No poster for Kalas',
    })
  })

  it('says on the page whether the frame is the default or a chosen one', () => {
    assert.equal(pageCoverWords('Kalas', { source: 'event' }).caption, 'Chosen frame')
    assert.equal(pageCoverWords('Kalas', { source: 'event' }).alt, 'Poster of Kalas, a chosen frame')
    assert.equal(pageCoverWords('Kalas', { source: 'default' }).caption, 'Default: first clip')
    assert.equal(
      pageCoverWords('Kalas', { source: 'default' }).alt,
      'Poster of Kalas, the default frame, the first clip',
    )
  })

  it('says there is no poster for an event that plays no clip', () => {
    const words = pageCoverWords('Kalas', null)
    assert.equal(words.caption, NO_POSTER)
    assert.equal(words.none, 'No poster for Kalas')
  })
})
