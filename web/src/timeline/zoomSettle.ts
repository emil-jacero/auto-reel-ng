/*
 * When a zoom is in progress (`edit-list-paint-cost`, design D6). The Track leaves the clips' edge
 * tools out from a zoom's first input until it settles, as it leaves them out behind a rippling
 * drag: each zoom would otherwise re-render and move every tool in view (each tool's place is in
 * px), which cost the slider drag its frame budget in Chrome. A zoom input starts or extends a
 * zoom; while the Zoom slider is pressed the zoom stays open however long the thumb rests, and its
 * release settles it at once; any other input (Ctrl/Cmd+wheel, pinch, the zoom buttons, `=`/`-` and
 * their key repeat, a key on the slider) settles `SETTLE_MS` after the last one. Pure but for the
 * timer it is given: `window.setTimeout` in the page, a fake clock in tests.
 */

/** A pause this long after the last zoom input settles the zoom (a key-repeat or wheel gap is less). */
export const SETTLE_MS = 150

/** The timer the machine uses. */
export type SettleTimer = {
  set: (run: () => void, ms: number) => number
  clear: (id: number) => void
}

export type ZoomSettle = {
  /** A zoom input of any kind: the zoom starts, or goes on. */
  input: () => void
  /** The Zoom slider is pressed: a zoom that starts now stays open until `release`. */
  press: () => void
  /** The Zoom slider is released: an open zoom settles at once. */
  release: () => void
  /** Unmount or Edit mode left: no timer runs on, the zoom is over without a call. */
  cancel: () => void
  zooming: () => boolean
}

/** `onChange` is called on each start (true) and settle (false) of a zoom, never per input. */
export function createZoomSettle(onChange: (zooming: boolean) => void, timer: SettleTimer): ZoomSettle {
  let zooming = false
  let held = false
  let pending: number | null = null
  const stopTimer = () => {
    if (pending !== null) {
      timer.clear(pending)
      pending = null
    }
  }
  const settle = () => {
    stopTimer()
    if (zooming) {
      zooming = false
      onChange(false)
    }
  }
  return {
    input() {
      stopTimer()
      if (!zooming) {
        zooming = true
        onChange(true)
      }
      if (!held) {
        pending = timer.set(() => {
          pending = null
          settle()
        }, SETTLE_MS)
      }
    },
    press() {
      held = true
      // A zoom already running from a key or the wheel is now the slider's: it waits for release.
      stopTimer()
    },
    release() {
      if (!held) {
        return
      }
      held = false
      settle()
    },
    cancel() {
      held = false
      stopTimer()
      zooming = false
    },
    zooming: () => zooming,
  }
}

/** An edge tool: a clip's identity and the side it trims. */
export type EdgeKey = { identity: string; side: 'start' | 'end' }

/**
 * Whether the Track renders a clip's edge tool: never behind a rippling drag (`after`); while a
 * zoom is in progress only the one tool that held focus when it started (`kept`).
 */
export function edgeToolShown(
  tool: EdgeKey,
  state: { after: boolean; zooming: boolean; kept: EdgeKey | null },
): boolean {
  if (state.after) {
    return false
  }
  if (!state.zooming) {
    return true
  }
  return state.kept !== null && state.kept.identity === tool.identity && state.kept.side === tool.side
}
