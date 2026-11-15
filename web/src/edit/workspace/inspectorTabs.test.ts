import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  INSPECTOR_TABS,
  INSPECTOR_TAB_NAME,
  inspectorTabAfterKey,
  shownTab,
  titleCardsWords,
} from './inspectorTabs.ts'
import type { PickedTab } from './inspectorTabs.ts'
import { NO_SELECTION } from './selection.ts'
import type { Selection } from './selection.ts'

const clip: Selection = { kind: 'clip', identity: 'a.mp4' }

test('the inspector tabs are Clip, Title card, Suggestion and Event, in that order', () => {
  assert.deepEqual(
    INSPECTOR_TABS.map((id) => INSPECTOR_TAB_NAME[id]),
    ['Clip', 'Title card', 'Suggestion', 'Event'],
  )
})

test('arrow keys move between the inspector tabs and wrap, Home and End jump, other keys are not theirs', () => {
  assert.equal(inspectorTabAfterKey('clip', 'ArrowRight'), 'card')
  assert.equal(inspectorTabAfterKey('event', 'ArrowRight'), 'clip')
  assert.equal(inspectorTabAfterKey('clip', 'ArrowLeft'), 'event')
  assert.equal(inspectorTabAfterKey('suggestion', 'ArrowLeft'), 'card')
  assert.equal(inspectorTabAfterKey('suggestion', 'Home'), 'clip')
  assert.equal(inspectorTabAfterKey('clip', 'End'), 'event')
  assert.equal(inspectorTabAfterKey('event', 'Tab'), null)
  assert.equal(inspectorTabAfterKey('event', 'Enter'), null)
})

test('with no pick the tab is the selection’s', () => {
  assert.equal(shownTab(null, NO_SELECTION, 0), 'event')
  assert.equal(shownTab(null, clip, 0), 'clip')
  assert.equal(shownTab(null, { kind: 'cut', identity: 'a.mp4', key: 'k' }, 0), 'clip')
  assert.equal(shownTab(null, { kind: 'card', chapter: 'Dag 2' }, 0), 'card')
  assert.equal(shownTab(null, { kind: 'suggestion', id: 's1' }, 0), 'suggestion')
})

test('a hand-picked tab stays while the same selection stands', () => {
  const picked: PickedTab = { tab: 'event', sel: clip, again: 0 }
  assert.equal(shownTab(picked, { kind: 'clip', identity: 'a.mp4' }, 0), 'event')
})

test('the next selection picks the tab again, and so does a press on the selected clip', () => {
  const picked: PickedTab = { tab: 'event', sel: clip, again: 0 }
  assert.equal(shownTab(picked, { kind: 'clip', identity: 'b.mp4' }, 0), 'clip')
  assert.equal(shownTab(picked, { kind: 'card', chapter: 'Dag 2' }, 0), 'card')
  assert.equal(shownTab(picked, NO_SELECTION, 0), 'event')
  assert.equal(shownTab({ tab: 'card', sel: clip, again: 0 }, clip, 1), 'clip')
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
