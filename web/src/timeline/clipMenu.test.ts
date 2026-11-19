import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Selection } from '../edit/workspace/selection.ts'
import { clipMenu, focusAfter, MENU_LOCKED, menuOpenKey, menuSelects } from './clipMenu.ts'
import type { ClipMenuFacts } from './clipMenu.ts'

const facts: ClipMenuFacts = { locked: false, cutWhy: null, posterWhy: null, others: [] }
const main = { key: 'main', name: 'Main' }
const evening = { key: 'k2', name: 'Kvällen' }

describe('clipMenu', () => {
  it('lists rotate, cut and poster, then ignore, in four groups with no reasons', () => {
    const { note, items } = clipMenu(facts)
    assert.equal(note, null)
    assert.deepEqual(
      items.map((i) => [i.label, i.group, i.why]),
      [
        ['Rotate left', 0, null],
        ['Rotate right', 0, null],
        ['Cut at playhead', 1, null],
        ['Use frame as poster', 1, null],
        ['Ignore clip', 3, null],
      ],
    )
    assert.deepEqual(
      items.map((i) => i.action),
      [
        { kind: 'rotate', way: 'left' },
        { kind: 'rotate', way: 'right' },
        { kind: 'cut' },
        { kind: 'poster' },
        { kind: 'ignore' },
      ],
    )
  })

  it('lists one Move to per other chapter, in the chapters’ order, between poster and ignore', () => {
    const { items } = clipMenu({ ...facts, others: [main, evening] })
    assert.deepEqual(
      items.map((i) => [i.label, i.group]),
      [
        ['Rotate left', 0],
        ['Rotate right', 0],
        ['Cut at playhead', 1],
        ['Use frame as poster', 1],
        ['Move to Main', 2],
        ['Move to Kvällen', 2],
        ['Ignore clip', 3],
      ],
    )
    assert.deepEqual(items[4]?.action, { kind: 'move', chapter: 'main', name: 'Main' })
    assert.deepEqual(items[5]?.action, { kind: 'move', chapter: 'k2', name: 'Kvällen' })
  })

  it('lists no Move to when only one chapter is drawn', () => {
    const { items } = clipMenu(facts)
    assert.equal(items.some((i) => i.action.kind === 'move'), false)
  })

  it('puts the cut and poster reasons on their own items only', () => {
    const cut = clipMenu({ ...facts, cutWhy: 'no cut' }).items
    assert.deepEqual(
      cut.map((i) => i.why),
      [null, null, 'no cut', null, null],
    )
    const poster = clipMenu({ ...facts, others: [main], posterWhy: 'no frame' }).items
    assert.deepEqual(
      poster.map((i) => i.why),
      [null, null, null, 'no frame', null, null],
    )
  })

  it('while locked sets the note and makes every item unavailable under it', () => {
    const { note, items } = clipMenu({
      locked: true,
      cutWhy: 'no cut',
      posterWhy: 'no frame',
      others: [main],
    })
    assert.equal(note, MENU_LOCKED)
    assert.equal(items.length, 6)
    for (const i of items) assert.equal(i.why, MENU_LOCKED)
  })
})

describe('menuSelects', () => {
  const clip = 'a.mp4'
  it('is false for the clip and for a cut of it', () => {
    assert.equal(menuSelects({ kind: 'clip', identity: clip }, clip), false)
    assert.equal(menuSelects({ kind: 'cut', identity: clip, key: 'c1' }, clip), false)
  })
  it('is true for nothing, another clip or its cut, a card and a suggestion', () => {
    const others: Selection[] = [
      { kind: 'none' },
      { kind: 'clip', identity: 'b.mp4' },
      { kind: 'cut', identity: 'b.mp4', key: 'c1' },
      { kind: 'card', chapter: 'main' },
      { kind: 'suggestion', id: 's1' },
    ]
    for (const s of others) assert.equal(menuSelects(s, clip), true)
  })
})

describe('focusAfter', () => {
  it('gives the next clip, else the previous one', () => {
    assert.equal(focusAfter(['a', 'b', 'c'], 'a'), 'b')
    assert.equal(focusAfter(['a', 'b', 'c'], 'b'), 'c')
    assert.equal(focusAfter(['a', 'b', 'c'], 'c'), 'b')
  })
  it('gives null for a lone clip and for one that is not drawn', () => {
    assert.equal(focusAfter(['a'], 'a'), null)
    assert.equal(focusAfter(['a', 'b'], 'x'), null)
    assert.equal(focusAfter([], 'a'), null)
  })
})

describe('menuOpenKey', () => {
  const press = (key: string, mods: Partial<Parameters<typeof menuOpenKey>[0]> = {}) => ({
    key,
    shiftKey: false,
    ctrlKey: false,
    altKey: false,
    metaKey: false,
    ...mods,
  })
  it('is the Menu key and Shift+F10', () => {
    assert.equal(menuOpenKey(press('ContextMenu')), true)
    assert.equal(menuOpenKey(press('F10', { shiftKey: true })), true)
  })
  it('is not F10 alone, nor Shift+F10 with Ctrl, Alt or Cmd, nor another key', () => {
    assert.equal(menuOpenKey(press('F10')), false)
    for (const mod of ['ctrlKey', 'altKey', 'metaKey'] as const) {
      assert.equal(menuOpenKey(press('F10', { shiftKey: true, [mod]: true })), false)
    }
    assert.equal(menuOpenKey(press('Enter', { shiftKey: true })), false)
  })
})
