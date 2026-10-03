import { memo, useCallback, useState, useSyncExternalStore } from 'react'

import { clipMediaUrl } from '../api/clipMedia'
import type { Clip } from '../api/event'
import type { Trim } from '../cuts/times'
import { ClipPreview, usePreviewOpen } from '../preview/ClipPreview'
import { HIDE_PLAYER, WATCH, hideName, watchName } from '../preview/playback'
import type { ClipPreviews } from '../preview/previews'
import { Icon } from '../ui/Icon'
import { canWatch } from './watch'

/*
 * Watching a clip from the event page's read view (change `clip-play-read-view`): a Watch
 * control in the clip's row, and the preview component of Edit mode (`preview/`, D-16) in a
 * row of its own under it, read-only (it is given no `onSet`). Nothing here loads before a
 * press: a closed clip has a button and an empty subscription, no element and no request.
 *
 * Each control subscribes to its own clip (`usePreviewOpen`), so opening a player re-renders
 * these two components of one clip and nothing else of the list.
 */

// Constant elements: rows re-render without rebuilding them.
const PLAY = <Icon name="play" />
const HIDE = <Icon name="x" />

/** A clip with no cuts on its bar: one array, so the memoised player is not re-rendered. */
export const NO_TRIMS: readonly Trim[] = []

/** The live region's words: one message at a time, set a frame after being cleared. */
export type Announcer = {
  announce(message: string): void
  subscribe(listener: () => void): () => void
  message(): string
}

/** A stable announcer: the page's one live region for its players (`LiveRegion`). */
export function createAnnouncer(): Announcer {
  let current = ''
  let frame = 0
  const listeners = new Set<() => void>()
  const set = (message: string) => {
    current = message
    for (const listener of listeners) {
      listener()
    }
  }
  return {
    // Cleared first, so the same words said twice are announced twice.
    announce(message) {
      set('')
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => set(message))
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    message: () => current,
  }
}

/**
 * The read view's polite live region for its players. It re-renders by itself, so a
 * spoken message re-renders no row.
 */
export function LiveRegion({ announcer }: { announcer: Announcer }) {
  const message = useSyncExternalStore(announcer.subscribe, announcer.message)
  return (
    <p role="status" className="visually-hidden">
      {message}
    </p>
  )
}

/**
 * The row's Watch control: the same words, names and icon as Edit mode's, "Watch" and
 * "Hide player". `watchId` and `playerId` are the row's ids, for `aria-controls` and for
 * the focus that Close and Escape give back.
 */
export const WatchButton = memo(function WatchButton({
  previews,
  identity,
  name,
  watchId,
  playerId,
}: {
  previews: ClipPreviews
  identity: string
  /** The clip's name as its row names it. */
  name: string
  watchId: string
  playerId: string
}) {
  const open = usePreviewOpen(previews, identity)
  return (
    <button
      id={watchId}
      type="button"
      className="btn btn-secondary btn-compact preview-toggle watch-button"
      aria-expanded={open}
      aria-controls={open ? playerId : undefined}
      aria-label={open ? hideName(name) : watchName(name)}
      onClick={() => {
        if (open) {
          previews.hide(identity)
        } else {
          previews.show(identity, 'toggle')
        }
      }}
    >
      {/* Open, it says what a press does: Hide player. */}
      {open ? HIDE : PLAY}
      {open ? HIDE_PLAYER : WATCH}
    </button>
  )
})

/**
 * The row under a clip's row that holds its player: nothing while the clip's preview is
 * closed (or its file is gone), so it costs nothing in a long list. It is no clip: no
 * position, counted nowhere.
 */
export const PlayerRow = memo(function PlayerRow({
  previews,
  eventId,
  clip,
  name,
  cuts,
  watchId,
  playerId,
  onAnnounce,
}: {
  previews: ClipPreviews
  eventId: string
  clip: Clip
  name: string
  /** The clip's cuts as the page lists them: none for an excluded clip. */
  cuts: readonly Trim[]
  watchId: string
  playerId: string
  onAnnounce: (message: string) => void
}) {
  const open = usePreviewOpen(previews, clip.identity)
  if (!open || !canWatch(clip)) {
    return null
  }
  return (
    <tr role="row" className="clip-preview-row">
      <td role="cell" colSpan={6}>
        {/* A changed file is a new key: the old element keeps its playhead for the new one. */}
        <OpenPlayer
          key={clipMediaUrl(eventId, clip)}
          previews={previews}
          eventId={eventId}
          clip={clip}
          name={name}
          cuts={cuts}
          watchId={watchId}
          playerId={playerId}
          onAnnounce={onAnnounce}
        />
      </td>
    </tr>
  )
})

/**
 * The player of one clip, for as long as its file is the one it opened with. It holds the
 * clip as it was at the open: a re-read that changes only the clip's preview copy must not
 * change the file under the operator (the next open uses the new state).
 */
function OpenPlayer({
  previews,
  eventId,
  clip,
  name,
  cuts,
  watchId,
  playerId,
  onAnnounce,
}: {
  previews: ClipPreviews
  eventId: string
  clip: Clip
  name: string
  cuts: readonly Trim[]
  watchId: string
  playerId: string
  onAnnounce: (message: string) => void
}) {
  const [opened] = useState(clip)
  const { identity } = opened
  // Close and Escape: the Watch control is not unmounted by it, so focus lands at once.
  const onClose = useCallback(() => {
    previews.hide(identity)
    document.getElementById(watchId)?.focus()
  }, [previews, identity, watchId])
  return (
    <ClipPreview
      id={playerId}
      eventId={eventId}
      clip={opened}
      proxy={opened.proxy ?? null}
      name={name}
      cuts={cuts}
      previews={previews}
      onClose={onClose}
      onAnnounce={onAnnounce}
    />
  )
}
