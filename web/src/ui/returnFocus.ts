/**
 * Whether closing a dialog may hand focus back to the control that opened it:
 * only while focus is still the dialog's, that is on no control (`null` or the
 * document body) or inside the dialog. Focus the operator has already moved to a
 * control outside it (Escape, then Save within the same task) stays put.
 */
export function mayReturnFocus(
  active: Element | null,
  dialog: Element,
  body: Element,
): boolean {
  return active === null || active === body || dialog.contains(active)
}
