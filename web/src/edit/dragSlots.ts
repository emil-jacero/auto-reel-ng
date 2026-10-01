import type { ChapterKey, Orders } from './draft'

/*
 * Where a dragged clip can land, as pure functions over the draft's orders (no
 * runtime imports, as `draft.ts`, so a scratch script runs it under Node).
 *
 * A clip lands at a **slot**: an index into a listed chapter's play order. In its
 * own chapter the slots are sortable's positions (the index it takes once the
 * others close up); in any other listed chapter they are the gaps before each
 * clip and after the last. The slots in page order are the keyboard's path
 * (`slotsOf`, `stepSlot`). A pointer picks one by height (`pointerTarget`).
 *
 * dnd-kit names a target by a droppable's id: a played clip's row is its identity,
 * a listed chapter is `/chapter/<key>` (the gap after its last clip, or the area of
 * a chapter that plays none) and a deleted chapter's placeholder is `/deleted/<key>`.
 * An identity is a path relative to the event folder, never starting with `/`, so
 * neither prefix can name a clip.
 */

export const CHAPTER_DROP = '/chapter/'
export const DELETED_DROP = '/deleted/'

/** Where a drop puts the clip: an index into a listed chapter's play order. */
export type Slot = { chapter: ChapterKey; index: number }

/** A vertical extent in the window's coordinates. */
export type Span = { top: number; bottom: number }

/** What the slots are taken from: the listed chapters and the clips each plays. */
export type DragModel = {
  /** The listed (not deleted) chapters, in the order shown. */
  listed: readonly ChapterKey[]
  orders: Orders
  /** Each clip a listed chapter plays → that chapter. */
  chapterOf: ReadonlyMap<string, ChapterKey>
}

const NONE: readonly string[] = []

export function dragModel(orders: Orders, listed: readonly ChapterKey[]): DragModel {
  const chapterOf = new Map<string, ChapterKey>()
  for (const key of listed) {
    for (const identity of orders.get(key) ?? NONE) {
      chapterOf.set(identity, key)
    }
  }
  return { listed, orders, chapterOf }
}

function orderOf(model: DragModel, key: ChapterKey): readonly string[] {
  return model.orders.get(key) ?? NONE
}

/** How many slots chapter `key` offers `identity`: its positions at home, its gaps elsewhere. */
function slotCount(model: DragModel, identity: string, key: ChapterKey): number {
  const length = orderOf(model, key).length
  return model.chapterOf.get(identity) === key ? length : length + 1
}

/** The chapters `identity` may land in, in page order: its own alone when it stays home. */
function reachable(model: DragModel, identity: string, staysHome: boolean): ChapterKey[] {
  const own = model.chapterOf.get(identity)
  if (own === undefined) {
    return []
  }
  return staysHome ? [own] : [...model.listed]
}

/**
 * Every slot `identity` can be dropped at, in page order: its own chapter's n positions
 * (sortable's index semantics), and, unless it stays home (a missing clip), each other
 * listed chapter's m + 1 gaps (before each of its m clips, then after the last).
 */
export function slotsOf(model: DragModel, identity: string, staysHome: boolean): Slot[] {
  return reachable(model, identity, staysHome).flatMap((chapter) =>
    Array.from({ length: slotCount(model, identity, chapter) }, (_, index) => ({ chapter, index })),
  )
}

/** The slot one step up (-1) or down (1) from `from`; null at either end. */
export function stepSlot(
  model: DragModel,
  identity: string,
  staysHome: boolean,
  from: Slot,
  delta: -1 | 1,
): Slot | null {
  const chapters = reachable(model, identity, staysHome)
  let at = chapters.indexOf(from.chapter)
  if (at === -1) {
    return null
  }
  const index = from.index + delta
  if (index >= 0 && index < slotCount(model, identity, from.chapter)) {
    return { chapter: from.chapter, index }
  }
  // Past this chapter's edge: the next chapter that offers a slot, at its near end.
  for (at += delta; at >= 0 && at < chapters.length; at += delta) {
    const count = slotCount(model, identity, chapters[at])
    if (count > 0) {
      return { chapter: chapters[at], index: delta === 1 ? 0 : count - 1 }
    }
  }
  return null
}

/** The droppable a slot stands for: a row's identity, or `/chapter/<key>` after the last clip. */
export function overIdOf(model: DragModel, identity: string, slot: Slot): string {
  const order = orderOf(model, slot.chapter)
  if (slot.index < order.length) {
    return order[slot.index]
  }
  // Its own chapter has no gap after its last clip: that position is the last row's.
  return model.chapterOf.get(identity) === slot.chapter
    ? (order[order.length - 1] ?? identity)
    : `${CHAPTER_DROP}${slot.chapter}`
}

/** The slot an `over` id stands for; null for none or a deleted placeholder. */
export function slotOf(model: DragModel, identity: string, overId: string | null): Slot | null {
  if (overId === null || overId.startsWith(DELETED_DROP)) {
    return null
  }
  if (overId.startsWith(CHAPTER_DROP)) {
    const chapter = overId.slice(CHAPTER_DROP.length)
    if (!model.listed.includes(chapter)) {
      return null
    }
    // After its last clip; in the clip's own chapter that is its last position.
    return { chapter, index: Math.max(slotCount(model, identity, chapter) - 1, 0) }
  }
  const chapter = model.chapterOf.get(overId)
  return chapter === undefined ? null : { chapter, index: orderOf(model, chapter).indexOf(overId) }
}

/** How far `y` lies outside `span`: 0 inside it. */
function distance(span: Span, y: number): number {
  return y < span.top ? span.top - y : y > span.bottom ? y - span.bottom : 0
}

/**
 * The droppable a pointer at height `y` targets, or null (a deleted chapter's placeholder).
 *
 * The chapter is the listed one whose span holds `y`, else the nearest (a pointer in the
 * gap between two panels); a clip that stays home always gets its own. In its own chapter
 * the row whose centre is nearest (sortable's index semantics, as `closestCenter` gives).
 * In another, the first row whose centre lies below `y` ("before that row"), else the
 * chapter itself ("after its last clip", or the area of a chapter that plays none).
 */
export function pointerTarget(
  model: DragModel,
  identity: string,
  staysHome: boolean,
  y: number,
  chapterSpan: (key: ChapterKey) => Span | undefined,
  deletedSpans: readonly Span[],
  rowSpan: (identity: string) => Span | undefined,
): string | null {
  if (deletedSpans.some((span) => distance(span, y) === 0)) {
    return null
  }
  const own = model.chapterOf.get(identity)
  if (own === undefined) {
    return null
  }
  let chapter = own
  if (!staysHome) {
    let nearest = Infinity
    for (const key of model.listed) {
      const span = chapterSpan(key)
      const away = span === undefined ? Infinity : distance(span, y)
      if (away < nearest) {
        nearest = away
        chapter = key
      }
    }
  }
  const centre = (row: string) => {
    const span = rowSpan(row)
    return span === undefined ? undefined : (span.top + span.bottom) / 2
  }
  const order = orderOf(model, chapter)
  if (chapter === own) {
    let best = identity
    let nearest = Infinity
    for (const row of order) {
      const middle = centre(row)
      if (middle !== undefined && Math.abs(middle - y) < nearest) {
        nearest = Math.abs(middle - y)
        best = row
      }
    }
    return best
  }
  for (const row of order) {
    const middle = centre(row)
    if (middle !== undefined && middle > y) {
      return row
    }
  }
  return `${CHAPTER_DROP}${chapter}`
}
