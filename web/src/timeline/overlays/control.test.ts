import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { decideControl } from './control.ts'

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
