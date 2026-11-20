import type { Selection } from './workspace/selection.ts'
import { lastClip } from './workspace/selection.ts'

/*
 * The clip the bin's player shows (`clip-tab-and-player`, design D1), as one pure rule. No DOM, no
 * React. It follows the selection, so the inspector, the track's scroll and the player stay in step.
 */

/**
 * The identity of the clip the player shows, or null for none.
 *
 * - A clip selection shows its last clip, a cut selection shows the cut's clip, when it is on disk
 *   (an ignored clip is on disk, so it plays; a missing one has nothing to play, so the player
 *   shows none).
 * - A card, a suggestion or no selection keeps `was`, so selecting a card to rename it does not
 *   blank the player. `was` is dropped once the event no longer lists it or it is no longer on disk.
 */
export function shownClip(
  sel: Selection,
  was: string | null,
  listed: ReadonlySet<string>,
  onDisk: (identity: string) => boolean,
): string | null {
  const own = sel.kind === 'cut' ? sel.identity : lastClip(sel)
  if (own !== null) {
    return onDisk(own) ? own : null
  }
  const keeps = sel.kind === 'card' || sel.kind === 'suggestion' || sel.kind === 'none'
  if (keeps && was !== null && listed.has(was) && onDisk(was)) {
    return was
  }
  return null
}
