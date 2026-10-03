/*
 * One playing video per page. The movie player and the Timeline's video each claim
 * playback when they start, and the element that held it is paused. A tiny registry of
 * the element that plays, with no React and no shared state beyond it: an element that
 * is gone is released by its owner.
 */

/** What the registry needs of an element: a `<video>` has it. */
export type Pausable = { pause(): void }

export type Exclusive = {
  /** `el` starts playing: the element that held playback is paused. Claiming twice pauses nothing. */
  claim(el: Pausable): void
  /** `el` is gone or has stopped: it no longer holds playback. */
  release(el: Pausable): void
}

export function createExclusive(): Exclusive {
  let holder: Pausable | null = null
  return {
    claim(el) {
      if (holder !== null && holder !== el) {
        holder.pause()
      }
      holder = el
    },
    release(el) {
      if (holder === el) {
        holder = null
      }
    },
  }
}

const page = createExclusive()

export const claimPlayback = page.claim
export const releasePlayback = page.release
