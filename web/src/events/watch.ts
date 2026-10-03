import type { Chapter, Clip } from '../api/event.ts'
import { hideName } from '../preview/playback.ts'

/*
 * Which clips the event page's read view offers Watch for, and what a re-read of the
 * event does to an open player (change `clip-play-read-view`). Pure: type-only imports,
 * so `npm test` runs it as it is.
 */

/**
 * Whether the clip's file is on disk, so that it can be watched: any status but missing.
 * An ignored clip and an excluded one are on disk and are served like any other.
 */
export function canWatch(clip: Pick<Clip, 'status'>): boolean {
  return clip.status !== 'missing'
}

/**
 * The identity of the open player after a new read of the event: `open` when the read
 * still lists that clip on disk, in any chapter, else `null` (the clip went missing, or
 * is no longer listed). `null` in, `null` out.
 */
export function watchedAfterRead(
  open: string | null,
  chapters: readonly { clips: readonly Pick<Chapter['clips'][number], 'identity' | 'status'>[] }[],
): string | null {
  if (open === null) {
    return null
  }
  for (const chapter of chapters) {
    for (const clip of chapter.clips) {
      if (clip.identity === open) {
        return canWatch(clip) ? open : null
      }
    }
  }
  return null
}

/**
 * The accessible name of the read view's play control over a clip's thumbnail: "Play
 * <name>" while the player is closed, "Hide player of <name>" while it is open. Neither
 * is the open player's own "Play <name>" / "Pause <name>", so no two controls of the page
 * share a name while a player is open.
 */
export function thumbControlName(name: string, open: boolean): string {
  return open ? hideName(name) : `Play ${name}`
}
