import './timeline.css'

import type { ReactNode } from 'react'
import {
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'

import { createPortal } from 'react-dom'

import '../rotate/rotate.css'
import { TimelinePanesContext } from './panes'
import { focusFacts, workspaceCommand } from '../edit/workspace/shortcuts.ts'
import { lastInput, pointerHeld } from '../edit/workspace/modality.ts'
import { shortcutsEnabled } from '../edit/workspace/shortcutSwitch.ts'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import type { IconName } from '../ui/Icon'
import { Menu } from '../ui/Menu'
import type { MenuClose } from '../ui/Menu'
import { mayReturnFocus } from '../ui/returnFocus'
import { clipMenu, focusAfter, focusAfterMany, menuSelects, targets } from './clipMenu'
import type { ClipAction } from './clipMenu'
import { clipPlace, clipSelectedWords, cutSelectedWords, lengthWords } from './clipPanel'
import { addCutAtPlayhead, cutAtClipPlayhead } from './cutAtPlayhead'
import { ClipTrackPart } from './ClipTrackPart'
import type { TrackCutsView } from './trackCuts'
import { CutFields } from './CutFields'
import type { Selected } from './CutFields'
import { posterFromPlayhead, USE_AS_POSTER } from '../edit/poster.ts'
import { PlayheadReadout } from './Playhead'
import { PrepareButton, PrepareJob } from './Prepare'
import type { PrepareControl } from './Prepare'
import type { AnalysisControl } from './overlays/control'
import { useSuggestions } from './overlays/useSuggestions'
import { CardLayer } from './CardLayer'
import { Track } from './Track'
import type { CardLaneModel, ScrubPhase, ScrubSurface } from './Track'
import {
  cardBlocks,
  cardHandles,
  withDurations,
  cardMap,
  cardPlacements,
  cardSubject,
  clipTimeAt,
  trackLayout as withCards,
} from './cards'
import type { CardMap, CardSpec, CardsSource, Decorators, Placement } from './cards'
import { cardJobs } from './cardRequests'
import { positionOnTrack, stepFramesOnTrack, trackStart } from './play'
import { useCardImages } from './useCardImages'
import type { SelectionBinding } from '../edit/workspace/useSelection.ts'
import { createDragStore, held as dragHeld, shiftMs } from './dragStore'
import { edgeAnnouncement, edgeEdit, snappingWords, toPlayheadRefusal, trimToPlayhead } from './edgeTrim'
import type { DragStore } from './dragStore'
import type { ChapterKey } from '../edit/draft'
import { chapterHeading } from '../events/labels.ts'
import type { ReorderModel } from './ClipDrag'
import { MOVE_LOCKED, MOVE_ONE_WORDS, bandSlot, spanHit } from './clipDrag'
import { lastClip, pressClip, selectedClips, selectionWords } from '../edit/workspace/selection.ts'
import type { Press } from '../edit/workspace/selection.ts'
import { stepSlot } from './keys'
import { dropSlot, includeSlot } from './reorder'
import type { DrawnChapter } from './reorder'
import type { ClipState } from '../edit/clipInspector'
import type { ClipMenuOpen, EditBinding } from './editing'
import { selectionStands } from './handles'
import type { KeyAction } from './keys'
import {
  CARDS_UNKNOWN,
  cardsNotes,
  FILM_FAILED,
  FILM_FAILED_DETAIL,
  FIT,
  PAUSE,
  PREVIEW_OPEN,
  PLAY,
  PREVIOUS_CLIP,
  NEXT_CLIP,
  ZOOM_IN,
  ZOOM_OUT,
  movieStat,
  playheadAnnouncement,
} from './labels'
import { chapterBands, footageMs, movieMs, trackLayout } from './layout'
import type { TrackClip } from './layout'
import type { ShiftFrom } from './Track'
import type { Layout } from './model'
import {
  DEFAULT_PPS,
  MAX_PPS,
  ZOOM_STEP,
  anchorFor,
  extentMs,
  fitCanvas,
  pxToTime,
  sliderToPps,
  timeToPx,
  wheelFactor,
  wheelPointerX,
  zoomAt,
} from './model'
import { createPlayhead } from './playhead'
import { afterRead, clipStep, endPosition, globalMs, hasKeptFrame, keptPosition, timedOf } from './position'
import type { Position } from './position'
import { hasFrame, snapshotOf, useFrameReady } from './posterFrame'
import { useTimelineVideo } from './useTimelineVideo'
import { useVisibleRange } from './useVisibleRange'
import { restoredZoom, zoomMemory } from './zoomMemory'
import { createZoomSettle } from './zoomSettle'
import type { EdgeKey } from './zoomSettle'
import type { ZoomMemo } from './zoomMemory'
import { ZoomSlider } from './ZoomSlider'

/*
 * Edit mode's Timeline (D-20): the picture, the transport and zoom, and the track. It writes
 * nothing itself: its edits go to the editor's draft. The pieces that move often are small and read the playhead's store
 * themselves, so a scrub or a playing video re-renders them and not the whole track.
 */

/** The icon of a menu item. */
function menuIcon(action: ClipAction): IconName {
  switch (action.kind) {
    case 'rotate':
      return action.way === 'left' ? 'rotate-ccw' : 'rotate-cw'
    case 'cut':
      return 'scissors'
    case 'poster':
      return 'film'
    case 'move':
      return 'arrow-right'
    case 'ignore':
      return 'eye-off'
    case 'include':
      return 'plus'
    case 'remove':
      return 'x'
    case 'restore':
      return 'rotate-ccw'
  }
}

/** What `Q` and `W` say while a save or a move of several clips is pending. */
const EDGE_UNAVAILABLE = 'Nothing trimmed: trimming waits for the save or the move of several clips to finish.'
/** The playhead is brought back into view when it comes this close to the scroller's edge. */
const EDGE_PX = 24
/** The track's margin around the view during a slider drag, in views (else one view a side). */
const LIVE_OVERSCAN = 0.25
const LIVE_SETTLE_MS = 200

/**
 * The edge tool a zoom keeps (design D6): the one being dragged, else the one in the track that
 * holds focus, else none.
 */
function heldEdge(
  track: HTMLElement | null,
  dragged: { identity: string; side: 'start' | 'end' } | null,
): EdgeKey | null {
  if (dragged !== null) {
    return { identity: dragged.identity, side: dragged.side }
  }
  const active = document.activeElement
  if (track === null || !(active instanceof HTMLElement) || !track.contains(active)) {
    return null
  }
  const tool = active.closest<HTMLElement>('.tl-edge')
  const identity = tool?.dataset.identity
  const side = tool?.dataset.side
  return identity !== undefined && (side === 'start' || side === 'end') ? { identity, side } : null
}

/** What the Timeline takes: the same for the stacked `Timeline` and for `useTimeline`. */
export type TimelineProps = {
  eventId: string
  clips: readonly TrackClip[]
  /** The drawn chapters' names by index, as `clips[].chapter` and `cards.specs` count them. */
  chapterNames: readonly string[]
  /** The drawn chapters' keys in the draft, by the same index. */
  chapterKeys: readonly ChapterKey[]
  prepare: PrepareControl
  /** The analysis lane (`overlays/`): absent, the Timeline has none and reads no analysis. */
  analysis?: AnalysisControl
  /** Edit mode's binding: the draft's cuts and turns, the trim handles, the poster. */
  editing: EditBinding
  /** The title cards: the drawn chapters' cards, the decorator, the page's one selection. */
  cards: {
    /** One per drawn chapter, by the index `clips[].chapter` uses (`draftCardSpecs`). */
    specs: readonly CardSpec[]
    /** The service's answer (`title_cards`), the draft's switch laid over it; `invalid` is no answer. */
    decorators: Decorators
    source: CardsSource | null
    /** The draft event style as a save would write it, while it is not the saved one (the previews send it). */
    previewStyle?: { [key: string]: unknown }
    /** The detail's `title_cards_error`, said when there is no answer. */
    error: string | null
    selection: SelectionBinding
  }
  /** The id of the Timeline help's paragraph that says what the cut fields take (Edit mode). */
  cutHintId: string
}

/**
 * The Timeline's parts over one state (design D2 of `editor-workspace-layout`): the viewer
 * (the picture and the transport), the track (the tool row, the lanes and their notes), the clip
 * panel (the track-only part of the Clip tab: trims, cuts, poster, and the selected cut's fields)
 * and the suggestion panel (the selected suggestion's decision). Each is its own
 * `.timeline` box, so it can sit in a pane of its own; there is still one `<video>`.
 */
export type TimelineParts = {
  viewer: ReactNode
  track: ReactNode
  /**
   * What the Clip tab needs the track for (`ClipTrackPart`) and the selected cut's fields: put into
   * the slot of the editor's `ClipInspector`, for a clip the track draws.
   */
  clipPanel: ReactNode
  /** The selected suggestion's decision (the inspector's Suggestion tab). */
  suggestionPanel: ReactNode
}

/**
 * The Timeline: in Edit mode's workspace the viewer and the two panels go to their panes (portals:
 * still one tree and one state), the track stays here; without one, the three are stacked.
 */
export function Timeline(props: TimelineProps) {
  const parts = useTimeline(props)
  const panes = useContext(TimelinePanesContext)
  // The clip pane is the editor's `ClipInspector` slot, there only while a clip a chapter plays is
  // selected: without it there is nowhere for the track-only part to go, and it renders nothing.
  if (panes !== null && panes.viewer !== null && panes.suggestion !== null) {
    return (
      <>
        {createPortal(parts.viewer, panes.viewer)}
        {parts.track}
        {panes.clip !== null && createPortal(parts.clipPanel, panes.clip)}
        {createPortal(parts.suggestionPanel, panes.suggestion)}
      </>
    )
  }
  return (
    <div className="tl-parts">
      {parts.viewer}
      {parts.track}
      {parts.clipPanel}
      {parts.suggestionPanel}
    </div>
  )
}

export function useTimeline({
  eventId,
  clips,
  chapterNames,
  chapterKeys,
  prepare,
  analysis,
  editing,
  cards,
  cutHintId,
}: TimelineProps): TimelineParts {
  const posterWhyId = useId()
  const clipLay = useMemo(() => trackLayout(clips), [clips])
  const turns = editing.turns
  const decorators = cards.decorators
  const drag = useMemo(() => createDragStore(), [])
  // A black card's end edge in the air (its chapter, or null). The layout below is the committed
  // one and does not change during the drag: the later layers are translated (`data-after`)
  // (set below, without a render) and the real layout is drawn once, on release.
  const specs = cards.specs
  const dragChapter = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.getCard()
    // Only a black card adds time and moves the rest; a video card's edge changes its own block.
    return d !== null && specs.find((s) => s.chapter === d.chapter)?.card?.background === 'black'
      ? d.chapter
      : null
  })
  const placeAll = useCallback(
    (all: readonly CardSpec[]): Placement[] =>
      cardPlacements(
        all,
        clips.map((clip) => ({
          chapter: clip.chapter,
          // The full length and every span: the placement derives the kept extent itself.
          durationMs: clip.facts.durationMs,
          spans: clip.spans,
        })),
        decorators,
      ),
    [clips, decorators],
  )
  const placements = useMemo(() => placeAll(specs), [placeAll, specs])
  // Clip time stays the one time of the playhead, the cuts and the marks; `lay` below is
  // where the clips are on the track, with the black cards' spans between them.
  const map = useMemo(() => cardMap(placements, clipLay), [placements, clipLay])
  const lay = useMemo(() => withCards(clipLay, map), [clipLay, map])
  const blocks = useMemo(() => cardBlocks(placements, lay), [placements, lay])
  const handles = useMemo(
    () => cardHandles(placements, blocks, specs, chapterNames),
    [placements, blocks, specs, chapterNames],
  )
  // A clip edge in the air (`clip-edge-trim`): its clip, or null. Its block is drawn live by the
  // track; what follows it moves by the change of its width, as behind a black card.
  const edgeIdentity = useSyncExternalStore(drag.subscribe, () => drag.getEdge()?.identity ?? null)
  const shifting = useMemo<ShiftFrom | null>(() => {
    if (edgeIdentity !== null) {
      const at = clips.findIndex((clip) => clip.identity === edgeIdentity)
      return at < 0
        ? null
        : { kind: 'edge', identity: edgeIdentity, fromMs: lay.startsMs[at] + extentMs(clips[at].kept) }
    }
    const handle = dragChapter === null ? undefined : handles.find((h) => h.chapter === dragChapter)
    const block = handle === undefined ? undefined : blocks[handle.index]
    return handle === undefined || block === undefined
      ? null
      : ({
          kind: 'card',
          chapter: handle.chapter,
          fromMs: block.startMs + block.widthMs,
          baseTenths: handle.tenths,
        } satisfies ShiftFrom)
  }, [edgeIdentity, clips, lay, dragChapter, handles, blocks])
  // The chapters' names now, by index: what a card's place on the playhead is called.
  const names = chapterNames
  const leadMs = useMemo(() => new Map(map.gaps.map((gap) => [gap.clip, gap.lengthMs])), [map])
  const selection = cards.selection
  // Each clip's timing with its kept extent: the playhead's rules land on kept frames only.
  const facts = useMemo(() => clips.map(timedOf), [clips])
  const bands = useMemo(() => chapterBands(chapterNames, clips), [chapterNames, clips])
  // What a clip block dragged on the track drops against (`track-drag-edit`): the drawn chapters
  // with their clips, the nearest slot, and the lists' own edit on release.
  const reorder = useMemo<ReorderModel>(() => {
    const named = chapterNames.some((name) => name !== '')
    const chapters: DrawnChapter[] = chapterKeys.map((key, at) => ({
      key,
      name: chapterHeading(chapterNames[at] ?? '', named),
      identities: clips.filter((clip) => clip.chapter === at).map((clip) => clip.identity),
    }))
    const drawn = new Set(clips.map((clip) => clip.identity))
    return {
      chapters,
      slotAt: (identity, trackMs) => dropSlot(clipLay, map, chapters, trackMs, identity),
      onDrop: (identity, slot) => editing.onMove(identity, slot, drawn),
      slotNear: (trackMs) => includeSlot(clipLay, map, chapters, trackMs),
      drawn,
      overBin: editing.overBin,
      onIgnore: editing.onIgnore,
      onGroupDrop: (identities, dragged, slot) => editing.onMoveMany(identities, dragged, slot, drawn),
      onGroupIgnore: editing.onIgnoreMany,
    }
  }, [chapterNames, chapterKeys, clips, clipLay, map, editing])
  const draftCuts = editing.cuts
  const movie = useMemo(() => movieMs(clips, draftCuts), [clips, draftCuts])
  // The footage the movie line counts against: full durations, which edge cuts do not shorten.
  const footage = useMemo(() => footageMs(clips), [clips])
  // The playhead opens at the start of the movie: its opening card when that is black.
  const playhead = useMemo(
    () => createPlayhead(trackStart(map, clipLay, facts, names)),
    [],
  )
  const previews = editing.previews
  const held = usePreviewHeld(previews)
  const video = useTimelineVideo({ eventId, clips, playhead, turns, held, map, names })
  // Every card's image, asked for once when the Timeline opens (one request at a time).
  const jobs = useMemo(
    () => cardJobs(specs, placements, cards.previewStyle),
    [specs, placements, cards.previewStyle],
  )
  const pictures = useCardImages(eventId, jobs)
  const longestCardMs = useMemo(() => Math.max(0, ...map.gaps.map((gap) => gap.lengthMs)), [map])
  // A trim in the air: the cuts' spans on the track step back while the live one is drawn.
  const trimming = useSyncExternalStore(drag.subscribe, () => drag.get() !== null)
  // The selected cut, from the page's one selection: selecting a card or a mark ends it.
  const selectedCut = selection.selection.kind === 'cut' ? selection.selection : null
  const selected = useMemo<Selected | null>(
    () => (selectedCut === null ? null : { identity: selectedCut.identity, key: selectedCut.key }),
    [selectedCut],
  )
  const setSelection = selection.set
  const keepSelection = selection.keep
  const select = useCallback(
    (identity: string, key: string) => setSelection({ kind: 'cut', identity, key }),
    [setSelection],
  )
  // The selected clip, from the page's one selection: the block's press and the bin row's write it.
  const selectedClip = selection.selection.kind === 'clip' ? selection.selection.identity : null
  const selectClip = useCallback(
    (identity: string) => setSelection({ kind: 'clip', identity }),
    [setSelection],
  )
  // Every clip the selection holds, read once per selection (a `Set` for each block's test).
  const selectedSet = useMemo<ReadonlySet<string>>(
    () => new Set(selectedClips(selection.selection)),
    [selection.selection],
  )
  // The clip pressed last: the track scrolls to it.
  const lastSelected = lastClip(selection.selection)
  // The order a Shift press ranges over: the clips the track draws a block for, in drawn order.
  const drawnOrder = useMemo(
    () => clips.filter((_, at) => hasKeptFrame(facts[at])).map((c) => c.identity),
    [clips, facts],
  )
  const clearSelection = selection.clear
  // A click on a clip's block: the cut whose span holds the press, else the clip (the cut's span
  // selects its cut, as it did when the lane took the press).
  const pressClipRef = useRef<(identity: string, x: number, press: Press) => void>(() => undefined)
  pressClipRef.current = (identity, x, press) => {
    if (press !== 'alone') {
      setSelection(pressClip(selection.selection, identity, press, drawnOrder))
      return
    }
    if (!Number.isNaN(x)) {
      const pos = positionOf(x)
      if (pos.card == null && clips[pos.clip].identity === identity) {
        const cut = editing
          .listed(identity)
          .find((c) => !c.removed && Math.round(c.in * 1000) <= pos.ms && pos.ms < Math.round(c.out * 1000))
        if (cut !== undefined) {
          select(identity, cut.key)
          return
        }
      }
    }
    selectClip(identity)
  }
  const spanAtRef = useRef<(identity: string, x: number) => boolean>(() => false)
  spanAtRef.current = (identity, x) => {
    const pos = positionOf(x)
    return spanHit(pos, clips[pos.clip]?.identity, identity, editing.listed(identity)) !== null
  }
  const spanAt = useCallback((identity: string, x: number) => spanAtRef.current(identity, x), [])
  const onPressClip = useCallback(
    (identity: string, x: number, press: Press) => pressClipRef.current(identity, x, press),
    [],
  )
  // Enter on a block: the clip alone, added or taken out (Ctrl/Cmd), or the range (Shift).
  const onPressClipKey = useCallback(
    (identity: string, press: Press) => pressClipRef.current(identity, Number.NaN, press),
    [],
  )
  const selectCard = selection.select
  const revealCard = selection.reveal
  const pickCard = selectCard
  // A block's body shows the card's editor in the inspector; focus stays on the block.
  const pressCard = revealCard
  // Reset ends a cut selection (the Timeline mounting anew, on a Refresh or a Save, does not).
  const epoch = editing.epoch
  const seenEpoch = useRef(epoch)
  useEffect(() => {
    if (seenEpoch.current !== epoch) {
      seenEpoch.current = epoch
      if (selection.selection.kind === 'cut') {
        selection.clear()
      }
    }
  }, [epoch, selection])
  // A new read numbers a clip's cuts again (`r0`, `r1`…), so a cut selection made on the old one
  // would name another cut: it ends with the read, also when the Timeline mounts anew (a Save, a
  // Refresh, leaving and re-entering Edit mode), where the cleanup does it.
  const baseline = editing.baseline
  const seenBaseline = useRef(baseline)
  useEffect(() => {
    if (seenBaseline.current !== baseline) {
      seenBaseline.current = baseline
      if (selection.selection.kind === 'cut') {
        selection.clear()
      }
    }
  }, [baseline, selection])
  const latestSelection = useRef(selection)
  latestSelection.current = selection
  useEffect(
    () => () => {
      if (latestSelection.current.selection.kind === 'cut') {
        latestSelection.current.clear()
      }
    },
    [],
  )
  // A cut removed ends a selection (`keptSelection`).
  useEffect(() => {
    if (selected !== null) {
      // A cut that became part of a leading or a trailing cut has no handle, nor a selection,
      // unless it is now the clip's edge cut, which its Trim In or Trim Out edits (`clip-edge-trim`).
      const clip = clips.find((c) => c.identity === selected.identity)
      const there = selectionStands(
        editing.listed(selected.identity),
        selected.key,
        clip?.kept ?? null,
        clip?.facts.durationMs ?? 0,
      )
      keepSelection({
        cuts: new Map([[selected.identity, there ? [{ key: selected.key, removed: false }] : []]]),
      })
    }
  }, [editing, selected, clips, keepSelection])

  // A clip or cut selection ending (Escape, a clear) while focus was in the Clip tab, which then
  // unmounts: focus goes back to the clip's block, so it never drops onto the page body.
  const heldClip = lastSelected ?? selectedCut?.identity ?? null
  const wasClip = useRef<string | null>(null)
  // Where focus goes when Ignore clips empties the selection: the clip that stays next to the
  // ones ignored (`focusAfterMany`), or the track (`null`). Absent when nothing was ignored.
  const ignoredFocus = useRef<{ next: string | null } | null>(null)
  useLayoutEffect(() => {
    const was = wasClip.current
    wasClip.current = heldClip
    if (was === null || heldClip !== null) {
      return
    }
    const active = document.activeElement
    const after = ignoredFocus.current
    ignoredFocus.current = null
    if (active === null || active === document.body) {
      if (after !== null) {
        const stays = Array.from(
          document.querySelectorAll<HTMLElement>('.tl-clip-press[data-identity]'),
        ).find((block) => block.dataset.identity === after.next)
        ;(stays ?? scroller.current)?.focus({ preventScroll: true })
        return
      }
      const at = clips.findIndex((c) => c.identity === was)
      document
        .querySelector<HTMLElement>(`.tl-clip-press[data-index="${at}"]`)
        ?.focus({ preventScroll: true })
    }
  }, [heldClip, clips])

  // A clip that left the event ends its selection (`keptSelection`): the editor's, which knows the
  // clips the track does not draw (ignored, missing) that the Clip tab still shows.

  const scroller = useRef<HTMLDivElement>(null)
  const grip = useRef<HTMLDivElement>(null)
  const [range, syncRange, expectRange] = useVisibleRange(scroller)
  // A Zoom slider drag in progress: the track draws a narrower margin around the view while it
  // lasts (`LIVE_OVERSCAN`), so each of its frames lays out fewer clips; the full margin comes
  // back `LIVE_SETTLE_MS` after the slider's last zoom.
  const [live, setLive] = useState(false)
  const settle = useRef(0)
  useEffect(() => () => window.clearTimeout(settle.current), [])
  // A zoom in progress (design D6): from its first input until it settles the track leaves the
  // edge tools out, but for the one that holds focus (or is dragged) when it starts. Null: no zoom.
  const [zoomHold, setZoomHold] = useState<{ kept: EdgeKey | null } | null>(null)
  const [zoomSettle] = useState(() =>
    createZoomSettle(
      (zooming) => setZoomHold(zooming ? { kept: heldEdge(scroller.current, drag.getEdge()) } : null),
      { set: (run, ms) => window.setTimeout(run, ms), clear: (id) => window.clearTimeout(id) },
    ),
  )
  useEffect(() => () => zoomSettle.cancel(), [zoomSettle])
  // The zoom this event had in this tab, else Fit (`zoomMemory`, design D4).
  const [zoom, setZoom] = useState<ZoomMemo>(
    () => zoomMemory.read(eventId) ?? { pps: DEFAULT_PPS, fitted: true },
  )
  const pendingScroll = useRef<number | null>(null)
  const dragging = useRef(false)
  const [announcement, setAnnouncement] = useState('')
  // The edge drags' snapping (`S`), on until switched off, for as long as the page is open.
  const snapping = useRef(true)
  const edgeSide = useSyncExternalStore(drag.subscribe, () => drag.getEdge()?.side ?? null)
  const [noPicture, setNoPicture] = useState<ReadonlySet<string>>(new Set())

  // The playhead grip's half-width (`--tl-end-gutter`): the canvas keeps it free past the end, and
  // Fit fits the timeline into the rest, so the grip at the last moment never makes it scroll.
  const [gutter, setGutter] = useState(0)
  useLayoutEffect(() => {
    const el = grip.current
    if (el !== null) {
      const half = el.offsetWidth / 2
      setGutter((was) => (was === half ? was : half))
    }
  }, [range.width])
  const fit = range.width > 0 ? fitCanvas(lay.totalMs, range.width, gutter).pps : DEFAULT_PPS
  // Held to [Fit, MAX_PPS] as the view now is: Fit follows the view, a kept scale is re-bounded.
  const shown = restoredZoom(zoom, fit, MAX_PPS) ?? zoom
  const pps = shown.pps
  const measured = range.width > 0
  // Kept for the tab's session once the view is measured (never the scale before it was).
  useEffect(() => {
    if (measured) {
      zoomMemory.write(eventId, { fitted: shown.fitted, pps })
    }
  }, [eventId, measured, shown.fitted, pps])
  // The scale as last requested: set by a zoom before its render, so two zooms in one frame
  // anchor on the second's real starting scale (design D2); a render brings it back in step.
  const ppsRef = useRef(pps)
  ppsRef.current = pps
  // A clip selected out of view (from the bin) is scrolled to: the zoom stays, and so does focus.
  useEffect(() => {
    const el = scroller.current
    const at = lastSelected === null ? -1 : clips.findIndex((c) => c.identity === lastSelected)
    if (el === null || at < 0 || !hasKeptFrame(facts[at])) {
      return
    }
    const left = timeToPx(lay.startsMs[at], ppsRef.current)
    const width = timeToPx(extentMs(clips[at].kept), ppsRef.current)
    if (left + width > el.scrollLeft && left < el.scrollLeft + el.clientWidth) {
      return
    }
    el.scrollLeft = Math.max(0, left - Math.max(0, (el.clientWidth - width) / 2))
    // Only a press or a change of the selection scrolls; a relayout does not.
  }, [lastSelected, selection.again])
  const fitRef = useRef(fit)
  fitRef.current = fit

  // The drag moves the layers behind the card by a translate on each of them (`data-after`): no
  // React render and no inherited property to resolve under the whole track. Removed in the
  // same commit that draws the released layout.
  useLayoutEffect(() => {
    const el = scroller.current
    if (shifting === null || el === null) {
      return undefined
    }
    const moved = new Set<HTMLElement>()
    const apply = () => {
      const ended = shifting.kind === 'card' ? drag.getCard() === null : drag.getEdge() === null
      if (ended) {
        return // ended: the layout drawn in this commit takes over, the cleanup lets go
      }
      const by = `${timeToPx(shiftMs(drag, shifting), ppsRef.current)}px 0`
      for (const node of el.querySelectorAll<HTMLElement>('[data-after]')) {
        if (node.style.translate !== by) {
          node.style.translate = by
          moved.add(node)
        }
      }
    }
    apply()
    const off = drag.subscribe(apply)
    return () => {
      off()
      for (const node of moved) {
        node.style.translate = ''
      }
    }
  }, [shifting, drag])

  // A zoom is applied after the commit that gave the canvas its new width. The browser rounds
  // `scrollLeft` to whole pixels: the exact value is kept, so a run of zooms (a slider drag)
  // anchors on it and the half pixels do not add up.
  const exactScroll = useRef<number | null>(null)
  useLayoutEffect(() => {
    const el = scroller.current
    if (el !== null && pendingScroll.current !== null) {
      el.scrollLeft = pendingScroll.current
      exactScroll.current = pendingScroll.current
      pendingScroll.current = null
      syncRange()
    }
  }, [pps, syncRange])

  // The clips the page read again, or the draft drew in another order: the playhead follows its
  // clip by identity, on a kept frame of it (a new leading or trailing cut moves it to the
  // nearest one); with its clip gone it goes to the start.
  const previous = useRef(clips)
  useEffect(() => {
    const was = previous.current
    previous.current = clips
    if (was === clips) {
      return
    }
    const next = afterRead(was, clips, playhead.get())
    if (next === 'start') {
      video.seekTo(trackStart(map, clipLay, facts, names))
    } else if (next !== null) {
      video.seekTo(next)
    }
  }, [clips, facts, playhead, video])

  // A card the playhead is in changed (its length dragged, the cards switched off): keep the
  // playhead where it still means the same card, else at the start of its clip.
  useEffect(() => {
    const at = playhead.get()
    const card = at.card
    if (card == null) {
      return
    }
    const gap = map.gaps.find((g) => g.chapter === card.chapter && g.clip === at.clip)
    if (gap === undefined) {
      video.seekTo(clips[at.clip] === undefined ? trackStart(map, clipLay, facts, names) : keptPosition(facts, at.clip, 0))
    } else if (gap.lengthMs !== card.lengthMs || names[gap.chapter] !== card.name) {
      video.seekTo({
        ...at,
        card: { ...card, name: names[gap.chapter] ?? '', lengthMs: gap.lengthMs, ms: Math.min(card.ms, gap.lengthMs) },
      })
    }
  }, [map, names])

  // The playhead is kept in view when it moves by key or while playing, never during a drag.
  useEffect(
    () =>
      playhead.subscribe(() => {
        const el = scroller.current
        if (el === null || dragging.current) {
          return
        }
        const x = timeToPx(globalMs(lay, playhead.get()), ppsRef.current)
        if (x < el.scrollLeft + EDGE_PX || x > el.scrollLeft + el.clientWidth - EDGE_PX) {
          el.scrollLeft = Math.max(0, x - el.clientWidth / 2)
          syncRange()
        }
      }),
    [lay, playhead, syncRange],
  )

  // Edit mode's open clip preview makes room for the Timeline's video when asked: closed,
  // then the video is created at the playhead (`useTimelineVideo`, `held`).
  const takePage = () => {
    const open = previews.open()
    if (open !== null) {
      previews.hide(open)
    }
  }
  const toggle = () => {
    if (!video.playing) {
      takePage()
    }
    video.toggle()
  }

  const announce = (pos: Position) =>
    setAnnouncement(playheadAnnouncement(clips[pos.clip].name, pos.ms, pos.card ?? null))

  /** A press on a cut's span selects the cut (a place in a card is no clip's). */
  const selectUnder = (pos: Position) => {
    if (pos.card != null) {
      return
    }
    const at = clips[pos.clip]
    const cut = editing
      .listed(at.identity)
      .find((c) => !c.removed && Math.round(c.in * 1000) <= pos.ms && pos.ms < Math.round(c.out * 1000))
    if (cut !== undefined) {
      select(at.identity, cut.key)
    }
  }

  /** The playhead's position for a track px: a clip's frame, or a place in a black card. */
  const positionOf = (x: number): Position =>
    positionOnTrack(map, clipLay, facts, names, pxToTime(x, ppsRef.current))

  const scrubAt = (x: number, phase: ScrubPhase, surface: ScrubSurface) => {
    if (surface === 'lane' && (phase === 'start' || phase === 'tap')) {
      const inCard = clipTimeAt(map, pxToTime(x, ppsRef.current))
      if (inCard.kind === 'card') {
        // A press in a black card's span selects the card, and the playhead goes there too.
        const chapter = cards.specs[inCard.chapter].chapter
        if (phase === 'tap') {
          // The tap is on the scrub surface; the block is the opener Escape in the editor returns focus to.
          const block = Array.from(
            document.querySelectorAll<HTMLElement>('button.tl-card[data-card]'),
          ).find((b) => b.dataset.card === chapter)
          block?.focus({ preventScroll: true })
          pressCard(chapter)
        } else {
          pickCard(chapter)
        }
      } else {
        // A press on the lane's bare ground, between or past the clips, selects nothing.
        clearSelection()
      }
    }
    if (phase === 'tap') {
      // A tap drags nothing: place the playhead and let a playing video go on from there.
      const pos = positionOf(x)
      takePage()
      video.seekTo(pos)
      announce(pos)
      if (surface === 'lane') {
        selectUnder(pos)
      }
      return
    }
    if (phase === 'start') {
      dragging.current = true
      takePage()
      video.scrubStart()
      if (surface === 'lane') {
        selectUnder(positionOf(x))
      }
    }
    const pos = positionOf(x)
    video.seekTo(pos)
    if (phase === 'end') {
      dragging.current = false
      video.scrubEnd()
      announce(pos)
    }
  }

  /** A press in a black card's block: the card is selected (by the block) and the playhead goes there. */
  const placeInCard = (_chapter: string, trackMs: number) => {
    const pos = positionOnTrack(map, clipLay, facts, names, trackMs)
    takePage()
    video.seekTo(pos)
    announce(pos)
  }

  /** Previous / Next clip: the playhead to the first kept frame of the drawn clip (null: none). */
  const toClip = (dir: 1 | -1) => {
    const pos = clipStep(facts, playhead.get(), dir)
    if (pos === null) {
      return
    }
    takePage()
    video.seekTo(pos)
    announce(pos)
  }

  const onKey = (action: KeyAction) => {
    if (action.kind !== 'toggle') {
      takePage()
    }
    const at = playhead.get()
    let pos: Position
    switch (action.kind) {
      case 'frames':
        pos = stepFramesOnTrack(map, facts, names, at, action.n)
        break
      case 'ms':
        pos = positionOnTrack(map, clipLay, facts, names, globalMs(lay, at) + action.ms)
        break
      case 'to':
        pos = action.where === 'start' ? trackStart(map, clipLay, facts, names) : endPosition(facts)
        break
      case 'toggle':
        toggle()
        return
    }
    video.seekTo(pos)
    announce(pos)
  }

  /**
   * The one zoom path: to `target` px per second, held to [Fit, MAX_PPS], keeping the moment under
   * the anchor where it is: the pointer when given (Ctrl+wheel), else the playhead while it is in
   * view, else the view's centre. Reaching Fit sets Fit, which then follows a resized view.
   */
  const zoomTo = (target: number, pointerX?: number) => {
    const el = scroller.current
    if (el === null || el.clientWidth === 0) {
      return
    }
    const from = ppsRef.current
    const fitNow = fitRef.current
    const to = Math.min(MAX_PPS, Math.max(fitNow, target))
    if (Math.abs(to - from) < 1e-9) {
      return
    }
    const exact = exactScroll.current
    const scrollLeft =
      pendingScroll.current ??
      (exact !== null && Math.abs(el.scrollLeft - exact) < 1 ? exact : el.scrollLeft)
    const view = { pps: from, scrollLeft, width: Math.max(1, el.clientWidth) }
    const playheadX = timeToPx(globalMs(lay, playhead.get()), from) - scrollLeft
    const anchor = anchorFor(playheadX, view.width, pointerX)
    const next = zoomAt(view, to / from, anchor, lay.totalMs)
    pendingScroll.current = next.scrollLeft
    zoomSettle.input()
    ppsRef.current = next.pps
    // The range the zoom will show, in the same render: one render per zoom, not two.
    expectRange(next.scrollLeft)
    setZoom({ pps: next.pps, fitted: next.pps <= fitNow + 1e-9 })
  }
  const zoomBy = (factor: number) => zoomTo(ppsRef.current * factor)
  const fitAll = () => {
    if (Math.abs(ppsRef.current - fitRef.current) > 1e-9) {
      zoomSettle.input()
    }
    pendingScroll.current = 0
    if (scroller.current !== null) {
      scroller.current.scrollLeft = 0 // also when the scale does not change (the floor of 4 px/s)
      syncRange()
    }
    ppsRef.current = fitRef.current
    setZoom({ pps: fitRef.current, fitted: true })
  }
  const onSlider = (position: number) => {
    beforeFit.current = null
    setLive(true)
    window.clearTimeout(settle.current)
    settle.current = window.setTimeout(() => setLive(false), LIVE_SETTLE_MS)
    if (position <= 0) {
      fitAll()
    } else {
      zoomTo(sliderToPps(position, fitRef.current))
    }
  }
  // `\` (Premiere): Fit, and pressed again at Fit, back to the zoom before it. Any other zoom
  // forgets that zoom.
  const beforeFit = useRef<number | null>(null)
  const toggleFit = () => {
    const back = beforeFit.current
    if (zoom.fitted || ppsRef.current <= fitRef.current + 1e-9) {
      beforeFit.current = null
      if (back !== null) {
        zoomTo(back)
      }
    } else {
      const now = ppsRef.current
      fitAll()
      beforeFit.current = now
    }
  }
  const onTrackKey = (key: string) => {
    if (key === '\\') {
      toggleFit()
      return
    }
    beforeFit.current = null
    if (key === '0') {
      fitAll()
    } else if (key === '+' || key === '=') {
      zoomBy(ZOOM_STEP)
    } else {
      zoomBy(1 / ZOOM_STEP)
    }
  }

  // Ctrl+wheel (Cmd+wheel; a trackpad pinch arrives as a Ctrl+wheel) zooms at most once per
  // animation frame, over the Timeline's own part (the tool row, the lanes and the track): about
  // the pointer when it is over the track, else about the playhead or the view's centre. A listener
  // of our own, not passive, so the page does not zoom instead; a wheel without Ctrl or Cmd is left
  // to the browser, and so is a wheel over the viewer, the bin and the inspector (portaled out of
  // the part). The part is held in state through a callback ref, so a remount re-attaches it.
  const [part, setPart] = useState<HTMLDivElement | null>(null)
  const wheelZoom = useRef({ zoomTo, forget: () => undefined as void })
  wheelZoom.current = {
    zoomTo,
    forget: () => {
      beforeFit.current = null
    },
  }
  useEffect(() => {
    if (part === null) {
      return undefined
    }
    let factor = 1
    let pointerX: number | undefined
    let frame = 0
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) {
        return
      }
      event.preventDefault()
      const el = scroller.current
      factor *= wheelFactor(event.deltaY, event.deltaMode, Math.max(1, el?.clientHeight ?? 1))
      if (el === null) {
        pointerX = undefined
      } else {
        const rect = el.getBoundingClientRect()
        pointerX = wheelPointerX(
          {
            left: rect.left + el.clientLeft,
            top: rect.top + el.clientTop,
            width: el.clientWidth,
            height: el.clientHeight,
          },
          event.clientX,
          event.clientY,
        )
      }
      if (frame === 0) {
        frame = requestAnimationFrame(() => {
          frame = 0
          const by = factor
          factor = 1
          wheelZoom.current.forget()
          wheelZoom.current.zoomTo(ppsRef.current * by, pointerX)
        })
      }
    }
    part.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      part.removeEventListener('wheel', onWheel)
      if (frame !== 0) {
        cancelAnimationFrame(frame)
      }
    }
  }, [part])

  /**
   * Alt+Left and Right (`track-drag-edit`, D4): the selected clip one place earlier or later, or
   * the words for why not. False when no drawn clip is selected or it has nowhere to go (the key
   * is then left to the browser).
   */
  const moveSelected = (way: -1 | 1): boolean => {
    // Several clips: "one place left" is undefined for them, so nothing moves and the words say why.
    if (selectedSet.size > 1) {
      editing.announce(MOVE_ONE_WORDS)
      return true
    }
    if (selectedClip === null) {
      return false
    }
    const step = stepSlot(reorder.chapters, selectedClip, way)
    if (step === null) {
      return false
    }
    if (editing.locked) {
      editing.announce(MOVE_LOCKED)
    } else if (step.kind === 'edge') {
      editing.announce(step.words)
    } else {
      reorder.onDrop(selectedClip, step.slot)
    }
    return true
  }

  /** `Q`/`W`: trim the start or end of the clip under the playhead to it; `S`: snapping off/on. */
  const onEdgeKey = (key: 'q' | 'w' | 's') => {
    if (key === 's') {
      snapping.current = !snapping.current
      editing.announce(snappingWords(snapping.current))
      return
    }
    // A press or a drag in progress holds the editor still until its release (one drag at a time).
    if (dragHeld(drag)) {
      return
    }
    if (editing.locked) {
      editing.announce(EDGE_UNAVAILABLE)
      return
    }
    const side = key === 'q' ? 'start' : 'end'
    const at = playhead.get()
    const clip = at.card == null ? clips[at.clip] : undefined
    if (clip === undefined) {
      editing.announce(toPlayheadRefusal({ kind: 'refused', why: 'not-in-clip' }, side, null))
      return
    }
    const listed = editing.listed(clip.identity)
    const result = trimToPlayhead(listed, side, at.ms, clip.facts)
    if (result.kind !== 'edit') {
      editing.announce(toPlayheadRefusal(result, side, clip.name))
      return
    }
    editing.onEdge(
      clip.identity,
      edgeEdit(listed, side, result.at.x, clip.facts),
      edgeAnnouncement(clip.name, side, result.at, clip.facts.durationMs),
    )
  }

  const onFilmFailed = useCallback(
    (identity: string) =>
      setNoPicture((held) => (held.has(identity) ? held : new Set(held).add(identity))),
    [],
  )

  // The workspace's keys (`editor-shortcuts`, D3): in Edit mode's workspace the playhead's, the
  // track's and the edge tools' keys work wherever focus is. One document listener in the bubble
  // phase, so a focused element's own handler runs first and its `preventDefault` shows.
  const inWorkspace = useContext(TimelinePanesContext) !== null
  const keys = useRef({ onKey, onTrackKey, onEdgeKey, moveSelected })
  keys.current = { onKey, onTrackKey, onEdgeKey, moveSelected }
  useEffect(() => {
    if (!inWorkspace) {
      return undefined
    }
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target instanceof HTMLElement ? event.target : null
      const command = workspaceCommand(
        {
          key: event.key,
          shiftKey: event.shiftKey,
          ctrlKey: event.ctrlKey,
          altKey: event.altKey,
          metaKey: event.metaKey,
          altGraph: event.getModifierState('AltGraph'),
          repeat: event.repeat,
          isComposing: event.isComposing,
          defaultPrevented: event.defaultPrevented,
        },
        focusFacts(target, {
          enabled: shortcutsEnabled(),
          dialogOpen: document.querySelector('dialog[open]') !== null,
          dragging: dragHeld(drag),
          pointerHeld: pointerHeld(),
          modality: lastInput(),
        }),
      )
      if (command === null) {
        return
      }
      const now = keys.current
      switch (command.kind) {
        case 'hold':
          event.preventDefault()
          return
        case 'move':
          // With nothing to move the key stays the browser's (Back, with the unsaved guard).
          if (now.moveSelected(command.way)) {
            event.preventDefault()
          }
          return
        case 'help':
          event.preventDefault()
          document.getElementById('ws-keys')?.togglePopover?.()
          return
        case 'playhead':
          event.preventDefault()
          now.onKey(command.action)
          return
        case 'zoom':
          event.preventDefault()
          now.onTrackKey(command.key)
          return
        case 'edge':
          event.preventDefault()
          now.onEdgeKey(command.key)
          return
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [inWorkspace, drag])

  const suggestions = useSuggestions(analysis, {
    clips,
    lay,
    pps,
    seekTo: video.seekTo,
    selection,
  })
  const cardLane = useMemo<CardLaneModel | undefined>(
    () =>
      blocks.length === 0
        ? undefined
        : {
            blocks,
            specs,
            names: chapterNames,
            leadMs,
            shifting,
            handles,
            onSet: editing.onCardDuration,
            selected: selection.selected,
            onSelect: pickCard,
            onOpen: pressCard,
            onPlace: placeInCard,
            pictures,
            onClear: selection.clear,
          },
    [specs, chapterNames, blocks, leadMs, shifting, handles, editing, selection.selected, selection.clear, pickCard, pressCard, pictures],
  )
  const cardNotes = cardsNotes(chapterNames, placements, decorators, cards.source, cards.error)
  // A card's chapter (saved name, or an added chapter's id) as the words call it: its name now.
  const nameOfCard = (chapter: string): string => {
    const at = specs.findIndex((spec) => spec.chapter === chapter)
    return at === -1 ? chapter : (chapterNames[at] ?? chapter)
  }

  const atFit = pps <= fit + 1e-9
  const atMax = pps >= MAX_PPS - 1e-9
  const note = video.note
  // Use as poster (Edit mode): why it cannot act now, in words, or null.
  const frame = useFrameReady(video.videoRef, held)
  const [posterFailed, setPosterFailed] = useState(false)
  // The reason for the control of `only` (the inspector's: the clip it is about) or the transport's.
  const posterWhyFor = (only: TrackClip | null): string | null => {
    const at = playhead.get()
    const result = posterFromPlayhead(clips, at, { locked: editing.locked, held, frame })
    if (only !== null && !editing.locked && (at.card != null || clips[at.clip]?.identity !== only.identity)) {
      return `Move the playhead into ${only.name} to use a frame as poster.`
    }
    return 'why' in result ? result.why : null
  }
  // Pressed while it cannot act: the reason in a tip under that button (no room taken in the
  // toolbar), said once in the live region; the tip goes on blur, Escape, or with the reason.
  // Each control (`suffix`) has its own tip.
  const [posterTip, setPosterTip] = useState<{ suffix: string; why: string } | null>(null)
  const reasonGone = posterWhyFor(null) === null
  useEffect(() => {
    if (reasonGone) {
      setPosterTip(null)
    }
  }, [reasonGone])
  // Whether it went ahead (true) or said why it cannot (false).
  const usePoster = (suffix: string, only: TrackClip | null): boolean => {
    const element = video.videoRef.current
    const shownWhy = posterWhyFor(only)
    // What the button shows first (it looks unavailable: it does not act), then the video now.
    const result = posterFromPlayhead(clips, playhead.get(), {
      locked: editing.locked,
      held,
      frame: frame && hasFrame(element),
    })
    if (shownWhy !== null || 'why' in result) {
      const why = shownWhy ?? ('why' in result ? result.why : '')
      setPosterTip({ suffix, why })
      setAnnouncement(why)
      return false
    }
    setPosterTip(null)
    // Not reached with no video: `hasFrame(null)` is false, so the refusal above has said why.
    if (element === null) {
      return false
    }
    setPosterFailed(false)
    const turn = turns.get(result.pick.clip) ?? 0
    snapshotOf(element).then(
      (url) => editing.onPoster(result.pick, { url, turn }),
      () => setPosterFailed(true),
    )
    return true
  }
  // The Use as poster control: in the transport, and in the inspector's Clip tab for its clip
  // (`suffix` keeps their ids and tips apart).
  const posterControl = (suffix: string, label: string, only: TrackClip | null = null) => {
    const why = posterWhyFor(only)
    const tip = posterTip !== null && posterTip.suffix === suffix ? posterTip.why : null
    return (
      <div className="tl-poster">
        <button
          type="button"
          className="btn btn-secondary"
          aria-disabled={why !== null || undefined}
          aria-describedby={`${posterWhyId}${suffix}`}
          title={why ?? undefined}
          onClick={() => usePoster(suffix, only)}
          onBlur={() => setPosterTip(null)}
          onKeyDown={(event) => {
            if (event.key === 'Escape' && tip !== null) {
              event.preventDefault()
              setPosterTip(null)
            }
          }}
        >
          <Icon name="film" />
          {label}
        </button>
        {/* Always there: its words are the button's description while it cannot act. */}
        <span id={`${posterWhyId}${suffix}`} className="visually-hidden">
          {why ?? ''}
        </span>
        {tip !== null && (
          <span className="tl-poster-tip" aria-hidden="true">
            {tip}
          </span>
        )}
      </div>
    )
  }
  // The clip's menu (`clip-context-menu`, D1): one, owned here, opened by the track (and, later, the
  // bin's rows). Its playhead reasons are taken when it opens; the lock follows `editing.locked`.
  const [menu, setMenu] = useState<{
    id: number
    open: ClipMenuOpen
    cutWhy: string | null
    posterWhy: string | null
    /** The clip's state when the menu opened: a change (an Undo, a Reset) closes it. */
    state: ClipState | null
  } | null>(null)
  const menuCount = useRef(0)
  // Where focus goes once the menu is gone (a layout effect: never onto a node about to unmount).
  const menuFocus = useRef<(() => void) | null>(null)
  useLayoutEffect(() => {
    const run = menuFocus.current
    menuFocus.current = null
    run?.()
  }, [menu])
  const blockOf = (identity: string): HTMLElement | null =>
    Array.from(
      scroller.current?.querySelectorAll<HTMLElement>('.tl-clip-press[data-identity]') ?? [],
    ).find((block) => block.dataset.identity === identity) ?? null
  /** The bin's row of a clip, in the list that shows now. */
  const rowOf = (identity: string): HTMLElement | null =>
    Array.from(document.querySelectorAll<HTMLElement>('[role="option"][data-identity]')).find(
      (row) => row.dataset.identity === identity && row.closest('[hidden]') === null,
    ) ?? null
  /** The clip's block, else the track: focus never falls to the page's body. */
  const focusBlock = (identity: string | null) => {
    ;(identity === null ? scroller.current : (blockOf(identity) ?? scroller.current))?.focus({
      preventScroll: true,
    })
  }
  const cutWhyFor = (clip: TrackClip): string | null => {
    const made = cutAtClipPlayhead({ clip, clips, editing, playhead })
    return made.ok ? null : made.words
  }
  // A clip the track does not draw (ignored, missing, removed, or any clip while it prepares) has its
  // menu too (`plain-clip-bin` D5): its facts come from the editor's draft, its track reasons are words.
  const openClipMenu = (open: ClipMenuOpen): boolean => {
    const clip = clips.find((c) => c.identity === open.identity)
    const known = editing.menuFacts().clip(open.identity)
    if (known === null) {
      return false
    }
    if (menuSelects(selection.selection, open.identity)) {
      selectClip(open.identity)
    }
    menuCount.current += 1
    setMenu({
      id: menuCount.current,
      open,
      cutWhy: clip === undefined ? null : cutWhyFor(clip),
      posterWhy: clip === undefined ? null : posterWhyFor(clip),
      state: known.state,
    })
    return true
  }
  // What the Clip tab's Cuts panel borrows while the track draws its clip (`plain-clip-bin` D4):
  // "+ Cut at playhead" and each cut's Edit. The panel is the editor's; this is the one bridge.
  const trackCuts = editing.trackCuts
  const cutAdder = useRef<(identity: string) => string | null>(() => null)
  cutAdder.current = (identity) => {
    const clip = clips.find((c) => c.identity === identity)
    return clip === undefined ? null : addCutAtPlayhead({ clip, clips, editing, playhead })
  }
  const trackCutsView = useMemo<TrackCutsView>(
    () => ({
      drawn: new Set(clips.map((clip) => clip.identity)),
      selected,
      select,
      selectClip,
      add: (identity) => cutAdder.current(identity),
    }),
    [clips, selected, select, selectClip],
  )
  useLayoutEffect(() => {
    trackCuts.set(trackCutsView)
  }, [trackCuts, trackCutsView])
  useLayoutEffect(() => () => trackCuts.set(null), [trackCuts])
  // The bin's rows open the same menu: the latest closure, while this is mounted.
  const menuAt = editing.menuAt
  useLayoutEffect(() => {
    menuAt.current = openClipMenu
    return () => {
      menuAt.current = null
    }
  })
  // `focusOn`: where a choice sends focus (D5): the clip's block by default, another clip's block,
  // or (null) the track.
  const closeMenu = (
    why: MenuClose | 'choice' | 'gone',
    el: HTMLElement | null,
    focusOn?: string | null,
  ) => {
    if (menu === null) {
      return
    }
    const identity = menu.open.identity
    const invoker = menu.open.invoker
    // Where focus goes back to once the press, scroll or resize closed it: the invoker, else the block.
    const focusInvoker = () => {
      if (invoker.isConnected) {
        invoker.focus({ preventScroll: true })
      } else {
        focusBlock(identity)
      }
    }
    setMenu(null)
    switch (why) {
      case 'escape':
      case 'tab':
      case 'choice':
        menuFocus.current = () => {
          // A menu opened from a bin row gives focus back to the row, which may have moved to
          // another group of the list (a removal, an inclusion): found again by its clip.
          if (focusOn === undefined && invoker.getAttribute('role') === 'option') {
            const row = invoker.isConnected ? invoker : rowOf(identity)
            if (row !== null) {
              row.focus({ preventScroll: true })
              return
            }
          }
          focusBlock(focusOn === undefined ? identity : focusOn)
        }
        return
      case 'outside':
        // The press goes on to its target first; focus comes back only if it was left nowhere.
        window.setTimeout(() => {
          if (el === null || mayReturnFocus<Node>(document.activeElement, el, document.body)) {
            focusInvoker()
          }
        }, 0)
        return
      case 'scroll':
      case 'resize':
      case 'gone':
        menuFocus.current = () => {
          if (el === null || mayReturnFocus<Node>(document.activeElement, el, document.body)) {
            focusInvoker()
          }
        }
        return
      case 'blur':
        return
    }
  }
  // Its clip leaving the event, or changing state (an Undo, a Reset), closes it.
  const menuFactsNow = menu === null ? null : editing.menuFacts()
  const menuInfo = menu === null ? null : (menuFactsNow?.clip(menu.open.identity) ?? null)
  const menuClipGone = menu !== null && (menuInfo === null || menuInfo.state !== menu.state)
  useEffect(() => {
    if (menuClipGone) {
      closeMenu('gone', null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuClipGone])
  const menuClip = menu === null ? undefined : clips.find((c) => c.identity === menu.open.identity)
  // The clips the menu acts on: the selected clips when it was opened on one of two or more, else
  // the clip alone (`clip-multi-select` D7). Taken in the bin's order, which holds ignored clips too.
  const menuTargets =
    menu === null || menuInfo === null || menuFactsNow === null
      ? []
      : targets(selection.selection, menu.open.identity, menuFactsNow.order)
  const menuView =
    menu === null || menuInfo === null || menuFactsNow === null
      ? null
      : clipMenu({
          locked: editing.locked,
          cutWhy: menu.cutWhy,
          posterWhy: menu.posterWhy,
          // Several clips may be gathered at the end of any chapter, their own included. A clip the
          // track draws lists the chapters the track draws; any other the chapters the draft lists.
          others:
            menuClip === undefined
              ? menuInfo.chapters.filter((chapter) => menuTargets.length > 1 || chapter.key !== menuInfo.own)
              : reorder.chapters
                  .filter((chapter) => menuTargets.length > 1 || !chapter.identities.includes(menuClip.identity))
                  .map((chapter) => ({ key: chapter.key, name: chapter.name ?? '' })),
          targets: menuTargets,
          name: menuInfo.name,
          state: menuInfo.state,
          drawn: menuClip !== undefined,
          played: menuTargets.filter((id) => menuFactsNow.clip(id)?.state !== 'ignored').length,
          ignored: menuTargets.filter((id) => menuFactsNow.clip(id)?.state === 'ignored').length,
        })
  // Move to… for one clip (the menu's and the Clip tab's): the clip at the end of the chapter, the
  // edit a drop on that chapter's band makes.
  const moveToEnd = (identity: string, chapter: string) => {
    const slot = bandSlot(
      reorder.chapters,
      reorder.chapters.findIndex((c) => c.key === chapter),
      identity,
    )
    // Not reached: both offer only the chapters `reorder.chapters` lists, so a slot exists.
    if (slot === null) {
      return
    }
    reorder.onDrop(identity, slot)
    // Selected again, so the track scrolls to the clip at its new place.
    if (selectedClip === identity) {
      selectClip(identity)
    }
  }
  // Choosing an item: one that cannot act says why and keeps the menu; otherwise it makes the
  // edit the Clip tab's control makes (D2) and the menu closes, focus going where D5 says.
  const chooseMenuItem = (index: number) => {
    const item = menuView?.items[index]
    if (item === undefined || menu === null || menuInfo === null) {
      return
    }
    if (item.why !== null) {
      setAnnouncement(item.why)
      return
    }
    const clip = menuClip
    const identity = menu.open.identity
    // The playhead's reasons are taken again now: Play may have moved it since the menu opened.
    const refused = (cutWhy: string | null, posterWhy: string | null) =>
      setMenu((was) => (was === null ? was : { ...was, cutWhy, posterWhy }))
    const action = item.action
    // Two or more selected clips: each item makes the edit the group tab makes (D7).
    if (menuTargets.length > 1) {
      switch (action.kind) {
        case 'rotate':
          editing.onRotateMany(menuTargets, action.way)
          break
        case 'move':
          editing.onMoveSelection(menuTargets, action.chapter)
          break
        case 'ignore': {
          const next = focusAfterMany(
            clips.map((c) => c.identity),
            menuTargets,
          )
          editing.onIgnoreMany(menuTargets)
          selection.clear()
          closeMenu('choice', null, next)
          return
        }
        // The clips stay selected, and the row the menu opened on takes focus back (it is played now).
        case 'include':
          editing.onIncludeMany(menuTargets)
          break
        // Not reached: Cut and Poster are unavailable for several clips, so `item.why` stopped them;
        // Remove and Undo remove are listed for one clip only.
        case 'cut':
        case 'poster':
        case 'remove':
        case 'restore':
          return
      }
      closeMenu('choice', null)
      return
    }
    switch (action.kind) {
      case 'rotate':
        editing.onRotate(identity, action.way)
        break
      case 'cut':
        // Not reached for a clip the track does not draw: `item.why` stopped it.
        if (clip === undefined || addCutAtPlayhead({ clip, clips, editing, playhead }) !== null) {
          if (clip !== undefined) {
            refused(cutWhyFor(clip), posterWhyFor(clip))
          }
          return
        }
        break
      case 'poster':
        if (clip === undefined || !usePoster('-menu', clip)) {
          if (clip !== undefined) {
            refused(cutWhyFor(clip), posterWhyFor(clip))
          }
          return
        }
        break
      case 'move':
        if (clip === undefined) {
          editing.onMoveToEnd(identity, action.chapter)
        } else {
          moveToEnd(identity, action.chapter)
        }
        break
      case 'ignore': {
        const next = focusAfter(
          clips.map((c) => c.identity),
          identity,
        )
        editing.onIgnore(identity)
        closeMenu('choice', null, next)
        return
      }
      // The three status items make the edit the Clip tab's end button makes; focus goes back to
      // the clip's row, which has moved to another group of the list.
      case 'include':
        editing.onInclude(identity)
        break
      case 'remove':
        editing.onRemoveClip(identity)
        break
      case 'restore':
        editing.onRestoreClip(identity)
        break
    }
    closeMenu('choice', null)
  }
  const stage = (
    <div className="tl-stage" data-turned>
      {held ? (
        <p className="tl-stage-held">{PREVIEW_OPEN}</p>
      ) : (
        <video
          ref={video.videoRef}
          className="tl-video"
          preload="auto"
          playsInline
          aria-hidden="true"
          tabIndex={-1}
          {...video.handlers}
        />
      )}
      {!held && (
        <CardLayer
          playhead={playhead}
          placements={placements}
          specs={specs}
          pictures={pictures}
          playing={video.playing}
        />
      )}
    </div>
  )
  const transport = (
    <div className="tl-controls tl-transport">
      <button type="button" className="btn btn-primary tl-play" onClick={toggle}>
        <Icon name={video.playing ? 'pause' : 'play'} />
        <span className="tl-play-words">
          <span data-off={video.playing || undefined} aria-hidden={video.playing || undefined}>
            {PLAY}
          </span>
          <span data-off={!video.playing || undefined} aria-hidden={!video.playing || undefined}>
            {PAUSE}
          </span>
        </span>
      </button>
      <div className="tl-clip-step" role="group" aria-label="Clips">
        <button
          type="button"
          className="btn btn-secondary btn-icon"
          aria-label={PREVIOUS_CLIP}
          title={PREVIOUS_CLIP}
          onClick={() => toClip(-1)}
        >
          <Icon name="skip-back" />
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-icon"
          aria-label={NEXT_CLIP}
          title={NEXT_CLIP}
          onClick={() => toClip(1)}
        >
          <Icon name="skip-forward" />
        </button>
      </div>
      <PlayheadReadout playhead={playhead} clips={clips} lay={lay} longestCardMs={longestCardMs} />
      {posterControl('', USE_AS_POSTER)}
    </div>
  )
  const viewer = (
    <div className="timeline tl-viewer">
      {stage}
      {transport}
      {posterFailed && (
        <Alert
          tone="warn"
          role="alert"
          title="The picture could not be copied."
          detail="The poster is not changed."
        />
      )}
      {note !== null && (
        <Alert
          tone={note.tone}
          role="alert"
          title={note.title}
          detail={note.detail}
          action={
            'gone' in note && note.gone ? <PrepareButton control={prepare} primary={false} /> : undefined
          }
        />
      )}
      {note !== null && 'gone' in note && note.gone && <PrepareJob control={prepare} />}
    </div>
  )
  const track = (
    <div
      ref={setPart}
      className="timeline tl-track-part"
      data-trimming={trimming || undefined}
      data-edge-side={edgeSide ?? undefined}
    >
      <div className="tl-controls tl-tools">
        <MovieStat
          drag={drag}
          shifting={shifting}
          specs={specs}
          placeAll={placeAll}
          clipLay={clipLay}
          footage={footage}
          map={map}
          movie={movie}
        />
        <div className="tl-zoom" role="group" aria-label="Zoom">
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            aria-label={ZOOM_OUT}
            title={ZOOM_OUT}
            aria-disabled={atFit || undefined}
            onClick={() => {
              beforeFit.current = null
              zoomBy(1 / ZOOM_STEP)
            }}
          >
            <Icon name="minus" />
          </button>
          <ZoomSlider
            pps={pps}
            fit={fit}
            fitted={atFit}
            disabled={fit >= MAX_PPS - 1e-9}
            onZoom={onSlider}
            onPress={zoomSettle.press}
            onRelease={zoomSettle.release}
          />
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            aria-label={ZOOM_IN}
            title={ZOOM_IN}
            aria-disabled={atMax || undefined}
            onClick={() => {
              beforeFit.current = null
              zoomBy(ZOOM_STEP)
            }}
          >
            <Icon name="plus" />
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              beforeFit.current = null
              fitAll()
            }}
          >
            <Icon name="maximize" />
            {FIT}
          </button>
        </div>
      </div>

      <Track
        eventId={eventId}
        clips={clips}
        lay={lay}
        bands={bands}
        pps={pps}
        range={range}
        overscan={live ? LIVE_OVERSCAN : 1}
        gutter={gutter}
        turns={turns}
        scrollerRef={scroller}
        playhead={playhead}
        gripRef={grip}
        noPicture={noPicture}
        onFilmFailed={onFilmFailed}
        onKey={onKey}
        onTrackKey={onTrackKey}
        onMoveSelected={moveSelected}
        onScrub={scrubAt}
        lane={suggestions.lane}
        editing={editing}
        drag={drag}
        selected={selected}
        onSelect={select}
        selectedClips={selectedSet}
        onSelectClip={selectClip}
        onPressClip={onPressClip}
        onPressClipKey={onPressClipKey}
        onSpanAt={spanAt}
        onClearSelection={clearSelection}
        cardLane={cardLane}
        shifting={shifting}
        snapping={snapping}
        onEdgeKey={onEdgeKey}
        zoomHold={zoomHold}
        reorder={reorder}
        onOpenMenu={openClipMenu}
      />

      {decorators === 'invalid' && <p className="tl-summary">{CARDS_UNKNOWN}</p>}

      {pictures.failures.map((failure) => (
        <Alert
          key={failure.chapter}
          tone="warn"
          role="note"
          title={`The title card for ${cardSubject(nameOfCard(failure.chapter))} could not be drawn here.`}
          detail={`${failure.message} Its title is shown on black.`}
        />
      ))}
      {cardNotes.map((note) => (
        <Alert key={note.title} tone="info" role="note" title={note.title} detail={note.detail} />
      ))}

      {suggestions.strip}

      <p className="visually-hidden" role="status">
        {announcement}
      </p>

      {menu !== null &&
        menuView !== null &&
        menuInfo !== null &&
        createPortal(
          <Menu
            key={menu.id}
            title={menuView.title ?? menuInfo.name}
            note={menuView.note}
            items={menuView.items.map((item) => ({
              label: item.label,
              icon: menuIcon(item.action),
              group: item.group,
              why: item.why,
            }))}
            at={'box' in menu.open.at ? { box: menu.open.at.box } : menu.open.at}
            onChoose={chooseMenuItem}
            onClose={closeMenu}
          />,
          document.body,
        )}

      {noPicture.size > 0 && (
        <Alert tone="warn" role="note" title={FILM_FAILED} detail={FILM_FAILED_DETAIL} />
      )}
    </div>
  )
  // The clip the panel is about: the selected clip, or the selected cut's.
  const panelClip = selectedClip ?? selected?.identity ?? null
  const place = useMemo(
    () => (panelClip === null ? null : clipPlace(clips, panelClip, chapterNames)),
    [clips, panelClip, chapterNames],
  )
  const panelClipRow = panelClip === null ? undefined : clips.find((c) => c.identity === panelClip)
  // The track-only part of the Clip tab (`clip-tab-and-player` D5), for the one clip the track
  // draws; the editor's `ClipInspector` has the rest. The group tab is the editor's too.
  const clipPanel = (
    <div className="timeline tl-cut-panel">
      {panelClipRow !== undefined && (
        <>
          <ClipTrackPart
            clip={panelClipRow}
            length={place === null ? null : lengthWords(place)}
            editing={editing}
            drag={drag}
            poster={posterControl('-clip', 'Use frame as poster', panelClipRow)}
          />
          <CutFields
            selected={selected}
            clips={clips}
            editing={editing}
            drag={drag}
            hintId={cutHintId}
          />
        </>
      )}
    </div>
  )
  // The selection announced once through the status below, when it changes to something: a
  // clip, a cut or a suggestion (the card's is the Timeline section's). A selection kept across a
  // remount is not announced again.
  const words = useMemo(() => {
    if (selected !== null) {
      const at = editing.listed(selected.identity).filter((c) => !c.removed)
      const n = at.findIndex((c) => c.key === selected.key) + 1
      const name = place?.name
      return n > 0 && name !== undefined ? cutSelectedWords(n, name) : null
    }
    return selectedClip !== null && place !== null
      ? clipSelectedWords(place)
      : suggestions.words
  }, [selected, selectedClip, place, editing, suggestions.words])
  const selectionKey =
    selected !== null
      ? `cut:${selected.identity}:${selected.key}`
      : selectedClip !== null
        ? `clip:${selectedClip}`
        : selectedSet.size > 1
          ? `clips:${[...selectedSet].join('|')}`
          : (suggestions.selectedKey ?? null)
  const announcedKey = useRef(selectionKey)
  // The selection before this one, for the words of a change to a set (design D6): "3 clips
  // selected.", "s1710003.mp4 added. 3 clips selected.".
  const sel = selection.selection
  const wasSel = useRef(sel)
  const nameOf = (identity: string) => clips.find((c) => c.identity === identity)?.name ?? identity
  const nameNow = useRef(nameOf)
  nameNow.current = nameOf
  useEffect(() => {
    const was = wasSel.current
    wasSel.current = sel
    if (announcedKey.current !== selectionKey) {
      announcedKey.current = selectionKey
      const said = selectionWords(was, sel, nameNow.current) ?? words
      if (said !== null) {
        setAnnouncement(said)
      }
    }
  }, [selectionKey, words, sel])
  const suggestionPanel = <div className="timeline tl-cut-panel">{suggestions.detail}</div>
  return { viewer, track, clipPanel, suggestionPanel }
}

/**
 * The movie's length as one line in the control row (`help-text-declutter`). It follows a black
 * card's edge in the air (the length of the movie, the card time) by itself, so a drag renders
 * this span and not the Timeline.
 */
function MovieStat({
  drag,
  shifting,
  specs,
  placeAll,
  clipLay,
  footage,
  map,
  movie,
}: {
  drag: DragStore
  shifting: ShiftFrom | null
  specs: readonly CardSpec[]
  placeAll: (specs: readonly CardSpec[]) => Placement[]
  clipLay: Layout
  /** The shown clips' full durations: "of footage". */
  footage: number
  map: CardMap
  movie: number
}) {
  const tenths = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.getCard()
    return shifting !== null && shifting.kind === 'card' && d !== null && d.chapter === shifting.chapter
      ? d.tenths
      : null
  })
  const now = useMemo(
    () =>
      tenths === null || shifting === null || shifting.kind !== 'card'
        ? map
        : cardMap(
            placeAll(withDurations(specs, new Map([[shifting.chapter, tenths / 10]]))),
            clipLay,
          ),
    [tenths, shifting, map, specs, placeAll, clipLay],
  )
  // One span per term: a narrow screen wraps between terms, never inside one.
  // The footage is the clips' full durations, which edge cuts do not shorten (not the rippled track).
  const terms = movieStat(movie, footage, now.totalMs).split(' \u00b7 ')
  return (
    <span className="tl-stat">
      {terms.map((term, index) => (
        <span key={term.split(' ')[0]} className="tl-stat-term">
          {index > 0 && '\u00b7 '}
          {term}
        </span>
      ))}
    </span>
  )
}

/** Whether a clip preview of Edit mode is open, and so holds the page's one video. */
function usePreviewHeld(previews: EditBinding['previews']): boolean {
  return useSyncExternalStore(previews.subscribe, () => previews.open() !== null)
}
