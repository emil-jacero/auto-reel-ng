import { useCallback, useEffect, useId, useLayoutEffect, useRef } from 'react'

import { Icon } from './Icon'
import type { IconName } from './Icon'
import {
  dismissToast,
  onModalOpened,
  pauseToasts,
  useModalOpen,
  useToastClearance,
  useToasts,
} from './toast'
import type { Toast, ToastTone } from './toast'

const TONE_ICON: Record<ToastTone, IconName> = {
  success: 'check',
  info: 'info',
  error: 'alert-triangle',
}

/** Dismiss a toast; the button is the one pressed, for the focus hand-off. */
type DismissHandler = (id: number, button: HTMLElement) => void

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: DismissHandler }) {
  const messageId = useId()
  return (
    <div className="toast" data-tone={toast.tone}>
      <Icon name={TONE_ICON[toast.tone]} />
      <div className="toast-body">
        <p id={messageId} className="toast-message">
          {toast.message}
        </p>
        {toast.action !== undefined && (
          <a className="toast-action" href={toast.action.href}>
            {toast.action.label}
          </a>
        )}
      </div>
      {/* Described by its message: landing on it says which toast it clears. */}
      <button
        type="button"
        className="btn btn-ghost btn-icon toast-dismiss"
        aria-describedby={messageId}
        onClick={(event) => onDismiss(toast.id, event.currentTarget)}
      >
        <Icon name="x" label="Dismiss" />
      </button>
    </div>
  )
}

/**
 * Focus the first candidate that takes it, without scrolling: a removed node, an
 * element in a hidden page or a disabled control is skipped.
 */
function focusFirst(candidates: readonly (HTMLElement | null | undefined)[]): void {
  for (const target of candidates) {
    if (target == null || !target.isConnected) {
      continue
    }
    target.focus({ preventScroll: true })
    if (document.activeElement === target) {
      return
    }
  }
}

/** The shown page's level-one heading (the selector `focusPageHeading` uses; ui/ cannot import shell/). */
function pageHeading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('main:not([hidden]) h1')
}

/**
 * Where toasts appear; the shell renders it once. Two live containers are
 * always present, so a toast added to one is announced: `role="status"`
 * (polite) for success and info, `role="alert"` for errors. Neither is atomic,
 * so a new toast is announced alone, not with the ones still shown. A pointer
 * or focus inside the region pauses the auto-dismiss clocks, and so does an
 * open modal dialog.
 *
 * The region is a manual popover, shown in the top layer and shown again each
 * time a modal dialog opens, so a toast is visible above the dialog and its
 * backdrop (it takes no focus or clicks until the dialog closes: the platform
 * makes everything outside a modal dialog inert).
 *
 * Focus never falls to <body> when a toast goes. Dismissing the toast that
 * holds focus hands it to the next toast's Dismiss, else the previous one's,
 * else the control focus came from, else the page's h1; a toast displaced by a
 * newer one hands it on the same way. Every move is `preventScroll`, so a
 * pointer dismissal (Chromium focuses a clicked button) leaves the page where
 * it is.
 *
 * While a modal dialog is open the region is inert, so `data-under-modal` is set
 * and its Dismiss buttons and links are drawn unavailable (see components.css).
 *
 * Its bottom offset follows a custom property (see `.toast-region`). With a
 * bar registered (`keepToastsClearOf`), the region places itself: above the bar
 * while the bar is held at the window's bottom edge, and in the room below it
 * once the bar rests in the page with room to spare. Otherwise it reads
 * `--toast-inset-bottom`, 0 unless a page sets it. The region's own height is
 * published on <html> as `--toast-region-h` (removed when empty), and, while a
 * bar is registered, its height plus the gap as `--toast-rise-h`; the page's
 * bottom scroll padding adds both, so a control focused by keyboard never
 * scrolls under a toast, including toasts that rise with a bar on its way up.
 * While the toasts sit above the bar, the same height is published as
 * `--toast-room-h`; a bar that rests in the page keeps that much room before
 * it (edit.css), so the toasts cover that room and no control. `place()` also
 * runs when the page above the bar changes size, as that moves the bar.
 */
export function ToastRegion() {
  const toasts = useToasts()
  const bar = useToastClearance()
  const underModal = useModalOpen()
  const regionRef = useRef<HTMLDivElement>(null)
  const pointerInside = useRef(false)
  // The control focus came from when it entered the region (null: from nowhere).
  const returnTo = useRef<HTMLElement | null>(null)
  // The last element inside the region to take focus; cleared once focus is
  // somewhere else. A pointer press alone does not clear it: a touch scroll
  // presses and leaves focus where it is.
  const lastFocused = useRef<HTMLElement | null>(null)

  const updatePause = useCallback(() => {
    const region = regionRef.current
    const focusInside = region !== null && region.contains(document.activeElement)
    pauseToasts(pointerInside.current || focusInside)
  }, [])

  /** Where focus goes when the toast holding it leaves: `first`, then out of the region. */
  const handOff = useCallback((first: readonly (HTMLElement | undefined)[]) => {
    const region = regionRef.current
    const back = returnTo.current
    const outside = back !== null && region !== null && !region.contains(back) ? back : null
    focusFirst([...first, outside, pageHeading()])
    // A move within the region is not an entry: keep where focus came from.
    returnTo.current = back
  }, [])

  // Focus moves before the toast goes, so it is never on a removed node.
  const dismiss = useCallback<DismissHandler>(
    (id, button) => {
      const region = regionRef.current
      if (region !== null && region.contains(document.activeElement)) {
        const buttons = [...region.querySelectorAll<HTMLElement>('.toast-dismiss')]
        const at = buttons.indexOf(button)
        handOff(at < 0 ? [] : [buttons[at + 1], buttons[at - 1]])
      }
      dismissToast(id)
    },
    [handOff],
  )

  // Hover is read from where the pointer arrives, not from enter/leave pairs:
  // a toast dismissed under the pointer disappears without any leave event.
  // Focus going anywhere else ends the region's hold on focus.
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
    const onFocusElsewhere = (event: FocusEvent) => {
      const region = regionRef.current
      if (region !== null && event.target instanceof Node && !region.contains(event.target)) {
        lastFocused.current = null
      }
    }
    // Focus left an element of the region. Chromium fires the same focusout,
    // with no related target, when the focused node itself is removed (a toast
    // displaced by a newer one), and that one must keep the record for the
    // hand-off. So decide once the work that fired it is done: by then a
    // removed node is disconnected, and the layout effect below has run.
    const onFocusOut = (event: FocusEvent) => {
      const region = regionRef.current
      const left = event.target
      if (region === null || !(left instanceof Node) || !region.contains(left)) {
        return
      }
      queueMicrotask(() => {
        if (left.isConnected && !region.contains(document.activeElement)) {
          lastFocused.current = null
        }
      })
    }
    document.addEventListener('pointerover', onOver)
    document.addEventListener('pointerout', onOut)
    document.addEventListener('focusin', onFocusElsewhere)
    document.addEventListener('focusout', onFocusOut)
    return () => {
      document.removeEventListener('pointerover', onOver)
      document.removeEventListener('pointerout', onOut)
      document.removeEventListener('focusin', onFocusElsewhere)
      document.removeEventListener('focusout', onFocusOut)
    }
  }, [updatePause])

  // A toast that held focus and went for another reason (a newer toast took its
  // place) leaves focus on <body>: hand it on, before the next paint.
  useLayoutEffect(() => {
    const last = lastFocused.current
    const active = document.activeElement
    if (last === null || last.isConnected || (active !== null && active !== document.body)) {
      return
    }
    lastFocused.current = null
    handOff([regionRef.current?.querySelector<HTMLElement>('.toast-dismiss') ?? undefined])
  }, [toasts, handOff])

  // A removed toast takes its focused button with it (the browser's blur then
  // finds no related target inside); an empty region cannot be hovered.
  useEffect(() => {
    if (toasts.length === 0) {
      pointerInside.current = false
    }
    updatePause()
  }, [toasts, updatePause])

  // In the top layer, as a manual popover: a modal dialog's backdrop and the
  // page under it are inert, and nothing but the top layer rises above them.
  // The top layer stacks by insertion time, so a dialog opening later covers the
  // region; it is shown again each time one opens. A browser without the API
  // keeps a plain fixed region, as does a call that throws: no toast is lost.
  useEffect(() => {
    const region = regionRef.current
    if (region === null || typeof region.showPopover !== 'function') {
      return
    }
    const lift = () => {
      try {
        if (region.matches(':popover-open')) {
          region.hidePopover()
        }
        region.showPopover()
      } catch {
        // Leave the region where it is.
      }
    }
    lift()
    const stop = onModalOpened(lift)
    return () => {
      stop()
      try {
        if (region.matches(':popover-open')) {
          region.hidePopover()
        }
      } catch {
        // Already gone.
      }
    }
  }, [])

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

  // Keep clear of a registered bar, live: above it while it is held at the
  // window's bottom edge, below it once the room under it fits the toasts. The
  // gap is the region's own (its CSS), read back from where it sits.
  useLayoutEffect(() => {
    const region = regionRef.current
    if (bar === null || region === null) {
      return
    }
    const root = document.documentElement
    let offset = 0
    let rise: number | null = null
    let room: number | null = null
    region.style.setProperty('--toast-offset', '0px')
    const place = () => {
      const viewport = root.clientHeight
      const box = bar.getBoundingClientRect()
      const height = region.offsetHeight
      const gap = viewport - region.getBoundingClientRect().bottom - offset
      // Decided on the bar as it would sit with no room before it (a resting bar
      // carries the room as its margin; a held one has none), so the choice does
      // not depend on the room it has already made: the above/below switch is at
      // one scroll position in both directions, with no band where either holds.
      const kept = Number.parseFloat(getComputedStyle(bar).marginBlockStart)
      const bare = box.bottom - (Number.isFinite(kept) ? kept : 0)
      const below = viewport - bare >= height + gap
      const next = below ? 0 : Math.max(0, Math.ceil(viewport - box.top))
      if (next !== offset) {
        offset = next
        region.style.setProperty('--toast-offset', `${next}px`)
      }
      const nextRise = height > 0 ? Math.ceil(height + gap) : null
      if (nextRise !== rise) {
        rise = nextRise
        if (nextRise === null) {
          root.style.removeProperty('--toast-rise-h')
        } else {
          root.style.setProperty('--toast-rise-h', `${nextRise}px`)
        }
      }
      // The room the toasts take above the bar, for a resting bar to keep between
      // the last chapter and itself; none while they sit below it or are absent.
      // Decided by `below` alone (not by the offset, which is 0 while the bar is
      // still under the window's edge), so the room never flips its own decision.
      const nextRoom = below ? null : nextRise
      if (nextRoom !== room) {
        room = nextRoom
        if (nextRoom === null) {
          root.style.removeProperty('--toast-room-h')
        } else {
          root.style.setProperty('--toast-room-h', `${nextRoom}px`)
        }
      }
    }
    place()
    window.addEventListener('scroll', place, { passive: true })
    window.addEventListener('resize', place)
    const observer = new ResizeObserver(place)
    observer.observe(bar)
    observer.observe(region)
    // The page above the bar grows or shrinks (a chapter added, a row more) and
    // moves the bar without a scroll, a resize, or any change of its own size.
    observer.observe(root)
    if (bar.parentElement !== null) {
      observer.observe(bar.parentElement)
    }
    return () => {
      window.removeEventListener('scroll', place)
      window.removeEventListener('resize', place)
      observer.disconnect()
      region.style.removeProperty('--toast-offset')
      root.style.removeProperty('--toast-rise-h')
      root.style.removeProperty('--toast-room-h')
    }
  }, [bar])

  return (
    <div
      ref={regionRef}
      className="toast-region"
      popover="manual"
      data-under-modal={underModal ? '' : undefined}
      onFocus={(event) => {
        const region = event.currentTarget
        const from = event.relatedTarget
        if (!(from instanceof Node && region.contains(from))) {
          returnTo.current = from instanceof HTMLElement ? from : null
        }
        if (event.target instanceof HTMLElement) {
          lastFocused.current = event.target
        }
        updatePause()
      }}
      onBlur={(event) => {
        // Focus moving to another control in the region keeps it paused.
        if (!event.currentTarget.contains(event.relatedTarget)) {
          pauseToasts(pointerInside.current)
        }
      }}
    >
      <div role="alert" aria-atomic="false" className="toast-stack">
        {toasts
          .filter((shown) => shown.tone === 'error')
          .map((shown) => (
            <ToastItem key={shown.id} toast={shown} onDismiss={dismiss} />
          ))}
      </div>
      <div role="status" aria-atomic="false" className="toast-stack">
        {toasts
          .filter((shown) => shown.tone !== 'error')
          .map((shown) => (
            <ToastItem key={shown.id} toast={shown} onDismiss={dismiss} />
          ))}
      </div>
    </div>
  )
}
