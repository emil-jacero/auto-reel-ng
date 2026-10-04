/*
 * The Timeline's zoom, kept per event for the browser tab's session (`timeline-zoom-slider`,
 * design D4): a Refresh, a Save, leaving and re-entering Edit mode and a reload of the tab show
 * the event at the scale it had; a new tab starts at Fit. In `sessionStorage`, best effort: every
 * access is guarded, and an in-memory copy keeps it for the page's life when storage throws. A
 * per-viewer convenience: nothing here is sent anywhere. Pure but for the storage it is given.
 */

/** The zoom as kept: Fit (which follows the view's width), or a scale in px per second. */
export type ZoomMemo = { fitted: boolean; pps: number }

/** The storage it uses: `sessionStorage` in the page, a stand-in in tests. */
export type MemoStorage = Pick<Storage, 'getItem' | 'setItem'>

export const ZOOM_KEY_PREFIX = 'auto-reel:timeline-zoom:'

export function zoomKey(eventId: string): string {
  return `${ZOOM_KEY_PREFIX}${eventId}`
}

/** A kept value read back, or null when it is missing or is not a zoom (never a guess). */
export function parseZoom(raw: string | null): ZoomMemo | null {
  if (raw === null) {
    return null
  }
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null) {
    return null
  }
  const { fitted, pps } = value as { fitted?: unknown; pps?: unknown }
  if (typeof fitted !== 'boolean' || typeof pps !== 'number' || !Number.isFinite(pps) || pps <= 0) {
    return null
  }
  return { fitted, pps }
}

/**
 * The scale a kept zoom gives once the view is measured: Fit stays Fit, a scale is held to
 * [fit, max]. Null for none kept: the Timeline opens at Fit.
 */
export function restoredZoom(memo: ZoomMemo | null, fit: number, max: number): ZoomMemo | null {
  if (memo === null) {
    return null
  }
  if (memo.fitted) {
    return { fitted: true, pps: fit }
  }
  const pps = Math.min(max, Math.max(fit, memo.pps))
  return { fitted: pps <= fit, pps }
}

export type ZoomMemory = {
  read(eventId: string): ZoomMemo | null
  write(eventId: string, memo: ZoomMemo): void
}

/** A memory over `storage()` (which may itself throw, as `window.sessionStorage` can). */
export function createZoomMemory(storage: () => MemoStorage | null): ZoomMemory {
  const mirror = new Map<string, ZoomMemo>()
  return {
    read(eventId) {
      // The page's own copy is the newest; after a reload only the storage has one.
      const held = mirror.get(eventId)
      if (held !== undefined) {
        return held
      }
      try {
        return parseZoom(storage()?.getItem(zoomKey(eventId)) ?? null)
      } catch {
        return null // storage unavailable: Fit
      }
    },
    write(eventId, memo) {
      mirror.set(eventId, memo)
      try {
        storage()?.setItem(zoomKey(eventId), JSON.stringify(memo))
      } catch {
        // storage unavailable or full: the page's own copy is kept
      }
    },
  }
}

/** The page's one memory, over the tab's `sessionStorage`. */
export const zoomMemory: ZoomMemory = createZoomMemory(() =>
  typeof window === 'undefined' ? null : window.sessionStorage,
)
