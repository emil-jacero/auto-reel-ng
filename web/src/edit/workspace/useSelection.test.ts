import assert from 'node:assert/strict'
import { test } from 'node:test'

import { escapeIsElsewhere } from './useSelection.ts'

test('Escape belongs to a field or an open dialog', () => {
  assert.equal(escapeIsElsewhere({ tagName: 'INPUT' } as unknown as EventTarget, false), true)
  assert.equal(escapeIsElsewhere({ tagName: 'TEXTAREA' } as unknown as EventTarget, false), true)
  assert.equal(escapeIsElsewhere({ tagName: 'DIV', isContentEditable: true } as unknown as EventTarget, false), true)
  assert.equal(escapeIsElsewhere({ tagName: 'BUTTON' } as unknown as EventTarget, true), true)
})

test('Escape on a button or the page clears the selection', () => {
  assert.equal(escapeIsElsewhere({ tagName: 'BUTTON' } as unknown as EventTarget, false), false)
  assert.equal(escapeIsElsewhere(null, false), false)
})
