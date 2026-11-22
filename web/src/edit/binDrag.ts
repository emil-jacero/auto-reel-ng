import type { BinRow } from './binList.ts'

/*
 * The bin's drag (`plain-clip-bin` D2): only the row of an ignored clip on disk drags, onto the
 * track, to include it. A press that moves less than the slop is a click. No DOM, no React.
 */

/** How far a press moves, in CSS pixels, before it is a drag and no longer a click. */
export const DRAG_SLOP = 3

/** Whether a press that moved `dx`, `dy` has become a drag. */
export function pastSlop(dx: number, dy: number): boolean {
  return Math.hypot(dx, dy) > DRAG_SLOP
}

/** Whether a row starts a drag: an ignored clip on disk. Every other row only selects. */
export function rowDrags(row: Pick<BinRow, 'group' | 'onDisk'>): boolean {
  return row.group === 'ignored' && row.onDisk
}

/** The pointers that drag: a mouse or a pen. A finger scrolls the list instead. */
export function pointerDrags(pointerType: string): boolean {
  return pointerType === 'mouse' || pointerType === 'pen'
}
