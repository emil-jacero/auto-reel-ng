/*
 * One video plays at a time on the event page (change `clip-play-read-view`): when a
 * video starts, every other one that plays is paused where it is. Nothing is closed,
 * replaced, restarted or seeked, and nothing is announced.
 *
 * A `<video>`'s `play` event does not bubble, so one capturing listener on the root
 * hears them all, however many videos the page holds and whichever component owns
 * them. Seeks, `load()` and Skip cuts' jumps fire `seeking` and `seeked`, never
 * `play`, so none of them counts as a start. Structural types only: no DOM, so
 * `npm test` runs it with stand-ins.
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
  isVideo(target: EventTarget | null): boolean
}

/** Starts keeping one video playing under `root`; returns the remover. */
export function keepOneVideoPlaying(root: VideoRoot): () => void {
  const onPlay = (event: Event) => {
    if (root.isVideo(event.target)) {
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
    isVideo: (target) => target instanceof HTMLVideoElement,
  }
}
