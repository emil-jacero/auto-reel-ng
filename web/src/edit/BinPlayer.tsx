import './binPlayer.css'

import { useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'

import type { Clip } from '../api/event'
import { ClipPreview, usePreviewOpen } from '../preview/ClipPreview'
import {
  HIDE_PLAYER_BARE,
  NO_CLIP_TO_WATCH,
  SHOW_PLAYER,
  SHOW_PLAYER_NAME,
} from '../preview/playback'
import type { ClipPreviews } from '../preview/previews'
import type { Turn } from '../rotate/turn.ts'
import { Icon } from '../ui/Icon'
import { shownClip } from './binPlayer.ts'
import { setBinPlayerShown, useBinPlayerShown } from './binPlayerPref.ts'
import type { DraftCut } from './draft'
import type { Selection } from './workspace/selection.ts'

/*
 * The bin's player (`clip-tab-and-player`, design D2): the one clip preview of Edit mode, at the
 * top of the clip bin, outside the bin's scroll box. It shows the clip the selection names
 * (`shownClip`), as its thumbnail, and loads nothing until Play is pressed. Hide player folds it to
 * its heading and a Show player, and the choice is kept (`binPlayerPref`). The whole region counts
 * as "inside a clip preview" for the workspace's keys (`.bin-player`, `shortcuts.ts`), open or not.
 *
 * `ClipPreview` does the playing; this decides which clip, and whether it is open. It is keyed by
 * the clip and by `open`, so opening and closing start it afresh, and a clip's move into another
 * chapter, which changes neither, leaves the preview as it was.
 */

const NO_CUTS: readonly DraftCut[] = []

/** `.preview-play` in a docked preview, and the controls Hide and Show leave focus on. */
type FocusTarget = 'play' | 'show' | 'hide'
const FOCUS_SELECTOR: Record<FocusTarget, string> = {
  play: '.preview-play',
  show: '.bin-player-show',
  hide: '.preview-close, .bin-player-hide',
}

export function BinPlayer({
  eventId,
  selection,
  clips,
  nameOf,
  cutsOf,
  turnOf,
  locked,
  previews,
  focusAsk,
  onAnnounce,
}: {
  eventId: string
  /** The page's one selection: it names the clip shown. */
  selection: Selection
  /** The clips the event lists, as the draft has them. */
  clips: ReadonlyMap<string, Clip>
  /** The clip's name as its row names it. */
  nameOf: (identity: string) => string
  /** The clip's cuts as listed now. */
  cutsOf: (identity: string) => readonly DraftCut[]
  /** The clip's turn in the draft. */
  turnOf: (identity: string) => Turn
  /** A save or a move of marked clips is pending: Set From and Set To change nothing. */
  locked: boolean
  previews: ClipPreviews
  /** Counts the row Watch presses: each moves keyboard focus to Play once the player shows its clip. */
  focusAsk: number
  onAnnounce: (message: string) => void
}) {
  const id = useId()
  const wanted = useBinPlayerShown()
  const [was, setWas] = useState<string | null>(null)
  const listed = useMemo(() => new Set(clips.keys()), [clips])
  // A clip on disk: an ignored one plays, a missing one has nothing to play.
  const onDisk = useCallback(
    (identity: string) => {
      const status = clips.get(identity)?.status
      return status !== undefined && status !== 'missing'
    },
    [clips],
  )
  const shown = shownClip(selection, was, listed, onDisk)
  if (shown !== was) {
    setWas(shown)
  }
  const clip = shown === null ? undefined : clips.get(shown)
  const mtime = clip?.mtime ?? null
  const identity = clip?.identity
  const ref = useMemo(
    () => (identity === undefined ? null : { identity, mtime }),
    [identity, mtime],
  )

  const open = usePreviewOpen(previews, shown ?? '')
  const rootRef = useRef<HTMLDivElement>(null)
  const focusNext = useRef<FocusTarget | null>(null)
  const playOnOpen = useRef(false)

  // A new shown clip, or a hidden player, closes whatever preview is open: one at a time.
  useLayoutEffect(() => {
    const held = previews.open()
    if (held !== null && (!wanted || held !== shown)) {
      previews.hide(held)
    }
  }, [previews, shown, wanted])

  useLayoutEffect(() => {
    if (!open) {
      playOnOpen.current = false
    }
  }, [open])

  const focusIn = (target: FocusTarget): void => {
    rootRef.current?.querySelector<HTMLElement>(FOCUS_SELECTOR[target])?.focus({ preventScroll: true })
  }
  // Focus once the change is on screen: the control that held it may have been replaced.
  useLayoutEffect(() => {
    const target = focusNext.current
    if (target !== null) {
      focusNext.current = null
      focusIn(target)
    }
  })
  // The row's Watch: Play takes focus once the player shows the clip that was pressed.
  const handledAsk = useRef(focusAsk)
  useLayoutEffect(() => {
    if (focusAsk !== handledAsk.current && wanted) {
      handledAsk.current = focusAsk
      focusIn('play')
    }
  })

  const onOpen = useCallback(() => {
    if (shown !== null) {
      playOnOpen.current = true
      previews.show(shown, 'player')
    }
  }, [previews, shown])
  // Escape: the preview closes, focus stays on Play, and the selection is left as it is.
  const onClose = useCallback(() => {
    if (shown !== null && previews.open() === shown) {
      focusNext.current = 'play'
      previews.hide(shown)
    } else {
      focusIn('play')
    }
  }, [previews, shown])
  const onHide = useCallback(() => {
    if (shown !== null) {
      previews.hide(shown)
    }
    focusNext.current = 'show'
    setBinPlayerShown(false)
  }, [previews, shown])
  const onShow = useCallback(() => {
    focusNext.current = 'hide'
    setBinPlayerShown(true)
  }, [])
  // Set From and Set To write the shown clip's panel fields in the next task (design D4).
  const onSet = useCallback(() => undefined, [])

  const name = shown === null ? null : nameOf(shown)
  const cuts = shown === null ? NO_CUTS : cutsOf(shown)

  return (
    <div
      ref={rootRef}
      className="bin-player"
      data-state={!wanted ? 'hidden' : shown === null ? 'empty' : open ? 'open' : 'closed'}
      onKeyDown={(event) => {
        // The player's own Escape (the preview's handles its own): never the selection's.
        if (event.key === 'Escape' && !event.defaultPrevented) {
          event.preventDefault()
          event.stopPropagation()
        }
      }}
    >
      <div className="bin-player-head">
        <h2 className="bin-player-title">
          <span>Player</span>
          {name !== null && <span className="bin-player-clip">{name}</span>}
        </h2>
        {!wanted && (
          <button
            type="button"
            className="btn btn-secondary btn-compact bin-player-show"
            aria-label={SHOW_PLAYER_NAME}
            onClick={onShow}
          >
            <Icon name="chevron-down" />
            {SHOW_PLAYER}
          </button>
        )}
        {wanted && shown === null && (
          <button
            type="button"
            className="btn btn-ghost btn-icon bin-player-hide"
            aria-label={HIDE_PLAYER_BARE}
            title="Hide player"
            onClick={onHide}
          >
            <Icon name="x" />
          </button>
        )}
      </div>
      {wanted && shown === null && <p className="bin-player-none">{NO_CLIP_TO_WATCH}</p>}
      {wanted && shown !== null && ref !== null && name !== null && (
        <ClipPreview
          key={`${shown}:${open}`}
          id={`player-${id}`}
          eventId={eventId}
          clip={ref}
          proxy={clip?.proxy ?? null}
          name={name}
          cuts={cuts}
          locked={locked}
          turn={turnOf(shown)}
          previews={previews}
          open={open}
          autoPlay={open && playOnOpen.current}
          onOpen={onOpen}
          onHide={onHide}
          onSet={onSet}
          onClose={onClose}
          onAnnounce={onAnnounce}
        />
      )}
    </div>
  )
}
