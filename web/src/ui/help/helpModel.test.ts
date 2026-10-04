import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { helpIds, panelAttributes, toggleAttributes } from './helpModel.ts'

describe('help ids and attributes', () => {
  const ids = helpIds(':r1:')

  it('has distinct ids derived from the section id', () => {
    assert.notEqual(ids.toggle, ids.panel)
    assert.ok(ids.toggle.startsWith(':r1:') && ids.panel.startsWith(':r1:'))
  })

  it('the toggle controls the panel and says whether it is open', () => {
    assert.deepEqual(toggleAttributes(ids, false), {
      id: ids.toggle,
      'aria-expanded': false,
      'aria-controls': ids.panel,
    })
    assert.equal(toggleAttributes(ids, true)['aria-expanded'], true)
  })

  it('the panel is hidden, not removed, while closed and is named by its toggle', () => {
    assert.equal(panelAttributes(ids, false).hidden, true)
    assert.equal(panelAttributes(ids, true).hidden, false)
    assert.equal(panelAttributes(ids, true)['aria-labelledby'], ids.toggle)
    assert.equal(panelAttributes(ids, true).id, ids.panel)
  })
})
