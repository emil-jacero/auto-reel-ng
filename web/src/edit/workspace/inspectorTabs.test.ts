import assert from 'node:assert/strict'
import { test } from 'node:test'

import { INSPECTOR_TAB_NAME, inspectorTabAfterKey, titleCardsWords } from './inspectorTabs.ts'

test('the inspector tabs are named Event and Cut', () => {
  assert.equal(INSPECTOR_TAB_NAME.event, 'Event')
  assert.equal(INSPECTOR_TAB_NAME.cut, 'Cut')
})

test('arrow keys move between the inspector tabs, Home and End jump, other keys are not theirs', () => {
  assert.equal(inspectorTabAfterKey('event', 'ArrowRight'), 'cut')
  assert.equal(inspectorTabAfterKey('cut', 'ArrowRight'), 'event')
  assert.equal(inspectorTabAfterKey('event', 'ArrowLeft'), 'cut')
  assert.equal(inspectorTabAfterKey('cut', 'ArrowLeft'), 'event')
  assert.equal(inspectorTabAfterKey('cut', 'Home'), 'event')
  assert.equal(inspectorTabAfterKey('event', 'End'), 'cut')
  assert.equal(inspectorTabAfterKey('event', 'Tab'), null)
  assert.equal(inspectorTabAfterKey('event', 'Enter'), null)
})

test('the Event tab says whether title cards are on, and never guesses without an answer', () => {
  const answer = { enabled: true, source: 'default' }
  assert.equal(titleCardsWords({ answer, error: null, on: true }), 'Title cards are on for this event.')
  assert.equal(titleCardsWords({ answer, error: null, on: false }), 'Title cards are off for this event.')
  assert.equal(
    titleCardsWords({ answer: null, error: 'The service did not answer.', on: true }),
    'Whether title cards are on is not known. The service did not answer.',
  )
  assert.equal(titleCardsWords({ answer: null, error: null, on: false }), 'Whether title cards are on is not known.')
})
