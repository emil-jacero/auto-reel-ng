import './timeline.css'

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import type { ClipCuts } from '../cuts/ReadCuts'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { PlayheadReadout } from './Playhead'
import { PrepareButton, PrepareJob } from './Prepare'
import type { PrepareControl } from './Prepare'
import { Track } from './Track'
import type { ScrubPhase } from './Track'
import type { KeyAction } from './keys'
import {
  CUTS_READING,
  CUTS_UNREADABLE,
  CUTS_UNREADABLE_DETAIL,
  FILM_FAILED,
  FILM_FAILED_DETAIL,
  FIT,
  PAUSE,
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
  failure: { cause: string; detail: string | null } | null
}

export function Timeline({
  eventId,
  clips,
  chapterNames,
  cuts,
  prepare,
}: {
  eventId: string
  clips: readonly TrackClip[]
  chapterNames: readonly string[]
  cuts: CutsRead
  prepare: PrepareControl
}) {
  const lay = useMemo(() => trackLayout(clips), [clips])
  const facts = useMemo(() => clips.map((clip) => clip.facts), [clips])
  const bands = useMemo(() => chapterBands(chapterNames, clips), [chapterNames, clips])
  const playhead = useMemo(() => createPlayhead(startPosition()), [])
  const video = useTimelineVideo({ eventId, clips, playhead })

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
  const toggle = () => {
    if (!cutsPending || video.playing) {
      video.toggle()
    }
  }

  const announce = (pos: Position) =>
    setAnnouncement(playheadAnnouncement(clips[pos.clip].name, pos.ms))

  const scrubAt = (x: number, phase: ScrubPhase) => {
    if (phase === 'tap') {
      // A tap drags nothing: place the playhead and let a playing video go on from there.
      const pos = positionAt(lay, facts, pxToTime(x, ppsRef.current))
      video.seekTo(pos)
      announce(pos)
      return
    }
    if (phase === 'start') {
      dragging.current = true
      video.scrubStart()
    }
    const pos = positionAt(lay, facts, pxToTime(x, ppsRef.current))
    video.seekTo(pos)
    if (phase === 'end') {
      dragging.current = false
      video.scrubEnd()
      announce(pos)
    }
  }

  const onKey = (action: KeyAction) => {
    const at = playhead.get()
    let pos: Position
    switch (action.kind) {
      case 'frames':
        pos = stepFrames(facts, at, action.n)
        break
      case 'ms':
        pos = stepMs(lay, facts, at, action.ms)
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

  const atFit = pps <= fit + 1e-9
  const atMax = pps >= MAX_PPS - 1e-9
  const note = video.note
  return (
    <div className="timeline">
      <div className="tl-stage">
        <video
          ref={video.videoRef}
          className="tl-video"
          preload="auto"
          playsInline
          aria-hidden="true"
          tabIndex={-1}
          {...video.handlers}
        />
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
        scrollerRef={scroller}
        playhead={playhead}
        gripRef={grip}
        noPicture={noPicture}
        onFilmFailed={onFilmFailed}
        onKey={onKey}
        onTrackKey={onTrackKey}
        onScrub={scrubAt}
      />

      <p className="tl-summary">
        {cuts.cuts !== null && movieWords(movieMs(clips, cuts.cuts), lay.totalMs)}
        {cutsPending && CUTS_READING}
      </p>

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
