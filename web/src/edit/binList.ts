import type { Clip, EventDetail } from '../api/event.ts'
import { formatTime, keptCuts } from '../cuts/times.ts'
import { chapterHeading } from '../events/labels.ts'
import { namesIn, plural } from '../events/names.ts'
import { playedMs } from '../timeline/edgeTrim.ts'
import {
  cutsOf,
  ignoredLists,
  keptOriginal,
  listedChapters,
  movedSet,
  originOf,
} from './draft.ts'
import type { Baseline, ChapterKey, Draft } from './draft.ts'

/*
 * The clip bin's rows (`plain-clip-bin` D1), as pure functions of the draft and the page's read:
 * one list of every clip of the event, in play order, then the ignored clips, then the missing
 * clips removed until Save. A row says where its clip is and what happened to it; it holds no
 * control. No DOM, no React, so `npm test` runs it as it is.
 */

/** A row's status, in the short words the bin's icons carry (the full words are `CLIP_STATUS_LABEL`). */
export type ClipStatusWords = 'New' | 'Missing' | 'Excluded' | 'Included' | 'Ignored'

/** Which part of the list a row is in. */
export type BinGroup = 'listed' | 'ignored' | 'removed'

/** One row of the bin. */
export type BinRow = {
  identity: string
  /** As the page names the clip: its file name, or its path when its chapter holds clips of other folders. */
  name: string
  group: BinGroup
  /** "Kvällen · 2 of 3"; null for an ignored or a removed clip, which no chapter plays. */
  place: string | null
  /**
   * "was 4" (moved within its chapter), "moved" (moved, and back at its old position, others
   * having moved around it), "from Main" (moved in from another chapter), or null: the clip is
   * where it was. The fewest-moves rule the top bar counts by, so the rows and the bar agree.
   */
  moved: string | null
  status: ClipStatusWords
  /**
   * What the clip plays, in ms: its duration less its live cuts, once; the whole duration for an
   * ignored, excluded or removed clip, whose cuts do not apply. Null when the read gives no
   * duration. Only the read's: a ready proxy's facts exist for the shown clip alone (nothing is
   * requested for the others), so the information, which falls back to them, can show a length
   * for the shown clip where its row shows none.
   */
  keptMs: number | null
  /** A cut was typed in the clip's Cuts panel and not added: Save holds. */
  typed: boolean
  /** The clip is a file on disk: a frame can be shown and it can be watched. */
  onDisk: boolean
}

/** The caption of the ignored group: "Ignored · 1 clip, not played". */
export function ignoredCaption(count: number): string {
  return `Ignored · ${plural(count, 'clip', 'clips')}, not played`
}

/** The caption of the removed group: "Removed from reel.yaml when you save · 1 clip". */
export function removedCaption(count: number): string {
  return `Removed from reel.yaml when you save · ${plural(count, 'clip', 'clips')}`
}

/** The identities the rows list, top to bottom: the order a Shift+press ranges over. */
export function binOrder(rows: readonly BinRow[]): readonly string[] {
  return rows.map((row) => row.identity)
}

/** A row's second line: where the clip is, and what happened to it ("Kvällen · 2 of 3 · was 4"). */
export function rowPlace(row: Pick<BinRow, 'place' | 'moved'>): string | null {
  if (row.place === null) {
    return null
  }
  return row.moved === null ? row.place : `${row.place} · ${row.moved}`
}

/** A row's kept length as the Timeline writes a length ("0:06.02"); null when it is unknown. */
export function rowLength(row: Pick<BinRow, 'keptMs'>): string | null {
  return row.keptMs === null ? null : formatTime(row.keptMs / 1000)
}

/**
 * What a row says to assistive technology, in one sentence: name, place, status, kept length and
 * a typed cut. Display words only: the row's own text and icons say the same.
 */
export function rowWords(row: BinRow): string {
  const parts = [row.name, rowPlace(row), row.status]
  const length = rowLength(row)
  if (length !== null) {
    parts.push(`kept ${length}`)
  }
  if (row.typed) {
    parts.push('a typed cut waits')
  }
  return parts.filter((part) => part !== null).join(', ')
}

/** The status a listed (played) clip has: what the page read, as the draft stands. */
function listedStatus(clip: Clip): ClipStatusWords {
  if (clip.status === 'new') {
    return 'New'
  }
  if (clip.status === 'missing') {
    return 'Missing'
  }
  return clip.excluded ? 'Excluded' : 'Included'
}

/** The clip the page read for an identity the draft lists: a draft naming one it has not read is a bug. */
function readClip(clips: ReadonlyMap<string, Clip>, identity: string): Clip {
  const clip = clips.get(identity)
  if (clip === undefined) {
    throw new Error(`The draft lists the clip ${identity}, which the event read does not hold.`)
  }
  return clip
}

/** A length in ms from a duration in seconds less the cuts; null for no length (never 0). */
function keptLength(
  duration: number | null | undefined,
  cuts: readonly { in: number; out: number; removed?: boolean }[],
): number | null {
  if (duration == null || !Number.isFinite(duration) || duration <= 0) {
    return null
  }
  return playedMs(keptCuts(cuts), Math.round(duration * 1000))
}

/**
 * The bin's rows for `draft`. `detail` is the page's read of the event (its chapters and clips as
 * read: the draft says what is played, ignored and removed now). `typed` holds the identities
 * whose Cuts panel has a cut typed and not added. `lastMoved` is the clip last moved
 * (`EventEditor`'s `lastMoved`): the fewest-moves rule breaks its ties by it, as the top bar does.
 */
export function binRows(
  draft: Draft,
  baseline: Baseline,
  detail: EventDetail,
  typed: ReadonlySet<string>,
  lastMoved: string | null = null,
): BinRow[] {
  const clips = new Map<string, Clip>()
  const readIgnore = new Set(baseline.read.ignore)
  // The ignored clips as the page read them, by chapter key (`r0`, `r1`…: the page's order).
  const readIgnored = new Map<ChapterKey, string[]>()
  detail.chapters.forEach((chapter, index) => {
    readIgnored.set(
      `r${index}`,
      chapter.clips.filter((clip) => readIgnore.has(clip.identity)).map((clip) => clip.identity),
    )
    for (const clip of chapter.clips) {
      clips.set(clip.identity, clip)
    }
  })

  const listed = listedChapters(draft.chapters)
  const named = listed.some((chapter) => chapter.name !== '')
  const headingOf = new Map(
    draft.chapters.map((chapter) => [chapter.key, chapterHeading(chapter.name, named)]),
  )
  const ignored = ignoredLists(baseline, draft, readIgnored)

  // The missing clips removed here, by the chapter that listed them, in their original order.
  const removed = new Map<ChapterKey, string[]>()
  for (const chapter of draft.chapters) {
    const gone = (baseline.original.get(chapter.key) ?? []).filter(
      (identity) => draft.removed.get(identity) === chapter.key,
    )
    if (gone.length > 0) {
      removed.set(chapter.key, gone)
    }
  }

  // Moved: against each original order without the clips it no longer holds, a clip included
  // here counted as included, not as moved (the top bar's own count, `EventEditor`).
  const movedIn = new Map<ChapterKey, Set<string>>()
  for (const [key, order] of draft.orders) {
    const played = order.filter((identity) => draft.ignoreEdits?.get(identity) !== 'include')
    movedIn.set(
      key,
      movedSet(keptOriginal(baseline.original.get(key) ?? [], played), played, lastMoved),
    )
  }
  const origin = originOf(baseline.original)

  const cutsNow = (identity: string) => cutsOf(baseline.cuts, draft.cuts, identity)
  const rows: BinRow[] = []

  for (const chapter of listed) {
    const order = draft.orders.get(chapter.key) ?? []
    const nameOf = namesIn(
      chapter.name,
      baseline.original.get(chapter.key) ?? [],
      order,
      ignored.get(chapter.key) ?? [],
      removed.get(chapter.key) ?? [],
    )
    const heading = headingOf.get(chapter.key) ?? ''
    const was = new Map((baseline.original.get(chapter.key) ?? []).map((id, at) => [id, at + 1]))
    const moved = movedIn.get(chapter.key)
    order.forEach((identity, at) => {
      const clip = readClip(clips, identity)
      const home = origin.get(identity)
      const wasAt = moved?.has(identity) === true ? was.get(identity) : undefined
      let movedWords: string | null = null
      if (home !== undefined && home !== chapter.key) {
        movedWords = `from ${headingOf.get(home) ?? ''}`
      } else if (wasAt !== undefined) {
        movedWords = wasAt === at + 1 ? 'moved' : `was ${wasAt}`
      }
      rows.push({
        identity,
        name: nameOf(identity),
        group: 'listed',
        place: `${heading} · ${at + 1} of ${order.length}`,
        moved: movedWords,
        status: listedStatus(clip),
        keptMs: keptLength(clip.duration, clip.excluded ? [] : cutsNow(identity)),
        typed: typed.has(identity),
        onDisk: clip.status !== 'missing',
      })
    })
  }

  // Every chapter, a deleted one too: a clip the document ignores stays ignored when its chapter
  // is deleted here, and the bin lists every clip of the event.
  for (const chapter of draft.chapters) {
    const order = draft.orders.get(chapter.key) ?? []
    const nameOf = namesIn(
      chapter.name,
      baseline.original.get(chapter.key) ?? [],
      order,
      ignored.get(chapter.key) ?? [],
      removed.get(chapter.key) ?? [],
    )
    for (const identity of ignored.get(chapter.key) ?? []) {
      const clip = readClip(clips, identity)
      rows.push({
        identity,
        name: nameOf(identity),
        group: 'ignored',
        place: null,
        moved: null,
        status: 'Ignored',
        keptMs: keptLength(clip.duration, []),
        typed: typed.has(identity),
        onDisk: clip.status !== 'missing',
      })
    }
  }

  // Every chapter, a deleted one too: a removal is a pending edit, and its Undo stays reachable.
  for (const chapter of draft.chapters) {
    const gone = removed.get(chapter.key)
    if (gone === undefined) {
      continue
    }
    const nameOf = namesIn(
      chapter.name,
      baseline.original.get(chapter.key) ?? [],
      draft.orders.get(chapter.key) ?? [],
      ignored.get(chapter.key) ?? [],
      gone,
    )
    for (const identity of gone) {
      const clip = readClip(clips, identity)
      rows.push({
        identity,
        name: nameOf(identity),
        group: 'removed',
        place: null,
        moved: null,
        status: 'Missing',
        keptMs: keptLength(clip.duration, []),
        typed: typed.has(identity),
        onDisk: false,
      })
    }
  }
  return rows
}
