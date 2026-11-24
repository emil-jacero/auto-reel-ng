import { useEffect, useRef } from 'react'
import type { FocusEvent, KeyboardEvent, MouseEvent, PointerEvent } from 'react'

import { DRAG_SLOP_PX, dragAction, edgeDistance, isPaneKey, keyAction, valueText } from './paneSizes.ts'
import type { Limits, PaneAction, PaneId } from './paneSizes.ts'

/*
 * A pane border (`resizable-panes`, design D4): a focusable WAI-ARIA window splitter that is also
 * dragged with the pointer. Drag, double-click and keys all say what they want as a `PaneAction`
 * (`paneSizes.ts` owns the maths); `Workspace.tsx` applies it and keeps it. The drag has
 * `TrimHandle`'s shape (pointer capture, an `active` ref, Escape, cancel and lost capture) with
 * one difference: a press never moves keyboard focus to the border, so after a drag Left and
 * Right still step the playhead.
 */

type Active = {
  pointerId: number
  startX: number
  startY: number
  startSize: number
  lim: Limits
  /** The pointer has moved `DRAG_SLOP_PX` or more along the pane's axis at some point. */
  moved: boolean
  /** `document.activeElement` at the press: focus is given back to it where a live hide did not last. */
  recorded: Element | null
}

export function PaneSeparator({
  pane,
  controls,
  label,
  size,
  limits,
  onLive,
  onCommit,
  onCancel,
}: {
  pane: PaneId
  /** The pane's element id. */
  controls: string
  label: string
  /** The pane's drawn size in CSS px; 0 when it is hidden. */
  size: number
  limits: Limits
  /** A drag's size for the pane this frame (0: hidden), written without a React render. */
  onLive: (px: number) => void
  onCommit: (action: PaneAction) => void
  onCancel: () => void
}) {
  const el = useRef<HTMLDivElement>(null)
  const active = useRef<Active | null>(null)
  const frame = useRef<number | null>(null)
  const escape = useRef<((event: globalThis.KeyboardEvent) => void) | null>(null)
  const axis = pane === 'tl' ? 'row' : 'col'
  const latest = useRef({ onLive, onCommit, onCancel })
  latest.current = { onLive, onCommit, onCancel }

  /** Everything a drag's end undoes; the drag's own state is left to the caller. */
  const clear = () => {
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current)
      frame.current = null
    }
    const a = active.current
    active.current = null
    const node = el.current
    node?.removeAttribute('data-dragging')
    delete document.documentElement.dataset.wsResizing
    if (escape.current !== null) {
      window.removeEventListener('keydown', escape.current, true)
      escape.current = null
    }
    if (a !== null && node !== null) {
      try {
        if (node.hasPointerCapture(a.pointerId)) {
          node.releasePointerCapture(a.pointerId)
        }
      } catch {
        // The pointer is already gone.
      }
    }
    return a
  }

  /** A live hide that did not last gives focus back to where it was (design D4). */
  const giveFocusBack = (recorded: Element | null) => {
    const now = document.activeElement
    if (
      recorded instanceof HTMLElement &&
      recorded.isConnected &&
      recorded.closest('[inert]') === null &&
      (now === null || now === document.body)
    ) {
      recorded.focus({ preventScroll: true })
    }
  }

  /** Escape, a cancelled pointer or a lost capture: back to the drag's start. */
  const finish = () => {
    const a = clear()
    if (a === null) {
      return
    }
    latest.current.onCancel()
    giveFocusBack(a.recorded)
  }

  useEffect(
    () => () => {
      clear()
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  const down = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !event.isPrimary || active.current !== null) {
      return
    }
    const node = event.currentTarget
    try {
      node.setPointerCapture(event.pointerId)
    } catch {
      // A synthetic pointer: the drag still follows the window's events.
    }
    active.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startSize:
        size === 0
          ? edgeDistance(
              pane,
              event.clientX,
              event.clientY,
              document.documentElement.clientWidth,
              document.documentElement.clientHeight,
            )
          : size,
      lim: limits,
      moved: false,
      recorded: document.activeElement,
    }
    node.setAttribute('data-dragging', '')
    document.documentElement.dataset.wsResizing = axis
    const onKey = (key: globalThis.KeyboardEvent) => {
      if (key.key === 'Escape' && active.current !== null) {
        key.preventDefault()
        key.stopPropagation()
        finish()
      }
    }
    escape.current = onKey
    window.addEventListener('keydown', onKey, true)
  }

  const move = (event: PointerEvent<HTMLDivElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const along = pane === 'tl' ? event.clientY - a.startY : event.clientX - a.startX
    if (!a.moved && Math.abs(along) < DRAG_SLOP_PX) {
      return
    }
    a.moved = true
    const action = dragAction(
      pane,
      a.startSize,
      event.clientX - a.startX,
      event.clientY - a.startY,
      a.lim,
    )
    const px = action.kind === 'size' ? action.px : 0
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current)
    }
    frame.current = requestAnimationFrame(() => {
      frame.current = null
      if (active.current !== null) {
        latest.current.onLive(px)
      }
    })
  }

  const up = (event: PointerEvent<HTMLDivElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const along = pane === 'tl' ? event.clientY - a.startY : event.clientX - a.startX
    const action = dragAction(
      pane,
      a.startSize,
      event.clientX - a.startX,
      event.clientY - a.startY,
      a.lim,
    )
    clear()
    // A drag that passed the slop keeps what it showed, wherever the release lands (even back
    // within the slop of the start); only a press that never moved is a cancel.
    if (a.moved || Math.abs(along) >= DRAG_SLOP_PX) {
      latest.current.onCommit(action)
    } else {
      latest.current.onCancel()
    }
    giveFocusBack(a.recorded)
  }

  const cancelled = () => {
    finish()
  }

  // A press must not focus the border: the compatibility mousedown is what would. This only runs
  // because `down` does not cancel the pointerdown (a cancelled one suppresses it).
  const mouseDown = (event: MouseEvent<HTMLDivElement>) => {
    event.preventDefault()
  }

  const focus = (event: FocusEvent<HTMLDivElement>) => {
    const a = active.current
    if (a === null) {
      return
    }
    const back = a.recorded
    if (
      back instanceof HTMLElement &&
      back !== document.body &&
      back.isConnected &&
      back.closest('[inert]') === null
    ) {
      back.focus({ preventScroll: true })
    } else {
      event.currentTarget.blur()
    }
  }

  const doubleClick = () => {
    latest.current.onCommit(size === 0 ? { kind: 'show' } : { kind: 'reset' })
  }

  const keyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const action = keyAction(
      pane,
      event.key,
      {
        shift: event.shiftKey,
        ctrl: event.ctrlKey,
        alt: event.altKey,
        meta: event.metaKey,
        repeat: event.repeat,
      },
      size,
      limits,
    )
    if (action !== null) {
      event.preventDefault()
      onCommit(action)
    } else if (
      !event.ctrlKey &&
      !event.altKey &&
      !event.metaKey &&
      isPaneKey(pane, event.key)
    ) {
      // A repeat that does nothing is still the border's: it never falls through to a scroll.
      event.preventDefault()
    }
  }

  return (
    <div
      ref={el}
      role="separator"
      tabIndex={0}
      className="ws-sep"
      data-pane={pane}
      data-hidden={size === 0 ? '' : undefined}
      aria-orientation={pane === 'tl' ? 'horizontal' : 'vertical'}
      aria-controls={controls}
      aria-label={label}
      aria-valuenow={size}
      aria-valuemin={0}
      aria-valuemax={limits.max}
      aria-valuetext={valueText(pane, size)}
      onMouseDown={mouseDown}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={cancelled}
      onLostPointerCapture={cancelled}
      onFocus={focus}
      onDoubleClick={doubleClick}
      onKeyDown={keyDown}
    />
  )
}
