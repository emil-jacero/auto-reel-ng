import type { ListedCut } from '../cuts/times.ts'
import { formatLength, formatTime } from '../cuts/times.ts'
import { toEnd, toMs } from '../preview/playback.ts'
import type { Skip } from '../preview/playback.ts'
import { cutSpans, frameMs, keptExtent, minCutMs, ModelError, nearestFrame, snapTo } from './model.ts'
import type { ClipFacts, Ms } from './model.ts'

/*
 * The clip edge tools' model (`clip-edge-trim`, D-20): a clip's **start edge** and **end edge**
 * are the places the track lays its block out by (its kept extent, `timeline-ripple-layout`),
 * and an edge is moved by editing the clip's **edge cut**: the leading cut `[0, x]` or the
 * trailing cut `[x, end]` it already lists in `trims`. No new field: what a Trim In or a Trim
 * Out does is one ordinary cut edit (add, trim or remove), which the render already plays.
 *
 * The value an edge tool moves is `x`, the edge cut's inner end (its `out` at the start, its `in`
 * at the end). The edge's **place** is where the block then starts or ends: `x`, unless `x`
 * reaches another cut, which the render joins (`cutSpans`), and then the far side of the joined
 * span. Pure: no DOM, no React; whole milliseconds like `model.ts`.
 */

/** Which edge of a clip: its start (Trim In) or its end (Trim Out). */
export type Side = 'start' | 'end'

/** A listed cut and its place in the clip's list (0-based; the Cuts panel's number is `index + 1`). */
type Indexed<C> = { cut: C; index: number }

function checkDuration(durationMs: Ms): void {
  if (typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs <= 0) {
    throw new ModelError(`durationMs must be a finite number above zero, got ${String(durationMs)}`)
  }
}

function checkFacts(f: ClipFacts): void {
  checkDuration(f.durationMs)
  if (typeof f.fps !== 'number' || !Number.isFinite(f.fps) || f.fps <= 0) {
    throw new ModelError(`fps must be a finite number above zero, got ${String(f.fps)}`)
  }
}

/** A cut's span clamped to the clip, or null when nothing of it is in the clip. */
function clamped(cut: ListedCut, durationMs: Ms): Skip | null {
  const from = Math.max(0, toMs(cut.in))
  const to = Math.min(durationMs, toMs(cut.out))
  return to > from ? { from, to } : null
}

/** Whether a cut is the kind of cut a start edge is: not removed, from the clip's start. */
function leading(cut: ListedCut, durationMs: Ms): boolean {
  const span = clamped(cut, durationMs)
  return cut.removed !== true && span !== null && span.from <= 0
}

/** Whether a cut is the kind of cut an end edge is: not removed, reaching the clip's end (Play's slack). */
function trailing(cut: ListedCut, durationMs: Ms): boolean {
  const span = clamped(cut, durationMs)
  return cut.removed !== true && span !== null && toEnd(span, durationMs)
}

/**
 * The clip's edge cut on a side, with its place in the list: at the start the leading cut that
 * ends latest, at the end the trailing cut that starts earliest, the first in list order on a
 * tie; null when the clip has none.
 */
export function edgeCutOf<C extends ListedCut>(
  listed: readonly C[],
  side: Side,
  durationMs: Ms,
): Indexed<C> | null {
  checkDuration(durationMs)
  let best: Indexed<C> | null = null
  listed.forEach((cut, index) => {
    if (side === 'start') {
      if (!leading(cut, durationMs)) {
        return
      }
      if (best === null || toMs(cut.out) > toMs(best.cut.out)) {
        best = { cut, index }
      }
    } else {
      if (!trailing(cut, durationMs)) {
        return
      }
      if (best === null || toMs(cut.in) < toMs(best.cut.in)) {
        best = { cut, index }
      }
    }
  })
  return best
}

/** The edges of the clip whose live spans are `spans`: kept in-point and out-point (not collapsed). */
function edgesOf(spans: readonly Skip[], durationMs: Ms): { inMs: Ms; outMs: Ms } {
  const first = spans[0]
  const inMs = first !== undefined && first.from <= 0 ? first.to : 0
  const last = spans.find((span) => toEnd(span, durationMs))
  return { inMs, outMs: last === undefined ? durationMs : last.from }
}

/**
 * The clip's start edge and end edge: its kept extent as the track lays it out (`keptExtent`,
 * the same function), or, for a clip whose cuts leave nothing, the joined spans' own ends.
 */
export function edgePlaces(listed: readonly ListedCut[], durationMs: Ms): { start: Ms; end: Ms } {
  checkDuration(durationMs)
  const spans = cutSpans(listed, durationMs)
  const kept = keptExtent(spans, durationMs)
  if (kept.outMs > kept.inMs) {
    return { start: kept.inMs, end: kept.outMs }
  }
  const raw = edgesOf(spans, durationMs)
  return { start: raw.inMs, end: raw.outMs }
}

/** How long a clip plays: its duration less what its live cuts cover, once. */
export function playedMs(listed: readonly ListedCut[], durationMs: Ms): Ms {
  checkDuration(durationMs)
  return durationMs - cutSpans(listed, durationMs).reduce((sum, s) => sum + (s.to - s.from), 0)
}

/** The other cuts of the clip: every listed cut but the edge cut, in list order, with their numbers. */
function othersOf<C extends ListedCut>(listed: readonly C[], edge: Indexed<C> | null): Indexed<C>[] {
  return listed
    .map((cut, index) => ({ cut, index }))
    .filter((row) => row.index !== edge?.index && row.cut.removed !== true)
}

/** The edge cut a side would have with its inner end at `x` (ms), as a listed cut. */
function edgeSpan(side: Side, x: Ms, durationMs: Ms, edge: ListedCut | null): ListedCut {
  if (side === 'start') {
    return { in: 0, out: x / 1000 }
  }
  // A trailing cut keeps its out as listed (one read past the end too).
  return { in: x / 1000, out: edge === null ? durationMs / 1000 : edge.out }
}

/** The cuts with the side's edge cut set to `x`. */
function withEdge(
  others: readonly ListedCut[],
  side: Side,
  x: Ms,
  durationMs: Ms,
  edge: ListedCut | null,
): ListedCut[] {
  return [...others, edgeSpan(side, x, durationMs, edge)]
}

/** The place of a side's edge with its edge cut's inner end at `x`. */
function placeWith(others: readonly ListedCut[], side: Side, x: Ms, durationMs: Ms, edge: ListedCut | null): Ms {
  const edges = edgesOf(cutSpans(withEdge(others, side, x, durationMs, edge), durationMs), durationMs)
  return side === 'start' ? edges.inMs : edges.outMs
}

/**
 * Why an edge stops at a limit: the file's start or end, another cut, three played frames, or
 * the clip's last 100 ms, which the track and Play take as its end (`END_SLACK_MS`).
 */
export type LimitWhy = 'file' | 'cut' | 'frames' | 'slack'

/** The range of `x` a side's edge cut may take, and why each end is there. */
export type EdgeLimits = {
  lowest: Ms
  highest: Ms
  /** What stops the edge at `lowest` and at `highest`. */
  lowWhy: LimitWhy
  highWhy: LimitWhy
  /** `x` now: the edge cut's inner end, or the edge's place when it has none. */
  currentX: Ms
  /** The cut that holds the file limit, by its number (start: the leading span the others form). */
  holdingCut: number | null
}

/** The last frame time strictly before `ms`, at `fps`. */
function frameBefore(ms: Ms, fps: number): Ms {
  let n = Math.ceil((ms * fps) / 1000)
  while (frameMs(n, fps) >= ms) {
    n -= 1
  }
  return frameMs(n, fps)
}

/** The first frame time strictly after `ms`, at `fps`. */
function frameAfter(ms: Ms, fps: number): Ms {
  let n = Math.floor((ms * fps) / 1000)
  while (frameMs(n, fps) <= ms) {
    n += 1
  }
  return frameMs(n, fps)
}

/**
 * The limits of a side's edge (spec "An edge moves within limits that keep three played
 * frames"). At the start: lowest the end of the leading span the other cuts form (0, the start
 * of the file, when they form none); highest the latest frame at which the clip still plays
 * three frames. The end mirrors it. The range always holds the current `x`, so a clip already
 * playing fewer than three frames keeps its edge, and the range is never inverted.
 */
export function edgeLimits(listed: readonly ListedCut[], side: Side, f: ClipFacts): EdgeLimits {
  checkFacts(f)
  const d = f.durationMs
  const edge = edgeCutOf(listed, side, d)
  const others = othersOf(listed, edge)
  const otherCuts = others.map((row) => row.cut)
  const alone = edgesOf(cutSpans(otherCuts, d), d)
  const short = minCutMs(f.fps)
  const after = (x: Ms) => withEdge(otherCuts, side, x, d, edge?.cut ?? null)
  // Three played frames (the render's length), and a kept extent at all: the track and Play take
  // a span within END_SLACK_MS of the clip's end as its end, so a clip whose cuts leave only its
  // last 100 ms keeps nothing on the Timeline (`timeline-ripple-layout`).
  const threeFrames = (x: Ms) => playedMs(after(x), d) >= short
  const keepsSome = (x: Ms) => {
    const kept = keptExtent(cutSpans(after(x), d), d)
    return kept.outMs > kept.inMs
  }
  const places = edgePlaces(listed, d)
  const holding = (from: Ms, to: Ms): number | null => {
    const row = others.find((r) => {
      const span = clamped(r.cut, d)
      return span !== null && span.from <= from && span.to >= to
    })
    return row === undefined ? null : row.index + 1
  }
  if (side === 'start') {
    const currentX = edge === null ? places.start : Math.min(d, toMs(edge.cut.out))
    const lowest = alone.inMs
    // The latest frame from `lowest` that still passes: both tests fail from some x on.
    const latest = (ok: (x: Ms) => boolean): Ms => {
      let lo = Math.ceil((lowest * f.fps) / 1000)
      let hi = Math.floor((d * f.fps) / 1000)
      let found: Ms = lowest
      while (lo <= hi) {
        const mid = (lo + hi) >> 1
        const x = frameMs(mid, f.fps)
        if (x < lowest) {
          lo = mid + 1
        } else if (x <= d && ok(x)) {
          found = x
          lo = mid + 1
        } else {
          hi = mid - 1
        }
      }
      return found
    }
    const byFrames = latest(threeFrames)
    const bySlack = latest(keepsSome)
    const highest = Math.min(byFrames, bySlack)
    return {
      lowest: Math.min(lowest, currentX),
      highest: Math.max(highest, currentX),
      lowWhy: lowest === 0 ? 'file' : 'cut',
      highWhy: bySlack < byFrames ? 'slack' : 'frames',
      currentX,
      holdingCut: lowest === 0 ? null : holding(0, lowest),
    }
  }
  const currentX = edge === null ? places.end : Math.max(0, toMs(edge.cut.in))
  const highest = alone.outMs
  // The earliest frame up to `highest` that passes: both tests pass from some x on.
  const earliest = (ok: (x: Ms) => boolean): Ms => {
    let lo = 0
    let hi = Math.floor((highest * f.fps) / 1000)
    let found: Ms = highest
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      const x = frameMs(mid, f.fps)
      if (x <= highest && ok(x)) {
        found = x
        hi = mid - 1
      } else {
        lo = mid + 1
      }
    }
    return found
  }
  const byFrames = earliest(threeFrames)
  const bySlack = earliest(keepsSome)
  const lowest = Math.max(byFrames, bySlack)
  return {
    lowest: Math.min(lowest, currentX),
    highest: Math.max(highest, currentX),
    lowWhy: bySlack > byFrames ? 'slack' : 'frames',
    highWhy: highest === d ? 'file' : 'cut',
    currentX,
    holdingCut: highest === d ? null : holding(highest, d),
  }
}

/** Where a moved edge lands, and what that does to the clip. */
export type EdgeAt = {
  /** The edge cut's inner end. */
  x: Ms
  /** The edge's place: where the block starts (start) or ends (end). */
  place: Ms
  /** The place snapped to, or null. */
  snappedTo: Ms | null
  /** What it snapped to: `playhead`, a cut's edge by number, or a whole second; null when not. */
  snap: { kind: 'playhead' } | { kind: 'cut'; n: number; edge: 'start' | 'end' } | { kind: 'second'; ms: Ms } | null
  /** The other cuts the edge has joined, by number. */
  joined: number[]
  /** The change in how long the clip plays, against the press (negative: footage removed). */
  changeMs: Ms
  /** How long the clip plays with the edge here. */
  playsMs: Ms
  /** The kept extent with the edge here, for the live block. */
  extent: { inMs: Ms; outMs: Ms }
  /** Which limit holds the edge, or null. */
  limit: LimitWhy | null
  /** The clip's cuts with the edge here (the edge cut keeps its reason; a new one is `manual`). */
  cuts: readonly (ListedCut & { reason?: string | null })[]
}

/** What an edge can snap to besides the cuts: the playhead's time in this clip, or null. */
export type EdgeContext = { playheadMs: Ms | null; snapping: boolean }

/**
 * Where an edge moved to `wantedMs` (in the clip's time) lands (spec "An edge dragged to a
 * place snaps, joins, and makes one edit"): on the nearest candidate within 8 px at `pps` (the
 * playhead in the clip, the other cuts' edges, whole seconds) when snapping, else the nearest
 * frame; then held to the limits (a limit returned exactly). The place is the far side of any
 * cut the edge cut then reaches; the cuts joined, the change in played length against `listed`
 * as given, and the new played length come with it.
 */
export function edgeAt(
  listed: readonly ListedCut[],
  side: Side,
  wantedMs: Ms,
  f: ClipFacts,
  pps: number,
  ctx: EdgeContext,
  limits: EdgeLimits = edgeLimits(listed, side, f),
): EdgeAt {
  checkFacts(f)
  if (!Number.isFinite(wantedMs)) {
    throw new ModelError(`wantedMs must be a finite number, got ${String(wantedMs)}`)
  }
  if (!Number.isFinite(pps) || pps <= 0) {
    throw new ModelError(`pps must be a finite number above zero, got ${String(pps)}`)
  }
  const d = f.durationMs
  const edge = edgeCutOf(listed, side, d)
  const others = othersOf(listed, edge)
  const otherCuts = others.map((row) => row.cut)
  // The candidates: the playhead, the other cuts' edges and the whole seconds near the pointer.
  type Candidate = { ms: Ms; snap: NonNullable<EdgeAt['snap']> }
  const candidates: Candidate[] = []
  if (ctx.playheadMs !== null && ctx.playheadMs >= 0 && ctx.playheadMs <= d) {
    candidates.push({ ms: ctx.playheadMs, snap: { kind: 'playhead' } })
  }
  for (const row of others) {
    const span = clamped(row.cut, d)
    if (span !== null) {
      candidates.push({ ms: span.from, snap: { kind: 'cut', n: row.index + 1, edge: 'start' } })
      candidates.push({ ms: span.to, snap: { kind: 'cut', n: row.index + 1, edge: 'end' } })
    }
  }
  const reachMs = (8 * 1000) / pps
  for (let s = Math.max(0, Math.floor((wantedMs - reachMs) / 1000)); s * 1000 <= Math.min(d, wantedMs + reachMs); s += 1) {
    candidates.push({ ms: s * 1000, snap: { kind: 'second', ms: s * 1000 } })
  }
  const snapped = ctx.snapping
    ? snapTo(
        wantedMs,
        candidates.map((c) => c.ms),
        pps,
      )
    : { ms: wantedMs, target: null }
  // A limit asked for exactly (Home, End, a key at a limit) is taken as it is, never moved to the grid.
  const exact = wantedMs === limits.lowest || wantedMs === limits.highest
  const placed = exact ? wantedMs : snapped.target === null ? nearestFrame(wantedMs, f.fps) : snapped.ms
  const x = Math.min(limits.highest, Math.max(limits.lowest, placed))
  const hit = snapped.target !== null && x === snapped.target ? candidates.find((c) => c.ms === x) : undefined
  const place = placeWith(otherCuts, side, x, d, edge?.cut ?? null)
  const after = withEdge(otherCuts, side, x, d, edge?.cut ?? null)
  const spans = cutSpans(after, d)
  const kept = edgesOf(spans, d)
  // Joined: another cut now inside the edge's removed span that the other cuts alone did not hold there.
  const alone = edgesOf(cutSpans(otherCuts, d), d)
  const within = (span: Skip, from: Ms, to: Ms) => to > from && span.from >= from && span.to <= to
  const joined = others.flatMap((row) => {
    const span = clamped(row.cut, d)
    if (span === null) {
      return []
    }
    const inside = side === 'start' ? within(span, 0, place) : within(span, place, d)
    const already = side === 'start' ? within(span, 0, alone.inMs) : within(span, alone.outMs, d)
    return inside && !already ? [row.index + 1] : []
  })
  const plays = playedMs(after, d)
  const limit = x === limits.lowest ? limits.lowWhy : x === limits.highest ? limits.highWhy : null
  return {
    x,
    place,
    snappedTo: hit === undefined ? null : x,
    snap: hit === undefined ? null : hit.snap,
    joined,
    changeMs: plays - playedMs(listed, d),
    playsMs: plays,
    extent: kept,
    limit,
    cuts: [
      ...otherCuts,
      { ...edgeSpan(side, x, d, edge?.cut ?? null), reason: reasonOf(edge?.cut) ?? 'manual' },
    ],
  }
}

function reasonOf(cut: ListedCut | undefined): string | null | undefined {
  return cut === undefined ? undefined : (cut as { reason?: string | null }).reason
}

/** The one edit a release makes (spec: add, trim, remove, or nothing). */
export type EdgeEdit<K extends string = string> =
  | { kind: 'none' }
  | { kind: 'add'; span: { in: number; out: number }; reason: 'manual' }
  | { kind: 'trim'; key: K; span: { in: number; out: number } }
  | { kind: 'remove'; key: K }

/**
 * The edit a release at `x` makes, relative to the cuts `listed` when the drag began: back to
 * the file's start (end) with an edge cut removes it; the edge's place unchanged is no edit;
 * no edge cut adds one (`manual`); else the edge cut is trimmed, keeping its key, place in the
 * list and reason (a trailing cut keeps its out as listed).
 */
export function edgeEdit<C extends ListedCut & { key: string }>(
  listed: readonly C[],
  side: Side,
  x: Ms,
  f: ClipFacts,
): EdgeEdit {
  checkFacts(f)
  const d = f.durationMs
  const edge = edgeCutOf(listed, side, d)
  const otherCuts = othersOf(listed, edge).map((row) => row.cut)
  const before = edgePlaces(listed, d)[side]
  const place = placeWith(otherCuts, side, x, d, edge?.cut ?? null)
  const fileLimit = side === 'start' ? 0 : d
  if (edge !== null && place === fileLimit) {
    return { kind: 'remove', key: edge.cut.key }
  }
  if (place === before) {
    return { kind: 'none' }
  }
  const span = edgeSpan(side, x, d, edge?.cut ?? null)
  if (edge === null) {
    return { kind: 'add', span: { in: span.in, out: span.out }, reason: 'manual' }
  }
  return {
    kind: 'trim',
    key: edge.cut.key,
    span: side === 'start' ? { in: edge.cut.in, out: span.out } : { in: span.in, out: edge.cut.out },
  }
}

// --- keys ------------------------------------------------------------------------------

/**
 * Where a key puts a focused edge's `x`, from its place now (spec "Each edge is a slider"):
 * Left and Right one frame, Shift one second (the nearest frame), Home and End the limits; null
 * for a key that is not an edge's. A step that lands inside another cut would not move the
 * place (the render joins it): a step outward skips past that cut, so every key that can move
 * the edge does.
 */
export function edgeKey(
  key: string,
  shift: boolean,
  listed: readonly ListedCut[],
  side: Side,
  f: ClipFacts,
  limits: EdgeLimits = edgeLimits(listed, side, f),
): Ms | null {
  checkFacts(f)
  const d = f.durationMs
  const place = edgePlaces(listed, d)[side]
  const hold = (ms: Ms) => Math.min(limits.highest, Math.max(limits.lowest, ms))
  let wanted: Ms
  switch (key) {
    case 'ArrowLeft':
      wanted = shift ? nearestFrame(place - 1000, f.fps) : frameBefore(place, f.fps)
      break
    case 'ArrowRight':
      wanted = shift ? nearestFrame(place + 1000, f.fps) : frameAfter(place, f.fps)
      break
    case 'Home':
      return limits.lowest
    case 'End':
      return limits.highest
    default:
      return null
  }
  let x = hold(wanted)
  // Outward (restoring footage): past a cut the step landed in, to the frame beyond it.
  const outward = side === 'start' ? x < place : x > place
  if (outward) {
    const edge = edgeCutOf(listed, side, d)
    const otherCuts = othersOf(listed, edge).map((row) => row.cut)
    const spans = cutSpans(otherCuts, d)
    for (;;) {
      const inside = spans.find((s) => s.from <= x && x <= s.to)
      if (inside === undefined) {
        break
      }
      const next = hold(side === 'start' ? frameBefore(inside.from, f.fps) : frameAfter(inside.to, f.fps))
      if (next === x) {
        break
      }
      x = next
    }
  }
  return x
}

/** What `Q` or `W` does: trim the clip's start (`Q`) or end (`W`) to the playhead. */
export type ToPlayhead = { kind: 'refused'; why: 'not-in-clip' } | { kind: 'same' } | { kind: 'edit'; at: EdgeAt }

/**
 * `Q` (start) and `W` (end): the edge of the clip the playhead is in, moved to the playhead's
 * frame (`playheadMs`, null when the playhead is in a title card), with the limits and joining
 * of a drag and no snapping. A place the edge already holds is `same`.
 */
export function trimToPlayhead(
  listed: readonly ListedCut[],
  side: Side,
  playheadMs: Ms | null,
  f: ClipFacts,
): ToPlayhead {
  checkFacts(f)
  if (playheadMs === null || playheadMs < 0 || playheadMs > f.durationMs) {
    return { kind: 'refused', why: 'not-in-clip' }
  }
  const at = edgeAt(listed, side, playheadMs, f, 1, { playheadMs: null, snapping: false })
  return at.place === edgePlaces(listed, f.durationMs)[side] ? { kind: 'same' } : { kind: 'edit', at }
}

// --- words -----------------------------------------------------------------------------

const MINUS = '−'

/** A signed change as the tip shows it: `−0:00.5`, `+0:01.2`, `±0:00` for none. */
export function signedChange(changeMs: Ms): string {
  const sign = changeMs < 0 ? MINUS : changeMs > 0 ? '+' : '±'
  return `${sign}${formatTime(Math.abs(changeMs) / 1000)}`
}

/** The tip: the signed change and the clip's new playing length (`−0:00.5 · 0:03.02`). */
export function edgeTip(at: Pick<EdgeAt, 'changeMs' | 'playsMs'>): string {
  return `${signedChange(at.changeMs)} · ${formatTime(at.playsMs / 1000)}`
}

/** The words under the tip: why it stopped, what it joined, what it snapped to; empty for none. */
export function edgeNotes(side: Side, at: Pick<EdgeAt, 'limit' | 'joined' | 'snap'>, holdingCut: number | null): string[] {
  const notes: string[] = []
  if (at.limit === 'file') {
    notes.push(side === 'start' ? 'Start of the file' : 'End of the file')
  } else if (at.limit === 'frames') {
    notes.push('The clip keeps three frames')
  } else if (at.limit === 'slack') {
    notes.push('The clip keeps 0.1 s')
  } else if (at.limit === 'cut') {
    notes.push(holdingCut === null ? 'Held by another cut' : `Held by cut ${holdingCut}`)
  }
  if (at.joined.length > 0) {
    notes.push(`Joined with ${cutList(at.joined)}`)
  }
  if (at.snap !== null) {
    notes.push(snapNote(at.snap))
  }
  return notes
}

function snapNote(snap: NonNullable<EdgeAt['snap']>): string {
  switch (snap.kind) {
    case 'playhead':
      return 'Snapped to the playhead'
    case 'cut':
      return `Snapped to cut ${snap.n} ${snap.edge}`
    case 'second':
      return `Snapped to ${formatTime(snap.ms / 1000)}`
  }
}

/** `cut 1`, `cuts 1 and 2`, `cuts 1, 2 and 3`. */
function cutList(numbers: readonly number[]): string {
  if (numbers.length === 1) {
    return `cut ${numbers[0]}`
  }
  return `cuts ${numbers.slice(0, -1).join(', ')} and ${numbers[numbers.length - 1]}`
}

/** The edge tool's name: `Trim start of s1710001.mp4`. */
export function edgeName(side: Side, name: string): string {
  return `Trim ${side} of ${name}`
}

/** How much a side trims at `place`: from 0 at the start, up to the duration at the end. */
function trimmedMs(side: Side, place: Ms, durationMs: Ms): Ms {
  return side === 'start' ? place : durationMs - place
}

const capital = (side: Side) => (side === 'start' ? 'Start' : 'End')

/** The slider's value text: `Start trimmed by 0.5 s, plays 0:03.02`; `Start not trimmed, plays 0:03.52`. */
export function edgeValueText(side: Side, place: Ms, durationMs: Ms, playsMs: Ms): string {
  const trimmed = trimmedMs(side, place, durationMs)
  const head = trimmed <= 0 ? `${capital(side)} not trimmed` : `${capital(side)} trimmed by ${formatLength(trimmed / 1000)}`
  return `${head}, plays ${formatTime(playsMs / 1000)}`
}

/**
 * What the live region says once a release or `Q`/`W` changed an edge: `s1710001.mp4 start
 * trimmed by 0.5 s, plays 0:03.02.`, or `… start restored to the start of the file.`; a join and
 * a limit are said after it.
 */
export function edgeAnnouncement(
  name: string,
  side: Side,
  at: Pick<EdgeAt, 'place' | 'playsMs' | 'joined' | 'limit'>,
  durationMs: Ms,
): string {
  const trimmed = trimmedMs(side, at.place, durationMs)
  const head =
    trimmed <= 0
      ? `${name} ${side} restored to the ${side} of the file.`
      : `${name} ${side} trimmed by ${formatLength(trimmed / 1000)}, plays ${formatTime(at.playsMs / 1000)}.`
  const tail: string[] = []
  if (at.joined.length > 0) {
    tail.push(`The ${side} joined ${cutList(at.joined)}.`)
  }
  if (at.limit === 'frames') {
    tail.push('The clip keeps three frames.')
  } else if (at.limit === 'slack') {
    tail.push('The clip keeps 0.1 s.')
  }
  return [head, ...tail].join(' ')
}

/**
 * What a key's edit says (the slider's value says the rest): a join and a limit only, or null:
 * `The start joined cuts 1 and 2. The clip keeps three frames.`, `Start of the file.`
 */
export function edgeKeyWords(side: Side, at: Pick<EdgeAt, 'joined' | 'limit'>, holdingCut: number | null): string | null {
  const words: string[] = []
  if (at.joined.length > 0) {
    words.push(`The ${side} joined ${cutList(at.joined)}.`)
  }
  if (at.limit === 'file') {
    words.push(side === 'start' ? 'Start of the file.' : 'End of the file.')
  } else if (at.limit === 'frames') {
    words.push('The clip keeps three frames.')
  } else if (at.limit === 'slack') {
    words.push('The clip keeps 0.1 s.')
  } else if (at.limit === 'cut') {
    words.push(holdingCut === null ? 'Held by another cut.' : `Held by cut ${holdingCut}.`)
  }
  return words.length === 0 ? null : words.join(' ')
}

/** Said for `Q`/`W` when nothing changes. */
export function toPlayheadRefusal(result: Exclude<ToPlayhead, { kind: 'edit' }>, side: Side, name: string | null): string {
  if (result.kind === 'refused' || name === null) {
    return `Nothing trimmed: the playhead is not in a clip.`
  }
  return `Nothing trimmed: the ${side} of ${name} is already at the playhead.`
}

/** The snapping switch's words. */
export function snappingWords(on: boolean): string {
  return on ? 'Edge snapping is on.' : 'Edge snapping is off.'
}

/** The edge tools' key hints (`aria-describedby`). */
export const EDGE_KEYS =
  'Left and Right move the edge one frame, Shift one second, Home and End to its limits. Q trims the start of the clip under the playhead to it, W its end; S switches snapping.'
