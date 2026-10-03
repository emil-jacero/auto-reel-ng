import { useMemo, useSyncExternalStore } from 'react'
import type { HTMLAttributes, KeyboardEvent, Ref } from 'react'

import { ClockGroup } from '../ui/Clock'
import { playheadKey } from './keys'
import type { KeyAction } from './keys'
import { PLAYHEAD, TRACK_KEYS, playheadValueText } from './labels'
import type { TrackClip } from './layout'
import type { Layout } from './model'
import { timeToPx } from './model'
import { clampPosition, globalMs } from './position'
import { readoutOf, readoutScales } from './readout'
import type { Playhead as PlayheadStore } from './playhead'

/**
 * The playhead: a line over the ruler and the clips with a grip on the ruler. The grip
 * is the keyboard control, a slider over the whole timeline in seconds, whose value text
 * names the clip and the time in it. It is positioned by the store (a scrub re-renders
 * this and the readers of the store, not the track). A key is handled only while it has
 * focus, and never with Ctrl, Alt or Meta held, which belong to the browser.
 */
export function PlayheadSlider({
  playhead,
  clips,
  lay,
  pps,
  gripRef,
  onKey,
  describedBy,
  grab,
}: {
  playhead: PlayheadStore
  clips: readonly TrackClip[]
  lay: Layout
  pps: number
  gripRef: Ref<HTMLDivElement>
  onKey: (action: KeyAction) => void
  describedBy: string
  /** The pointer handlers of a scrub: the grip is dragged like the ruler. */
  grab: HTMLAttributes<HTMLDivElement>
}) {
  const at = clampPosition(clips, useSyncExternalStore(playhead.subscribe, playhead.get))
  const clip = clips[at.clip]
  const now = globalMs(lay, at)
  return (
    <div className="tl-playhead" style={{ insetInlineStart: timeToPx(now, pps) }}>
      <div
        ref={gripRef}
        className="tl-grip"
        role="slider"
        tabIndex={0}
        aria-label={PLAYHEAD}
        aria-orientation="horizontal"
        aria-valuemin={0}
        aria-valuemax={lay.totalMs / 1000}
        aria-valuenow={now / 1000}
        aria-valuetext={playheadValueText(clip.name, at.ms, clip.facts.durationMs, now, lay.totalMs)}
        aria-describedby={describedBy}
        {...grab}
        onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
          if (event.ctrlKey || event.altKey || event.metaKey) {
            return
          }
          const action = playheadKey(event.key, event.shiftKey)
          if (action !== null) {
            event.preventDefault()
            onKey(action)
          }
        }}
      />
    </div>
  )
}

/** The hidden description the slider points at: what its keys do. */
export function PlayheadKeys({ id }: { id: string }) {
  return (
    <span id={id} className="visually-hidden">
      {TRACK_KEYS}
    </span>
  )
}

/**
 * The visible time, in words: the clip's name (one line, cut with an ellipsis, the whole
 * name as its tooltip), then `Clip` with the time in it and its length, then `Event` with
 * the time in the whole timeline and its length. Each time is in a cell of fixed width.
 */
export function PlayheadReadout({
  playhead,
  clips,
  lay,
}: {
  playhead: PlayheadStore
  clips: readonly TrackClip[]
  lay: Layout
}) {
  const at = useSyncExternalStore(playhead.subscribe, playhead.get)
  const scales = useMemo(() => readoutScales(clips, lay), [clips, lay])
  const readout = readoutOf(at, clips, lay, scales)
  return (
    <p className="tl-readout">
      <span className="tl-readout-line">
        <span className="tl-readout-name" title={readout.name}>
          {readout.name}
        </span>
        <ClockGroup label="Clip" time={readout.clip.time} length={readout.clip.length} />
        <ClockGroup label="Event" time={readout.event.time} length={readout.event.length} />
      </span>
    </p>
  )
}
