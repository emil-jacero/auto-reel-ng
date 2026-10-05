import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { analysisOf, decideControl } from './control.ts'
import type { AnalysisBinding } from '../../analysis/useEventAnalysis.ts'
import type { Dismissals } from './Dismissals.ts'

/*
 * What Edit mode's binding gives the lane to decide with (`timeline-overlay-decisions`): the
 * editor's own add, lock and live region. The Timeline is Edit mode's only, so there is no
 * read-view lane without a decision (`timeline-zoom-slider`).
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
  const page = { read: { status: 'reading' } } as unknown as AnalysisBinding

  it('gives the lane a decision and the draft’s cuts', () => {
    const { added, editing } = binding()
    const control = analysisOf('ev', page, editing, dismissals)
    assert.deepEqual(control.cutsOf('a.mp4'), [
      { key: 'k1', in: 1, out: 2, reason: null, removed: false },
    ])
    assert.deepEqual(control.cutsOf('b.mp4'), [])
    control.decide.onApprove('a.mp4', { in: 3, out: 4 }, 'freeze')
    assert.deepEqual(added, [['a.mp4', { in: 3, out: 4 }, 'freeze']])
  })

  it('carries the event and the page’s dismissals', () => {
    const control = analysisOf('ev-7', page, binding().editing, dismissals)
    assert.equal(control.eventId, 'ev-7')
    assert.equal(control.dismissals, dismissals)
    // The page's one read: the Timeline reads nothing itself.
    assert.equal(control.binding, page)
  })
})
