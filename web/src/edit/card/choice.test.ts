import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { BACKGROUND_OPTIONS, inheritedTag, optionState } from './choice.ts'

describe('optionState', () => {
  it('shows the inherited option while the field is unset', () => {
    assert.equal(optionState('video', null, 'video'), 'inherited')
    assert.equal(optionState('black', null, 'video'), 'none')
  })

  it('shows the own value chosen, and the inherited one no longer', () => {
    assert.equal(optionState('black', 'black', 'video'), 'chosen')
    assert.equal(optionState('video', 'black', 'video'), 'none')
  })

  it('an unknown inherited value shows no option', () => {
    assert.equal(optionState('black', null, null), 'none')
    assert.equal(optionState('video', null, undefined), 'none')
    assert.equal(optionState('video', null, 'sideways'), 'none')
  })

  it('the tag names the layer', () => {
    assert.equal(inheritedTag('Event style'), '(event style)')
    assert.equal(inheritedTag('Project default'), '(project default)')
  })

  it('the Background helper copy', () => {
    assert.deepEqual(
      BACKGROUND_OPTIONS.map((o) => `${o.label}: ${o.words}`),
      ['Black: text on black, before the chapter', 'Video: text over the start of the chapter’s first clip'],
    )
  })
})
