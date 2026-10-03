import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createClipPreviews } from './previews.ts'

/*
 * The editor's clip previews as a store (`previews.ts`), run by `npm test`: the operator's
 * choice of the original over a clip's preview copy (Play original), which lives and dies
 * with the preview and the kept playhead.
 */

function counted() {
  const previews = createClipPreviews()
  let calls = 0
  previews.subscribe(() => {
    calls += 1
  })
  return { previews, calls: () => calls }
}

describe('the original chosen over the preview copy', () => {
  it('is off by default and reads back what was set', () => {
    const { previews } = counted()
    assert.equal(previews.original('a.mp4'), false)
    previews.show('a.mp4', 'toggle')
    previews.setOriginal('a.mp4', true)
    assert.equal(previews.original('a.mp4'), true)
    assert.equal(previews.original('b.mp4'), false)
    previews.setOriginal('a.mp4', false)
    assert.equal(previews.original('a.mp4'), false)
  })

  it('is forgotten when its preview closes, and not by closing another clip', () => {
    const { previews } = counted()
    previews.show('a.mp4', 'toggle')
    previews.setOriginal('a.mp4', true)
    previews.hide('b.mp4')
    assert.equal(previews.original('a.mp4'), true)
    previews.hide('a.mp4')
    assert.equal(previews.original('a.mp4'), false)
    previews.show('a.mp4', 'toggle')
    assert.equal(previews.original('a.mp4'), false)
  })

  it('is forgotten when another clip is shown, as the kept playhead is', () => {
    const { previews } = counted()
    previews.show('a.mp4', 'toggle')
    previews.setOriginal('a.mp4', true)
    previews.keepPlayhead('a.mp4', 2.5)
    previews.show('b.mp4', 'thumb')
    assert.equal(previews.original('a.mp4'), false)
    assert.equal(previews.playhead('a.mp4'), undefined)
  })

  it('survives showing the same clip again and a remount (the playhead stays with it)', () => {
    const { previews } = counted()
    previews.show('a.mp4', 'toggle')
    previews.setOriginal('a.mp4', true)
    previews.keepPlayhead('a.mp4', 2.5)
    previews.show('a.mp4', 'thumb')
    assert.equal(previews.original('a.mp4'), true)
    assert.equal(previews.playhead('a.mp4'), 2.5)
  })

  it('is forgotten with every preview by hideAll', () => {
    const { previews } = counted()
    previews.show('a.mp4', 'toggle')
    previews.setOriginal('a.mp4', true)
    previews.setOriginal('b.mp4', true)
    previews.hideAll()
    assert.equal(previews.original('a.mp4'), false)
    assert.equal(previews.original('b.mp4'), false)
  })

  it('notifies once per real change, never for setting the same value', () => {
    const { previews, calls } = counted()
    previews.setOriginal('a.mp4', false)
    assert.equal(calls(), 0)
    previews.setOriginal('a.mp4', true)
    assert.equal(calls(), 1)
    previews.setOriginal('a.mp4', true)
    assert.equal(calls(), 1)
    previews.setOriginal('a.mp4', false)
    assert.equal(calls(), 2)
  })
})
