import { memo, useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, KeyboardEvent, MouseEvent, PointerEvent, RefObject } from 'react'

import type { ClipTurns } from '../cuts/ReadCuts'
import type { Turn } from '../rotate/turn.ts'
import { TRIM_KEYS, formatTime, reasonWords } from '../cuts/times'
import { CardHandles, CARD_KEYS } from './CardHandles'
import { CardLane } from './CardLane'
import type { CardPictures } from './useCardImages'
import { Filmstrip } from './Filmstrip'
import { PlayheadKeys, PlayheadSlider } from './Playhead'
import { ClipHandles } from './TrimHandle'
import { EdgeTool } from './EdgeHandles'
import type { PressTargets, SnapSwitch } from './EdgeHandles'
import { EDGE_KEYS } from './edgeTrim'
import { edgeToolShown } from './zoomSettle'
import type { EdgeKey } from './zoomSettle'
import { ClipDragLayer, useClipDrag } from './ClipDrag'
import type { ReorderModel } from './ClipDrag'
import { MOVE_LOCKED, inBox } from './clipDrag'
import { held, shiftMs } from './dragStore'
import type { DragStore } from './dragStore'
import type { ClipMenuOpen, EditBinding } from './editing'
import { bandStartMs } from './cards'
import type { CardBlock, CardHandle, CardSpec } from './cards'
import { clipMoveKey, trackZoomKey } from './keys'
import { lastInput, pointerHeld } from '../edit/workspace/modality.ts'
import { blockYieldsSpace } from '../edit/workspace/shortcuts.ts'
import { shortcutsEnabled } from '../edit/workspace/shortcutSwitch.ts'
import type { KeyAction } from './keys'
import { menuOpenKey } from './clipMenu'
import { pressOf } from '../edit/workspace/selection.ts'
import type { Press } from '../edit/workspace/selection.ts'
import { contextAnchor, visiblePart } from '../ui/menu'
import type { Box } from '../ui/menu'
import { clipDescription } from './labels'
import { cutLabel, drawnCuts } from './layout'
import type { ChapterBand, TrackClip } from './layout'
import {
  canvasWidth,
  edgeCut,
  extentMs,
  interiorSpans,
  pxToTime,
  tickLabelFits,
  timeToPx,
  visibleClips,
  visibleTicks,
} from './model'
import type { Layout } from './model'
import type { LaneSlot } from './overlays/control'
import type { Playhead } from './playhead'
import { hasKeptFrame, timedOf } from './position'
import type { VisibleRange } from './useVisibleRange'

/*
 * The track: a ruler, the chapter band and the clips end to end at `pps`, inside the
 * Timeline's own horizontal scroller. Only what meets the visible range and a margin of
 * one view on each side is drawn (a 400-clip event holds a few dozen elements). The cuts
 * are spans with a hatch and a text alternative, and each clip drawn with its cuts gets its
 * trim handles (`TrimHandle.tsx`), a layer after the playhead so that Tab reaches them after
 * it. The Timeline is Edit mode's only.
 */

/**
 * The phases of a scrub by pointer: where, in px from the track's start. A `tap` is a
 * touch that only places the playhead: nothing is dragged, so the video is not paused.
 */
export type ScrubPhase = 'start' | 'move' | 'end' | 'tap'

/** Where a scrub began: the ruler (and the grip), or the clips' lane. */
export type ScrubSurface = 'ruler' | 'lane'

/** Clips narrower than this are drawn as a block only: no name, picture or cuts. */
const MIN_DETAIL_PX = 6
/** Clips at least this wide show their name; a cut at least this wide shows its reason. */
const NAME_PX = 28
const CUT_TEXT_PX = 72
/** A touch that moves less than this and ends within `TAP_MS` is a tap. */
const TAP_PX = 8
const TAP_MS = 600
/** What the edge tools say while a save or a move of several clips is pending. */
const EDGE_LOCKED = 'Trimming waits for the save or the move of several clips to finish.'

/** Whether a key's target takes text: the track's letters never reach a field. */
function inField(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || target.matches('input, textarea, select, [contenteditable="true"]'))
  )
}

/** A box (client px) as the `DOMRectReadOnly` a menu request carries. */
const rectOf = (box: Box): DOMRectReadOnly =>
  new DOMRect(box.left, box.top, box.right - box.left, box.bottom - box.top)

/** No black cards: no band starts before its first clip. */
const NO_LEAD: ReadonlyMap<number, number> = new Map()

type Pointer = { id: number; x: number; y: number; at: number }

/**
 * Pointer handlers that scrub: a mouse or pen on the ruler or the track captures the
 * pointer and the playhead follows it; a touch on the ruler does the same (it has
 * `touch-action: none`); a touch on the track body scrolls it, and only a tap moves the
 * playhead.
 */
function useScrub(
  canvas: RefObject<HTMLDivElement | null>,
  onScrub: (x: number, phase: ScrubPhase, surface: ScrubSurface) => void,
  focusGrip: () => void,
  surface: ScrubSurface,
) {
  const drag = useRef<number | null>(null)
  const touch = useRef<Pointer | null>(null)
  const place = (event: PointerEvent): number => {
    const box = canvas.current?.getBoundingClientRect()
    return event.clientX - (box?.left ?? 0)
  }
  return {
    onPointerDown(event: PointerEvent<HTMLElement>) {
      if (event.button !== 0 && event.pointerType === 'mouse') {
        return
      }
      if (event.pointerType === 'touch' && surface === 'lane') {
        touch.current = { id: event.pointerId, x: event.clientX, y: event.clientY, at: event.timeStamp }
        return
      }
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)
      drag.current = event.pointerId
      focusGrip()
      onScrub(place(event), 'start', surface)
    },
    onPointerMove(event: PointerEvent<HTMLElement>) {
      if (drag.current === event.pointerId) {
        onScrub(place(event), 'move', surface)
      }
    },
    onPointerUp(event: PointerEvent<HTMLElement>) {
      if (drag.current === event.pointerId) {
        drag.current = null
        onScrub(place(event), 'end', surface)
        return
      }
      const tap = touch.current
      touch.current = null
      if (
        tap !== null &&
        tap.id === event.pointerId &&
        Math.hypot(event.clientX - tap.x, event.clientY - tap.y) < TAP_PX &&
        event.timeStamp - tap.at < TAP_MS
      ) {
        focusGrip()
        onScrub(place(event), 'tap', surface)
      }
    },
    onPointerCancel(event: PointerEvent<HTMLElement>) {
      touch.current = null
      if (drag.current === event.pointerId) {
        drag.current = null
        onScrub(place(event), 'end', surface)
      }
    },
  }
}

/** What the Track needs to draw the card lane. */
export type CardLaneModel = {
  blocks: readonly CardBlock[]
  specs: readonly CardSpec[]
  /** The drawn chapters' names by index (the draft's): what the cards' words call them. */
  names: readonly string[]
  /** Clip index → the length of the black card that opens it: its chapter band starts at the card. */
  leadMs: ReadonlyMap<number, number>
  /** The end-edge handles and the draft edit they write. */
  handles: readonly CardHandle[]
  onSet: (chapter: string, seconds: number, words: string | null) => void
  /** The selected card's chapter or null. */
  selected: string | null
  onSelect: (chapter: string) => void
  /** Activating a block's body shows the card's editor in the inspector. */
  onOpen: (chapter: string) => void
  /** A press in a black card's block also puts the playhead there (the track time of the press). */
  onPlace: (chapter: string, trackMs: number) => void
  /** The cards' images: the blocks' miniatures. */
  pictures: CardPictures
  onClear: () => void
}

/**
 * A black card's edge, or a clip's edge (`clip-edge-trim`), in the air: everything that starts at
 * `fromMs` or later is drawn where it was and translated by the Timeline (no render,
 * `data-after`), and what spans it grows by it (`shiftMs`). The real layout is drawn once, on release.
 */
export type ShiftFrom =
  | {
      kind: 'card'
      /** The card's chapter (saved name). */
      chapter: string
      /** Where the card ends on the track, before the drag. */
      fromMs: number
      /** The card's length before the drag. */
      baseTenths: number
    }
  | {
      kind: 'edge'
      /** The clip whose edge is dragged. */
      identity: string
      /** Where the clip's block ends on the track, before the drag. */
      fromMs: number
    }

/** Whether something that starts at `ms` is behind a dragged card's end. */
const behind = (shift: ShiftFrom | null, ms: number): boolean => shift !== null && ms >= shift.fromMs - 0.5

/**
 * The ruler's ticks. During a black card's drag they follow its edge by themselves (the movie
 * is longer or shorter by the shift, and a tick's time is the time of the movie as it will be),
 * so that the labels are never those of the layout before the drag.
 */
function Ticks({
  lay,
  view,
  overscan,
  canvasPx,
  drag,
  shifting,
}: {
  lay: Layout
  view: { pps: number; scrollLeft: number; width: number }
  overscan: number
  /** The canvas's width: a label that would reach past it is not written (its line stays). */
  canvasPx: number
  drag: DragStore
  shifting: ShiftFrom | null
}) {
  const delta = useSyncExternalStore(drag.subscribe, () => shiftMs(drag, shifting))
  if (overscan === 0) {
    return null
  }
  const total = lay.totalMs + delta
  const ticks = visibleTicks({ ...lay, totalMs: total }, view, overscan)
  const nodes = []
  for (let i = ticks.first; i <= ticks.last; i += 1) {
    const ms = i * ticks.stepMs
    const x = timeToPx(ms, view.pps)
    const text = formatTime(ms / 1000)
    nodes.push(
      <span key={i} className="tl-tick" style={{ insetInlineStart: x }}>
        {tickLabelFits(x, text, canvasPx) ? text : null}
      </span>,
    )
  }
  return <>{nodes}</>
}

/** A chapter's band; the one of a dragged black card follows its edge by itself. */
function ChapterBand({
  chapter,
  heading,
  left,
  right,
  behind: after,
  grows,
  pps,
  drag,
  shifting,
}: {
  chapter: number
  heading: string
  left: number
  right: number
  behind: boolean
  grows: boolean
  pps: number
  drag: DragStore
  shifting: ShiftFrom | null
}) {
  const delta = useSyncExternalStore(drag.subscribe, () => (grows ? shiftMs(drag, shifting) : 0))
  return (
    <li
      className="tl-chapter"
      data-chapter={chapter}
      data-after={after || undefined}
      style={{ insetInlineStart: left, inlineSize: right - left + timeToPx(delta, pps) }}
    >
      <span className="tl-chapter-name">{heading}</span>
    </li>
  )
}

/** What a clip's block needs besides the clip. */
type BlockProps = {
  eventId: string
  index: number
  left: number
  pps: number
  /** The track px the filmstrip window spans (primitives, so that a block can be memoized). */
  windowFrom: number
  windowTo: number
  turn: Turn
  noPicture: boolean
  onFilmFailed: (identity: string) => void
  after: boolean
  descId: string
}

/** A clip's block over its kept extent: its filmstrip, its interior cuts and its name. */
const ClipBlock = memo(function ClipBlock({
  clip,
  eventId,
  index,
  left,
  pps,
  windowFrom,
  windowTo,
  turn,
  noPicture,
  onFilmFailed,
  after,
  descId,
}: BlockProps & { clip: TrackClip }) {
  const keptMs = extentMs(clip.kept)
  const widthPx = timeToPx(keptMs, pps)
  const detailed = widthPx >= MIN_DETAIL_PX
  return (
    <div
      className="tl-clip"
      data-index={index}
      data-after={after || undefined}
      data-no-picture={noPicture || undefined}
      style={{ insetInlineStart: left, inlineSize: Math.max(1, widthPx) }}
    >
      <span id={descId} className="visually-hidden" aria-hidden="true">
        {clipDescription(clip.facts.durationMs, clip.cutCount, keptMs)}
      </span>
      {detailed && !noPicture && (
        <Filmstrip
          eventId={eventId}
          clip={clip}
          pps={pps}
          window={{ from: windowFrom - left, to: windowTo - left }}
          turn={turn}
          onFail={onFilmFailed}
        />
      )}
      {detailed &&
        clip.drawn.map((cut) => {
          const cutPx = timeToPx(cut.to - cut.from, pps)
          return (
            <span
              key={cut.from}
              className="tl-cut"
              role="img"
              aria-label={cutLabel(cut)}
              data-reason={cut.reasons[0] ?? 'manual'}
              style={{ insetInlineStart: timeToPx(cut.from - clip.kept.inMs, pps), inlineSize: Math.max(2, cutPx) }}
            >
              {cutPx >= CUT_TEXT_PX && (
                <span className="tl-cut-text" aria-hidden="true">
                  {cut.reasons.length === 0 ? 'Cut' : cut.reasons.map(reasonWords).join(', ')}
                </span>
              )}
            </span>
          )
        })}
      {widthPx >= NAME_PX && (
        <span className="tl-clip-label" aria-hidden="true">
          <span className="tl-clip-tag">
            <span className="tl-clip-name">{clip.name}</span>
            <span className="tl-clip-length">{formatTime(keptMs / 1000)}</span>
          </span>
        </span>
      )}
    </div>
  )
})

/**
 * A clip's control: a transparent button over its block, in the tools' layer so that Tab reaches
 * it right before the clip's Trim In (clip, Trim In, cut handles, Trim Out). A press selects the
 * clip and never moves the playhead; a double press places it (`editor-selection`, design D2).
 * The edge zones and the cut handles come after it in the layer and so take their own presses.
 */
const ClipPress = memo(function ClipPress({
  identity,
  name,
  index,
  left,
  widthPx,
  descId,
  lockedId,
  selected,
  after,
  grab,
  onKeyPress,
  onPress,
  onPlace,
  onMenu,
}: {
  identity: string
  name: string
  index: number
  left: number
  widthPx: number
  descId: string
  /** The words that moving waits for the save, while it does (else null). */
  lockedId: string | null
  selected: boolean
  after: boolean
  /** The block's drag (`ClipDrag`): a mouse or pen drag past the slop reorders the clip. */
  grab: ReturnType<typeof useClipDrag>
  /** Enter or Space: Enter with Ctrl, Cmd or Shift adds to the set or ranges (`pressOf`). */
  onKeyPress: (identity: string, press: Press) => void
  /** A click: selects the cut whose span holds the press, else the clip (a modifier: the set). */
  onPress: (identity: string, clientX: number, press: Press) => void
  onPlace: (clientX: number) => void
  /** Shift+F10 or the Menu key on the block: the clip's menu, under the block. */
  onMenu: (identity: string, block: HTMLElement) => void
}) {
  return (
    <div
      className="tl-clip-press"
      role="button"
      tabIndex={0}
      aria-label={name}
      aria-pressed={selected}
      aria-keyshortcuts="Shift+F10 ContextMenu"
      data-identity={identity}
      aria-describedby={lockedId === null ? descId : `${descId} ${lockedId}`}
      data-index={index}
      data-selected={selected || undefined}
      data-after={after || undefined}
      style={{ insetInlineStart: left, inlineSize: Math.max(1, widthPx) }}
      onPointerDown={(event: PointerEvent<HTMLElement>) => grab.onDown(event, identity, index)}
      onPointerMove={grab.onMove}
      onPointerUp={grab.onUp}
      onPointerCancel={grab.onCancel}
      onLostPointerCapture={grab.onLostCapture}
      onClick={(event: MouseEvent<HTMLElement>) => {
        // A drag that moved a clip (or tried to) ends in a click; that click selects nothing.
        if (grab.consumeDragged()) {
          return
        }
        // Enter and Space come through onKeyDown; a click with no pointer (detail 0) selects the clip.
        onPress(identity, event.detail === 0 ? Number.NaN : event.clientX, pressOf(event))
      }}
      onDoubleClick={(event: MouseEvent<HTMLElement>) => onPlace(event.clientX)}
      onKeyDown={(event: KeyboardEvent<HTMLElement>) => {
        if (event.target === event.currentTarget && menuOpenKey(event)) {
          event.preventDefault()
          onMenu(identity, event.currentTarget)
          return
        }
        // After a pointer press Space is Play (the workspace's listener) when it will take the
        // key: with the switch off or a pointer held it does not, so the block selects as before.
        if (event.key === ' ' && blockYieldsSpace(lastInput(), shortcutsEnabled(), pointerHeld())) {
          return
        }
        // Enter takes Ctrl, Cmd and Shift (the set's presses); Space only selects the clip alone.
        if (
          event.target === event.currentTarget &&
          !event.altKey &&
          (event.key === 'Enter' ||
            (event.key === ' ' && !event.ctrlKey && !event.metaKey && !event.shiftKey))
        ) {
          event.preventDefault()
          onKeyPress(identity, event.key === 'Enter' ? pressOf(event) : 'alone')
        }
      }}
    />
  )
})

/**
 * The block of a clip whose edge is dragged (`clip-edge-trim`): drawn from the edge in the air,
 * its left side where it was, as wide as its new kept extent, its tiles and cuts from the new in-point.
 */
function LiveClipBlock({ clip, drag, ...props }: BlockProps & { clip: TrackClip; drag: DragStore }) {
  const live = useSyncExternalStore(drag.subscribe, () => {
    const e = drag.getEdge()
    return e !== null && e.identity === clip.identity ? e : null
  })
  if (live === null) {
    return <ClipBlock clip={clip} {...props} />
  }
  const durationMs = clip.facts.durationMs
  const shown: TrackClip = {
    ...clip,
    kept: live.extent,
    drawn: interiorSpans(drawnCuts(live.cuts, durationMs), live.extent),
  }
  return <ClipBlock clip={shown} {...props} />
}

export function Track({
  eventId,
  clips,
  lay,
  bands,
  pps,
  range,
  overscan: overscanViews = 1,
  gutter,
  turns,
  scrollerRef,
  playhead,
  gripRef,
  noPicture,
  onFilmFailed,
  onKey,
  onTrackKey,
  onMoveSelected,
  onScrub,
  lane: analysisLane,
  editing,
  drag,
  selected,
  onSelect,
  selectedClips,
  onSelectClip,
  onPressClip,
  onPressClipKey,
  onSpanAt,
  onClearSelection,
  cardLane,
  shifting = null,
  snapping,
  onEdgeKey,
  zoomHold = null,
  reorder,
  onOpenMenu,
}: {
  eventId: string
  clips: readonly TrackClip[]
  /** The clips end to end on the track, with the black cards' spans between them. */
  lay: Layout
  bands: readonly ChapterBand[]
  pps: number
  range: VisibleRange
  /** The margin drawn on each side of the view, in views (one; less during a slider drag). */
  overscan?: number
  /** The px kept free past the timeline's end: the playhead's grip reaches that far (Fit, D5). */
  gutter: number
  /** Each clip's turn (`rotate`): its tiles show the frame turned. */
  turns: ClipTurns
  scrollerRef: RefObject<HTMLDivElement | null>
  playhead: Playhead
  gripRef: RefObject<HTMLDivElement | null>
  /** Clips whose sprite failed. */
  noPicture: ReadonlySet<string>
  onFilmFailed: (identity: string) => void
  onKey: (action: KeyAction) => void
  /** `+`, `=`, `-`, `0` and `\\` while the track has focus. */
  onTrackKey: (key: string) => void
  /** Alt+Left and Right: move the selected clip one place; false when there is nothing to move. */
  onMoveSelected: (way: -1 | 1) => boolean
  /** The analysis lane, a row of the canvas under the clips (`overlays/`). */
  lane?: LaneSlot
  onScrub: (x: number, phase: ScrubPhase, surface: ScrubSurface) => void
  /** Edit mode's binding: the trim handles. */
  editing: EditBinding
  drag: DragStore
  /** The selected cut, if any. */
  selected: { identity: string; key: string } | null
  /** A cut is selected: by its handle's focus or press. */
  onSelect: (identity: string, key: string) => void
  /** The selected clips' identities (the page's one selection): none, one or a set. */
  selectedClips: ReadonlySet<string>
  /** A press on a clip's block (or its Enter) selects it; it does not move the playhead. */
  onSelectClip: (identity: string) => void
  /** A click on a clip's block at track px `x` (NaN: none): a cut's span there, else the clip; a modifier press edits the set. */
  onPressClip: (identity: string, x: number, press: Press) => void
  /** Enter on a block: `alone`, `toggle` (Ctrl/Cmd) or `range` (Shift). */
  onPressClipKey: (identity: string, press: Press) => void
  /** Whether a press at this track px on the clip lands on a cut's or a card's span. */
  onSpanAt: (identity: string, x: number) => boolean
  /** A press on empty track selects nothing. */
  onClearSelection: () => void
  /** The title cards' lane; absent, the Timeline draws none. */
  cardLane?: CardLaneModel
  /** A black card's or a clip edge's drag in progress (`ShiftFrom`), or null. */
  shifting?: ShiftFrom | null
  /** The edge drags' snapping switch (`S`). */
  snapping: SnapSwitch
  /** `q`, `w` and `s` on the track in Edit mode (`clip-edge-trim`). */
  onEdgeKey: (key: 'q' | 'w' | 's') => void
  /** A zoom in progress (design D6) and the edge tool it keeps, or null. */
  zoomHold?: { kept: EdgeKey | null } | null
  /** The drop model of a clip block dragged on the track (`track-drag-edit`). */
  reorder: ReorderModel
  /** A request for a clip's menu (`clip-context-menu`): the Timeline's one `openClipMenu`. */
  onOpenMenu: (open: ClipMenuOpen) => void
}) {
  const base = useId()
  const canvas = useRef<HTMLDivElement>(null)
  const focusGrip = () => gripRef.current?.focus({ preventScroll: true })
  const ruler = useScrub(canvas, onScrub, focusGrip, 'ruler')
  const lane = useScrub(canvas, onScrub, focusGrip, 'lane')
  const grab = useScrub(canvas, onScrub, focusGrip, 'ruler')
  // A double press on a clip places the playhead there (a clip press alone does not).
  const scrubNow = useRef(onScrub)
  scrubNow.current = onScrub
  const spanNow = useRef(onSpanAt)
  spanNow.current = onSpanAt
  const pressNow = useRef(onPressClip)
  pressNow.current = onPressClip
  const pressAt = useCallback((identity: string, clientX: number, press: Press) => {
    const box = canvas.current?.getBoundingClientRect()
    pressNow.current(identity, clientX - (box?.left ?? 0), press)
  }, [])
  const placeAt = useCallback(
    (clientX: number) => {
      const box = canvas.current?.getBoundingClientRect()
      gripRef.current?.focus({ preventScroll: true })
      scrubNow.current(clientX - (box?.left ?? 0), 'tap', 'ruler')
    },
    [gripRef],
  )
  // The clip's menu from a key on its block: under the part of the block that shows.
  const openMenuNow = useRef(onOpenMenu)
  openMenuNow.current = onOpenMenu
  const openMenuAtBlock = useCallback(
    (identity: string, block: HTMLElement) => {
      const own = block.getBoundingClientRect()
      const shown = visiblePart(own, scrollerRef.current?.getBoundingClientRect() ?? own)
      openMenuNow.current({ identity, at: { box: rectOf(shown) }, invoker: block })
    },
    [scrollerRef],
  )
  // A mouse or pen drag on a clip's block reorders it (`ClipDrag`); a press alone still selects.
  const clipGrab = useClipDrag(drag, canvas, scrollerRef, {
    clips,
    lay,
    pps,
    reorder,
    selected: selectedClips,
    locked: editing.locked,
    announce: editing.announce,
    onSelectClip,
    onSpan: (identity, clientX) => {
      const box = canvas.current?.getBoundingClientRect()
      return spanNow.current(identity, clientX - (box?.left ?? 0))
    },
  })
  // The bin's drag asks where a release would land on this track (`track-drag-edit`): the nearest
  // boundary to the pointer, when the pointer is over the track's viewport.
  const reorderNow = useRef(reorder)
  reorderNow.current = reorder
  const ppsNow = useRef(pps)
  ppsNow.current = pps
  const trackAt = editing.trackAt
  useEffect(() => {
    trackAt.current = (x, y, identity) => {
      const view = scrollerRef.current?.getBoundingClientRect()
      const box = canvas.current?.getBoundingClientRect()
      if (view === undefined || box === undefined || !inBox(view, x, y)) {
        return null
      }
      const model = reorderNow.current
      let slot = null
      try {
        const ms = pxToTime(x - box.left, ppsNow.current)
        // A clip the track draws has its own place among the boundaries; any other has none.
        slot = model.drawn.has(identity) ? model.slotAt(identity, ms) : model.slotNear(ms)
      } catch {
        slot = null
      }
      return { slot, drawn: model.drawn }
    }
    return () => {
      trackAt.current = null
    }
  }, [trackAt, scrollerRef])
  const clipDragging = useSyncExternalStore(drag.subscribe, () => drag.getClip() !== null)
  // Every cut handle and edge tool: one nearest-wins press test across them.
  const [targets] = useState<PressTargets>(() => new Map())
  const edgeDragged = shifting !== null && shifting.kind === 'edge' ? shifting.identity : null
  // The clip whose edge tool holds focus: its tools stay while the block is too narrow for detail
  // (an End that trims the clip to three frames leaves its tool there for a Home).
  const [focusedEdge, setFocusedEdge] = useState<string | null>(null)

  const totalPx = timeToPx(lay.totalMs, pps)
  const canvasPx = canvasWidth(lay.totalMs, pps, gutter)
  const view = { pps, scrollLeft: range.left, width: Math.max(1, range.width) }
  const overscan = Math.round(range.width * overscanViews)
  const shown = range.width === 0 ? null : visibleClips(lay, view, overscan)
  const windowFrom = range.left - overscan
  const windowTo = range.left + range.width + overscan

  const clipNodes = []
  const handleNodes = []
  const keysId = `${base}-trim-keys`
  const edgeKeysId = `${base}-edge-keys`
  const lockedId = `${base}-edge-locked`
  const moveLockedId = `${base}-move-locked`
  if (shown !== null) {
    for (let index = shown[0]; index <= shown[1]; index += 1) {
      const clip = clips[index]
      // A clip that keeps no frame (its cuts cover it, or its extent holds none) has no block:
      // the clips around it meet (`timeline-ripple-layout`).
      if (!hasKeptFrame(timedOf(clip))) {
        continue
      }
      // The block spans the clip's kept extent: its left edge (`lay.startsMs`) is the clip's kept
      // start, and the description says the full length beside the kept one.
      const left = timeToPx(lay.startsMs[index], pps)
      const inPx = timeToPx(clip.kept.inMs, pps)
      const keptMs = extentMs(clip.kept)
      const widthPx = timeToPx(keptMs, pps)
      const detailed = widthPx >= MIN_DETAIL_PX
      const descId = `${base}-c${index}`
      const after = behind(shifting, lay.startsMs[index])
      handleNodes.push(
        <ClipPress
          key={`${clip.identity}|press`}
          identity={clip.identity}
          name={clip.name}
          index={index}
          left={left}
          widthPx={widthPx}
          descId={descId}
          selected={selectedClips.has(clip.identity)}
          lockedId={editing.locked ? moveLockedId : null}
          after={after}
          grab={clipGrab}
          onKeyPress={onPressClipKey}
          onPress={pressAt}
          onPlace={placeAt}
          onMenu={openMenuAtBlock}
        />,
      )
      if (detailed || focusedEdge === clip.identity) {
        const listed = editing.listed(clip.identity)
        const edge = (side: 'start' | 'end') => (
          <EdgeTool
            key={`${clip.identity}|${side}`}
            identity={clip.identity}
            name={clip.name}
            clipIndex={index}
            side={side}
            facts={clip.facts}
            kept={clip.kept}
            listed={listed}
            blockLeft={left}
            widthPx={widthPx}
            pps={pps}
            after={after}
            playhead={playhead}
            drag={drag}
            locked={editing.locked}
            keysId={edgeKeysId}
            lockedId={lockedId}
            selectedKey={selected?.identity === clip.identity ? selected.key : null}
            clipSelected={selectedClips.has(clip.identity)}
            targets={targets}
            snapping={snapping}
            onSelect={onSelect}
            onEdge={editing.onEdge}
            onFocusChange={setFocusedEdge}
            fallbackRef={gripRef}
          />
        )
        // Tab order per clip: Trim In, its cut handles, Trim Out. While a drag ripples the track, the
        // tools of the clips behind its edge are left out (a drag holds the one claim, and an invisible
        // zone need not be moved on every frame); they come back with the released layout. So while a
        // zoom is in progress (design D6), but for the tool it keeps; they come back when it settles.
        const shows = (side: 'start' | 'end') =>
          edgeToolShown(
            { identity: clip.identity, side },
            { after, zooming: zoomHold !== null, kept: zoomHold?.kept ?? null },
          )
        if (shows('start')) {
          handleNodes.push(edge('start'))
        }
        // The cut handles of a clip whose edge is in the air step out until it is released.
        if (
          detailed &&
          edgeDragged !== clip.identity &&
          listed.some((cut) => !cut.removed && !edgeCut(cut, clip.kept, clip.facts.durationMs))
        ) {
          handleNodes.push(
            <ClipHandles
              key={clip.identity}
              identity={clip.identity}
              name={clip.name}
              index={index}
              facts={clip.facts}
              kept={clip.kept}
              left={left - inPx}
              widthPx={inPx + widthPx}
              totalPx={totalPx}
              shifted={after}
              pps={pps}
              listed={listed}
              playhead={playhead}
              drag={drag}
              locked={editing.locked}
              keysId={keysId}
              selectedKey={selected?.identity === clip.identity ? selected.key : null}
              onSelect={onSelect}
              onTrim={editing.onTrim}
              announce={editing.announce}
              fallbackRef={gripRef}
              targets={targets}
            />,
          )
        }
        if (shows('end')) {
          handleNodes.push(edge('end'))
        }
      }
      const blockProps: BlockProps = {
        eventId,
        index,
        left,
        pps,
        windowFrom,
        windowTo,
        turn: turns.get(clip.identity) ?? 0,
        noPicture: noPicture.has(clip.identity),
        onFilmFailed,
        after,
        descId,
      }
      clipNodes.push(
        edgeDragged === clip.identity ? (
          <LiveClipBlock key={clip.identity} clip={clip} drag={drag} {...blockProps} />
        ) : (
          <ClipBlock key={clip.identity} clip={clip} {...blockProps} />
        ),
      )
    }
  }

  return (
    <div
      className="tl-viewport"
      ref={scrollerRef}
      data-clip-drag={clipDragging || undefined}
      // Focusable by script and by a press, not by Tab (the playhead is the track's tab stop): a
      // browser that makes only scrolling boxes focusable would otherwise drop the focus when Fit
      // leaves nothing to scroll, and the next zoom key would go nowhere.
      tabIndex={-1}
      onContextMenu={(event: MouseEvent<HTMLElement>) => {
        // One listener for every clip's block, edge tools and cut handles (`data-identity`); the
        // ruler, the cards, the suggestions and the empty ground have none, so the browser's own
        // menu shows there.
        const owner = (event.target as HTMLElement).closest<HTMLElement>('[data-identity]')
        const identity = owner?.dataset.identity
        if (owner === null || identity === undefined || !event.currentTarget.contains(owner)) {
          return
        }
        // A drag is on (a clip drag cancelled itself first and prevented this event): no menu, and
        // not the browser's either.
        if (event.defaultPrevented || held(drag)) {
          event.preventDefault()
          return
        }
        event.preventDefault()
        const block = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>('.tl-clip-press[data-identity]'),
        ).find((candidate) => candidate.dataset.identity === identity)
        if (block === undefined) {
          return
        }
        const target = (event.target as HTMLElement).getBoundingClientRect()
        const shown = visiblePart(
          block.getBoundingClientRect(),
          event.currentTarget.getBoundingClientRect(),
        )
        const at = contextAnchor({ x: event.clientX, y: event.clientY }, target, shown)
        onOpenMenu({ identity, at: 'box' in at ? { box: rectOf(at.box) } : at, invoker: block })
      }}
      onPointerDown={(event: PointerEvent<HTMLElement>) => {
        // A press on the track's empty ground (not a scrollbar) selects nothing.
        const box = event.currentTarget
        const rect = box.getBoundingClientRect()
        if (event.clientX - rect.left >= box.clientWidth || event.clientY - rect.top >= box.clientHeight) {
          return
        }
        const target = event.target as HTMLElement
        if (target === box || target === canvas.current || target.classList.contains('tl-analysis')) {
          onClearSelection()
        }
      }}
      onKeyDown={(event: KeyboardEvent) => {
        const key = trackZoomKey({
          key: event.key,
          ctrlKey: event.ctrlKey,
          altKey: event.altKey,
          metaKey: event.metaKey,
          altGraph: event.getModifierState('AltGraph'),
        })
        if (key !== null) {
          event.preventDefault()
          onTrackKey(key)
          return
        }
        // Alt+Left and Right move the selected clip one place (`track-drag-edit`, D4); handled (and
        // the browser's history keys held back) only when a drawn clip is selected, never in a field.
        const way = clipMoveKey({
          key: event.key,
          altKey: event.altKey,
          ctrlKey: event.ctrlKey,
          metaKey: event.metaKey,
          shiftKey: event.shiftKey,
          altGraph: event.getModifierState('AltGraph'),
        })
        if (way !== null && selectedClips.size > 0 && !inField(event.target) && onMoveSelected(way)) {
          event.preventDefault()
          return
        }
        if (event.ctrlKey || event.altKey || event.metaKey) {
          return
        }
        // Q, W and S: the edge tools' keys, never in a field.
        const letter = event.key.toLowerCase()
        if ((letter === 'q' || letter === 'w' || letter === 's') && !inField(event.target)) {
          event.preventDefault()
          onEdgeKey(letter)
        }
      }}
    >
      <div
        className="tl-canvas"
        ref={canvas}
        style={
          {
            inlineSize: canvasPx,
            ...(analysisLane === undefined ? {} : { '--tl-lane-rows': analysisLane.rows }),
            ...(cardLane === undefined ? {} : { '--tl-cards-h': 'var(--tl-cards-row)' }),
          } as CSSProperties
        }
      >
        <div className="tl-ruler" aria-hidden="true" {...ruler}>
          <Ticks
            lay={lay}
            view={view}
            overscan={overscan}
            canvasPx={canvasPx}
            drag={drag}
            shifting={shifting}
          />
        </div>
        <ol className="tl-chapters" aria-label="Chapters">
          {bands.map((band) => {
            const starts = bandStartMs(
              lay.startsMs,
              cardLane?.leadMs ?? NO_LEAD,
              band.first,
              band.last,
            )
            const left = timeToPx(starts, pps)
            const right = timeToPx(lay.startsMs[band.last] + extentMs(clips[band.last].kept), pps)
            if (right < windowFrom || left > windowTo) {
              return null
            }
            return (
              <ChapterBand
                key={band.first}
                chapter={band.chapter}
                heading={band.heading}
                left={left}
                right={right}
                behind={behind(shifting, starts)}
                // The dragged card's chapter band starts at the card and grows with it.
                grows={
                  shifting !== null &&
                  starts < shifting.fromMs - 0.5 &&
                  lay.startsMs[band.last] + extentMs(clips[band.last].kept) >= shifting.fromMs - 0.5
                }
                pps={pps}
                drag={drag}
                shifting={shifting}
              />
            )
          })}
        </ol>
        {cardLane !== undefined && (
          <CardLane
            blocks={cardLane.blocks}
            specs={cardLane.specs}
            names={cardLane.names}
            pps={pps}
            window={{ from: windowFrom, to: windowTo }}
            selected={cardLane.selected}
            drag={drag}
            shifting={shifting}
            pictures={cardLane.pictures}
            onOpen={cardLane.onOpen}
            onPlace={cardLane.onPlace}
            onClear={cardLane.onClear}
          />
        )}
        <div className="tl-lane" {...lane}>
          {clipNodes}
        </div>
        {analysisLane !== undefined && (
          <div className="tl-analysis">
            {analysisLane.render({
              clips,
              lay,
              pps,
              shown,
              shifted: (index) => behind(shifting, lay.startsMs[index]),
              held: (index) => clips[index]?.identity === edgeDragged,
            })}
          </div>
        )}
        <ClipDragLayer drag={drag} canvas={canvas} pps={pps} />
        <PlayheadSlider
          playhead={playhead}
          clips={clips}
          lay={lay}
          pps={pps}
          shiftFromMs={shifting === null ? null : shifting.fromMs - 0.5}
          gripRef={gripRef}
          onKey={onKey}
          describedBy={`${base}-keys`}
          grab={grab}
        />
        <PlayheadKeys id={`${base}-keys`} />
        <>
            <span id={keysId} className="visually-hidden">
              {TRIM_KEYS}
            </span>
            <span id={edgeKeysId} className="visually-hidden">
              {EDGE_KEYS}
            </span>
            {editing.locked && (
              <>
                <span id={lockedId} className="visually-hidden">
                  {EDGE_LOCKED}
                </span>
                <span id={moveLockedId} className="visually-hidden">
                  {MOVE_LOCKED}
                </span>
              </>
            )}
            <span id={`${base}-card-keys`} className="visually-hidden">
              {CARD_KEYS}
            </span>
            {/* After the playhead: Tab reaches the handles after it, in time order; the
                card handles come first, being in the lane above the clips. */}
            {cardLane !== undefined && (
              <CardHandles
                key={`cards-${editing.epoch}`}
                handles={cardLane.handles}
                pps={pps}
                window={{ from: windowFrom, to: windowTo }}
                drag={drag}
                shifting={shifting}
                locked={editing.locked}
                keysId={`${base}-card-keys`}
                selected={cardLane.selected}
                onSelect={cardLane.onSelect}
                onSet={cardLane.onSet}
              />
            )}
            <div className="tl-trims-host" data-locked={editing.locked || undefined} key={editing.epoch}>
              {handleNodes}
            </div>
        </>
      </div>
    </div>
  )
}
