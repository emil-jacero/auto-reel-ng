import assert from 'node:assert/strict'
import { test } from 'node:test'

import { shownClip } from './binPlayer.ts'
import type { Selection } from './workspace/selection.ts'

const listed = new Set(['a', 'b', 'c', 'gone'])
const disk = new Set(['a', 'b', 'c'])
const onDisk = (id: string): boolean => disk.has(id)

const none: Selection = { kind: 'none' }
const clip = (identity: string): Selection => ({ kind: 'clip', identity })
const cut = (identity: string): Selection => ({ kind: 'cut', identity, key: 'r0' })
const card: Selection = { kind: 'card', chapter: 'r0' }
const suggestion: Selection = { kind: 'suggestion', id: 's1|0|3.2|black' }

test('one clip shows itself', () => {
  assert.equal(shownClip(clip('a'), null, listed, onDisk), 'a')
  assert.equal(shownClip(clip('b'), 'a', listed, onDisk), 'b')
})

test('several clips show the one pressed last, not the first or the anchor', () => {
  const sel: Selection = { kind: 'clips', identities: ['a', 'b', 'c'], anchor: 'a', last: 'c' }
  assert.equal(shownClip(sel, 'b', listed, onDisk), 'c')
})

test('a cut shows its clip', () => {
  assert.equal(shownClip(cut('b'), 'a', listed, onDisk), 'b')
})

test('a card, a suggestion and no selection keep the clip shown', () => {
  for (const sel of [card, suggestion, none]) {
    assert.equal(shownClip(sel, 'a', listed, onDisk), 'a')
  }
})

test('with nothing shown before, a card, a suggestion and no selection show none', () => {
  for (const sel of [card, suggestion, none]) {
    assert.equal(shownClip(sel, null, listed, onDisk), null)
  }
})

test('a selected clip that is not on disk shows none, and does not fall back to the old one', () => {
  assert.equal(shownClip(clip('gone'), 'a', listed, onDisk), null)
  const sel: Selection = { kind: 'clips', identities: ['a', 'gone'], anchor: 'a', last: 'gone' }
  assert.equal(shownClip(sel, 'a', listed, onDisk), null)
  assert.equal(shownClip(cut('gone'), 'a', listed, onDisk), null)
})

test('an ignored clip is on disk, so it plays', () => {
  // Ignored clips are listed and on disk; only the disk decides.
  assert.equal(shownClip(clip('c'), null, listed, onDisk), 'c')
})

test('the shown clip is dropped once the event stops listing it', () => {
  const without = new Set(['b', 'c'])
  for (const sel of [card, suggestion, none]) {
    assert.equal(shownClip(sel, 'a', without, onDisk), null)
  }
})

test('the shown clip is dropped once it leaves the disk', () => {
  const lost = (id: string): boolean => id !== 'a' && onDisk(id)
  for (const sel of [card, suggestion, none]) {
    assert.equal(shownClip(sel, 'a', listed, lost), null)
  }
})

test('a clip that was listed but is missing now is dropped even when still listed', () => {
  assert.equal(shownClip(none, 'gone', listed, onDisk), null)
})
