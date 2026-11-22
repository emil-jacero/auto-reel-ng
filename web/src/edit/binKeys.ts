import { menuOpenKey } from '../timeline/clipMenu.ts'
import { pressOf } from './workspace/selection.ts'
import type { Press } from './workspace/selection.ts'

/*
 * The clip bin's list keys (`plain-clip-bin` D2), as one pure rule: what a keydown on a focused
 * row asks for. The list is one keyboard stop with a roving focus: Up, Down, Home and End move
 * it (and select nothing), Enter selects as a press on a clip block does, and the menu keys open
 * the clip's menu. No DOM, no React.
 */

/** What a rule reads of a keydown. */
export type ListPress = {
  key: string
  shiftKey: boolean
  ctrlKey: boolean
  altKey: boolean
  metaKey: boolean
}

/** Where a move of focus goes. */
export type ListStep = 'previous' | 'next' | 'first' | 'last'

export type ListCommand =
  | { kind: 'move'; to: ListStep }
  /** Selects the focused clip: alone, added or taken out (Ctrl or Cmd), or a range (Shift). */
  | { kind: 'select'; press: Press }
  | { kind: 'menu' }

const STEPS: Record<string, ListStep> = {
  ArrowUp: 'previous',
  ArrowDown: 'next',
  Home: 'first',
  End: 'last',
}

const isSpace = (key: string) => key === ' ' || key === 'Spacebar'

/**
 * What a keydown on a row of the list does, or null to leave it to the browser and the workspace.
 *
 * - The menu keys (Shift+F10 alone, ContextMenu): `menu`.
 * - Up, Down, Home and End with no modifier: `move`. A chord is the browser's.
 * - Enter selects, taking Ctrl, Cmd and Shift as a click does (`pressOf`); Alt makes it null.
 * - Space with no Ctrl, Cmd or Alt selects the clip alone, but only while `spaceYields` is false:
 *   after a pointer press the workspace's listener plays on Space (`blockYieldsSpace`), so the
 *   list does not take it.
 */
export function listKey(press: ListPress, spaceYields = false): ListCommand | null {
  if (menuOpenKey(press)) {
    return { kind: 'menu' }
  }
  const { key, ctrlKey, altKey, metaKey, shiftKey } = press
  const step = STEPS[key]
  if (step !== undefined) {
    return ctrlKey || altKey || metaKey || shiftKey ? null : { kind: 'move', to: step }
  }
  if (key === 'Enter') {
    return altKey ? null : { kind: 'select', press: pressOf(press) }
  }
  if (isSpace(key)) {
    if (spaceYields || ctrlKey || altKey || metaKey) {
      return null
    }
    return { kind: 'select', press: 'alone' }
  }
  return null
}

/**
 * The identity a `step` from `from` lands on in `order` (the rows top to bottom), or null for an
 * empty list. It stops at the ends (no wrap), as a listbox does; a `from` the list does not
 * hold starts from the top.
 */
export function stepTo(order: readonly string[], from: string | null, to: ListStep): string | null {
  if (order.length === 0) {
    return null
  }
  const at = from === null ? -1 : order.indexOf(from)
  switch (to) {
    case 'first':
      return order[0] as string
    case 'last':
      return order[order.length - 1] as string
    case 'previous':
      return order[Math.max(at < 0 ? 0 : at - 1, 0)] as string
    case 'next':
      return order[Math.min(at + 1, order.length - 1)] as string
  }
}
