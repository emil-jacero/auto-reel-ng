import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  clearState,
  inspectorTab,
  keepState,
  keptIn,
  keptSelection,
  NO_SELECTION,
  NOTHING,
  openState,
  sameSelection,
  selectState,
} from './selection.ts'
import { shownTab } from './inspectorTabs.ts'
import type { SelectionState } from './selection.ts'
import type { Selection, World } from './selection.ts'

const world: World = {
  clips: new Set(['s1710001.mp4', 's1710003.mp4']),
  cuts: new Map([
    [
      's1710001.mp4',
      [
        { key: 'r0', removed: false },
        { key: 'a1', removed: true },
      ],
    ],
  ]),
  chapters: new Set(['r0', 'r1']),
  suggestions: new Set(['s1|0|3.2|black']),
}

const all: Selection[] = [
  NO_SELECTION,
  { kind: 'clip', identity: 's1710003.mp4' },
  { kind: 'cut', identity: 's1710001.mp4', key: 'r0' },
  { kind: 'card', chapter: 'r1' },
  { kind: 'suggestion', id: 's1|0|3.2|black' },
]

test('each kind shows its tab, and a cut shows the clip tab', () => {
  assert.deepEqual(
    all.map(inspectorTab),
    ['event', 'clip', 'clip', 'card', 'suggestion'],
  )
})

test('a selection whose target stands is kept as it is', () => {
  for (const sel of all) assert.equal(keptSelection(sel, world), sel)
})

test('a clip that is gone ends the selection', () => {
  assert.deepEqual(keptSelection({ kind: 'clip', identity: 'missing.mp4' }, world), NO_SELECTION)
})

test('a cut that is gone, removed, or on a gone clip ends the selection', () => {
  assert.deepEqual(keptSelection({ kind: 'cut', identity: 's1710001.mp4', key: 'r9' }, world), NO_SELECTION)
  assert.deepEqual(keptSelection({ kind: 'cut', identity: 's1710001.mp4', key: 'a1' }, world), NO_SELECTION)
  assert.deepEqual(keptSelection({ kind: 'cut', identity: 'missing.mp4', key: 'r0' }, world), NO_SELECTION)
})

test('a card whose chapter is gone ends the selection', () => {
  assert.deepEqual(keptSelection({ kind: 'card', chapter: 'r5' }, world), NO_SELECTION)
})

test('a suggestion the read no longer lists ends the selection', () => {
  assert.deepEqual(keptSelection({ kind: 'suggestion', id: 'gone' }, world), NO_SELECTION)
})

test('nothing stays nothing', () => {
  assert.equal(keptSelection(NO_SELECTION, world), NO_SELECTION)
})

test('sameSelection compares by kind and target', () => {
    assert.equal(sameSelection(NO_SELECTION, { kind: 'none' }), true)
    assert.equal(sameSelection({ kind: 'cut', identity: 'a', key: '1' }, { kind: 'cut', identity: 'a', key: '1' }), true)
    assert.equal(sameSelection({ kind: 'cut', identity: 'a', key: '1' }, { kind: 'cut', identity: 'a', key: '2' }), false)
    assert.equal(sameSelection({ kind: 'card', chapter: 'x' }, { kind: 'suggestion', id: 'x' }), false)
})

test('keptIn judges only the kinds the part knows', () => {
    const card = { kind: 'card', chapter: 'Dag' } as const
    const mark = { kind: 'suggestion', id: 's' } as const
    assert.equal(keptIn(card, { suggestions: new Set() }), card)
    assert.equal(keptIn(card, { chapters: new Set(['Dag']) }), card)
    assert.deepEqual(keptIn(card, { chapters: new Set() }), NO_SELECTION)
    assert.deepEqual(keptIn(mark, { suggestions: new Set() }), NO_SELECTION)
    assert.equal(keptIn(mark, { chapters: new Set() }), mark)
})

const card = (chapter: string): Selection => ({ kind: 'card', chapter })
const clip = (identity: string): Selection => ({ kind: 'clip', identity })

test('selecting one thing ends the other, whatever the kinds', () => {
  for (const from of all) {
    for (const to of all) {
      const was: SelectionState = { sel: from, opened: null, again: 0 }
      const now = selectState(was, to)
      assert.deepEqual(now.sel, to)
    }
  }
  let state = selectState(NOTHING, clip('s1710003.mp4'))
  state = selectState(state, card('r1'))
  assert.deepEqual(state.sel, card('r1'))
  state = selectState(state, { kind: 'suggestion', id: 'x' })
  assert.equal(inspectorTab(state.sel), 'suggestion')
  assert.equal('chapter' in state.sel, false)
})

test('selecting the same target again changes nothing, except a clip counts the press', () => {
  const dag = selectState(NOTHING, card('Dag 2'))
  assert.equal(selectState(dag, card('Dag 2')), dag)
  const mark = selectState(NOTHING, { kind: 'suggestion', id: 's' })
  assert.equal(selectState(mark, { kind: 'suggestion', id: 's' }), mark)
  const one = selectState(NOTHING, clip('a'))
  const again = selectState(one, clip('a'))
  assert.deepEqual(again.sel, one.sel)
  assert.equal(again.again, one.again + 1)
})

test('opening an already selected card counts as a press, so the inspector shows the card', () => {
  const sel = selectState(NOTHING, card('Dag 2'))
  const opened = openState(sel, 'Dag 2')
  assert.equal(opened.again, sel.again + 1)
  const picked = { tab: 'event' as const, sel: sel.sel, again: sel.again }
  assert.equal(shownTab(picked, sel.sel, sel.again), 'event')
  assert.equal(shownTab(picked, opened.sel, opened.again), 'card')
})

test('open selects and opens the card, keeping the same state for the same request', () => {
  const opened = openState(NOTHING, '', 'event')
  assert.deepEqual(opened.sel, card(''))
  assert.deepEqual(opened.opened, { tab: 'event' })
  // Every request is a new one: the editor takes focus again.
  assert.equal(openState(opened, '', 'event').again, opened.again + 1)
  // Opened again without a tab, the editor picks its own.
  assert.deepEqual(openState(opened, '').opened, { tab: null })
  assert.deepEqual(openState(selectState(NOTHING, card('Dag 2')), 'Dag 2').opened, { tab: null })
  // Opening another card moves the selection.
  assert.deepEqual(openState(opened, 'Dag 3').sel, card('Dag 3'))
  // Opening replaces a selection of another kind.
  assert.deepEqual(openState(selectState(NOTHING, clip('a')), 'Dag 2').sel, card('Dag 2'))
})

test('selecting another thing ends the request; select never opens', () => {
  const opened = openState(NOTHING, 'Dag 2')
  assert.equal(selectState(opened, card('Dag 3')).opened, null)
  assert.equal(selectState(opened, { kind: 'cut', identity: 'a', key: 'r0' }).opened, null)
  assert.equal(selectState(NOTHING, card('Dag 3')).opened, null)
  assert.equal(selectState(opened, card('Dag 2')), opened)
})

test('clear and a vanished target end the selection and its request', () => {
  const opened = openState(NOTHING, 'Dag 2')
  assert.deepEqual(clearState(opened).sel, NO_SELECTION)
  assert.equal(clearState(opened).opened, null)
  assert.equal(clearState(NOTHING), NOTHING)
  assert.deepEqual(keepState(opened, { chapters: new Set(['']) }).sel, NO_SELECTION)
  assert.equal(keepState(opened, { chapters: new Set(['Dag 2']) }), opened)
  // A part that says nothing about the kind keeps it.
  assert.equal(keepState(opened, { suggestions: new Set() }), opened)
  assert.equal(keepState(NOTHING, { chapters: new Set() }), NOTHING)
})
