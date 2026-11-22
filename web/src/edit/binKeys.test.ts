import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { listKey, stepTo } from './binKeys.ts'
import type { ListPress } from './binKeys.ts'

const press = (key: string, mods: Partial<Omit<ListPress, 'key'>> = {}): ListPress => ({
  key,
  shiftKey: false,
  ctrlKey: false,
  altKey: false,
  metaKey: false,
  ...mods,
})

describe('listKey', () => {
  it('moves focus with Up, Down, Home and End, and selects nothing', () => {
    assert.deepEqual(listKey(press('ArrowUp')), { kind: 'move', to: 'previous' })
    assert.deepEqual(listKey(press('ArrowDown')), { kind: 'move', to: 'next' })
    assert.deepEqual(listKey(press('Home')), { kind: 'move', to: 'first' })
    assert.deepEqual(listKey(press('End')), { kind: 'move', to: 'last' })
  })

  it('leaves a chord on a movement key to the browser', () => {
    for (const mods of [{ ctrlKey: true }, { altKey: true }, { metaKey: true }, { shiftKey: true }]) {
      for (const key of ['ArrowUp', 'ArrowDown', 'Home', 'End']) {
        assert.equal(listKey(press(key, mods)), null, `${key} ${JSON.stringify(mods)}`)
      }
    }
  })

  it('selects alone on Enter, adds on Ctrl or Cmd+Enter and ranges on Shift+Enter', () => {
    assert.deepEqual(listKey(press('Enter')), { kind: 'select', press: 'alone' })
    assert.deepEqual(listKey(press('Enter', { ctrlKey: true })), { kind: 'select', press: 'toggle' })
    assert.deepEqual(listKey(press('Enter', { metaKey: true })), { kind: 'select', press: 'toggle' })
    assert.deepEqual(listKey(press('Enter', { shiftKey: true })), { kind: 'select', press: 'range' })
    // Ctrl and Cmd win over Shift, as for a click.
    assert.deepEqual(
      listKey(press('Enter', { ctrlKey: true, shiftKey: true })),
      { kind: 'select', press: 'toggle' },
    )
    assert.equal(listKey(press('Enter', { altKey: true })), null)
  })

  it('selects alone on Space reached by keyboard, and yields it after a pointer press', () => {
    assert.deepEqual(listKey(press(' ')), { kind: 'select', press: 'alone' })
    assert.deepEqual(listKey(press(' ', { shiftKey: true })), { kind: 'select', press: 'alone' })
    assert.deepEqual(listKey(press('Spacebar')), { kind: 'select', press: 'alone' })
    assert.equal(listKey(press(' '), true), null)
    assert.equal(listKey(press(' ', { ctrlKey: true })), null)
    assert.equal(listKey(press(' ', { altKey: true })), null)
    assert.equal(listKey(press(' ', { metaKey: true })), null)
  })

  it('opens the menu on Shift+F10 alone and on the Menu key', () => {
    assert.deepEqual(listKey(press('F10', { shiftKey: true })), { kind: 'menu' })
    assert.deepEqual(listKey(press('ContextMenu')), { kind: 'menu' })
    assert.equal(listKey(press('F10')), null)
    assert.equal(listKey(press('F10', { shiftKey: true, ctrlKey: true })), null)
  })

  it('answers no other key', () => {
    for (const key of ['a', 'Tab', 'Escape', 'ArrowLeft', 'ArrowRight', 'PageDown', 'Delete', 'q']) {
      assert.equal(listKey(press(key)), null, key)
    }
  })
})

describe('stepTo', () => {
  const order = ['a', 'b', 'c']
  it('steps one row and stops at the ends', () => {
    assert.equal(stepTo(order, 'b', 'previous'), 'a')
    assert.equal(stepTo(order, 'b', 'next'), 'c')
    assert.equal(stepTo(order, 'a', 'previous'), 'a')
    assert.equal(stepTo(order, 'c', 'next'), 'c')
  })

  it('goes to the first and the last row', () => {
    assert.equal(stepTo(order, 'b', 'first'), 'a')
    assert.equal(stepTo(order, 'b', 'last'), 'c')
  })

  it('starts from the top when the row is not in the list, and gives none for an empty list', () => {
    assert.equal(stepTo(order, 'gone', 'next'), 'a')
    assert.equal(stepTo(order, null, 'next'), 'a')
    assert.equal(stepTo(order, 'gone', 'previous'), 'a')
    assert.equal(stepTo([], 'a', 'next'), null)
  })
})
