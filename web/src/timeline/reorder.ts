import type { ChapterKey, Orders } from '../edit/draft.ts'
import { ModelError } from './model.ts'
import type { Layout, Ms } from './model.ts'

/*
 * Where a clip dragged on the track drops (`track-drag-edit`, D1), as pure rules: no DOM,
 * no React. The slot is the clip boundary nearest the centre of the dragged block; snapping
 * is to boundaries only. A slot at the clip's own place is no edit (`applyDrop` returns the
 * orders it was given).
 *
 * `index` is the index the clip takes in the chapter's order once it has left its old place
 * (the lists' semantics: `moveClip`'s `to`, and the gap index in another chapter), and
 * `beforeIdentity` the clip that then follows it, null at the chapter's end.
 */

/** The lay's chapters as drawn, in order, each with the clips it plays (the dragged one included). */
export type DrawnChapter = { key: ChapterKey; name?: string; identities: readonly string[] }

/** Where a drop puts the clip, and words naming it. */
export type DropSlot = {
  chapter: ChapterKey
  index: number
  beforeIdentity: string | null
  words: string
}

/** The clip's file name: an identity is a path relative to the event folder. */
function baseName(identity: string): string {
  return identity.slice(identity.lastIndexOf('/') + 1)
}

/** Words for a slot: "Before s1710001.mp4", or the end of a chapter. */
export function slotWords(before: string | null, chapterName: string): string {
  return before === null ? `At the end of ${chapterName}` : `Before ${baseName(before)}`
}

type Candidate = { chapter: DrawnChapter; position: number; ms: Ms }

/**
 * The drop slot for the dragged block whose centre is at `trackMs` on the track. `lay` lays
 * the drawn chapters' clips end to end, in the chapters' order. Boundaries are before each
 * clip and after each chapter's last; an empty chapter offers one, where it sits. On a tie
 * the clip's own place wins, then the earlier boundary (the end of a chapter over the start
 * of the next).
 */
export function dropSlot(
  lay: Layout,
  chapters: readonly DrawnChapter[],
  trackMs: Ms,
  dragged: string,
): DropSlot {
  if (typeof trackMs !== 'number' || !Number.isFinite(trackMs)) {
    throw new ModelError(`trackMs must be a finite number, got ${String(trackMs)}`)
  }
  const total = chapters.reduce((sum, chapter) => sum + chapter.identities.length, 0)
  if (total !== lay.startsMs.length) {
    throw new ModelError(`the lay has ${lay.startsMs.length} clips, the chapters ${total}`)
  }
  const own = chapters.find((chapter) => chapter.identities.includes(dragged))
  if (own === undefined) {
    throw new ModelError(`${dragged} is in no drawn chapter`)
  }
  const ownAt = own.identities.indexOf(dragged)

  const candidates: Candidate[] = []
  let flat = 0
  for (const chapter of chapters) {
    const n = chapter.identities.length
    for (let position = 0; position <= n; position += 1) {
      const ms = flat + position < lay.startsMs.length ? lay.startsMs[flat + position] : lay.totalMs
      candidates.push({ chapter, position, ms })
    }
    flat += n
  }

  const isOwn = (c: Candidate) =>
    c.chapter === own && (c.position === ownAt || c.position === ownAt + 1)
  let best = candidates[0]
  let bestAway = Math.abs(best.ms - trackMs)
  for (const c of candidates.slice(1)) {
    const away = Math.abs(c.ms - trackMs)
    if (away < bestAway || (away === bestAway && isOwn(c) && !isOwn(best))) {
      best = c
      bestAway = away
    }
  }

  // The index among the chapter's clips with the dragged one taken out.
  const index = best.chapter === own && best.position > ownAt ? best.position - 1 : best.position
  const rest = best.chapter.identities.filter((identity) => identity !== dragged)
  const beforeIdentity = rest[index] ?? null
  return {
    chapter: best.chapter.key,
    index,
    beforeIdentity,
    words: slotWords(beforeIdentity, best.chapter.name ?? best.chapter.key),
  }
}

/**
 * The orders after dropping `from.identity` at `slot`. The same `Orders` when the slot is
 * the clip's own place (no edit) or the clip is not in `from.chapter`.
 */
export function applyDrop(
  orders: Orders,
  from: { identity: string; chapter: ChapterKey },
  slot: Pick<DropSlot, 'chapter' | 'index'>,
): Orders {
  const source = orders.get(from.chapter)
  const at = source?.indexOf(from.identity) ?? -1
  if (source === undefined || at === -1) {
    return orders
  }
  if (slot.chapter === from.chapter && slot.index === at) {
    return orders
  }
  const target = orders.get(slot.chapter)
  if (target === undefined) {
    return orders
  }
  const next = new Map(orders)
  const rest = source.filter((identity) => identity !== from.identity)
  next.set(from.chapter, rest)
  const base = slot.chapter === from.chapter ? rest : target
  const index = Math.min(Math.max(slot.index, 0), base.length)
  next.set(slot.chapter, [...base.slice(0, index), from.identity, ...base.slice(index)])
  return next
}
