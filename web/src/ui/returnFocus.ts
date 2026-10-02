/**
 * Whether closing a dialog may hand focus back to the control that opened it:
 * only while focus is still the dialog's, that is on no control (`null` or the
 * document body) or inside the dialog. Focus the operator has already moved to a
 * control outside it (Escape, then Save within the same task) stays put. Generic
 * over the node type, so the rule is tested with stand-ins and needs no DOM.
 */
export function mayReturnFocus<T extends object>(
  active: T | null,
  dialog: { contains(other: T): boolean },
  body: T,
): boolean {
  return active === null || active === body || dialog.contains(active)
}
