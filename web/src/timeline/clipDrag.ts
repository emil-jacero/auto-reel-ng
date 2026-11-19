import type { Ms } from './model.ts'
import { slotWords } from './reorder.ts'
import type { DrawnChapter, DropSlot } from './reorder.ts'

/*
 * The pure parts of a clip block dragged on the track (`track-drag-edit`, D2): the slop, where
 * the block lands in the order, which clips it passes (they shift by its width) and where the
 * drop line stands. No DOM, no React: `ClipDrag.tsx` reads the pointer and draws.
 */

/** A press that moves less than this is still a press: it selects (`editor-selection`, D2). */
export const CLIP_SLOP_PX = 3

/** What a track tool says while a save or a "Move marked…" is pending. */
export const MOVE_LOCKED = 'Moving clips waits for the save or the move of several clips to finish.'

/** What Alt+Left and Alt+Right say while several clips are selected: they move nothing (design D6). */
export const MOVE_ONE_WORDS =
  'Alt and an arrow move one clip. Move to\u2026 in the Clip tab moves the selected clips.'

/** What the tip says while the pointer is over the bin: a release there ignores the clip. */
export const IGNORE_WORDS = 'Release on the bin to ignore the clip'

/** What the tip says while the pointer is outside the track: a release there cancels. */
export const MOVE_CANCEL = 'Release outside the track cancels the move'

/**
 * What a press on a clip's block lands on: a cut's span or a card's span (each selects its own
 * and is not dragged), or null for the rest of the body (which reorders). `at` is the playhead
 * position under the press, `cuts` the clip's cuts in seconds.
 */
export function spanHit(
  at: { clip: number; ms: Ms; card?: unknown | null },
  clipIdentity: string | undefined,
  identity: string,
  cuts: readonly { removed?: boolean; in: number; out: number }[],
): 'cut' | 'card' | null {
  if (at.card != null) {
    return 'card'
  }
  if (clipIdentity !== identity) {
    return null
  }
  const cut = cuts.find((c) => !c.removed && Math.round(c.in * 1000) <= at.ms && at.ms < Math.round(c.out * 1000))
  return cut === undefined ? null : 'cut'
}

/** Whether a press has moved far enough to be a drag. */
export function pastSlop(dx: number, dy: number): boolean {
  return Math.hypot(dx, dy) >= CLIP_SLOP_PX
}

const flatten = (chapters: readonly DrawnChapter[]): string[] =>
  chapters.flatMap((chapter) => [...chapter.identities])

/** The clip's index in the drawn order now; -1 when it is not drawn. */
export function flatIndex(chapters: readonly DrawnChapter[], identity: string): number {
  return flatten(chapters).indexOf(identity)
}

/**
 * Where a drop at `slot` puts the dragged clip: `from` its index in the drawn order now, `to` its
 * index in that order once it has taken the slot (the order without it, with it put back at the
 * slot). `from === to` is its own place.
 */
export function flatMove(
  chapters: readonly DrawnChapter[],
  slot: Pick<DropSlot, 'chapter' | 'index'>,
  dragged: string,
): { from: number; to: number } {
  const from = flatIndex(chapters, dragged)
  let before = 0
  for (const chapter of chapters) {
    if (chapter.key === slot.chapter) {
      return { from, to: before + slot.index }
    }
    before += chapter.identities.filter((identity) => identity !== dragged).length
  }
  return { from, to: from }
}

/**
 * Which way the block at drawn index `at` shifts while the dragged clip goes from `from` to
 * `to`: -1 (left, by the dragged block's width) for the clips it passes going right, +1 for
 * those it passes going left, 0 for the rest and for the dragged one itself. Only clip blocks
 * shift: a move across a chapter join into the end of the earlier chapter has `from === to` and
 * the card between the chapters stays put in the preview (accepted gap; the drop is right).
 */
export function shiftOf(from: number, to: number, at: number): -1 | 0 | 1 {
  if (at === from) {
    return 0
  }
  if (from < to && at > from && at <= to) {
    return -1
  }
  if (to < from && at >= to && at < from) {
    return 1
  }
  return 0
}

/** Whether the slot is the clip's own place: nothing would change. */
export function isOwnPlace(
  chapters: readonly DrawnChapter[],
  slot: Pick<DropSlot, 'chapter' | 'index'>,
  dragged: string,
): boolean {
  const own = chapters.find((chapter) => chapter.identities.includes(dragged))
  return own !== undefined && own.key === slot.chapter && own.identities.indexOf(dragged) === slot.index
}

/**
 * The track time of the drop line: the start of the clip the dragged one goes before, else the
 * end of the chapter's last other clip (an empty chapter: where the clips before it end; none: 0).
 * `starts` and `extents` are per drawn index, in track time.
 */
export function slotLineMs(
  starts: readonly Ms[],
  extents: readonly Ms[],
  chapters: readonly DrawnChapter[],
  slot: Pick<DropSlot, 'chapter' | 'beforeIdentity'>,
  dragged: string,
): Ms {
  const order = flatten(chapters)
  if (slot.beforeIdentity !== null) {
    return starts[order.indexOf(slot.beforeIdentity)] ?? 0
  }
  let end: Ms = 0
  let flat = 0
  for (const chapter of chapters) {
    chapter.identities.forEach((identity, i) => {
      if (identity !== dragged) {
        end = starts[flat + i] + extents[flat + i]
      }
    })
    flat += chapter.identities.length
    if (chapter.key === slot.chapter) {
      break
    }
  }
  return end
}

/** The slot for a drop on a chapter's band: the end of that chapter. */
export function bandSlot(chapters: readonly DrawnChapter[], at: number, dragged: string): DropSlot | null {
  const chapter = chapters[at]
  if (chapter === undefined) {
    return null
  }
  const rest = chapter.identities.filter((identity) => identity !== dragged)
  return {
    chapter: chapter.key,
    index: rest.length,
    beforeIdentity: null,
    words: slotWords(null, chapter.name ?? chapter.key),
  }
}

export type Box = { left: number; right: number; top: number; bottom: number }

/** Whether a point is inside a box. */
export function inBox(box: Box, x: number, y: number): boolean {
  return x >= box.left && x <= box.right && y >= box.top && y <= box.bottom
}

/** The words for a slot: its own, or that the clip stays where it is. */
export function dropWords(own: boolean, slot: Pick<DropSlot, 'words'>): string {
  return own ? 'Stays where it is' : slot.words
}

/** What the tip says while the pointer is over the bin with a group: a release there ignores them all. */
export const IGNORE_GROUP_WORDS = 'Release on the bin to ignore the clips'

/** Where a group released would land: before a clip that is not in the group, or at a chapter's end. */
export type GroupSlot = {
  chapter: DropSlot['chapter']
  /** The first clip at or after the gap that is not in the group; null: the end of the chapter. */
  beforeIdentity: string | null
  /** The slot alone: "Before s1710001.mp4", "End of Main". */
  place: string
  /** The tip: "3 clips · Before s1710001.mp4". */
  words: string
  /** The line's track time. */
  lineMs: Ms
}

const baseName = (identity: string): string => identity.slice(identity.lastIndexOf('/') + 1)

/** "3 clips · End of Main": the group's count and the place. */
const groupWords = (count: number, place: string): string => `${count} clips \u00b7 ${place}`

/** How many of the group the drawn chapters hold. */
export function groupCount(chapters: readonly DrawnChapter[], group: ReadonlySet<string>): number {
  return flatten(chapters).filter((identity) => group.has(identity)).length
}

/**
 * The boundaries a group can land on, over the drawn order without the group: before each clip
 * that is not in the group, and at the end of each chapter. `starts` and `extents` are per drawn
 * index, in track time; a chapter's end is where its last drawn clip ends (an empty chapter: where
 * the chapters before it end).
 */
function groupBoundaries(
  chapters: readonly DrawnChapter[],
  group: ReadonlySet<string>,
  starts: readonly Ms[],
  extents: readonly Ms[],
): { chapter: DrawnChapter; before: string | null; ms: Ms }[] {
  const out: { chapter: DrawnChapter; before: string | null; ms: Ms }[] = []
  let flat = 0
  let cursor: Ms = 0
  for (const chapter of chapters) {
    chapter.identities.forEach((identity, i) => {
      if (!group.has(identity)) {
        out.push({ chapter, before: identity, ms: starts[flat + i] ?? 0 })
      }
    })
    const n = chapter.identities.length
    if (n > 0) {
      cursor = (starts[flat + n - 1] ?? 0) + (extents[flat + n - 1] ?? 0)
    }
    out.push({ chapter, before: null, ms: cursor })
    flat += n
  }
  return out
}

function groupSlotOf(
  count: number,
  chapter: DrawnChapter,
  before: string | null,
  ms: Ms,
): GroupSlot {
  const place = before === null ? `End of ${chapter.name ?? chapter.key}` : `Before ${baseName(before)}`
  return { chapter: chapter.key, beforeIdentity: before, place, words: groupWords(count, place), lineMs: ms }
}

/**
 * The slot for a group of clips whose pointer is at track time `ms` (`clip-multi-select`, D4): the
 * nearest boundary over the drawn order without the group. The run then goes before the first
 * clip at or after the gap that is not in the group (`moveGroup`'s rule), so only a clip outside
 * the group can be "before". Where two boundaries share a time, the pointer before it takes the
 * earlier and at or after it the later (as `dropSlot`). Null when no chapter is drawn.
 */
export function groupSlot(
  chapters: readonly DrawnChapter[],
  group: ReadonlySet<string>,
  starts: readonly Ms[],
  extents: readonly Ms[],
  ms: Ms,
): GroupSlot | null {
  const candidates = groupBoundaries(chapters, group, starts, extents)
  if (candidates.length === 0) {
    return null
  }
  const nearest = Math.min(...candidates.map((c) => Math.abs(c.ms - ms)))
  const ties = candidates.filter((c) => Math.abs(c.ms - ms) === nearest)
  const at = ties[0].ms
  const same = ties.filter((c) => c.ms === at)
  const best = ms < at ? same[0] : same[same.length - 1]
  return groupSlotOf(groupCount(chapters, group), best.chapter, best.before, best.ms)
}

/** The slot for a group released on chapter `at`'s band: the end of that chapter. */
export function groupBandSlot(
  chapters: readonly DrawnChapter[],
  group: ReadonlySet<string>,
  starts: readonly Ms[],
  extents: readonly Ms[],
  at: number,
): GroupSlot | null {
  const chapter = chapters[at]
  if (chapter === undefined) {
    return null
  }
  const end = groupBoundaries(chapters, group, starts, extents).find(
    (c) => c.chapter === chapter && c.before === null,
  )
  return end === undefined ? null : groupSlotOf(groupCount(chapters, group), chapter, null, end.ms)
}

/**
 * Whether a drop at `slot` leaves the drawn order as it is: the group's run, in drawn order, goes
 * before `slot.beforeIdentity` (or to the chapter's end) and every chapter plays what it did.
 */
export function isGroupOwnPlace(
  chapters: readonly DrawnChapter[],
  group: ReadonlySet<string>,
  slot: Pick<GroupSlot, 'chapter' | 'beforeIdentity'>,
): boolean {
  const run = flatten(chapters).filter((identity) => group.has(identity))
  return chapters.every((chapter) => {
    const rest = chapter.identities.filter((identity) => !group.has(identity))
    let next: readonly string[] = rest
    if (chapter.key === slot.chapter) {
      const at = slot.beforeIdentity === null ? rest.length : rest.indexOf(slot.beforeIdentity)
      next = [...rest.slice(0, at < 0 ? rest.length : at), ...run, ...rest.slice(at < 0 ? rest.length : at)]
    }
    return next.length === chapter.identities.length && next.every((identity, i) => identity === chapter.identities[i])
  })
}
