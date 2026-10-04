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

import { NO_TURNS } from '../cuts/ReadCuts'
import type { ClipCuts, ClipTurns } from '../cuts/ReadCuts'
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
import { createDragStore } from './dragStore'
import type { DragStore } from './dragStore'
import type { EditBinding } from './editing'
import type { KeyAction } from './keys'
import {
  CUTS_READING,
  CUTS_UNREADABLE,
  CUTS_UNREADABLE_DETAIL,
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
import { chapterBands, movieMs, trackLayout } from './layout'
import type { TrackClip } from './layout'
import type { ShiftFrom } from './Track'
import type { Layout } from './model'
import { DEFAULT_PPS, MAX_PPS, fitPps, pxToTime, timeToPx, zoomAt } from './model'
import { createPlayhead } from './playhead'
import { endPosition, globalMs, onGrid } from './position'
import type { Position } from './position'
import { hasFrame, snapshotOf, useFrameReady } from './posterFrame'
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
  cutHintId,
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
  const turns = cuts.turns ?? NO_TURNS
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
  const shifting = useMemo(() => {
    const handle = dragChapter === null ? undefined : handles.find((h) => h.chapter === dragChapter)
    const block = handle === undefined ? undefined : blocks[handle.index]
    return handle === undefined || block === undefined
      ? null
      : ({
          chapter: handle.chapter,
          fromMs: block.startMs + block.widthMs,
          baseTenths: handle.tenths,
        } satisfies ShiftFrom)
  }, [dragChapter, handles, blocks])
  const names = useMemo(() => specs.map((spec) => spec.chapter), [specs])
  const leadMs = useMemo(() => new Map(map.gaps.map((gap) => [gap.clip, gap.lengthMs])), [map])
  const selection = cards.selection
  const facts = useMemo(() => clips.map((clip) => clip.facts), [clips])
  const bands = useMemo(() => chapterBands(chapterNames, clips), [chapterNames, clips])
  const movie = useMemo(
    () => (cuts.cuts === null ? null : movieMs(clips, cuts.cuts)),
    [clips, cuts.cuts],
  )
  // The playhead opens at the start of the movie: its opening card when that is black.
  const playhead = useMemo(
    () => createPlayhead(trackStart(map, clipLay, facts, names)),
    [],
  )
  const previews = editing?.previews ?? null
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
  // A block's body in Edit mode opens the card's dialog; the read view only selects.
  const pressCard = useCallback(
    (chapter: string) => {
      setSelected(null)
      if (editing === null) {
        selectCard(chapter)
      } else {
        openCard(chapter)
      }
    },
    [editing, selectCard, openCard],
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
  const wanted = zoom.fitted ? fit : Math.min(MAX_PPS, Math.max(fit, zoom.pps))
  const pps = wanted
  const ppsRef = useRef(pps)
  ppsRef.current = pps

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
      const d = drag.getCard()
      if (d === null || d.chapter !== shifting.chapter) {
        return // ended: the layout drawn in this commit takes over, the cleanup lets go
      }
      const by = `${timeToPx((d.tenths - shifting.baseTenths) * 100, ppsRef.current)}px 0`
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
      video.seekTo(trackStart(map, clipLay, facts, names))
    } else if (at.ms > now.facts.durationMs) {
      video.seekTo({ clip: at.clip, ms: onGrid(now.facts, now.facts.durationMs) })
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
      video.seekTo(clips[at.clip] === undefined ? trackStart(map, clipLay, facts, names) : { clip: at.clip, ms: 0 })
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
    setAnnouncement(playheadAnnouncement(clips[pos.clip].name, pos.ms, pos.card ?? null))

  /** A press on a cut's span selects the cut (a place in a card is no clip's). */
  const selectUnder = (pos: Position) => {
    if (editing === null || pos.card != null) {
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
          if (editing !== null) {
            // The tap is on the scrub surface; the block is the opener the dialog returns focus to.
            const block = Array.from(
              document.querySelectorAll<HTMLElement>('button.tl-card[data-card]'),
            ).find((b) => b.dataset.card === chapter)
            block?.focus({ preventScroll: true })
          }
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
            specs,
            leadMs,
            shifting,
            handles: editing === null ? null : handles,
            onSet: editing === null ? null : editing.onCardDuration,
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
  const posterWhy =
    editing === null
      ? null
      : (() => {
          const result = posterFromPlayhead(clips, playhead.get(), {
            locked: editing.locked,
            held,
            frame,
          })
          return 'why' in result ? result.why : null
        })()
  const usePoster = () => {
    const element = video.videoRef.current
    const result = posterFromPlayhead(clips, playhead.get(), {
      locked: editing?.locked ?? true,
      held,
      frame: hasFrame(element),
    })
    if (editing === null || element === null || 'why' in result) {
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
          aria-disabled={(cutsPending && !video.playing) || undefined}
          onClick={toggle}
        >
          <Icon name={video.playing ? 'pause' : 'play'} />
          {video.playing ? PAUSE : PLAY}
        </button>
        <PlayheadReadout playhead={playhead} clips={clips} lay={lay} longestCardMs={longestCardMs} />
        <MovieStat
          drag={drag}
          shifting={shifting}
          specs={specs}
          placeAll={placeAll}
          clipLay={clipLay}
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
        {editing !== null && (
          <div className="tl-poster">
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={posterWhy !== null || undefined}
              aria-describedby={posterWhy !== null ? posterWhyId : undefined}
              onClick={usePoster}
            >
              <Icon name="film" />
              {USE_AS_POSTER}
            </button>
            {posterWhy !== null && (
              <span id={posterWhyId} className="tl-poster-why">
                {posterWhy}
              </span>
            )}
          </div>
        )}
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
        shifting={shifting}
      />

      {editing !== null && (
        <CutFields
          selected={selected}
          clips={clips}
          editing={editing}
          drag={drag}
          hintId={cutHintId}
        />
      )}

      {editing?.orderChanged === true && <Alert tone="info" role="note" title={ORDER_SAVED} />}

      <SummaryNotes cardsUnknown={decorators === 'invalid'} pending={cutsPending} />

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
  map,
  movie,
}: {
  drag: DragStore
  shifting: ShiftFrom | null
  specs: readonly CardSpec[]
  placeAll: (specs: readonly CardSpec[]) => Placement[]
  clipLay: Layout
  map: CardMap
  movie: number | null
}) {
  const tenths = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.getCard()
    return shifting !== null && d !== null && d.chapter === shifting.chapter ? d.tenths : null
  })
  const now = useMemo(
    () =>
      tenths === null || shifting === null
        ? map
        : cardMap(
            placeAll(withDurations(specs, new Map([[shifting.chapter, tenths / 10]]))),
            clipLay,
          ),
    [tenths, shifting, map, specs, placeAll, clipLay],
  )
  if (movie === null) {
    return null
  }
  // One span per term: a narrow screen wraps between terms, never inside one.
  const terms = movieStat(movie, clipLay.totalMs, now.totalMs).split(' \u00b7 ')
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

/** What the stat cannot say: the cuts are still being read, or whether cards are drawn is not known. */
function SummaryNotes({ cardsUnknown, pending }: { cardsUnknown: boolean; pending: boolean }) {
  if (!cardsUnknown && !pending) {
    return null
  }
  return (
    <p className="tl-summary">
      {cardsUnknown && 'Whether title cards are drawn is not known.'}
      {cardsUnknown && pending && ' '}
      {pending && CUTS_READING}
    </p>
  )
}

/** Whether a clip preview of Edit mode is open, and so holds the page's one video. */
function usePreviewHeld(previews: EditBinding['previews'] | null): boolean {
  return useSyncExternalStore(
    previews === null ? NEVER : previews.subscribe,
    () => previews !== null && previews.open() !== null,
  )
}
