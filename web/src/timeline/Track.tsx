import { useId, useRef } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent, RefObject } from 'react'

import { formatTime, reasonWords } from '../cuts/times'
import { Filmstrip } from './Filmstrip'
import { PlayheadKeys, PlayheadSlider } from './Playhead'
import type { KeyAction } from './keys'
import { clipDescription } from './labels'
import { cutLabel } from './layout'
import type { ChapterBand, TrackClip } from './layout'
import { timeToPx, visibleClips, visibleTicks } from './model'
import type { Layout } from './model'
import type { LaneSlot } from './overlays/control'
import type { Playhead } from './playhead'
import type { VisibleRange } from './useVisibleRange'

/*
 * The track: a ruler, the chapter band and the clips end to end at `pps`, inside the
 * Timeline's own horizontal scroller. Only what meets the visible range and a margin of
 * one view on each side is drawn (a 400-clip event holds a few dozen elements). Read
 * only: the cuts are spans with a hatch and a text alternative, with no handle.
 */

/**
 * The phases of a scrub by pointer: where, in px from the track's start. A `tap` is a
 * touch that only places the playhead: nothing is dragged, so the video is not paused.
 */
export type ScrubPhase = 'start' | 'move' | 'end' | 'tap'

/** Clips narrower than this are drawn as a block only: no name, picture or cuts. */
const MIN_DETAIL_PX = 6
/** Clips at least this wide show their name; a cut at least this wide shows its reason. */
const NAME_PX = 28
const CUT_TEXT_PX = 72
/** A touch that moves less than this and ends within `TAP_MS` is a tap. */
const TAP_PX = 8
const TAP_MS = 600

type Pointer = { id: number; x: number; y: number; at: number }

/**
 * Pointer handlers that scrub: a mouse or pen on the ruler or the track captures the
 * pointer and the playhead follows it; a touch on the ruler does the same (it has
 * `touch-action: none`); a touch on the track body scrolls it, and only a tap moves the
 * playhead.
 */
function useScrub(
  canvas: RefObject<HTMLDivElement | null>,
  onScrub: (x: number, phase: ScrubPhase) => void,
  focusGrip: () => void,
  surface: 'ruler' | 'lane',
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
      onScrub(place(event), 'start')
    },
    onPointerMove(event: PointerEvent<HTMLElement>) {
      if (drag.current === event.pointerId) {
        onScrub(place(event), 'move')
      }
    },
    onPointerUp(event: PointerEvent<HTMLElement>) {
      if (drag.current === event.pointerId) {
        drag.current = null
        onScrub(place(event), 'end')
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
        onScrub(place(event), 'tap')
      }
    },
    onPointerCancel(event: PointerEvent<HTMLElement>) {
      touch.current = null
      if (drag.current === event.pointerId) {
        drag.current = null
        onScrub(place(event), 'end')
      }
    },
  }
}

export function Track({
  eventId,
  clips,
  lay,
  bands,
  pps,
  range,
  showCuts,
  scrollerRef,
  playhead,
  gripRef,
  noPicture,
  onFilmFailed,
  onKey,
  onTrackKey,
  onScrub,
  lane: analysisLane,
}: {
  eventId: string
  clips: readonly TrackClip[]
  lay: Layout
  bands: readonly ChapterBand[]
  pps: number
  range: VisibleRange
  /** Whether the cuts were read: without them the clips are drawn whole. */
  showCuts: boolean
  scrollerRef: RefObject<HTMLDivElement | null>
  playhead: Playhead
  gripRef: RefObject<HTMLDivElement | null>
  /** Clips whose sprite failed. */
  noPicture: ReadonlySet<string>
  onFilmFailed: (identity: string) => void
  onKey: (action: KeyAction) => void
  /** `+`, `-` and `0` while the track has focus. */
  onTrackKey: (key: string) => void
  onScrub: (x: number, phase: ScrubPhase) => void
  /** The analysis lane, a row of the canvas under the clips (`overlays/`). */
  lane?: LaneSlot
}) {
  const base = useId()
  const canvas = useRef<HTMLDivElement>(null)
  const focusGrip = () => gripRef.current?.focus({ preventScroll: true })
  const ruler = useScrub(canvas, onScrub, focusGrip, 'ruler')
  const lane = useScrub(canvas, onScrub, focusGrip, 'lane')
  const grab = useScrub(canvas, onScrub, focusGrip, 'ruler')

  const totalPx = timeToPx(lay.totalMs, pps)
  const view = { pps, scrollLeft: range.left, width: Math.max(1, range.width) }
  const overscan = range.width
  const shown = range.width === 0 ? null : visibleClips(lay, view, overscan)
  const ticks = range.width === 0 ? null : visibleTicks(lay, view, overscan)
  const windowFrom = range.left - overscan
  const windowTo = range.left + range.width + overscan

  const tickNodes = []
  if (ticks !== null) {
    for (let i = ticks.first; i <= ticks.last; i += 1) {
      const ms = i * ticks.stepMs
      tickNodes.push(
        <span key={i} className="tl-tick" style={{ insetInlineStart: timeToPx(ms, pps) }}>
          {formatTime(ms / 1000)}
        </span>,
      )
    }
  }

  const clipNodes = []
  if (shown !== null) {
    for (let index = shown[0]; index <= shown[1]; index += 1) {
      const clip = clips[index]
      const left = timeToPx(lay.startsMs[index], pps)
      const widthPx = timeToPx(clip.facts.durationMs, pps)
      const detailed = widthPx >= MIN_DETAIL_PX
      const descId = `${base}-c${index}`
      clipNodes.push(
        <div
          key={clip.identity}
          className="tl-clip"
          role="group"
          tabIndex={-1}
          aria-label={clip.name}
          aria-describedby={descId}
          data-index={index}
          data-no-picture={noPicture.has(clip.identity) || undefined}
          style={{ insetInlineStart: left, inlineSize: Math.max(1, widthPx) }}
        >
          <span id={descId} className="visually-hidden">
            {clipDescription(clip.facts.durationMs, showCuts ? clip.cutCount : 0)}
          </span>
          {detailed && !noPicture.has(clip.identity) && (
            <Filmstrip
              eventId={eventId}
              clip={clip}
              pps={pps}
              window={{ from: windowFrom - left, to: windowTo - left }}
              onFail={onFilmFailed}
            />
          )}
          {detailed &&
            showCuts &&
            clip.drawn.map((cut) => {
              const cutPx = timeToPx(cut.to - cut.from, pps)
              return (
                <span
                  key={cut.from}
                  className="tl-cut"
                  role="img"
                  aria-label={cutLabel(cut)}
                  data-reason={cut.reasons[0] ?? 'manual'}
                  style={{ insetInlineStart: timeToPx(cut.from, pps), inlineSize: Math.max(2, cutPx) }}
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
                <span className="tl-clip-length">{formatTime(clip.facts.durationMs / 1000)}</span>
              </span>
            </span>
          )}
        </div>,
      )
    }
  }

  return (
    <div
      className="tl-viewport"
      ref={scrollerRef}
      onKeyDown={(event: KeyboardEvent) => {
        if (!event.ctrlKey && !event.altKey && !event.metaKey && ['+', '=', '-', '_', '0'].includes(event.key)) {
          event.preventDefault()
          onTrackKey(event.key)
        }
      }}
    >
      <div
        className="tl-canvas"
        ref={canvas}
        style={
          {
            inlineSize: totalPx,
            ...(analysisLane === undefined ? {} : { '--tl-lane-rows': analysisLane.rows }),
          } as CSSProperties
        }
      >
        <div className="tl-ruler" aria-hidden="true" {...ruler}>
          {tickNodes}
        </div>
        <ol className="tl-chapters" aria-label="Chapters">
          {bands.map((band) => {
            const left = timeToPx(lay.startsMs[band.first], pps)
            const right = timeToPx(lay.startsMs[band.last] + clips[band.last].facts.durationMs, pps)
            if (right < windowFrom || left > windowTo) {
              return null
            }
            return (
              <li
                key={band.first}
                className="tl-chapter"
                style={{ insetInlineStart: left, inlineSize: right - left }}
              >
                <span className="tl-chapter-name">{band.heading}</span>
              </li>
            )
          })}
        </ol>
        <div className="tl-lane" {...lane}>
          {clipNodes}
        </div>
        {analysisLane !== undefined && (
          <div className="tl-analysis">
            {analysisLane.render({ clips, lay, pps, shown })}
          </div>
        )}
        <PlayheadSlider
          playhead={playhead}
          clips={clips}
          lay={lay}
          pps={pps}
          gripRef={gripRef}
          onKey={onKey}
          describedBy={`${base}-keys`}
          grab={grab}
        />
        <PlayheadKeys id={`${base}-keys`} />
      </div>
    </div>
  )
}
