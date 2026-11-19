/*
 * The clip menu's two pure rules (`clip-context-menu`, D3): what a keydown does while the menu has
 * focus, and where the menu goes on the window. `ui/Menu.tsx` listens, applies and measures; these
 * decide, so `menu.test.ts` checks every rule without a DOM.
 */

/** What a rule reads of a keydown. */
export type MenuPress = {
  key: string
  shiftKey: boolean
  ctrlKey: boolean
  altKey: boolean
  metaKey: boolean
}

/**
 * What the menu does with a key.
 * - `focus`: move focus to item `index`. `choose`: choose the focused item. `close`: close the menu
 *   and hand focus back. All three are `preventDefault`ed and `stopPropagation`ed.
 * - `pass`: a Ctrl or Cmd chord. Nothing is done with it, so Ctrl+S and Ctrl+Z reach the workspace.
 * - `keep`: any other key is `stopPropagation`ed, so no workspace or track key acts while the menu
 *   has focus, and `preventDefault`ed too unless `preventDefault` is false (F1 to F12, which keep
 *   the browser's own function).
 */
export type MenuKey =
  | { kind: 'focus'; index: number }
  | { kind: 'choose' }
  | { kind: 'close' }
  | { kind: 'pass' }
  | { kind: 'keep'; preventDefault: boolean }

const isSpace = (key: string) => key === ' ' || key === 'Spacebar'
const isFunctionKey = (key: string) => /^F([1-9]|1[0-2])$/.test(key)

/**
 * The rule for a keydown in the menu, with `count` items and focus on item `at` (-1: on none).
 * Up and Down wrap; Home and End go to the ends; Enter and Space choose; Escape, Tab and
 * Shift+Tab close. Any key with Alt held, and any with nothing to focus, is `keep` (so Alt+Left
 * cannot go back behind the menu).
 */
export function menuKey(press: MenuPress, count: number, at: number): MenuKey {
  if (press.ctrlKey || press.metaKey) return { kind: 'pass' }
  const { key } = press
  const keep: MenuKey = { kind: 'keep', preventDefault: !isFunctionKey(key) }
  if (press.altKey) return keep
  switch (key) {
    case 'ArrowDown':
      return count > 0 ? { kind: 'focus', index: at < 0 ? 0 : (at + 1) % count } : keep
    case 'ArrowUp': {
      const index = at < 0 ? count - 1 : (at - 1 + count) % count
      return count > 0 ? { kind: 'focus', index } : keep
    }
    case 'Home':
      return count > 0 ? { kind: 'focus', index: 0 } : keep
    case 'End':
      return count > 0 ? { kind: 'focus', index: count - 1 } : keep
    case 'Enter':
      return { kind: 'choose' }
    case 'Escape':
    case 'Tab':
      return { kind: 'close' }
    default:
      return isSpace(key) ? { kind: 'choose' } : keep
  }
}

export type Point = { x: number; y: number }
/** A rectangle by its edges: a `DOMRectReadOnly` is one. */
export type Box = { left: number; top: number; right: number; bottom: number }
export type Size = { width: number; height: number }

/** The least distance the menu keeps from the window's edges. */
export const MENU_MARGIN = 8
/** The gap between a block and the menu opened under or above it. */
export const MENU_GAP = 4

export type MenuPlace = { left: number; top: number; maxHeight: number }

/** `value` held within [`low`, `high`]; `low` wins when the range is empty. */
function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(value, high))
}

/**
 * Where the menu of `size` goes in a `view` (the window's inner size), as `position: fixed`
 * coordinates, and the tallest it may be before it scrolls within itself.
 * - At a point, the menu's corner is at the point. It flips left, or up, where it would come
 *   within 8 px of the window's edge, and is then clamped to 8 px.
 * - At a box, it goes under the box, start-aligned with a 4 px gap. It goes above instead when it
 *   does not fit below and there is more room above. It is clamped the same way.
 */
export function placeMenu(anchor: Point | Box, size: Size, view: Size): MenuPlace {
  const m = MENU_MARGIN
  const maxHeight = Math.max(0, view.height - 2 * m)
  const width = Math.min(size.width, Math.max(0, view.width - 2 * m))
  const height = Math.min(size.height, maxHeight)
  const left = (wanted: number) => clamp(wanted, m, view.width - m - width)
  const top = (wanted: number) => clamp(wanted, m, view.height - m - height)

  if ('left' in anchor) {
    const below = anchor.bottom + MENU_GAP
    const roomBelow = view.height - m - below
    const roomAbove = anchor.top - MENU_GAP - m
    const above = height > roomBelow && roomAbove > roomBelow
    return {
      left: left(anchor.left),
      top: top(above ? anchor.top - MENU_GAP - height : below),
      maxHeight,
    }
  }
  const flipLeft = anchor.x + width + m > view.width
  const flipUp = anchor.y + height + m > view.height
  return {
    left: left(flipLeft ? anchor.x - width : anchor.x),
    top: top(flipUp ? anchor.y - height : anchor.y),
    maxHeight,
  }
}
