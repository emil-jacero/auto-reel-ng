import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { DRAG_SLOP, dragsGroup, pastSlop, pointerDrags, rowDrags } from './binDrag.ts'

describe('pastSlop', () => {
  it('is a click up to the slop and a drag beyond it', () => {
    assert.equal(pastSlop(0, 0), false)
    assert.equal(pastSlop(DRAG_SLOP, 0), false)
    assert.equal(pastSlop(2, 2), false)
    assert.equal(pastSlop(0, -DRAG_SLOP - 0.5), true)
    assert.equal(pastSlop(3, 3), true)
    assert.equal(pastSlop(40, 0), true)
  })
})

describe('rowDrags', () => {
  it('lets only an ignored clip on disk drag', () => {
    assert.equal(rowDrags({ group: 'ignored', onDisk: true }), true)
    assert.equal(rowDrags({ group: 'listed', onDisk: true }), false)
    assert.equal(rowDrags({ group: 'listed', onDisk: false }), false)
    assert.equal(rowDrags({ group: 'removed', onDisk: false }), false)
    assert.equal(rowDrags({ group: 'ignored', onDisk: false }), false)
  })
})

describe('pointerDrags', () => {
  it('drags with a mouse or a pen, not a finger', () => {
    assert.equal(pointerDrags('mouse'), true)
    assert.equal(pointerDrags('pen'), true)
    assert.equal(pointerDrags('touch'), false)
  })
})

describe('dragsGroup', () => {
  it('is a group only for a row of a selection of several', () => {
    assert.equal(dragsGroup(new Set(['a', 'b']), 'a'), true)
    assert.equal(dragsGroup(new Set(['a', 'b']), 'b'), true)
    assert.equal(dragsGroup(new Set(['a']), 'a'), false)
    assert.equal(dragsGroup(new Set<string>(), 'a'), false)
    assert.equal(dragsGroup(new Set(['a', 'b']), 'c'), false)
  })
})
