import { useEffect, useRef } from 'react'

import { Icon } from './Icon'
import type { IconName } from './Icon'
import { dismissToast, pauseToasts, useToasts } from './toast'
import type { Toast, ToastTone } from './toast'

const TONE_ICON: Record<ToastTone, IconName> = {
  success: 'check',
  info: 'info',
  error: 'alert-triangle',
}

function ToastItem({ toast }: { toast: Toast }) {
  return (
    <div className="toast" data-tone={toast.tone}>
      <Icon name={TONE_ICON[toast.tone]} />
      <div className="toast-body">
        <p className="toast-message">{toast.message}</p>
        {toast.action !== undefined && (
          <a className="toast-action" href={toast.action.href}>
            {toast.action.label}
          </a>
        )}
      </div>
      <button
        type="button"
        className="btn btn-ghost btn-icon toast-dismiss"
        onClick={() => dismissToast(toast.id)}
      >
        <Icon name="x" label="Dismiss" />
      </button>
    </div>
  )
}

/**
 * Where toasts appear; the shell renders it once. Two live containers are
 * always present, so a toast added to one is announced: `role="status"`
 * (polite) for success and info, `role="alert"` for errors. A pointer or focus
 * inside the region pauses the auto-dismiss clocks.
 *
 * Its bottom offset follows a custom property (see `.toast-region`), 0 unless
 * a page sets it, so a page with a sticky bar at the bottom can lift the toasts
 * above it.
 */
export function ToastRegion() {
  const toasts = useToasts()
  const regionRef = useRef<HTMLDivElement>(null)
  const pointerInside = useRef(false)

  const updatePause = () => {
    const region = regionRef.current
    const focusInside = region !== null && region.contains(document.activeElement)
    pauseToasts(pointerInside.current || focusInside)
  }

  // A dismissed toast takes its focused button with it, and no blur fires.
  useEffect(updatePause, [toasts])

  return (
    <div
      ref={regionRef}
      className="toast-region"
      onPointerEnter={() => {
        pointerInside.current = true
        updatePause()
      }}
      onPointerLeave={() => {
        pointerInside.current = false
        updatePause()
      }}
      onFocus={updatePause}
      onBlur={(event) => {
        // Focus moving to another control in the region keeps it paused.
        if (!event.currentTarget.contains(event.relatedTarget)) {
          pauseToasts(pointerInside.current)
        }
      }}
    >
      <div role="alert" className="toast-stack">
        {toasts
          .filter((shown) => shown.tone === 'error')
          .map((shown) => (
            <ToastItem key={shown.id} toast={shown} />
          ))}
      </div>
      <div role="status" className="toast-stack">
        {toasts
          .filter((shown) => shown.tone !== 'error')
          .map((shown) => (
            <ToastItem key={shown.id} toast={shown} />
          ))}
      </div>
    </div>
  )
}
