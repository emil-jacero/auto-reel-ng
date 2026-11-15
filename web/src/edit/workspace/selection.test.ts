import assert from 'node:assert/strict'
import { test } from 'node:test'

import { inspectorTab, keptIn, keptSelection, NO_SELECTION, sameSelection } from './selection.ts'
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

test('a new selection replaces the old: the one value holds a single kind', () => {
  let sel: Selection = { kind: 'clip', identity: 's1710003.mp4' }
  sel = { kind: 'card', chapter: 'r1' }
  assert.equal(sel.kind, 'card')
  assert.equal(inspectorTab(sel), 'card')
  sel = { kind: 'suggestion', id: 'x' }
  assert.equal(inspectorTab(sel), 'suggestion')
  assert.equal('chapter' in sel, false)
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
