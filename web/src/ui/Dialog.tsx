import { useEffect, useId, useRef } from 'react'
import type { ReactNode, RefObject } from 'react'

/**
 * A modal dialog over the native `<dialog>` and `showModal()`: focus stays
 * inside it, Escape cancels, and it sits in the top layer, all without script.
 *
 * - `open` drives it. Opening records the focused element, and closing returns
 *   focus there when it is still in the document.
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
 * `children` are the body and the action buttons.
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
    const first = initialFocus?.current
    if (first != null && first.isConnected) {
      first.focus()
    }
    return () => {
      if (dialog.open) {
        closingItself.current = true
        dialog.close()
      }
      if (opener instanceof HTMLElement && opener.isConnected) {
        opener.focus()
      }
    }
  }, [open, initialFocus])

  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      aria-labelledby={titleId}
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
      {children}
    </dialog>
  )
}
