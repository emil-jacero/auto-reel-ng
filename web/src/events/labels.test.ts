import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Staleness } from '../api/events'
import { REASON_NOTE, chapterHeading } from './labels.ts'

/*
 * The event page's note for a reason (`REASON_NOTE`), run by `npm test`: the words stay
 * the service's own, and a verdict without both file names gets the sentence without them.
 */

function verdict(patch: Partial<Staleness>): Staleness {
  return { stale: true, reasons: ['output_renamed'], renamed_from: null, output_name: null, ...patch }
}

function words(parts: ReturnType<NonNullable<(typeof REASON_NOTE)['output_renamed']>>): string {
  return parts.map((part) => (typeof part === 'string' ? part : `<${part.code}>`)).join('')
}

describe('the output_renamed note', () => {
  const note = REASON_NOTE.output_renamed
  assert.notEqual(note, null)

  it('names the new file and the old one, each apart from the words', () => {
    const parts = note!(verdict({ renamed_from: 'a - Old.mp4', output_name: 'a - New.mp4' }))
    assert.deepEqual(
      parts.filter((part) => typeof part !== 'string'),
      [{ code: 'a - New.mp4' }, { code: 'a - Old.mp4' }],
    )
    assert.equal(
      words(parts),
      'The next render saves the movie as <a - New.mp4>. The movie <a - Old.mp4> stays on disk.',
    )
  })

  it('says the same without file names when either is missing', () => {
    const plain =
      'The next render saves the movie under its new name. The movie under its old name stays on disk.'
    for (const patch of [
      {},
      { renamed_from: 'a - Old.mp4' },
      { output_name: 'a - New.mp4' },
    ] satisfies Partial<Staleness>[]) {
      assert.equal(words(note!(verdict(patch))), plain)
    }
  })

  it('is the only reason with a note', () => {
    const withNote = Object.entries(REASON_NOTE).filter(([, value]) => value !== null)
    assert.deepEqual(
      withNote.map(([reason]) => reason),
      ['output_renamed'],
    )
  })
})

describe('chapterHeading', () => {
  it('writes the default chapter as Main beside a named one and as Clips alone', () => {
    assert.equal(chapterHeading('', true), 'Main')
    assert.equal(chapterHeading('', false), 'Clips')
  })

  it('returns a name as it is', () => {
    assert.equal(chapterHeading('Majstången', true), 'Majstången')
    assert.equal(chapterHeading('Main', false), 'Main')
  })
})
