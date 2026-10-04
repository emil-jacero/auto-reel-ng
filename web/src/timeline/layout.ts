import type { Clip, EventDetail } from '../api/event.ts'
import { reasonWords, spanWords } from '../cuts/times.ts'
import type { Trim } from '../cuts/times.ts'
import { chapterHeading } from '../events/labels.ts'
import { clipNames, plural } from '../events/names.ts'
import { copyHasSound, copyLengthMs } from '../preview/source.ts'
import type { Skip } from '../preview/playback.ts'
import {
  clipFacts,
  cutSpans,
  extentMs,
  interiorSpans,
  keptExtent,
  layout,
  movieLengthMs,
  timeToPx,
  wholeExtent,
} from './model.ts'
import type { ClipFacts, Extent, Layout, Ms } from './model.ts'

/*
 * What the event page's Timeline shows, as pure rules (D-20): which clips, whether each
 * has a proxy it can be laid out from, how they are grouped in chapters, where their
 * cuts and filmstrip tiles are. No DOM, no React, type-only imports where they would
 * reach either, so `npm test` runs it.
 *
 * A clip's length and frame rate come from its proxy's facts alone. The events read is
 * probe-free (§4.9) and has neither, so a clip whose facts are missing or unusable is
 * not ready: nothing here guesses a length (Principle I).
 */

// --- which clips, and are their proxies ready -----------------------------------------

/** The filmstrip sprite's geometry, from the facts (tile `k` is at column `k % columns`, row `k / columns`). */
export type FilmGeometry = {
  tileWidth: number
  tileHeight: number
  columns: number
  tiles: number
  interval: number
}

/** What a ready proxy gives the timeline. */
export type ReadyProxy = {
  facts: ClipFacts
  vfr: boolean | null
  film: FilmGeometry
  /** The proxy file's entity tag, the `v` of its addresses. */
  version: string
  hasSound: boolean
}

/**
 * Where a clip's proxy stands: the service's four states, `unknown` (the detail gives
 * none: the proxy cache or its configuration could not be read) and `unusable` (the state
 * is `ready` but the facts, or the tag the addresses need, are missing or unusable).
 */
export type ProxyHealth = 'ready' | 'absent' | 'stale' | 'failed' | 'unusable' | 'unknown'

const positive = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0

/** The proxy as the timeline can use it, or why not. Never defaulted. */
export function readProxy(
  proxy: Clip['proxy'],
): { health: 'ready'; ready: ReadyProxy } | { health: Exclude<ProxyHealth, 'ready'>; ready: null } {
  if (proxy == null) {
    return { health: 'unknown', ready: null }
  }
  switch (proxy.state) {
    case 'ready':
      break
    case 'absent':
    case 'stale':
    case 'failed':
      return { health: proxy.state, ready: null }
    default:
      return { health: 'unknown', ready: null }
  }
  const { facts, version } = proxy
  const seconds = copyLengthMs(facts)
  if (
    facts == null ||
    seconds === null ||
    !positive(facts.fps_num) ||
    !positive(facts.fps_den) ||
    typeof version !== 'string' ||
    version === ''
  ) {
    return { health: 'unusable', ready: null }
  }
  const { filmstrip: film } = facts
  if (
    film == null ||
    !positive(film.tile_width) ||
    !positive(film.tile_height) ||
    !positive(film.columns) ||
    !positive(film.tiles) ||
    !positive(film.interval)
  ) {
    return { health: 'unusable', ready: null }
  }
  return {
    health: 'ready',
    ready: {
      facts: clipFacts(facts.duration, facts.fps_num / facts.fps_den),
      vfr: facts.vfr,
      film: {
        tileWidth: film.tile_width,
        tileHeight: film.tile_height,
        columns: film.columns,
        tiles: film.tiles,
        interval: film.interval,
      },
      version,
      hasSound: copyHasSound(facts),
    },
  }
}

/** A clip the timeline shows, in play order. */
export type ShownClip = {
  identity: string
  /** As the page names it (`clipNames`). */
  name: string
  /** Index into the event's chapters. */
  chapter: number
  health: ProxyHealth
  ready: ReadyProxy | null
}

export type Omitted = { missing: number; excluded: number }

/**
 * The clips the event page plays, chapter by chapter and clip by clip, as the page
 * lists them: not the ones the event ignores (they have no place in the play order),
 * and not a clip that is missing from disk or that `reel.yaml` excludes, which are
 * counted apart (an excluded clip counts as excluded, also when its file is gone).
 */
export function shownClips(event: Pick<EventDetail, 'chapters'>): {
  clips: ShownClip[]
  omitted: Omitted
} {
  const clips: ShownClip[] = []
  const omitted: Omitted = { missing: 0, excluded: 0 }
  event.chapters.forEach((chapter, index) => {
    const nameOf = clipNames(
      chapter.name,
      chapter.clips.map((clip) => clip.identity),
    )
    for (const clip of chapter.clips) {
      if (clip.status === 'ignored') {
        continue
      }
      if (clip.excluded) {
        omitted.excluded += 1
      } else if (clip.status === 'missing') {
        omitted.missing += 1
      } else {
        clips.push({
          identity: clip.identity,
          name: nameOf(clip.identity),
          chapter: index,
          ...readProxy(clip.proxy),
        })
      }
    }
  })
  return { clips, omitted }
}

export type Readiness = Record<ProxyHealth, number> & {
  /** The clips shown. */
  total: number
  /** The track opens: at least one clip, and every one ready. */
  open: boolean
}

export function readiness(clips: readonly Pick<ShownClip, 'health'>[]): Readiness {
  const counts: Readiness = {
    total: clips.length,
    open: false,
    ready: 0,
    absent: 0,
    stale: 0,
    failed: 0,
    unusable: 0,
    unknown: 0,
  }
  for (const clip of clips) {
    counts[clip.health] += 1
  }
  counts.open = clips.length > 0 && counts.ready === clips.length
  return counts
}

/** What the section shows: closed wins; no clip to show is `none`; else Prepare until all are ready. */
export type SectionState = 'closed' | 'none' | 'prepare' | 'track'

/**
 * Whether the section is open. The read view opens it with its button (`toggled`) and starts
 * closed, costing nothing; Edit mode (`editing`) is where the cuts are trimmed, so it is open
 * from the start, has no button, and a Refresh keeps it open (`edit-mode-declutter`).
 */
export function sectionOpen(editing: boolean, toggled: boolean): boolean {
  return editing || toggled
}

export function sectionState(open: boolean, clips: readonly Pick<ShownClip, 'health'>[]): SectionState {
  if (!open) {
    return 'closed'
  }
  if (clips.length === 0) {
    return 'none'
  }
  return readiness(clips).open ? 'track' : 'prepare'
}

// --- the track's clips ------------------------------------------------------------------

/** A cut as the track draws it: the render's joined span, with the reasons of the cuts it joins. */
export type DrawnCut = { from: Ms; to: Ms; reasons: string[] }

export type TrackClip = {
  identity: string
  name: string
  /** Index into the event's chapters. */
  chapter: number
  facts: ClipFacts
  vfr: boolean | null
  film: FilmGeometry
  version: string
  /** How many cuts `reel.yaml` lists for the clip. */
  cutCount: number
  /**
   * The clip's kept extent (`timeline-ripple-layout`): its block spans only this, a leading
   * and a trailing cut are not drawn, and the clips after it close up.
   */
  kept: Extent
  /**
   * The interior spans the render leaves out, joined, clamped to the clip, in the clip's own
   * time (the block's left edge is `kept.inMs`); the leading and trailing cuts are not among them.
   */
  drawn: DrawnCut[]
  /** Every cut span (leading and trailing too) as skip spans, for playing. */
  spans: Skip[]
}

/** Whether `a` overlaps `b` by more than an instant, or `a` lies inside it, in ms. */
function within(cut: Trim, span: Skip): boolean {
  const from = Math.round(cut.in * 1000)
  const to = Math.round(cut.out * 1000)
  return from < span.to && to > span.from
}

/** The spans of one clip's cuts, as the render joins them, each with the reasons that made it. */
export function drawnCuts(cuts: readonly Trim[], durationMs: Ms): DrawnCut[] {
  return cutSpans(cuts, durationMs).map((span) => {
    const reasons: string[] = []
    for (const cut of cuts) {
      const reason = (cut.reason ?? '').trim()
      if (reason !== '' && within(cut, span) && !reasons.includes(reason)) {
        reasons.push(reason)
      }
    }
    return { from: span.from, to: span.to, reasons }
  })
}

/**
 * The clips as the track lays them out, or null while any is not ready. `cuts` is the
 * page's read of `reel.yaml` (identity → its cuts); null when it could not be read or is
 * not read yet, then no clip has cuts.
 */
export function trackClips(
  shown: readonly ShownClip[],
  cuts: ReadonlyMap<string, readonly Trim[]> | null,
): TrackClip[] | null {
  const clips: TrackClip[] = []
  for (const clip of shown) {
    if (clip.ready === null) {
      return null
    }
    const trims = cuts?.get(clip.identity) ?? []
    const { facts, vfr, film, version } = clip.ready
    const spans = cutSpans(trims, facts.durationMs)
    const kept = keptExtent(spans, facts.durationMs)
    clips.push({
      identity: clip.identity,
      name: clip.name,
      chapter: clip.chapter,
      facts,
      vfr,
      film,
      version,
      cutCount: trims.length,
      kept,
      drawn: interiorSpans(drawnCuts(trims, facts.durationMs), kept),
      spans,
    })
  }
  return clips
}

/** The clips end to end, each as long as its kept extent. */
export function trackLayout(clips: readonly TrackClip[]): Layout {
  return layout(clips.map((clip) => ({ ...clip.facts, ...clip.kept })))
}

/** The footage: the shown clips' full proxy durations, which edge cuts do not shorten (the movie line's "of footage"). */
export function footageMs(clips: readonly { facts: { durationMs: Ms } }[]): Ms {
  return clips.reduce((sum, clip) => sum + clip.facts.durationMs, 0)
}

/** The movie's length: the footage less the cuts, each span once (the render's rule). */
export function movieMs(clips: readonly TrackClip[], cuts: ReadonlyMap<string, readonly Trim[]> | null): Ms {
  return movieLengthMs(
    clips.map((clip) => ({ ...clip.facts, cuts: cuts?.get(clip.identity) ?? [] })),
  )
}

// --- chapters ---------------------------------------------------------------------------

/** A run of clips of one chapter: indexes into the shown clips, inclusive. */
export type ChapterBand = { chapter: number; heading: string; first: number; last: number }

/**
 * One band per chapter that has a shown clip, headed as the page headings it: its name,
 * else "Main" beside a named chapter, else "Clips" (`chapterHeading`).
 */
export function chapterBands(
  chapterNames: readonly string[],
  clips: readonly { chapter: number }[],
): ChapterBand[] {
  const named = chapterNames.some((name) => name !== '')
  const bands: ChapterBand[] = []
  clips.forEach((clip, index) => {
    const last = bands.at(-1)
    if (last !== undefined && last.chapter === clip.chapter) {
      last.last = index
    } else {
      bands.push({
        chapter: clip.chapter,
        heading: chapterHeading(chapterNames[clip.chapter] ?? '', named),
        first: index,
        last: index,
      })
    }
  })
  return bands
}

// --- the filmstrip ----------------------------------------------------------------------

/** The height a filmstrip tile is drawn at, in px. */
export const FILM_TILE_HEIGHT = 54

/** How much a sprite is scaled to be drawn at `FILM_TILE_HEIGHT`. */
export function filmScale(film: FilmGeometry): number {
  return FILM_TILE_HEIGHT / film.tileHeight
}

/** A drawn tile: where in the clip (px), how wide, and where in the sprite (tile column and row). */
export type Tile = { x: number; width: number; index: number; col: number; row: number }

/**
 * The filmstrip tiles to draw for a clip's block at `pps`, within the window `[from, to)` (px
 * from the block's left edge). `kept` is the clip's kept extent (a length in ms is the whole
 * clip): the block starts at its kept start. A tile is drawn `tileWidth * scale` px wide (96 for
 * the usual 160x90) and the place at `x` shows the sprite tile of the clip's second
 * `kept.inMs / 1000 + x / pps` (the first place the kept start, the last no later than the
 * sprite's last tile); at a zoom where tiles would overlap, places are left out, not squeezed.
 * A block of under a tile's width has one. The last place is cut to the block's end.
 */
export function filmTiles(
  film: FilmGeometry,
  kept: Ms | Extent,
  pps: number,
  window: { from: number; to: number },
): Tile[] {
  const extent = typeof kept === 'number' ? wholeExtent(kept) : kept
  const placeWidth = film.tileWidth * filmScale(film)
  const clipWidth = timeToPx(extentMs(extent), pps)
  const places = Math.max(1, Math.ceil(clipWidth / placeWidth))
  const first = Math.max(0, Math.floor(window.from / placeWidth))
  const last = Math.min(places - 1, Math.ceil(window.to / placeWidth) - 1)
  const tiles: Tile[] = []
  for (let place = first; place <= last; place += 1) {
    const x = place * placeWidth
    const index = Math.min(film.tiles - 1, Math.floor((extent.inMs / 1000 + x / pps) / film.interval))
    tiles.push({
      x,
      width: Math.min(placeWidth, Math.max(1, clipWidth - x)),
      index,
      col: index % film.columns,
      row: Math.floor(index / film.columns),
    })
  }
  return tiles
}

// --- words ------------------------------------------------------------------------------

/** The note for the clips left out, one sentence per kind; empty when none were. */
export function omittedWords(omitted: Omitted): string[] {
  const words: string[] = []
  if (omitted.missing > 0) {
    const n = omitted.missing
    words.push(`${plural(n, 'clip', 'clips')} ${n === 1 ? 'is' : 'are'} missing from disk and ${n === 1 ? 'is' : 'are'} not shown`)
  }
  if (omitted.excluded > 0) {
    const n = omitted.excluded
    words.push(`${plural(n, 'clip', 'clips')} ${n === 1 ? 'is' : 'are'} excluded and ${n === 1 ? 'is' : 'are'} not shown`)
  }
  return words
}

/** `Cut 0:02 to 0:04, Black frames` for a cut span's text alternative (no reason: no comma). */
export function cutLabel(cut: DrawnCut): string {
  const span = `Cut ${spanWords({ in: cut.from / 1000, out: cut.to / 1000 })}`
  return cut.reasons.length === 0 ? span : `${span}, ${cut.reasons.map(reasonWords).join(', ')}`
}
