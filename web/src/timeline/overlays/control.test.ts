import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { analysisOf, decideControl } from './control.ts'
import type { Dismissals } from './Dismissals.ts'

/*
 * What Edit mode's binding gives the lane to decide with (`timeline-overlay-decisions`):
 * nothing in the read view, and in Edit mode the editor's own add, lock and live region.
 */

type Add = [string, { in: number; out: number }, string | undefined]

function binding(locked = false) {
  const added: Add[] = []
  const said: string[] = []
  return {
    added,
    said,
    editing: {
      listed: (identity: string) => (identity === 'a.mp4' ? [{ key: 'k1', in: 1, out: 2, reason: null, removed: false }] : []),
      onAdd: (identity: string, span: { in: number; out: number }, reason?: string) => {
        added.push([identity, span, reason])
      },
      locked,
      announce: (words: string) => {
        said.push(words)
      },
    },
  }
}

describe('decideControl', () => {
  it('gives the read view no decision', () => {
    assert.equal(decideControl(null), null)
  })

  it('hands an approval to the editor’s add once, with the same three arguments', () => {
    const { added, editing } = binding()
    const decide = decideControl(editing)
    assert.notEqual(decide, null)
    const span = { in: 0, out: 3.203 }
    decide?.onApprove('C0012.MP4', span, 'black')
    assert.equal(added.length, 1)
    assert.equal(added[0][0], 'C0012.MP4')
    assert.deepEqual(added[0][1], { in: 0, out: 3.203 })
    assert.equal(added[0][2], 'black')
  })

  it('passes a kind it does not know on as written', () => {
    const { added, editing } = binding()
    decideControl(editing)?.onApprove('a.mp4', { in: 1, out: 2 }, 'speech')
    assert.equal(added[0][2], 'speech')
  })

  it('has the editor’s lock and live region', () => {
    const open = binding(false)
    const shut = binding(true)
    assert.equal(decideControl(open.editing)?.locked, false)
    assert.equal(decideControl(shut.editing)?.locked, true)
    decideControl(open.editing)?.announce('Dismissed black frames.')
    assert.deepEqual(open.said, ['Dismissed black frames.'])
    assert.deepEqual(shut.said, [])
  })
})

describe('analysisOf', () => {
  const dismissals = {} as Dismissals
  const readView = { cuts: new Map([['a.mp4', [{ in: 5, out: 6 }]]]), failure: null, look: null }
  const reading = { cuts: null, failure: null, look: null }

  it('gives Edit mode’s lane a decision and the draft’s cuts, never "reading"', () => {
    const { added, editing } = binding()
    const control = analysisOf('ev', reading, editing, dismissals)
    assert.notEqual(control.decide, null)
    assert.equal(control.cutsState, 'ok')
    assert.deepEqual(control.cutsOf('a.mp4'), [
      { key: 'k1', in: 1, out: 2, reason: null, removed: false },
    ])
    control.decide?.onApprove('a.mp4', { in: 3, out: 4 }, 'freeze')
    assert.deepEqual(added, [['a.mp4', { in: 3, out: 4 }, 'freeze']])
  })

  it('gives the read view no decision and the cuts as read', () => {
    const control = analysisOf('ev', readView, null, dismissals)
    assert.equal(control.decide, null)
    assert.equal(control.cutsState, 'ok')
    assert.deepEqual(control.cutsOf('a.mp4'), [{ in: 5, out: 6 }])
    assert.deepEqual(control.cutsOf('b.mp4'), [])
  })

  it('says reading or unreadable in the read view while the cuts are not known', () => {
    assert.equal(analysisOf('ev', reading, null, dismissals).cutsState, 'reading')
    const failed = { cuts: null, failure: { cause: 'x', detail: null }, look: null }
    assert.equal(analysisOf('ev', failed, null, dismissals).cutsState, 'unreadable')
    assert.equal(analysisOf('ev', failed, null, dismissals).decide, null)
  })

  it('carries the event and the page’s dismissals', () => {
    const control = analysisOf('ev-7', readView, null, dismissals)
    assert.equal(control.eventId, 'ev-7')
    assert.equal(control.dismissals, dismissals)
  })
})
