import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  clearState,
  consumeState,
  inspectorTab,
  keepState,
  keptIn,
  keptSelection,
  lastClip,
  NO_SELECTION,
  NOTHING,
  openState,
  pressClip,
  sameSelection,
  selectedClips,
  selectionWords,
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

test('a request that asks for no focus still counts as a press and shows the card', () => {
  const shown = openState(NOTHING, 'Dag 2', undefined, false)
  assert.deepEqual(shown.opened, { tab: null, focus: false })
  assert.equal(shown.again, 1)
  assert.deepEqual(shown.sel, card('Dag 2'))
})

test('open selects and opens the card, keeping the same state for the same request', () => {
  const opened = openState(NOTHING, '', 'event')
  assert.deepEqual(opened.sel, card(''))
  assert.deepEqual(opened.opened, { tab: 'event', focus: true })
  // Every request is a new one: the editor takes focus again.
  assert.equal(openState(opened, '', 'event').again, opened.again + 1)
  // Opened again without a tab, the editor picks its own.
  assert.deepEqual(openState(opened, '').opened, { tab: null, focus: true })
  assert.deepEqual(openState(selectState(NOTHING, card('Dag 2')), 'Dag 2').opened, { tab: null, focus: true })
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

test('a handled request ends and the selection stays, so a remount does not ask again', () => {
  const asked = openState(NOTHING, 'Day one', 'card')
  const done = consumeState(asked)
  assert.deepEqual(done.sel, { kind: 'card', chapter: 'Day one' })
  assert.equal(done.opened, null)
  assert.equal(done.again, asked.again)
  assert.equal(consumeState(done), done)
  // Asking again (the button pressed once more) is a new request.
  assert.notEqual(openState(done, 'Day one').opened, null)
})

// --- A selection of several clips (clip-multi-select, design D1 and D6) ---

const order = ['a', 'b', 'c', 'd', 'e']
const set = (identities: string[], anchor: string, last: string): Selection => ({
  kind: 'clips',
  identities,
  anchor,
  last,
})
const nameOf = (identity: string) => `${identity}.mp4`
const others: Selection[] = [
  NO_SELECTION,
  { kind: 'cut', identity: 'a', key: 'r0' },
  { kind: 'card', chapter: 'r1' },
  { kind: 'suggestion', id: 's' },
]

test('an alone press selects the clip only, from every kind', () => {
  for (const from of [...others, clip('b'), set(['a', 'b', 'c'], 'a', 'c')]) {
    assert.deepEqual(pressClip(from, 'd', 'alone', order), clip('d'))
  }
})

test('a toggle press adds a clip to one, to a set, and starts a set from another kind', () => {
  assert.deepEqual(pressClip(clip('a'), 'c', 'toggle', order), set(['a', 'c'], 'c', 'c'))
  assert.deepEqual(
    pressClip(set(['a', 'c'], 'c', 'c'), 'b', 'toggle', order),
    set(['a', 'c', 'b'], 'b', 'b'),
  )
  for (const from of others) {
    assert.deepEqual(pressClip(from, 'c', 'toggle', order), clip('c'))
  }
})

test('a toggle press takes a selected clip out, and normalises to one clip, then to none', () => {
  assert.deepEqual(
    pressClip(set(['a', 'b', 'c'], 'c', 'c'), 'b', 'toggle', order),
    set(['a', 'c'], 'b', 'b'),
  )
  assert.deepEqual(pressClip(set(['a', 'c'], 'c', 'c'), 'a', 'toggle', order), clip('c'))
  assert.deepEqual(pressClip(clip('a'), 'a', 'toggle', order), NO_SELECTION)
})

test('a range press runs from the anchor to the clip, either way, and keeps the anchor', () => {
  assert.deepEqual(pressClip(clip('b'), 'd', 'range', order), set(['b', 'c', 'd'], 'b', 'd'))
  assert.deepEqual(pressClip(clip('d'), 'b', 'range', order), set(['b', 'c', 'd'], 'd', 'b'))
  // A second range from the same anchor replaces the first rather than growing it.
  const first = pressClip(clip('b'), 'e', 'range', order)
  assert.deepEqual(pressClip(first, 'c', 'range', order), set(['b', 'c'], 'b', 'c'))
  // The anchor after a toggle is the toggled clip.
  const toggled = pressClip(clip('a'), 'c', 'toggle', order)
  assert.deepEqual(pressClip(toggled, 'e', 'range', order), set(['c', 'd', 'e'], 'c', 'e'))
})

test('a range press on the anchor itself is that clip alone', () => {
  assert.deepEqual(pressClip(clip('c'), 'c', 'range', order), clip('c'))
})

test('a range from nothing, a cut, a card or a suggestion is the clip alone', () => {
  for (const from of others) {
    assert.deepEqual(pressClip(from, 'c', 'range', order), clip('c'))
  }
})

test('a range runs across a chapter edge, as its order is the drawn order', () => {
  // Main: a b; Kvällen: c d. The track draws them in this one order.
  assert.deepEqual(pressClip(clip('b'), 'c', 'range', order), set(['b', 'c'], 'b', 'c'))
  assert.deepEqual(pressClip(clip('a'), 'd', 'range', order), set(['a', 'b', 'c', 'd'], 'a', 'd'))
})

test('a range whose anchor left the order, or a clip outside it, is the clip alone', () => {
  assert.deepEqual(pressClip(clip('gone'), 'c', 'range', order), clip('c'))
  assert.deepEqual(pressClip(set(['gone', 'a'], 'gone', 'a'), 'c', 'range', order), clip('c'))
  assert.deepEqual(pressClip(clip('b'), 'stranger', 'range', order), clip('stranger'))
})

test('selectedClips and lastClip read every kind', () => {
  assert.deepEqual(selectedClips(NO_SELECTION), [])
  assert.deepEqual(selectedClips(clip('a')), ['a'])
  assert.deepEqual(selectedClips(set(['a', 'c'], 'a', 'c')), ['a', 'c'])
  for (const sel of others) {
    assert.deepEqual(selectedClips(sel), [])
    assert.equal(lastClip(sel), null)
  }
  assert.equal(lastClip(clip('a')), 'a')
  assert.equal(lastClip(set(['a', 'c', 'b'], 'b', 'b')), 'b')
})

test('a set shows the clip tab', () => {
  assert.equal(inspectorTab(set(['a', 'b'], 'a', 'b')), 'clip')
})

test('keptSelection keeps the clips the event still lists, and normalises what is left', () => {
  const clips = new Set(['a', 'b', 'c'])
  const w: World = { ...world, clips }
  const whole = set(['a', 'b'], 'a', 'b')
  assert.equal(keptSelection(whole, w), whole)
  // One of three left: the rest stay, the last clip moves off the one that left.
  assert.deepEqual(
    keptSelection(set(['a', 'b', 'x'], 'a', 'x'), w),
    set(['a', 'b'], 'a', 'b'),
  )
  assert.deepEqual(keptSelection(set(['a', 'b', 'x'], 'a', 'b'), w), set(['a', 'b'], 'a', 'b'))
  // One left is a clip, none left is nothing.
  assert.deepEqual(keptSelection(set(['a', 'x', 'y'], 'a', 'y'), w), clip('a'))
  assert.deepEqual(keptSelection(set(['x', 'y'], 'x', 'y'), w), NO_SELECTION)
})

test('keptIn judges a set only when the part knows the clips', () => {
  const sel = set(['a', 'b', 'c'], 'a', 'c')
  assert.equal(keptIn(sel, { chapters: new Set() }), sel)
  assert.deepEqual(keptIn(sel, { clips: new Set(['a', 'c']) }), set(['a', 'c'], 'a', 'c'))
  assert.deepEqual(keptIn(sel, { clips: new Set() }), NO_SELECTION)
})

test('keepState trims a set and keeps it, and clears it when none is left', () => {
  const was = selectState(NOTHING, set(['a', 'b', 'c'], 'a', 'c'))
  const trimmed = keepState(was, { clips: new Set(['a', 'b']) })
  assert.deepEqual(trimmed.sel, set(['a', 'b'], 'a', 'b'))
  assert.deepEqual(keepState(was, { clips: new Set(['c']) }).sel, clip('c'))
  assert.deepEqual(keepState(was, { clips: new Set() }).sel, NO_SELECTION)
  assert.equal(keepState(was, { clips: new Set(['a', 'b', 'c']) }), was)
})

test('sameSelection compares a set by its clips, anchor and last clip', () => {
  const a = set(['a', 'b'], 'a', 'b')
  assert.equal(sameSelection(a, set(['a', 'b'], 'a', 'b')), true)
  assert.equal(sameSelection(a, set(['b', 'a'], 'a', 'b')), false)
  assert.equal(sameSelection(a, set(['a', 'b'], 'b', 'b')), false)
  assert.equal(sameSelection(a, set(['a', 'c'], 'a', 'c')), false)
  assert.equal(sameSelection(a, clip('a')), false)
  assert.equal(sameSelection(clip('a'), a), false)
})

test('a set is replaced by another selection, and selecting it again changes nothing', () => {
  const state = selectState(NOTHING, set(['a', 'b'], 'a', 'b'))
  assert.equal(selectState(state, set(['a', 'b'], 'a', 'b')), state)
  assert.deepEqual(selectState(state, card('r1')).sel, card('r1'))
  assert.deepEqual(selectState(state, clip('a')).sel, clip('a'))
})

test('the words of a set: its count, and the clip added or taken out', () => {
  const two = set(['a', 'c'], 'c', 'c')
  const three = set(['a', 'c', 'e'], 'e', 'e')
  assert.equal(selectionWords(clip('a'), two, nameOf), 'c.mp4 added. 2 clips selected.')
  assert.equal(selectionWords(two, three, nameOf), 'e.mp4 added. 3 clips selected.')
  assert.equal(selectionWords(three, set(['a', 'e'], 'c', 'c'), nameOf), 'c.mp4 taken out. 2 clips selected.')
})

test('a range or a set from another kind says only the count, once', () => {
  assert.equal(selectionWords(clip('b'), set(['b', 'c', 'd'], 'b', 'd'), nameOf), '3 clips selected.')
  assert.equal(selectionWords(NO_SELECTION, set(['a', 'b'], 'a', 'b'), nameOf), '2 clips selected.')
  assert.equal(selectionWords(card('r1'), set(['a', 'b'], 'a', 'b'), nameOf), '2 clips selected.')
  // A range that changes a set by more than one clip.
  assert.equal(
    selectionWords(set(['a', 'b'], 'a', 'b'), set(['a', 'b', 'c', 'd'], 'a', 'd'), nameOf),
    '4 clips selected.',
  )
  // The same count with other clips is a new set.
  assert.equal(
    selectionWords(set(['a', 'b'], 'a', 'b'), set(['b', 'c'], 'b', 'c'), nameOf),
    '2 clips selected.',
  )
})

test('taking one clip out of a set of two names it, and says one clip is left', () => {
  const two = set(['a', 'c'], 'c', 'c')
  assert.equal(selectionWords(two, clip('c'), nameOf), 'a.mp4 taken out. 1 clip selected.')
  assert.equal(selectionWords(two, clip('a'), nameOf), 'c.mp4 taken out. 1 clip selected.')
  // The Ctrl+click that does it, end to end.
  assert.equal(
    selectionWords(two, pressClip(two, 'a', 'toggle', ['a', 'b', 'c']), nameOf),
    'a.mp4 taken out. 1 clip selected.',
  )
  // A press on another clip replaces the set: nothing is taken out.
  assert.equal(selectionWords(two, clip('b'), nameOf), null)
  // A larger set that collapses to one clip, or the last clip going, says nothing.
  assert.equal(selectionWords(set(['a', 'b', 'c'], 'c', 'c'), clip('a'), nameOf), null)
  assert.equal(selectionWords(clip('a'), NO_SELECTION, nameOf), null)
})

test('a change to one clip, to another kind, or to nothing new keeps today\'s words: none', () => {
  const two = set(['a', 'c'], 'c', 'c')
  assert.equal(selectionWords(clip('a'), clip('b'), nameOf), null)
  assert.equal(selectionWords(two, NO_SELECTION, nameOf), null)
  assert.equal(selectionWords(two, card('r1'), nameOf), null)
  // The same clips with another anchor say nothing.
  assert.equal(selectionWords(two, set(['a', 'c'], 'a', 'a'), nameOf), null)
  assert.equal(selectionWords(two, two, nameOf), null)
})
