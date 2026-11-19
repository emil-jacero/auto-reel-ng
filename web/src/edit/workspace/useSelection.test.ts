import assert from 'node:assert/strict'
import { test } from 'node:test'

import { escapeIsElsewhere, returnTarget } from './useSelection.ts'

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

test('Escape belongs to the open Keyboard shortcuts list', () => {
  assert.equal(escapeIsElsewhere({ tagName: 'BUTTON' } as unknown as EventTarget, false, true), true)
  assert.equal(escapeIsElsewhere(null, false, true), true)
  assert.equal(escapeIsElsewhere(null, false, false), false)
})

test('Escape from the card editor returns focus to the opener, then the button, the block, the heading', () => {
  const shown = (element: { on: boolean }) => element.on
  const opener = { on: true }
  const button = { on: true }
  const block = { on: true }
  const heading = { on: true }
  assert.equal(returnTarget([opener, button, block, heading], shown), opener)
  opener.on = false
  assert.equal(returnTarget([opener, button, block, heading], shown), button)
  button.on = false
  assert.equal(returnTarget([opener, button, block, heading], shown), block)
  // The chapter was deleted meanwhile: its button and block are gone, the heading stays.
  block.on = false
  assert.equal(returnTarget([opener, null, undefined, heading], shown), heading)
  heading.on = false
  assert.equal(returnTarget([opener, button, block, heading], shown), null)
})

test('Escape from a block-selected card (no opener) returns focus to the block, not the row button', () => {
  const shown = (element: { on: boolean }) => element.on
  const button = { on: true }
  const block = { on: true }
  const heading = { on: true }
  // As `leave` orders them when `reveal` recorded no opener.
  assert.equal(returnTarget([block, button, heading], shown), block)
  // In Prepare there is no block: the row's button is next.
  assert.equal(returnTarget([undefined, button, heading], shown), button)
})
