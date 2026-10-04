import './timeline.css'

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'

import { NO_TURNS } from '../cuts/ReadCuts'
import type { ClipCuts, ClipTurns } from '../cuts/ReadCuts'
import '../rotate/rotate.css'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { CutFields } from './CutFields'
import type { Selected } from './CutFields'
import { PlayheadReadout } from './Playhead'
import { PrepareButton, PrepareJob } from './Prepare'
import type { PrepareControl } from './Prepare'
import type { AnalysisControl } from './overlays/control'
import { useSuggestions } from './overlays/useSuggestions'
import { Track } from './Track'
import type { CardLaneModel, ScrubPhase, ScrubSurface } from './Track'
import {
  cardBlocks,
  cardMap,
  cardPlacements,
  cardTimeWords,
  clipTimeAt,
  movieWithCards,
  trackLayout as withCards,
} from './cards'
import type { CardSpec, DecoratorsRead, Placement } from './cards'
import type { CardsBinding } from './useCardSelection'
import { createDragStore } from './dragStore'
import type { EditBinding } from './editing'
import type { KeyAction } from './keys'
import {
  CUTS_READING,
  CUTS_UNREADABLE,
  CUTS_UNREADABLE_DETAIL,
  CARDS_NOT_PLAYED,
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
  movieWords,
  playheadAnnouncement,
} from './labels'
import { chapterBands, movieMs, trackLayout } from './layout'
import type { TrackClip } from './layout'
import { DEFAULT_PPS, MAX_PPS, fitPps, pxToTime, timeToPx, zoomAt } from './model'
import { createPlayhead } from './playhead'
import {
  endPosition,
  globalMs,
  onGrid,
  positionAt,
  startPosition,
  stepFrames,
  stepMs,
} from './position'
import type { Position } from './position'
import { useTimelineVideo } from './useTimelineVideo'
import { useVisibleRange } from './useVisibleRange'

/*
 * The open Timeline (D-20): the picture, the transport and zoom, and the track. Read only:
 * it writes nothing. The pieces that move often are small and read the playhead's store
 * themselves, so a scrub or a playing video re-renders them and not the whole track.
 */

const ZOOM_STEP = 1.5
/** The playhead is brought back into view when it comes this close to the scroller's edge. */
const EDGE_PX = 24

/** What the page's read of `reel.yaml` gave: the cuts, or why not (null cuts and no failure: not read yet). */
export type CutsRead = {
  cuts: ClipCuts | null
  /** The clips' turns (the draft's in Edit mode); null: not read, shown unturned. */
  turns?: ClipTurns | null
  failure: { cause: string; detail: string | null } | null
}

export function Timeline({
  eventId,
  clips,
  chapterNames,
  cuts,
  prepare,
  analysis,
  editing = null,
  cards,
}: {
  eventId: string
  clips: readonly TrackClip[]
  chapterNames: readonly string[]
  cuts: CutsRead
  prepare: PrepareControl
  /** The analysis lane (`overlays/`): absent, the Timeline has none and reads no analysis. */
  analysis?: AnalysisControl
  /** Edit mode's binding (trim handles, the draft's cuts); null in the read view. */
  editing?: EditBinding | null
  /** The title cards: the event's resolved cards, the decorator, the page's one selection. */
  cards: { specs: readonly CardSpec[]; decorators: DecoratorsRead; selection: CardsBinding }
}) {
  const clipLay = useMemo(() => trackLayout(clips), [clips])
  const turns = cuts.turns ?? NO_TURNS
  const decorators = cards.decorators
  const placements = useMemo<Placement[]>(
    () =>
      decorators === 'pending' || decorators === 'unreadable'
        ? []
        : cardPlacements(
            cards.specs,
            clips.map((clip) => ({
              chapter: clip.chapter,
              durationMs: clip.facts.durationMs,
              spans: clip.spans,
            })),
            decorators,
          ),
    [cards.specs, clips, decorators],
  )
  // Clip time stays the one time of the playhead, the cuts and the marks; `lay` below is
  // where the clips are on the track, with the black cards' spans between them.
  const map = useMemo(() => cardMap(placements, clipLay), [placements, clipLay])
  const lay = useMemo(() => withCards(clipLay, map), [clipLay, map])
  const blocks = useMemo(() => cardBlocks(placements, lay), [placements, lay])
  const leadMs = useMemo(() => new Map(map.gaps.map((gap) => [gap.clip, gap.lengthMs])), [map])
  const selection = cards.selection
  const facts = useMemo(() => clips.map((clip) => clip.facts), [clips])
  const bands = useMemo(() => chapterBands(chapterNames, clips), [chapterNames, clips])
  const playhead = useMemo(() => createPlayhead(startPosition()), [])
  const drag = useMemo(() => createDragStore(), [])
  const previews = editing?.previews ?? null
  const held = usePreviewHeld(previews)
  const video = useTimelineVideo({ eventId, clips, playhead, turns, held })
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
  const pickCard = useCallback(
    (chapter: string) => {
      setSelected(null)
      selectCard(chapter)
    },
    [selectCard],
  )
  // Reset, and a cut removed, end a selection.
  const epoch = editing?.epoch
  useEffect(() => setSelected(null), [epoch])
  useEffect(() => {
    if (selected !== null && editing !== null) {
      const there = editing
        .listed(selected.identity)
        .some((cut) => cut.key === selected.key && !cut.removed)
      if (!there) {
        setSelected(null)
      }
    }
  }, [editing, selected])

  const scroller = useRef<HTMLDivElement>(null)
  const grip = useRef<HTMLDivElement>(null)
  const [range, syncRange] = useVisibleRange(scroller)
  const [zoom, setZoom] = useState({ pps: DEFAULT_PPS, fitted: true })
  const pendingScroll = useRef<number | null>(null)
  const dragging = useRef(false)
  const [announcement, setAnnouncement] = useState('')
  const [noPicture, setNoPicture] = useState<ReadonlySet<string>>(new Set())

  const fit = range.width > 0 ? fitPps(lay.totalMs, range.width) : DEFAULT_PPS
  const pps = zoom.fitted ? fit : Math.min(MAX_PPS, Math.max(fit, zoom.pps))
  const ppsRef = useRef(pps)
  ppsRef.current = pps

  // A zoom is applied after the commit that gave the canvas its new width.
  useLayoutEffect(() => {
    const el = scroller.current
    if (el !== null && pendingScroll.current !== null) {
      el.scrollLeft = pendingScroll.current
      pendingScroll.current = null
      syncRange()
    }
  }, [pps, syncRange])

  // The clips the page read again: the playhead stays only where it still means the same clip.
  const previous = useRef(clips)
  useEffect(() => {
    const was = previous.current
    previous.current = clips
    if (was === clips) {
      return
    }
    const at = playhead.get()
    const now = clips[at.clip]
    if (now === undefined || was[at.clip]?.identity !== now.identity) {
      video.seekTo(startPosition())
    } else if (at.ms > now.facts.durationMs) {
      video.seekTo({ clip: at.clip, ms: onGrid(now.facts, now.facts.durationMs) })
    }
  }, [clips, facts, playhead, video])

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

  // Play shows no frame the movie omits: until the cuts are read (or known unreadable) it waits.
  const cutsPending = cuts.cuts === null && cuts.failure === null
  // Edit mode's open clip preview makes room for the Timeline's video when asked: closed,
  // then the video is created at the playhead (`useTimelineVideo`, `held`).
  const takePage = () => {
    const open = previews?.open() ?? null
    if (previews !== null && open !== null) {
      previews.hide(open)
    }
  }
  const toggle = () => {
    if (!cutsPending || video.playing) {
      if (!video.playing) {
        takePage()
      }
      video.toggle()
    }
  }

  const announce = (pos: Position) =>
    setAnnouncement(playheadAnnouncement(clips[pos.clip].name, pos.ms))

  /** A press on a cut's span selects the cut. */
  const selectUnder = (pos: Position) => {
    if (editing === null) {
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

  /** The playhead's position for a track px, or null inside a black card (nothing to play there). */
  const positionOf = (x: number, surface: ScrubSurface): Position | null => {
    const at = clipTimeAt(map, pxToTime(x, ppsRef.current))
    if (at.kind === 'clip') {
      return positionAt(clipLay, facts, at.ms)
    }
    // The ruler goes to the footage after the card; a press on the lane selects the card.
    return surface === 'ruler' ? positionAt(clipLay, facts, at.afterMs) : null
  }
  const heldInCard = useRef(false)

  const scrubAt = (x: number, phase: ScrubPhase, surface: ScrubSurface) => {
    const inCard = clipTimeAt(map, pxToTime(x, ppsRef.current))
    if (surface === 'lane' && inCard.kind === 'card' && (phase === 'start' || phase === 'tap')) {
      // A press in a black card's span selects the card and leaves the playhead where it is.
      pickCard(cards.specs[inCard.chapter].chapter)
      heldInCard.current = phase === 'start'
      return
    }
    if (heldInCard.current) {
      heldInCard.current = phase !== 'end'
      return
    }
    if (phase === 'tap') {
      // A tap drags nothing: place the playhead and let a playing video go on from there.
      const pos = positionOf(x, surface) ?? playhead.get()
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
        selectUnder(positionOf(x, surface) ?? playhead.get())
      }
    }
    const pos = positionOf(x, surface) ?? playhead.get()
    video.seekTo(pos)
    if (phase === 'end') {
      dragging.current = false
      video.scrubEnd()
      announce(pos)
    }
  }

  const onKey = (action: KeyAction) => {
    if (action.kind !== 'toggle') {
      takePage()
    }
    const at = playhead.get()
    let pos: Position
    switch (action.kind) {
      case 'frames':
        pos = stepFrames(facts, at, action.n)
        break
      case 'ms':
        pos = stepMs(clipLay, facts, at, action.ms)
        break
      case 'to':
        pos = action.where === 'start' ? startPosition() : endPosition(facts)
        break
      case 'toggle':
        toggle()
        return
    }
    video.seekTo(pos)
    announce(pos)
  }

  const zoomBy = (factor: number) => {
    const el = scroller.current
    if (el === null) {
      return
    }
    const target = Math.min(MAX_PPS, Math.max(fit, pps * factor))
    if (Math.abs(target - pps) < 1e-9) {
      return
    }
    const view = { pps, scrollLeft: el.scrollLeft, width: Math.max(1, el.clientWidth) }
    // Keep the playhead where it is in the view; centre on the view when it is out of it.
    const px = timeToPx(globalMs(lay, playhead.get()), pps) - el.scrollLeft
    const anchor = px >= 0 && px <= view.width ? px : view.width / 2
    const next = zoomAt(view, target / pps, anchor, lay.totalMs)
    pendingScroll.current = next.scrollLeft
    setZoom({ pps: next.pps, fitted: false })
  }
  const fitAll = () => {
    pendingScroll.current = 0
    if (scroller.current !== null) {
      scroller.current.scrollLeft = 0 // also when the scale does not change (the floor of 4 px/s)
      syncRange()
    }
    setZoom({ pps: fit, fitted: true })
  }
  const onTrackKey = (key: string) => {
    if (key === '0') {
      fitAll()
    } else if (key === '+' || key === '=') {
      zoomBy(ZOOM_STEP)
    } else {
      zoomBy(1 / ZOOM_STEP)
    }
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
            specs: cards.specs,
            leadMs,
            selected: selection.selected,
            onSelect: pickCard,
            onClear: selection.clear,
          },
    [cards.specs, blocks, leadMs, selection.selected, selection.clear, pickCard],
  )
  const cardNotes = cardsNotes(cards.specs, placements, decorators)

  const atFit = pps <= fit + 1e-9
  const atMax = pps >= MAX_PPS - 1e-9
  const note = video.note
  return (
    <div className="timeline" data-trimming={trimming || undefined}>
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
      </div>

      <div className="tl-controls">
        <button
          type="button"
          className="btn btn-primary tl-play"
          aria-disabled={(cutsPending && !video.playing) || undefined}
          onClick={toggle}
        >
          <Icon name={video.playing ? 'pause' : 'play'} />
          {video.playing ? PAUSE : PLAY}
        </button>
        <PlayheadReadout playhead={playhead} clips={clips} lay={lay} />
        <div className="tl-zoom" role="group" aria-label="Zoom">
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            aria-label={ZOOM_OUT}
            title={ZOOM_OUT}
            aria-disabled={atFit || undefined}
            onClick={() => zoomBy(1 / ZOOM_STEP)}
          >
            <Icon name="minus" />
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            aria-label={ZOOM_IN}
            title={ZOOM_IN}
            aria-disabled={atMax || undefined}
            onClick={() => zoomBy(ZOOM_STEP)}
          >
            <Icon name="plus" />
          </button>
          <button type="button" className="btn btn-secondary" onClick={fitAll}>
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
        showCuts={cuts.cuts !== null}
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
      />

      {editing !== null && (
        <CutFields selected={selected} clips={clips} editing={editing} drag={drag} />
      )}

      {editing?.orderChanged === true && <Alert tone="info" role="note" title={ORDER_SAVED} />}

      <p className="tl-summary">
        {cuts.cuts !== null && movieWords(movieWithCards(movieMs(clips, cuts.cuts), map), clipLay.totalMs, cardTimeWords(map))}
        {decorators === 'unset' && placements.some((place) => place.kind === 'off') && '. Title cards are not counted.'}
        {cutsPending && CUTS_READING}
      </p>

      {blocks.length > 0 && <p className="tl-cards-note">{CARDS_NOT_PLAYED}</p>}
      {cardNotes.map((note) => (
        <Alert key={note.title} tone="info" role="note" title={note.title} detail={note.detail} />
      ))}

      {suggestions.strip}

      <p className="visually-hidden" role="status">
        {announcement}
      </p>

      {cuts.failure !== null && (
        <Alert
          tone="warn"
          role="note"
          title={CUTS_UNREADABLE}
          detail={`${CUTS_UNREADABLE_DETAIL} ${cuts.failure.cause}${cuts.failure.detail === null ? '' : ` ${cuts.failure.detail}`}`}
        />
      )}
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

const NEVER = () => () => undefined

/** Whether a clip preview of Edit mode is open, and so holds the page's one video. */
function usePreviewHeld(previews: EditBinding['previews'] | null): boolean {
  return useSyncExternalStore(
    previews === null ? NEVER : previews.subscribe,
    () => previews !== null && previews.open() !== null,
  )
}
