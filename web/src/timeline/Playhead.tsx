import { useSyncExternalStore } from 'react'
import type { HTMLAttributes, KeyboardEvent, Ref } from 'react'

import { formatTime } from '../cuts/times'
import { playheadKey } from './keys'
import type { KeyAction } from './keys'
import { PLAYHEAD, TRACK_KEYS, playheadValueText } from './labels'
import type { TrackClip } from './layout'
import type { Layout } from './model'
import { timeToPx } from './model'
import { clampPosition, globalMs } from './position'
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

/** The visible time: the clip, the time in it, and the place in the whole timeline. */
export function PlayheadReadout({
  playhead,
  clips,
  lay,
}: {
  playhead: PlayheadStore
  clips: readonly TrackClip[]
  lay: Layout
}) {
  const at = clampPosition(clips, useSyncExternalStore(playhead.subscribe, playhead.get))
  const clip = clips[at.clip]
  return (
    <p className="tl-readout">
      <span className="tl-readout-name">{clip.name}</span>
      <span className="tl-readout-time">
        {formatTime(at.ms / 1000)} / {formatTime(clip.facts.durationMs / 1000)}
      </span>
      <span className="tl-readout-time tl-readout-all">
        {formatTime(globalMs(lay, at) / 1000)} / {formatTime(lay.totalMs / 1000)} in all
      </span>
    </p>
  )
}
