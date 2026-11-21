import './binPlayer.css'

import {
  useCallback,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import type { CSSProperties } from 'react'
import { createPortal } from 'react-dom'

import { clipMediaUrl } from '../api/clipMedia'
import type { Clip } from '../api/event'
import type { CutPanels } from '../cuts/CutsPanel'
import { checkCut, clipLength, formatTime } from '../cuts/times'
import type { CutField } from '../cuts/times'
import { ClipPreview, useClipLength, usePreviewOpen } from '../preview/ClipPreview'
import {
  HIDE_PLAYER_BARE,
  NOT_LOADED,
  NO_CLIP_TO_WATCH,
  SET_WORDS,
  SHOW_PLAYER,
  SKIP_CUTS,
  setWords,
  showPlayerName,
  timeCells,
} from '../preview/playback'
import type { Turn } from '../rotate/turn.ts'
import { ClockGroup } from '../ui/Clock'
import { Icon } from '../ui/Icon'
import { cuttable, shownClip } from './binPlayer.ts'
import { setBinPlayerShown, useBinPlayerShown } from './binPlayerPref.ts'
import type { DraftCut } from './draft'
import type { Selection } from './workspace/selection.ts'

/*
 * The bin's player (`clip-tab-and-player`, design D2): the one clip preview of Edit mode, at the
 * top of the clip bin, outside the bin's scroll box. It shows the clip the selection names
 * (`shownClip`), as its thumbnail, and loads nothing until Play is pressed. Hide player removes
 * it, leaving no bar of its own: a Show player button, named for the shown clip, takes its place in
 * the bin toolbar's first row (`showSlot`), and the choice is kept (`binPlayerPref`). The whole region counts
 * as "inside a clip preview" for the workspace's keys (`.bin-player`, `shortcuts.ts`), open or not.
 *
 * `ClipPreview` does the playing; this decides which clip, and whether it is open. It is keyed by
 * the clip and by `open`, so opening and closing start it afresh (Skip cuts is kept here, per
 * clip), and a clip's move into another chapter, which changes neither, leaves the preview as it
 * was.
 */

const NO_CUTS: readonly DraftCut[] = []
const NEVER = (): (() => void) => () => undefined

/** `.preview-play` in a docked preview, and the controls Hide and Show leave focus on. */
type FocusTarget = 'play' | 'show' | 'hide'
const FOCUS_SELECTOR: Record<'play' | 'hide', string> = {
  play: '.preview-play',
  hide: '.preview-close, .bin-player-hide',
}

/**
 * The player with no shown clip: the closed preview's own box and rows (head, 16:9 stage, Play
 * and playhead, the source line, Skip cuts and the Set buttons) with a placeholder for the
 * picture and every control `aria-disabled`, so the first selection moves no row of the bin
 * (design D2). It shares `ClipPreview`'s classes, so the two cannot drift apart in size.
 */
function EmptyPreview({ onHide }: { onHide: () => void }) {
  const { time, length } = timeCells(0, null)
  const none = (): void => undefined
  return (
    <section className="clip-preview" aria-label="Player">
      <div className="preview-head">
        <span className="preview-time" aria-hidden="true">
          <ClockGroup label="Clip" time={time} length={length} />
        </span>
        <button
          type="button"
          className="btn btn-ghost btn-icon preview-close bin-player-hide"
          aria-label={HIDE_PLAYER_BARE}
          title="Hide player"
          onClick={onHide}
        >
          <Icon name="x" />
        </button>
      </div>
      <div className="preview-stage">
        <span className="preview-status">{NO_CLIP_TO_WATCH}</span>
      </div>
      <div className="preview-transport">
        <button
          type="button"
          className="btn btn-secondary btn-icon preview-play"
          aria-label="Play"
          aria-disabled="true"
          onClick={none}
        >
          <Icon name="play" />
        </button>
        <div
          className="cut-bar"
          role="slider"
          tabIndex={0}
          aria-label="Playhead"
          aria-disabled="true"
          aria-valuemin={0}
          aria-valuemax={0}
          aria-valuenow={0}
          aria-valuetext={NOT_LOADED}
        >
          <span className="cut-bar-track" />
          <span className="cut-bar-head" style={{ '--at': '0%' } as CSSProperties} />
        </div>
      </div>
      <p className="preview-source">{NOT_LOADED}</p>
      <div className="preview-actions">
        <button
          type="button"
          className="btn btn-ghost btn-compact preview-skip"
          aria-pressed={false}
          aria-disabled="true"
          onClick={none}
        >
          <Icon name="skip-forward" />
          {SKIP_CUTS}
        </button>
        {(['start', 'end'] as const).map((field) => (
          <button
            key={field}
            type="button"
            className="btn btn-secondary btn-compact preview-set"
            data-field={field}
            aria-disabled="true"
            onClick={none}
          >
            {SET_WORDS[field]}
          </button>
        ))}
      </div>
    </section>
  )
}

export function BinPlayer({
  eventId,
  selection,
  clips,
  nameOf,
  cutsOf,
  turnOf,
  locked,
  panels,
  onTyped,
  focusAsk,
  showSlot,
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
  /** The editor's panel store: Set From and Set To write the shown clip's fields in it. */
  panels: CutPanels
  /** The shown clip's panel went from no typed text to some, or back (the Cuts control says "typed"). */
  onTyped: (identity: string, typed: boolean) => void
  /** Counts the row Watch presses: each moves keyboard focus to Play once the player shows its clip. */
  focusAsk: number
  /** Where the Show player button goes while the player is hidden: the toolbar's first row. */
  showSlot: HTMLElement | null
  onAnnounce: (message: string) => void
}) {
  const id = useId()
  const wanted = useBinPlayerShown()
  const [was, setWas] = useState<string | null>(null)
  // Skip cuts is the shown clip's: off for each clip shown, and it outlives the preview's remount
  // when the preview opens or closes.
  const [skipping, setSkipping] = useState(false)
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
    setSkipping(false)
  }
  const clip = shown === null ? undefined : clips.get(shown)
  const mtime = clip?.mtime ?? null
  const identity = clip?.identity
  const ref = useMemo(
    () => (identity === undefined ? null : { identity, mtime }),
    [identity, mtime],
  )

  const { previews } = panels
  const open = usePreviewOpen(previews, shown ?? '')
  const rootRef = useRef<HTMLDivElement>(null)
  const showRef = useRef<HTMLButtonElement>(null)
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
    const control =
      target === 'show'
        ? showRef.current
        : rootRef.current?.querySelector<HTMLElement>(FOCUS_SELECTOR[target])
    control?.focus({ preventScroll: true })
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
      previews.show(shown)
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
  // Set From and Set To write the shown clip's panel fields, shown panel or hidden (design D4):
  // the panel is not opened, the bin does not scroll and focus stays on the pressed control. The
  // clip then counts as typed, as for any typed time, and the value is announced.
  const onSet = useCallback(
    (field: CutField, seconds: number) => {
      if (shown === null || locked || clip === undefined || !cuttable(clip)) {
        return
      }
      const held = panels.get(shown)
      const had = (held?.start.trim() ?? '') !== '' || (held?.end.trim() ?? '') !== ''
      panels.setTyped(shown, field, formatTime(seconds))
      if (!had) {
        onTyped(shown, true)
      }
      onAnnounce(setWords(field, seconds))
    },
    [shown, clip, locked, panels, onTyped, onAnnounce],
  )

  const name = shown === null ? null : nameOf(shown)
  const cuts = shown === null ? NO_CUTS : cutsOf(shown)
  // The panel's fields as typed: the bar draws the span they make, when a cut would accept it.
  const fields = useSyncExternalStore(
    useCallback(
      (listener: () => void) => (shown === null ? NEVER() : panels.subscribe(shown, listener)),
      [panels, shown],
    ),
    () => (shown === null ? undefined : panels.get(shown)),
  )
  const previewed = useClipLength(previews, clipMediaUrl(eventId, { identity: shown ?? '', mtime }))
  const length = clipLength(previewed, clip?.duration ?? null)
  const typed = useMemo(() => {
    if (fields === undefined) {
      return null
    }
    const checked = checkCut(cuts, fields.start, fields.end, length)
    return checked.ok ? { in: checked.in, out: checked.out } : null
  }, [cuts, fields, length])

  // Hidden, the player has no bar: only the button in the toolbar, which names the shown clip.
  if (!wanted) {
    return showSlot === null
      ? null
      : createPortal(
          <button
            ref={showRef}
            type="button"
            className="btn btn-secondary btn-compact bin-player-show"
            aria-label={showPlayerName(name)}
            title={SHOW_PLAYER}
            onClick={onShow}
          >
            <Icon name="chevron-down" />
            <span className="mark-words">{SHOW_PLAYER}</span>
          </button>,
          showSlot,
        )
  }

  return (
    <div
      ref={rootRef}
      className="bin-player"
      data-state={shown === null ? 'empty' : open ? 'open' : 'closed'}
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
      </div>
      {shown === null && <EmptyPreview onHide={onHide} />}
      {shown !== null && ref !== null && name !== null && (
        <ClipPreview
          key={`${shown}:${open}`}
          id={`player-${id}`}
          eventId={eventId}
          clip={ref}
          proxy={clip?.proxy ?? null}
          name={name}
          cuts={cuts}
          typed={typed}
          locked={locked}
          turn={turnOf(shown)}
          previews={previews}
          open={open}
          autoPlay={open && playOnOpen.current}
          onOpen={onOpen}
          onHide={onHide}
          onSet={clip !== undefined && cuttable(clip) ? onSet : undefined}
          skipOn={skipping}
          onSkip={setSkipping}
          onClose={onClose}
          onAnnounce={onAnnounce}
        />
      )}
    </div>
  )
}
