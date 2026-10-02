import { Children, isValidElement, useEffect, useId, useRef } from 'react'
import type { ReactNode, RefObject } from 'react'

import { mayReturnFocus } from './returnFocus'
import { enterModal } from './toast'

/** Whether `child` is an element with the class `name`. */
function hasClass(child: ReactNode, name: string): boolean {
  if (!isValidElement<{ className?: unknown }>(child)) {
    return false
  }
  const { className } = child.props
  return typeof className === 'string' && className.split(/\s+/).includes(name)
}

/** The `.dialog-fields` form and the `.dialog-actions` row: not the dialog's description. */
function isOutsideDescription(child: ReactNode): boolean {
  return hasClass(child, 'dialog-fields') || hasClass(child, 'dialog-actions')
}

/**
 * A modal dialog over the native `<dialog>` and `showModal()`: focus stays
 * inside it, Escape cancels, and it sits in the top layer, all without script.
 *
 * - `open` drives it. Opening records the focused element, and closing returns
 *   focus there when it is still in the document and focus is still the dialog's
 *   (inside it, or on no control): focus the operator has already moved to a
 *   control outside it (Escape, then Save at once) is left where it is.
 * - While it is open, the toasts' auto-dismiss clocks wait (`enterModal`), and
 *   the toast region lifts itself above it, so a notification is seen.
 * - `initialFocus` is the control to focus first — the caller's safe action.
 *   Without it the first focusable child gets focus (native `showModal()`).
 *   React's autofocus prop cannot do this: it focuses at commit, while the
 *   dialog is still closed, so the call does nothing.
 * - `onClose` means the operator dismissed it: Escape, or a close the browser
 *   forces. A close this component starts itself (`open` turning false, or an
 *   unmount) does not call it. Under StrictMode the simulated unmount's close
 *   queues a `close` event that fires after the remount has reopened the
 *   dialog; the guard keeps it from closing a dialog that mounted open.
 *
 * `children` are the body and a `.dialog-actions` row of buttons, with a
 * `.dialog-fields` form between them when the dialog asks for input. The body,
 * every child but those two, is the dialog's accessible description
 * (`aria-describedby`), so its consequence is read when it opens even though
 * focus goes straight to a button or a field; the fields and the row follow it,
 * so a long list of choices is never read out as the description.
 */
export function Dialog({
  open,
  title,
  onClose,
  initialFocus,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  initialFocus?: RefObject<HTMLElement | null>
  children: ReactNode
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const bodyId = useId()
  // Set before a close this component starts; the next `close` event clears it.
  const closingItself = useRef(false)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!open || dialog === null) {
      return
    }
    const opener = document.activeElement
    if (!dialog.open) {
      dialog.showModal()
    }
    const leaveModal = enterModal()
    const first = initialFocus?.current
    if (first != null && first.isConnected) {
      first.focus()
    }
    return () => {
      // Read before `close()`, which may itself move focus.
      const active = document.activeElement
      if (dialog.open) {
        closingItself.current = true
        dialog.close()
      }
      leaveModal()
      if (
        opener instanceof HTMLElement &&
        opener.isConnected &&
        mayReturnFocus<Node>(active, dialog, document.body)
      ) {
        opener.focus()
      }
    }
  }, [open, initialFocus])

  const parts = Children.toArray(children)
  const body = parts.filter((part) => !isOutsideDescription(part))
  const fields = parts.filter((part) => hasClass(part, 'dialog-fields'))
  const actions = parts.filter((part) => hasClass(part, 'dialog-actions'))

  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      aria-labelledby={titleId}
      aria-describedby={body.length > 0 ? bodyId : undefined}
      onClose={() => {
        if (closingItself.current) {
          closingItself.current = false
          return
        }
        onCloseRef.current()
      }}
    >
      <h2 id={titleId} className="dialog-title">
        {title}
      </h2>
      <div id={bodyId} className="dialog-body">
        {body}
      </div>
      {fields}
      {actions}
    </dialog>
  )
}
