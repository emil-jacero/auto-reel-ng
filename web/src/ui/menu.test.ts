import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { menuKey, placeMenu } from './menu.ts'
import type { MenuPress } from './menu.ts'

const press = (key: string, mods: Partial<MenuPress> = {}): MenuPress => ({
  key,
  shiftKey: false,
  ctrlKey: false,
  altKey: false,
  metaKey: false,
  ...mods,
})

describe('menuKey', () => {
  it('moves focus with Down and Up', () => {
    assert.deepEqual(menuKey(press('ArrowDown'), 5, 1), { kind: 'focus', index: 2 })
    assert.deepEqual(menuKey(press('ArrowUp'), 5, 3), { kind: 'focus', index: 2 })
  })
  it('wraps Up on the first item to the last', () => {
    assert.deepEqual(menuKey(press('ArrowUp'), 5, 0), { kind: 'focus', index: 4 })
  })
  it('wraps Down on the last item to the first', () => {
    assert.deepEqual(menuKey(press('ArrowDown'), 5, 4), { kind: 'focus', index: 0 })
  })
  it('starts from the ends when no item has focus', () => {
    assert.deepEqual(menuKey(press('ArrowDown'), 5, -1), { kind: 'focus', index: 0 })
    assert.deepEqual(menuKey(press('ArrowUp'), 5, -1), { kind: 'focus', index: 4 })
  })
  it('sends Home and End to the ends', () => {
    assert.deepEqual(menuKey(press('Home'), 5, 3), { kind: 'focus', index: 0 })
    assert.deepEqual(menuKey(press('End'), 5, 1), { kind: 'focus', index: 4 })
  })
  it('keeps the arrows, Home and End without items', () => {
    for (const key of ['ArrowDown', 'ArrowUp', 'Home', 'End']) {
      assert.deepEqual(menuKey(press(key), 0, -1), { kind: 'keep', preventDefault: true })
    }
  })
  it('chooses on Enter and Space', () => {
    assert.deepEqual(menuKey(press('Enter'), 5, 2), { kind: 'choose' })
    assert.deepEqual(menuKey(press(' '), 5, 2), { kind: 'choose' })
    assert.deepEqual(menuKey(press('Spacebar'), 5, 2), { kind: 'choose' })
  })
  it('closes on Escape, Tab and Shift+Tab', () => {
    assert.deepEqual(menuKey(press('Escape'), 5, 2), { kind: 'close' })
    assert.deepEqual(menuKey(press('Tab'), 5, 2), { kind: 'close' })
    assert.deepEqual(menuKey(press('Tab', { shiftKey: true }), 5, 2), { kind: 'close' })
  })
  it('passes Ctrl and Cmd chords', () => {
    assert.deepEqual(menuKey(press('s', { ctrlKey: true }), 5, 2), { kind: 'pass' })
    assert.deepEqual(menuKey(press('z', { metaKey: true }), 5, 2), { kind: 'pass' })
    assert.deepEqual(menuKey(press('Z', { ctrlKey: true, shiftKey: true }), 5, 2), { kind: 'pass' })
    assert.deepEqual(menuKey(press('Enter', { ctrlKey: true }), 5, 2), { kind: 'pass' })
  })
  it('keeps W, Right and Alt+Left, and takes them from the browser', () => {
    const keep = { kind: 'keep', preventDefault: true }
    assert.deepEqual(menuKey(press('w'), 5, 2), keep)
    assert.deepEqual(menuKey(press('ArrowRight'), 5, 2), keep)
    assert.deepEqual(menuKey(press('ArrowLeft', { altKey: true }), 5, 2), keep)
  })
  it('keeps F5 and leaves it to the browser', () => {
    assert.deepEqual(menuKey(press('F5'), 5, 2), { kind: 'keep', preventDefault: false })
    assert.deepEqual(menuKey(press('F12'), 5, 2), { kind: 'keep', preventDefault: false })
  })
  it('does not take Alt+Up or Alt+Enter for a menu key', () => {
    assert.deepEqual(menuKey(press('ArrowUp', { altKey: true }), 5, 2), {
      kind: 'keep',
      preventDefault: true,
    })
    assert.deepEqual(menuKey(press('Enter', { altKey: true }), 5, 2), {
      kind: 'keep',
      preventDefault: true,
    })
  })
})

describe('placeMenu at a point', () => {
  const size = { width: 200, height: 240 }
  const view = { width: 1280, height: 720 }

  it('puts the corner at the point when there is room', () => {
    const place = placeMenu({ x: 100, y: 100 }, size, view)
    assert.deepEqual(place, { left: 100, top: 100, maxHeight: 704 })
  })
  it('flips left for a point 20 px from the right edge', () => {
    const place = placeMenu({ x: 1260, y: 100 }, size, view)
    assert.equal(place.left, 1060)
    assert.ok(place.left + size.width <= view.width - 8)
  })
  it('flips up for a point near the bottom', () => {
    const place = placeMenu({ x: 100, y: 700 }, size, view)
    assert.equal(place.top, 460)
    assert.ok(place.top + size.height <= view.height - 8)
  })
  it('flips both ways in the corner', () => {
    assert.deepEqual(placeMenu({ x: 1270, y: 710 }, size, view), {
      left: 1070,
      top: 470,
      maxHeight: 704,
    })
  })
  it('keeps 8 px from the edges at a point nearer the corner than that', () => {
    const place = placeMenu({ x: 2, y: 3 }, size, view)
    assert.equal(place.left, 8)
    assert.equal(place.top, 8)
  })
  it('clamps to 8 px in a 320x568 view, with a maxHeight of 552', () => {
    const phone = { width: 320, height: 568 }
    const tall = { width: 400, height: 900 }
    const place = placeMenu({ x: 150, y: 300 }, tall, phone)
    assert.deepEqual(place, { left: 8, top: 8, maxHeight: 552 })
  })
  it('lies inside a 320x568 view for a menu that fits it', () => {
    const phone = { width: 320, height: 568 }
    const place = placeMenu({ x: 300, y: 560 }, { width: 192, height: 300 }, phone)
    assert.equal(place.left, 108)
    assert.equal(place.top, 260)
  })
})

describe('placeMenu at a box', () => {
  const size = { width: 200, height: 240 }
  const view = { width: 1280, height: 720 }
  const box = (left: number, top: number, width = 120, height = 40) => ({
    left,
    top,
    right: left + width,
    bottom: top + height,
  })

  it('goes under the box, start-aligned with a 4 px gap', () => {
    assert.deepEqual(placeMenu(box(300, 100), size, view), { left: 300, top: 144, maxHeight: 704 })
  })
  it('opens above a box with room only above it', () => {
    const place = placeMenu(box(300, 640), size, view)
    assert.equal(place.top, 640 - 4 - 240)
  })
  it('stays under when it fits below even though there is more room above', () => {
    const place = placeMenu(box(300, 400), size, view)
    assert.equal(place.top, 444)
  })
  it('goes above when it fits in neither and there is more room above', () => {
    const place = placeMenu(box(300, 500, 120, 40), { width: 200, height: 600 }, view)
    assert.equal(place.top, 8)
    assert.equal(place.maxHeight, 704)
  })
  it('goes under when it fits in neither and there is more room below', () => {
    const place = placeMenu(box(300, 100, 120, 40), { width: 200, height: 700 }, view)
    assert.equal(place.top, 720 - 8 - 700)
  })
  it('clamps a box that starts out of view, and one near the right edge', () => {
    assert.equal(placeMenu(box(-300, 100, 500), size, view).left, 8)
    assert.equal(placeMenu(box(1200, 100), size, view).left, 1280 - 8 - 200)
  })
})
