/*
 * One video plays at a time on the page (change `clip-play-overlay-one-player`, which
 * replaced `playback/exclusive.ts` and `events/onePlayer.ts`): when a video starts, every
 * other one that plays is paused where it is. The rule is held here and nowhere else: no
 * player claims, releases or names another, so the movie player, a clip's player in the
 * read view, a clip's preview in Edit mode, the Timeline and any player added later are
 * covered. Nothing is closed, replaced, restarted or seeked, and nothing is announced.
 *
 * A `<video>`'s `play` event does not bubble, so one capturing listener on the document
 * (`main.tsx`) hears them all, whichever component owns them. Seeks, `load()` and Skip
 * cuts' jumps fire `seeking` and `seeked`, never `play`, so none of them counts as a
 * start. Structural types only: no DOM, so `npm test` runs it with stand-ins.
 */

/** What this module needs of a video. */
export type PausableVideo = { readonly paused: boolean; pause(): void }

/** Pauses each video that plays and is not `started`. */
export function pauseOthers(started: unknown, videos: Iterable<PausableVideo>): void {
  for (const video of videos) {
    if (video !== started && !video.paused) {
      video.pause()
    }
  }
}

/** What this module needs of the root: a capturing listener, and the videos below it. */
export type VideoRoot = {
  addEventListener(type: 'play', listener: (event: Event) => void, capture: boolean): void
  removeEventListener(type: 'play', listener: (event: Event) => void, capture: boolean): void
  /** The page's videos; for a `document`, `querySelectorAll('video')`. */
  videos(): Iterable<PausableVideo>
  /** Whether the event's target is one of its videos. */
  isVideo(target: EventTarget | null): target is EventTarget & PausableVideo
}

/** Starts keeping one video playing under `root`; returns the remover. */
export function keepOneVideoPlaying(root: VideoRoot): () => void {
  const onPlay = (event: Event) => {
    // The event is queued: a video that has been paused since it was started (a start and a
    // pause in one task) is not playing, and starts nothing.
    if (root.isVideo(event.target) && !event.target.paused) {
      pauseOthers(event.target, root.videos())
    }
  }
  root.addEventListener('play', onPlay, true)
  return () => root.removeEventListener('play', onPlay, true)
}

/** The page's own root: its `document`, whose `<video>` elements are the videos. */
export function documentRoot(document: Document): VideoRoot {
  return {
    addEventListener: (type, listener, capture) =>
      document.addEventListener(type, listener, capture),
    removeEventListener: (type, listener, capture) =>
      document.removeEventListener(type, listener, capture),
    videos: () => document.querySelectorAll('video'),
    isVideo: (target): target is EventTarget & PausableVideo =>
      target instanceof HTMLVideoElement,
  }
}

/** Whether a video other than `self` is playing (the Timeline asks before it resumes by itself). */
export function anotherPlays(self: unknown, videos: Iterable<PausableVideo>): boolean {
  for (const video of videos) {
    if (video !== self && !video.paused) {
      return true
    }
  }
  return false
}
