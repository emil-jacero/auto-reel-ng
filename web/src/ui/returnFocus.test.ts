import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { mayReturnFocus } from './returnFocus.ts'

/** A stand-in node: `contains` is true for itself and for its listed children. */
function node(...children: object[]) {
  const self = { contains: (other: object | null) => other === self || children.includes(other!) }
  return self
}

describe('mayReturnFocus', () => {
  const body = node()
  const inside = node()
  const dialog = node(inside)
  const outside = node()

  it('returns focus when nothing has it', () => {
    assert.equal(mayReturnFocus(null, dialog, body), true)
  })
  it('returns focus when it is on the body', () => {
    assert.equal(mayReturnFocus(body, dialog, body), true)
  })
  it('returns focus when it is on the dialog itself', () => {
    assert.equal(mayReturnFocus(dialog, dialog, body), true)
  })
  it('returns focus when it is on a control inside the dialog', () => {
    assert.equal(mayReturnFocus(inside, dialog, body), true)
  })
  it('leaves focus on a control the operator moved to outside the dialog', () => {
    assert.equal(mayReturnFocus(outside, dialog, body), false)
  })
})
