import { useCallback, useEffect, useRef } from 'react'

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
 * above it. The region's own height is published on <html> as
 * `--toast-region-h` (removed when empty); the page's bottom scroll padding
 * adds it, so a control focused by keyboard never scrolls under a toast.
 */
export function ToastRegion() {
  const toasts = useToasts()
  const regionRef = useRef<HTMLDivElement>(null)
  const pointerInside = useRef(false)

  const updatePause = useCallback(() => {
    const region = regionRef.current
    const focusInside = region !== null && region.contains(document.activeElement)
    pauseToasts(pointerInside.current || focusInside)
  }, [])

  // Hover is read from where the pointer arrives, not from enter/leave pairs:
  // a toast dismissed under the pointer disappears without any leave event.
  useEffect(() => {
    const onOver = (event: PointerEvent) => {
      const region = regionRef.current
      const inside = region !== null && event.target instanceof Node && region.contains(event.target)
      if (inside !== pointerInside.current) {
        pointerInside.current = inside
        updatePause()
      }
    }
    const onOut = (event: PointerEvent) => {
      // The pointer left the page (a null related target): nothing is hovered.
      if (event.relatedTarget === null && pointerInside.current) {
        pointerInside.current = false
        updatePause()
      }
    }
    document.addEventListener('pointerover', onOver)
    document.addEventListener('pointerout', onOut)
    return () => {
      document.removeEventListener('pointerover', onOver)
      document.removeEventListener('pointerout', onOut)
    }
  }, [updatePause])

  // A dismissed toast takes its focused button with it, and no blur fires; an
  // empty region cannot be hovered.
  useEffect(() => {
    if (toasts.length === 0) {
      pointerInside.current = false
    }
    updatePause()
  }, [toasts, updatePause])

  useEffect(() => {
    const region = regionRef.current
    if (region === null) {
      return
    }
    const root = document.documentElement
    const publish = () => {
      const height = Math.ceil(region.getBoundingClientRect().height)
      if (height > 0) {
        root.style.setProperty('--toast-region-h', `${height}px`)
      } else {
        root.style.removeProperty('--toast-region-h')
      }
    }
    const observer = new ResizeObserver(publish)
    observer.observe(region)
    return () => {
      observer.disconnect()
      root.style.removeProperty('--toast-region-h')
    }
  }, [])

  return (
    <div
      ref={regionRef}
      className="toast-region"
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
