import { memo, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'

import { formatTime, handleName, handleValueText, NOT_IN_CLIP, stoppedWords } from '../cuts/times'
import type { TrimEdge } from '../cuts/times'
import type { DraftCut } from '../edit/draft'
import { toMs } from '../preview/playback'
import type { DragStore } from './dragStore'
import type { TrimNote } from './editing'
import { keyOutcome, nearestHandle, snapWords } from './handles'
import type { SnapContext } from './handles'
import type { ClipFacts, Ms } from './model'
import { snapCandidates, timeToPx, trimEdge, trimLimits } from './model'
import type { Playhead } from './playhead'

/*
 * The trim handles (D-20, `timeline-trim`): two on each cut of a clip the Timeline draws
 * with its cuts, in the Edit-mode Timeline only. A handle is a slider (`role="slider"`),
 * not a draggable: it has a value, a range and keys, and is moved by the distance the
 * pointer moves, snapping to the clip's ends, the other cuts' edges and the playhead within
 * 8 px. While it is dragged the edge lives in the drag store and only the handle, the
 * cut's live span and the selected cut's fields show it; the draft is written once, on
 * release, by `onTrim`. A key press is its own edit.
 *
 * The handles of a clip are one layer (`ClipHandles`), windowed with the clip, drawn after
 * the playhead so that Tab reaches them after it, in time order.
 */

/** A press this close to where it began (px) is a click, not a drag. */
const SLOP_PX = 3

/** The area of a handle, in px, by pointer: its press reach. */
const FINE_PX = 24
const COARSE_PX = 44

function coarse(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches
}

/** One handle's identity within its clip. */
const handleId = (key: string, edge: TrimEdge) => `${key}:${edge}`

type Row = { cut: DraftCut; index: number }

/** A clip's cuts that are not removed, by start (a cut's handles are consecutive in Tab order). */
function rowsOf(listed: readonly DraftCut[]): Row[] {
  return listed
    .map((cut, index) => ({ cut, index }))
    .filter((row) => !row.cut.removed)
    .sort((a, b) => a.cut.in - b.cut.in || a.index - b.index)
}

type Begin = (event: PointerEvent<HTMLElement>) => void
type Registered = { el: HTMLElement; begin: Begin }

export function ClipHandles({
  identity,
  name,
  index,
  facts,
  left,
  widthPx,
  totalPx,
  pps,
  listed,
  playhead,
  drag,
  locked,
  keysId,
  selectedKey,
  onSelect,
  onTrim,
  announce,
}: {
  identity: string
  name: string
  /** The clip's place among the shown clips: the playhead's `clip`. */
  index: number
  facts: ClipFacts
  /** The clip's left edge and the whole canvas's width, in px. */
  left: number
  widthPx: number
  totalPx: number
  pps: number
  /** The clip's cuts as its Cuts panel lists them. */
  listed: readonly DraftCut[]
  playhead: Playhead
  drag: DragStore
  locked: boolean
  keysId: string
  /** The selected cut's key, when it is this clip's. */
  selectedKey: string | null
  onSelect: (identity: string, key: string) => void
  onTrim: (
    identity: string,
    key: string,
    span: { in: number; out: number },
    note: TrimNote,
  ) => void
  announce: (words: string) => void
}) {
  const registry = useRef(new Map<string, Registered>())
  const layer = useRef<HTMLDivElement>(null)
  const rows = rowsOf(listed)
  // The edge being dragged in this clip: its cut's live span and the snap line.
  const live = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.get()
    return d !== null && d.identity === identity ? d : null
  })

  /** A press on a handle goes to the nearer edge where the areas of two overlap. */
  const press = (event: PointerEvent<HTMLElement>, id: string) => {
    const box = layer.current?.getBoundingClientRect()
    const reach = coarse() ? COARSE_PX : FINE_PX
    const contenders = rows.flatMap(({ cut }) =>
      (['in', 'out'] as const).flatMap((edge) => {
        const entry = registry.current.get(handleId(cut.key, edge))
        if (entry === undefined) {
          return []
        }
        const area = entry.el.getBoundingClientRect()
        if (event.clientX < area.left || event.clientX > area.right) {
          return []
        }
        const ms = Math.min(facts.durationMs, toMs(edge === 'in' ? cut.in : cut.out))
        return [{ id: handleId(cut.key, edge), px: timeToPx(ms, pps) }]
      }),
    )
    const pressPx = event.clientX - (box?.left ?? 0)
    const winner = nearestHandle(pressPx, contenders, reach) ?? id
    registry.current.get(winner)?.begin(event)
  }

  const dragged = live === null ? undefined : rows.find((row) => row.cut.key === live.key)
  const ghost =
    live !== null && dragged !== undefined
      ? {
          from: Math.min(
            facts.durationMs,
            live.edge === 'in' ? live.ms : toMs(dragged.cut.in),
          ),
          to: Math.min(facts.durationMs, live.edge === 'out' ? live.ms : toMs(dragged.cut.out)),
        }
      : null

  return (
    <div
      ref={layer}
      className="tl-trims"
      data-index={index}
      style={
        {
          insetInlineStart: left,
          inlineSize: Math.max(1, widthPx),
          '--clip-left': `${left}px`,
          '--canvas-w': `${totalPx}px`,
        } as React.CSSProperties
      }
    >
      {ghost !== null && ghost.to > ghost.from && (
        <span
          className="tl-trim-ghost"
          aria-hidden="true"
          style={{
            insetInlineStart: timeToPx(ghost.from, pps),
            inlineSize: timeToPx(ghost.to - ghost.from, pps),
          }}
        />
      )}
      {live !== null && live.snappedTo !== null && (
        <span
          className="tl-snap-line"
          aria-hidden="true"
          style={{ insetInlineStart: timeToPx(live.snappedTo, pps) }}
        />
      )}
      {rows.flatMap(({ cut, index: at }) =>
        (['in', 'out'] as const).map((edge) => (
          <TrimHandle
            key={handleId(cut.key, edge)}
            identity={identity}
            name={name}
            clipIndex={index}
            facts={facts}
            edge={edge}
            cut={cut}
            at={at}
            listed={listed}
            left={left}
            pps={pps}
            playhead={playhead}
            drag={drag}
            locked={locked}
            keysId={keysId}
            selected={selectedKey === cut.key}
            registry={registry.current}
            onPress={press}
            onSelect={onSelect}
            onTrim={onTrim}
            announce={announce}
          />
        )),
      )}
    </div>
  )
}

const TrimHandle = memo(function TrimHandle({
  identity,
  name,
  clipIndex,
  facts,
  edge,
  cut,
  at,
  listed,
  left,
  pps,
  playhead,
  drag,
  locked,
  keysId,
  selected,
  registry,
  onPress,
  onSelect,
  onTrim,
  announce,
}: {
  identity: string
  name: string
  clipIndex: number
  facts: ClipFacts
  edge: TrimEdge
  cut: DraftCut
  /** The cut's place in the clip's list: the model's index, and `at + 1` is the panel's number. */
  at: number
  listed: readonly DraftCut[]
  left: number
  pps: number
  playhead: Playhead
  drag: DragStore
  locked: boolean
  keysId: string
  selected: boolean
  registry: Map<string, Registered>
  onPress: (event: PointerEvent<HTMLElement>, id: string) => void
  onSelect: (identity: string, key: string) => void
  onTrim: (
    identity: string,
    key: string,
    span: { in: number; out: number },
    note: TrimNote,
  ) => void
  announce: (words: string) => void
}) {
  const id = handleId(cut.key, edge)
  const number = at + 1
  const el = useRef<HTMLDivElement>(null)
  const active = useRef<{
    pointerId: number
    startX: number
    startMs: Ms
    moved: boolean
    candidates: Ms[]
    ctx: SnapContext
  } | null>(null)
  const ppsRef = useRef(pps)
  ppsRef.current = pps
  const [focused, setFocused] = useState(false)

  const ownMs = toMs(edge === 'in' ? cut.in : cut.out)
  // The edge in the air, or null: only the dragged handle re-renders while it moves.
  const dragging = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.get()
    return d !== null && d.identity === identity && d.key === cut.key && d.edge === edge ? d : null
  })
  const nowMs = dragging === null ? ownMs : dragging.ms
  const [lowest, highest] = trimLimits(listed, at, edge, facts)
  const seconds = (ms: Ms) => ms / 1000
  const shownMs = Math.min(nowMs, facts.durationMs)
  const x = timeToPx(shownMs, pps)

  const span = (ms: Ms) => ({
    in: edge === 'in' ? seconds(ms) : cut.in,
    out: edge === 'out' ? seconds(ms) : cut.out,
  })

  const playheadMs = (): Ms | null => {
    const p = playhead.get()
    return p.clip === clipIndex ? p.ms : null
  }

  /** A key's or Enter's result: one edit of the draft, if the edge moved. */
  const apply = (ms: Ms, spoken: boolean) => {
    if (ms === ownMs) {
      return
    }
    onTrim(identity, cut.key, span(ms), { name, spoken })
  }

  const cancel = () => {
    const a = active.current
    active.current = null
    drag.set(null)
    if (a !== null && el.current?.hasPointerCapture(a.pointerId)) {
      el.current.releasePointerCapture(a.pointerId)
    }
  }

  // A save that starts ends a drag in progress, as if Escape were pressed.
  useEffect(() => {
    if (locked) {
      cancel()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked])
  // Gone from the window mid-drag (it was scrolled away): its own edge in the air goes with it, no one else's.
  useEffect(
    () => () => {
      const d = drag.get()
      if (d !== null && d.identity === identity && d.key === cut.key && d.edge === edge) {
        drag.set(null)
      }
    },
    [drag, identity, cut.key, edge],
  )

  const begin: Begin = (event) => {
    const target = el.current
    if (target === null) {
      return
    }
    const p = playheadMs()
    const others = listed.flatMap((other, i) =>
      i !== at && !other.removed
        ? [{ n: i + 1, inMs: toMs(other.in), outMs: toMs(other.out) }]
        : [],
    )
    target.setPointerCapture(event.pointerId)
    target.focus({ preventScroll: true })
    // The handle that takes the press is the one selected, whichever area it landed in.
    onSelect(identity, cut.key)
    active.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startMs: ownMs,
      moved: false,
      candidates: snapCandidates(listed, at, facts, p, []),
      ctx: { playheadMs: p, durationMs: facts.durationMs, others },
    }
  }
  useEffect(() => {
    registry.set(id, { el: el.current as HTMLElement, begin })
    return () => {
      registry.delete(id)
    }
  })

  const move = (event: PointerEvent<HTMLElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const dx = event.clientX - a.startX
    if (!a.moved && Math.abs(dx) < SLOP_PX) {
      return
    }
    a.moved = true
    const wanted = a.startMs + Math.round((dx * 1000) / ppsRef.current)
    const placed = trimEdge(listed, at, edge, wanted, facts, ppsRef.current, a.candidates)
    drag.set({
      identity,
      key: cut.key,
      edge,
      ms: placed.ms,
      snappedTo: placed.snappedTo,
      words: placed.snappedTo === null ? '' : snapWords(placed.snappedTo, a.ctx),
    })
  }

  const release = (event: PointerEvent<HTMLElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const last = drag.get()
    cancel()
    if (a.moved && last !== null && last.ms !== a.startMs) {
      onTrim(identity, cut.key, span(last.ms), { name, spoken: true, snap: last.words || null })
    }
  }

  const keyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape' && active.current !== null) {
      event.preventDefault()
      event.stopPropagation()
      cancel()
      return
    }
    if (event.ctrlKey || event.altKey || event.metaKey) {
      return
    }
    const outcome = keyOutcome(
      event.key,
      event.shiftKey,
      ownMs,
      [lowest, highest],
      facts.fps,
      facts.durationMs,
      playheadMs(),
    )
    if (outcome.kind === 'ignore') {
      return
    }
    event.preventDefault()
    if (locked) {
      return
    }
    if (outcome.kind === 'refused') {
      announce(NOT_IN_CLIP(name))
    } else if (outcome.kind === 'set') {
      apply(outcome.ms, false)
      if (outcome.stopped) {
        announce(stoppedWords(handleName(edge, number, name), seconds(outcome.ms)))
      }
    }
  }

  const cutNow = span(nowMs)
  // Brought into the view when focus arrives from the keyboard and the edge is out of it.
  const keepInView = () => {
    const viewport = el.current?.closest<HTMLElement>('.tl-viewport')
    if (viewport === null || viewport === undefined) {
      return
    }
    const edgeX = left + x
    if (edgeX < viewport.scrollLeft || edgeX > viewport.scrollLeft + viewport.clientWidth) {
      viewport.scrollLeft = Math.max(0, edgeX - viewport.clientWidth / 2)
    }
  }

  return (
    <div
      ref={el}
      className="tl-trim"
      role="slider"
      tabIndex={0}
      aria-label={handleName(edge, number, name)}
      aria-orientation="horizontal"
      aria-valuemin={seconds(lowest)}
      aria-valuemax={seconds(highest)}
      aria-valuenow={seconds(nowMs)}
      aria-valuetext={handleValueText(seconds(nowMs), cutNow, seconds(facts.durationMs))}
      aria-describedby={keysId}
      aria-disabled={locked || undefined}
      data-edge={edge}
      data-selected={selected || undefined}
      data-dragging={dragging !== null || undefined}
      data-snapped={(dragging !== null && dragging.snappedTo !== null) || undefined}
      style={{ '--x': `${x}px` } as React.CSSProperties}
      onPointerDown={(event) => {
        if (event.button !== 0 && event.pointerType === 'mouse') {
          return
        }
        // A press on a handle is the handle's: no text selection, no native drag.
        event.preventDefault()
        if (locked) {
          return
        }
        onPress(event, id)
      }}
      onPointerMove={move}
      onPointerUp={release}
      onPointerCancel={cancel}
      onLostPointerCapture={() => {
        if (active.current !== null) {
          cancel()
        }
      }}
      onKeyDown={keyDown}
      onFocus={(event) => {
        // The time beside the edge for a keyboard user; a press has the drag's own.
        setFocused(event.currentTarget.matches(':focus-visible'))
        onSelect(identity, cut.key)
        keepInView()
      }}
      onBlur={() => setFocused(false)}
    >
      <span className="tl-trim-bar" aria-hidden="true" />
      {(dragging !== null || focused) && (
        <span className="tl-trim-tip" aria-hidden="true">
          {formatTime(seconds(shownMs))}
          {dragging !== null && dragging.words !== '' && (
            <span className="tl-trim-snap"> · {dragging.words}</span>
          )}
        </span>
      )}
    </div>
  )
})
