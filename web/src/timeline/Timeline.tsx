import './timeline.css'

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'

import '../rotate/rotate.css'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
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
import type { CardsBinding } from './useCardSelection'
import { createDragStore, shiftMs } from './dragStore'
import { edgeAnnouncement, edgeEdit, snappingWords, toPlayheadRefusal, trimToPlayhead } from './edgeTrim'
import type { DragStore } from './dragStore'
import type { EditBinding } from './editing'
import { selectionStands } from './handles'
import type { KeyAction } from './keys'
import {
  CARDS_UNKNOWN,
  cardsNotes,
  FILM_FAILED,
  FILM_FAILED_DETAIL,
  FIT,
  ORDER_SAVED,
  PAUSE,
  PREVIEW_OPEN,
  PLAY,
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
  zoomAt,
} from './model'
import { createPlayhead } from './playhead'
import { afterRead, endPosition, globalMs, keptPosition, timedOf } from './position'
import type { Position } from './position'
import { hasFrame, snapshotOf, useFrameReady } from './posterFrame'
import { useTimelineVideo } from './useTimelineVideo'
import { useVisibleRange } from './useVisibleRange'
import { restoredZoom, zoomMemory } from './zoomMemory'
import type { ZoomMemo } from './zoomMemory'
import { ZoomSlider } from './ZoomSlider'

/*
 * Edit mode's Timeline (D-20): the picture, the transport and zoom, and the track. It writes
 * nothing itself: its edits go to the editor's draft. The pieces that move often are small and read the playhead's store
 * themselves, so a scrub or a playing video re-renders them and not the whole track.
 */

/** What `Q` and `W` say while a save or a move of marked clips is pending. */
const EDGE_UNAVAILABLE = 'Nothing trimmed: trimming is unavailable while the save runs or marked clips are moved.'
/** The playhead is brought back into view when it comes this close to the scroller's edge. */
const EDGE_PX = 24
/** The track's margin around the view during a slider drag, in views (else one view a side). */
const LIVE_OVERSCAN = 0.25
const LIVE_SETTLE_MS = 200

export function Timeline({
  eventId,
  clips,
  chapterNames,
  prepare,
  analysis,
  editing,
  cards,
  cutHintId,
}: {
  eventId: string
  clips: readonly TrackClip[]
  chapterNames: readonly string[]
  prepare: PrepareControl
  /** The analysis lane (`overlays/`): absent, the Timeline has none and reads no analysis. */
  analysis?: AnalysisControl
  /** Edit mode's binding: the draft's cuts and turns, the trim handles, the poster. */
  editing: EditBinding
  /** The title cards: the event's resolved cards, the decorator, the page's one selection. */
  cards: {
    specs: readonly CardSpec[]
    /** The service's answer (`title_cards`), the draft's switch laid over it; `invalid` is no answer. */
    decorators: Decorators
    source: CardsSource | null
    /** The draft event style as a save would write it, while it is not the saved one (the previews send it). */
    previewStyle?: { [key: string]: unknown }
    /** The detail's `title_cards_error`, said when there is no answer. */
    error: string | null
    selection: CardsBinding
  }
  /** The id of the Timeline help's paragraph that says what the cut fields take (Edit mode). */
  cutHintId: string
}) {
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
  const handles = useMemo(() => cardHandles(placements, blocks, specs), [placements, blocks, specs])
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
  const names = useMemo(() => specs.map((spec) => spec.chapter), [specs])
  const leadMs = useMemo(() => new Map(map.gaps.map((gap) => [gap.clip, gap.lengthMs])), [map])
  const selection = cards.selection
  // Each clip's timing with its kept extent: the playhead's rules land on kept frames only.
  const facts = useMemo(() => clips.map(timedOf), [clips])
  const bands = useMemo(() => chapterBands(chapterNames, clips), [chapterNames, clips])
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
  const [selected, setSelected] = useState<Selected | null>(null)
  const clearCard = selection.clear
  const select = useCallback(
    (identity: string, key: string) => {
      setSelected((was) => (was?.identity === identity && was.key === key ? was : { identity, key }))
      clearCard()
    },
    [clearCard],
  )
  const selectCard = selection.select
  const openCard = selection.open
  const pickCard = useCallback(
    (chapter: string) => {
      setSelected(null)
      selectCard(chapter)
    },
    [selectCard],
  )
  // A block's body opens the card's dialog.
  const pressCard = useCallback(
    (chapter: string) => {
      setSelected(null)
      openCard(chapter)
    },
    [openCard],
  )
  // Reset, and a cut removed, end a selection.
  const epoch = editing.epoch
  useEffect(() => setSelected(null), [epoch])
  useEffect(() => {
    if (selected !== null) {
      // A cut that became part of a leading or a trailing cut has no handle: nor a selection.
      const clip = clips.find((c) => c.identity === selected.identity)
      const there = selectionStands(
        editing.listed(selected.identity),
        selected.key,
        clip?.kept ?? null,
        clip?.facts.durationMs ?? 0,
      )
      if (!there) {
        setSelected(null)
      }
    }
  }, [editing, selected, clips])

  const scroller = useRef<HTMLDivElement>(null)
  const grip = useRef<HTMLDivElement>(null)
  const [range, syncRange, expectRange] = useVisibleRange(scroller)
  // A Zoom slider drag in progress: the track draws a narrower margin around the view while it
  // lasts (`LIVE_OVERSCAN`), so each of its frames lays out fewer clips; the full margin comes
  // back `LIVE_SETTLE_MS` after the slider's last zoom.
  const [live, setLive] = useState(false)
  const settle = useRef(0)
  useEffect(() => () => window.clearTimeout(settle.current), [])
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

  // The clips the page read again: the playhead stays only where it still means the same clip,
  // and on a kept frame of it (a new leading or trailing cut moves it to the nearest one).
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
          // The tap is on the scrub surface; the block is the opener the dialog returns focus to.
          const block = Array.from(
            document.querySelectorAll<HTMLElement>('button.tl-card[data-card]'),
          ).find((b) => b.dataset.card === chapter)
          block?.focus({ preventScroll: true })
          pressCard(chapter)
        } else {
          pickCard(chapter)
        }
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
    ppsRef.current = next.pps
    // The range the zoom will show, in the same render: one render per zoom, not two.
    expectRange(next.scrollLeft)
    setZoom({ pps: next.pps, fitted: next.pps <= fitNow + 1e-9 })
  }
  const zoomBy = (factor: number) => zoomTo(ppsRef.current * factor)
  const fitAll = () => {
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

  // Ctrl+wheel (Cmd+wheel; a trackpad pinch arrives as a Ctrl+wheel) zooms about the pointer, at
  // most once per animation frame. A listener of our own, not passive, so the page does not zoom
  // instead; a wheel without Ctrl or Cmd is left to the browser.
  const wheelZoom = useRef({ zoomTo, forget: () => undefined as void })
  wheelZoom.current = {
    zoomTo,
    forget: () => {
      beforeFit.current = null
    },
  }
  useEffect(() => {
    const el = scroller.current
    if (el === null) {
      return undefined
    }
    let factor = 1
    let pointerX = 0
    let frame = 0
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) {
        return
      }
      event.preventDefault()
      factor *= wheelFactor(event.deltaY, event.deltaMode, Math.max(1, el.clientHeight))
      pointerX = event.clientX - el.getBoundingClientRect().left - el.clientLeft
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
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      el.removeEventListener('wheel', onWheel)
      if (frame !== 0) {
        cancelAnimationFrame(frame)
      }
    }
  }, [])

  /** `Q`/`W`: trim the start or end of the clip under the playhead to it; `S`: snapping off/on. */
  const onEdgeKey = (key: 'q' | 'w' | 's') => {
    if (key === 's') {
      snapping.current = !snapping.current
      editing.announce(snappingWords(snapping.current))
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

  const suggestions = useSuggestions(analysis, { clips, lay, pps, seekTo: video.seekTo })
  const cardLane = useMemo<CardLaneModel | undefined>(
    () =>
      blocks.length === 0
        ? undefined
        : {
            blocks,
            specs,
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
    [specs, blocks, leadMs, shifting, handles, editing, selection.selected, selection.clear, pickCard, pressCard, pictures],
  )
  const cardNotes = cardsNotes(cards.specs, placements, decorators, cards.source, cards.error)

  const atFit = pps <= fit + 1e-9
  const atMax = pps >= MAX_PPS - 1e-9
  const note = video.note
  // Use as poster (Edit mode): why it cannot act now, in words, or null.
  const frame = useFrameReady(video.videoRef, held)
  const [posterFailed, setPosterFailed] = useState(false)
  const posterWhy = (() => {
    const result = posterFromPlayhead(clips, playhead.get(), {
      locked: editing.locked,
      held,
      frame,
    })
    return 'why' in result ? result.why : null
  })()
  // Pressed while it cannot act: the reason in a tip under the button (no room taken in the
  // toolbar), said once in the live region; the tip goes on blur, Escape, or with the reason.
  const [posterTip, setPosterTip] = useState<string | null>(null)
  const reasonGone = posterWhy === null
  useEffect(() => {
    if (reasonGone) {
      setPosterTip(null)
    }
  }, [reasonGone])
  const usePoster = () => {
    const element = video.videoRef.current
    // What the button shows first (it looks unavailable: it does not act), then the video now.
    const result = posterFromPlayhead(clips, playhead.get(), {
      locked: editing.locked,
      held,
      frame: posterWhy === null && hasFrame(element),
    })
    if ('why' in result) {
      const why = posterWhy ?? result.why
      setPosterTip(why)
      setAnnouncement(why)
      return
    }
    setPosterTip(null)
    if (element === null) {
      return
    }
    setPosterFailed(false)
    const turn = turns.get(result.pick.clip) ?? 0
    snapshotOf(element).then(
      (url) => editing.onPoster(result.pick, { url, turn }),
      () => setPosterFailed(true),
    )
  }
  return (
    <div className="timeline" data-trimming={trimming || undefined} data-edge-side={edgeSide ?? undefined}>
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

      <div className="tl-controls">
        <button
          type="button"
          className="btn btn-primary tl-play"
          onClick={toggle}
        >
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
        <PlayheadReadout playhead={playhead} clips={clips} lay={lay} longestCardMs={longestCardMs} />
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
        <div className="tl-poster">
          <button
            type="button"
            className="btn btn-secondary"
            aria-disabled={posterWhy !== null || undefined}
            aria-describedby={posterWhyId}
            title={posterWhy ?? undefined}
            onClick={usePoster}
            onBlur={() => setPosterTip(null)}
            onKeyDown={(event) => {
              if (event.key === 'Escape' && posterTip !== null) {
                event.preventDefault()
                setPosterTip(null)
              }
            }}
          >
            <Icon name="film" />
            {USE_AS_POSTER}
          </button>
          {/* Always there: its words are the button's description while it cannot act. */}
          <span id={posterWhyId} className="visually-hidden">
            {posterWhy ?? ''}
          </span>
          {posterTip !== null && (
            <span className="tl-poster-tip" aria-hidden="true">
              {posterTip}
            </span>
          )}
        </div>
      </div>
      {posterFailed && (
        <Alert
          tone="warn"
          role="alert"
          title="The picture could not be copied."
          detail="The poster is not changed."
        />
      )}

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
        onScrub={scrubAt}
        lane={suggestions.lane}
        editing={editing}
        drag={drag}
        selected={selected}
        onSelect={select}
        cardLane={cardLane}
        shifting={shifting}
        snapping={snapping}
        onEdgeKey={onEdgeKey}
      />

      <CutFields
        selected={selected}
        clips={clips}
        editing={editing}
        drag={drag}
        hintId={cutHintId}
      />

      {editing.orderChanged && <Alert tone="info" role="note" title={ORDER_SAVED} />}

      {decorators === 'invalid' && <p className="tl-summary">{CARDS_UNKNOWN}</p>}

      {pictures.failures.map((failure) => (
        <Alert
          key={failure.chapter}
          tone="warn"
          role="note"
          title={`The title card for ${cardSubject(failure.chapter)} could not be drawn here.`}
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

      {noPicture.size > 0 && (
        <Alert tone="warn" role="note" title={FILM_FAILED} detail={FILM_FAILED_DETAIL} />
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
