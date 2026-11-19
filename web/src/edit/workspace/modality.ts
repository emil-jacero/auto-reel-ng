import { useEffect } from 'react'

/*
 * The last input (`editor-shortcuts`, D2): did the operator last move focus by keyboard or press a
 * pointer? Space on a focused button, checkbox or clip block belongs to that control after Tab and
 * to Play after a click (`shortcuts.ts`). The pure steps are tested (`modality.test.ts`); the
 * workspace installs the listeners while it is mounted (`useModalityTracking`). Without a
 * workspace the value stays `keyboard`, which keeps every control's native behaviour.
 */

export type Modality = 'keyboard' | 'pointer'

/** What the steps read of an event. */
export type InputEvent = { type: string; key?: string; button?: number }

/**
 * The input after `event`: a pointer press is `pointer`, Tab (with or without Shift) is
 * `keyboard`, and anything else, arrows included, leaves it as it was: a click on Rotate, then
 * Right, then Space must still play.
 */
export function nextModality(was: Modality, event: InputEvent): Modality {
  if (event.type === 'pointerdown') {
    return 'pointer'
  }
  if (event.type === 'keydown' && event.key === 'Tab') {
    return 'keyboard'
  }
  return was
}

/**
 * Whether a pointer is held: from a primary-button `pointerdown` to `pointerup`, `pointercancel`,
 * `contextmenu` or the window's `blur`. A right-click's release goes to the context menu, not
 * the page, so a press of another button is not held.
 */
export function nextHeld(was: boolean, event: InputEvent): boolean {
  switch (event.type) {
    case 'pointerdown':
      return event.button === 0
    case 'pointerup':
    case 'pointercancel':
    case 'contextmenu':
    case 'blur':
      return false
    default:
      return was
  }
}

let modality: Modality = 'keyboard'
let held = false

/** The last input, `keyboard` before any and without a workspace. */
export function lastInput(): Modality {
  return modality
}

/** Whether a primary-button press has not yet ended. */
export function pointerHeld(): boolean {
  return held
}

// An options object, not `true`: Node's EventTarget (the tests) does not remove a listener by it.
const CAPTURE = { capture: true }
const HELD_EVENTS = ['pointerdown', 'pointerup', 'pointercancel', 'contextmenu'] as const

/**
 * Listen (capture phase, so no handler can hide an event) on `doc` for the last input and the
 * held pointer, and on `win` for its `blur`. Returns the function that stops and resets both.
 */
export function installModality(doc: EventTarget, win: EventTarget): () => void {
  const input = (event: Event) => {
    const e = event as unknown as InputEvent
    modality = nextModality(modality, e)
    held = nextHeld(held, e)
  }
  const blur = () => {
    held = nextHeld(held, { type: 'blur' })
  }
  doc.addEventListener('keydown', input, CAPTURE)
  for (const type of HELD_EVENTS) {
    doc.addEventListener(type, input, CAPTURE)
  }
  win.addEventListener('blur', blur)
  return () => {
    doc.removeEventListener('keydown', input, CAPTURE)
    for (const type of HELD_EVENTS) {
      doc.removeEventListener(type, input, CAPTURE)
    }
    win.removeEventListener('blur', blur)
    modality = 'keyboard'
    held = false
  }
}

/** `Workspace.tsx` calls this: the listeners live while the workspace is mounted. */
export function useModalityTracking(): void {
  useEffect(() => installModality(document, window), [])
}
