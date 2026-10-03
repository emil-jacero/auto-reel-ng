import type { Ms } from './model.ts'

/*
 * The seek coalescer (D-20, design 4). A scrub produces pointer moves faster than a
 * `<video>` seeks. This keeps one load or seek in flight and, when it settles, goes to
 * the latest target only: a scrub across many clips never queues a seek per move, and
 * it always ends where the pointer ended. Pure: the video is two injected calls, and
 * the caller reports `settled()` (on `loadedmetadata` / `seeked`) or `failed()`.
 */

export type Target = { clip: number; ms: Ms }

export type SeekIo = {
  /** Put this clip's proxy into the video; `settled()` follows its `loadedmetadata`. */
  load(clip: number): void
  /** Seek the loaded clip to this time; `settled()` follows its `seeked`. */
  seek(ms: Ms): void
}

export type Coalescer = {
  /** Go to this target when nothing is in flight, else when what is in flight settles. */
  request(target: Target): void
  /** The load or seek in flight has finished. */
  settled(): void
  /** The load in flight failed, or the video was let go: nothing is in flight or loaded, and nothing is started. */
  failed(): void
  /** The video was swapped from outside (an address changed): nothing is loaded. */
  reset(): void
  /**
   * The video is at this target by itself (it played, or skipped a cut, there): that is
   * now the target, so a settled seek of its own never takes it back to an older request.
   * Ignored while a load or seek is in flight.
   */
  sync(target: Target): void
  /** Whether a load or seek is in flight. */
  busy(): boolean
}

export function createCoalescer(io: SeekIo): Coalescer {
  let want: Target | null = null
  let loaded: number | null = null
  let shown: Ms | null = null
  let inFlight = false

  function pump(): void {
    if (inFlight || want === null) {
      return
    }
    if (want.clip !== loaded) {
      inFlight = true
      loaded = want.clip
      shown = null
      io.load(want.clip)
    } else if (want.ms !== shown) {
      inFlight = true
      shown = want.ms
      io.seek(want.ms)
    }
  }

  return {
    request(target) {
      want = target
      pump()
    },
    settled() {
      inFlight = false
      pump()
    },
    failed() {
      inFlight = false
      loaded = null
      shown = null
    },
    reset() {
      inFlight = false
      loaded = null
      shown = null
      pump()
    },
    sync(target) {
      if (!inFlight) {
        want = target
        loaded = target.clip
        shown = target.ms
      }
    },
    busy: () => inFlight,
  }
}
