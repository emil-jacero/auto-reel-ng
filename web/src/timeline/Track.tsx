import { useId, useRef } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent, RefObject } from 'react'

import type { ClipTurns } from '../cuts/ReadCuts'
import { TRIM_KEYS, formatTime, reasonWords } from '../cuts/times'
import { CardHandles, CARD_KEYS } from './CardHandles'
import { CardLane } from './CardLane'
import { Filmstrip } from './Filmstrip'
import { PlayheadKeys, PlayheadSlider } from './Playhead'
import { ClipHandles } from './TrimHandle'
import type { DragStore } from './dragStore'
import type { EditBinding } from './editing'
import type { CardBlock, CardHandle, CardSpec } from './cards'
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
 * one view on each side is drawn (a 400-clip event holds a few dozen elements). The cuts
 * are spans with a hatch and a text alternative; in the read view that is all (no handle,
 * no drag). In Edit mode (`editing`) each clip drawn with its cuts also gets its trim
 * handles (`TrimHandle.tsx`), a layer after the playhead so that Tab reaches them after it.
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
  /** Clip index → the length of the black card that opens it: its chapter band starts at the card. */
  leadMs: ReadonlyMap<number, number>
  /** The end-edge handles (Edit mode only; null in the read view) and the draft edit they write. */
  handles: readonly CardHandle[] | null
  onSet: ((chapter: string, seconds: number, words: string | null) => void) | null
  /** The selected card's chapter or null. */
  selected: string | null
  onSelect: (chapter: string) => void
  onClear: () => void
}

export function Track({
  eventId,
  clips,
  lay,
  bands,
  pps,
  range,
  showCuts,
  turns,
  scrollerRef,
  playhead,
  gripRef,
  noPicture,
  onFilmFailed,
  onKey,
  onTrackKey,
  onScrub,
  lane: analysisLane,
  editing,
  drag,
  selected,
  onSelect,
  cardLane,
}: {
  eventId: string
  clips: readonly TrackClip[]
  /** The clips end to end on the track, with the black cards' spans between them. */
  lay: Layout
  bands: readonly ChapterBand[]
  pps: number
  range: VisibleRange
  /** Whether the cuts were read: without them the clips are drawn whole. */
  showCuts: boolean
  /** Each clip's turn (`rotate`): its tiles show the frame turned. */
  turns: ClipTurns
  scrollerRef: RefObject<HTMLDivElement | null>
  playhead: Playhead
  gripRef: RefObject<HTMLDivElement | null>
  /** Clips whose sprite failed. */
  noPicture: ReadonlySet<string>
  onFilmFailed: (identity: string) => void
  onKey: (action: KeyAction) => void
  /** `+`, `-` and `0` while the track has focus. */
  onTrackKey: (key: string) => void
  /** The analysis lane, a row of the canvas under the clips (`overlays/`). */
  lane?: LaneSlot
  onScrub: (x: number, phase: ScrubPhase, surface: ScrubSurface) => void
  /** Edit mode's binding: the trim handles; null in the read view. */
  editing: EditBinding | null
  drag: DragStore
  /** The selected cut, if any. */
  selected: { identity: string; key: string } | null
  /** A cut is selected: by its handle's focus or press. */
  onSelect: (identity: string, key: string) => void
  /** The title cards' lane; absent, the Timeline draws none. */
  cardLane?: CardLaneModel
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
  const handleNodes = []
  const keysId = `${base}-trim-keys`
  if (shown !== null) {
    for (let index = shown[0]; index <= shown[1]; index += 1) {
      const clip = clips[index]
      const left = timeToPx(lay.startsMs[index], pps)
      const widthPx = timeToPx(clip.facts.durationMs, pps)
      const detailed = widthPx >= MIN_DETAIL_PX
      const descId = `${base}-c${index}`
      if (editing !== null && detailed && showCuts) {
        const listed = editing.listed(clip.identity)
        if (listed.some((cut) => !cut.removed)) {
          handleNodes.push(
            <ClipHandles
              key={clip.identity}
              identity={clip.identity}
              name={clip.name}
              index={index}
              facts={clip.facts}
              left={left}
              widthPx={widthPx}
              totalPx={totalPx}
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
            />,
          )
        }
      }
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
              turn={turns.get(clip.identity) ?? 0}
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
            ...(cardLane === undefined ? {} : { '--tl-cards-h': 'var(--tl-cards-row)' }),
          } as CSSProperties
        }
      >
        <div className="tl-ruler" aria-hidden="true" {...ruler}>
          {tickNodes}
        </div>
        <ol className="tl-chapters" aria-label="Chapters">
          {bands.map((band) => {
            const left = timeToPx(
              lay.startsMs[band.first] - (cardLane?.leadMs.get(band.first) ?? 0),
              pps,
            )
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
        {cardLane !== undefined && (
          <CardLane
            blocks={cardLane.blocks}
            specs={cardLane.specs}
            pps={pps}
            window={{ from: windowFrom, to: windowTo }}
            selected={cardLane.selected}
            drag={cardLane.handles === null ? null : drag}
            onSelect={cardLane.onSelect}
            onClear={cardLane.onClear}
          />
        )}
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
        {editing !== null && (
          <>
            <span id={keysId} className="visually-hidden">
              {TRIM_KEYS}
            </span>
            <span id={`${base}-card-keys`} className="visually-hidden">
              {CARD_KEYS}
            </span>
            {/* After the playhead: Tab reaches the handles after it, in time order; the
                card handles come first, being in the lane above the clips. */}
            {cardLane?.handles != null && cardLane.onSet !== null && (
              <CardHandles
                key={`cards-${editing.epoch}`}
                handles={cardLane.handles}
                pps={pps}
                window={{ from: windowFrom, to: windowTo }}
                drag={drag}
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
        )}
      </div>
    </div>
  )
}
