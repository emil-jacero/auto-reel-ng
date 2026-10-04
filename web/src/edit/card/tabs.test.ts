import assert from 'node:assert/strict'
import { test } from 'node:test'

import { TAB_NAME, openingTab, tabAfterKey, tabLabel } from './tabs.ts'

test('arrow keys move between the tabs, Home and End jump, other keys are not the tabs\'', () => {
  assert.equal(tabAfterKey('card', 'ArrowRight'), 'event')
  assert.equal(tabAfterKey('event', 'ArrowRight'), 'card')
  assert.equal(tabAfterKey('card', 'ArrowLeft'), 'event')
  assert.equal(tabAfterKey('event', 'ArrowLeft'), 'card')
  assert.equal(tabAfterKey('event', 'Home'), 'card')
  assert.equal(tabAfterKey('card', 'End'), 'event')
  assert.equal(tabAfterKey('card', 'Tab'), null)
  assert.equal(tabAfterKey('card', 'a'), null)
})

test('a tab with a problem says so in its label', () => {
  assert.equal(tabLabel('event', { card: 0, event: 0 }), TAB_NAME.event)
  assert.equal(
    tabLabel('event', { card: 0, event: 1 }),
    'All title cards in this event, 1 problem',
  )
  assert.equal(tabLabel('card', { card: 2, event: 0 }), 'This title card, 2 problems')
})

test('the dialog opens on the first tab with a problem the service named, else the card', () => {
  assert.equal(openingTab({ card: 0, event: 0 }), 'card')
  assert.equal(openingTab({ card: 0, event: 1 }), 'event')
  assert.equal(openingTab({ card: 1, event: 1 }), 'card')
})
