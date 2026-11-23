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

/**
 * Pauses each video that plays and is not `started`. `samePlayer` (optional) names the
 * videos that form one player with `started` (the Timeline's two slots): those are left
 * alone, since the player runs its own hand-over between them.
 */
export function pauseOthers(
  started: unknown,
  videos: Iterable<PausableVideo>,
  samePlayer?: (video: PausableVideo) => boolean,
): void {
  for (const video of videos) {
    if (video !== started && !video.paused && !samePlayer?.(video)) {
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
  /** Whether two videos are slots of one player (the Timeline's shown and standby). */
  samePlayer(a: PausableVideo, b: PausableVideo): boolean
}

/** Starts keeping one video playing under `root`; returns the remover. */
export function keepOneVideoPlaying(root: VideoRoot): () => void {
  const onPlay = (event: Event) => {
    // The event is queued: a video that has been paused since it was started (a start and a
    // pause in one task) is not playing, and starts nothing.
    if (root.isVideo(event.target) && !event.target.paused) {
      const started = event.target
      pauseOthers(started, root.videos(), (video) => root.samePlayer(started, video))
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
    // slots of one player carry the same `data-player` marker on a common ancestor
    samePlayer: (a, b) => {
      const pa = a instanceof Element ? a.closest('[data-player]') : null
      return pa !== null && pa === (b instanceof Element ? b.closest('[data-player]') : null)
    },
  }
}

/**
 * Whether a video that is not `own` is playing (the Timeline asks before it resumes by
 * itself). `own` says which videos belong to the asking player: the Timeline has two slots
 * (change `seamless-playback`), and one that plays while the other does too (the lead of
 * an early start) is the player's own, not "another". A paused video never counts.
 */
export function anotherPlays(
  own: (video: PausableVideo) => boolean,
  videos: Iterable<PausableVideo>,
): boolean {
  for (const video of videos) {
    if (!own(video) && !video.paused) {
      return true
    }
  }
  return false
}

/**
 * Calls `onOther` whenever a video that is not `own` starts playing. The Timeline uses it
 * to drop its claim on a Play that is still loading: the video started after the press is
 * the last start, and wins. The player's own starts, of either slot, call nothing.
 */
export function watchOtherStarts(
  root: VideoRoot,
  own: (video: unknown) => boolean,
  onOther: () => void,
): () => void {
  const onPlay = (event: Event) => {
    if (root.isVideo(event.target) && !own(event.target)) {
      onOther()
    }
  }
  root.addEventListener('play', onPlay, true)
  return () => root.removeEventListener('play', onPlay, true)
}

/** What `installPagePlayback` needs of the page: the `document`'s event surface. */
export type PageDocument = Pick<Document, 'addEventListener' | 'removeEventListener'> & {
  querySelectorAll: Document['querySelectorAll']
}

/** Installs the page's one-video rule on `document` (called once, from `main.tsx`). */
export function installPagePlayback(document: PageDocument): () => void {
  return keepOneVideoPlaying(documentRoot(document as Document))
}
