import type { ChapterKey, Orders } from '../edit/draft.ts'
import { ModelError } from './model.ts'
import type { Layout, Ms } from './model.ts'
import { trackX } from './cards.ts'
import type { CardMap } from './cards.ts'

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
export type DrawnChapter = {
  key: ChapterKey
  name?: string
  identities: readonly string[]
}

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
 * The drop slot for the dragged block whose centre is at `trackMs` on the track. `lay` is the
 * CLIP lay (the drawn clips end to end, in the chapters' order, no cards) and `map` the black
 * cards among them (`cardMap`; `{ gaps: [], totalMs: 0 }` for none): `trackMs` and the
 * boundaries are track times, so a black card sits between the end of one chapter's last clip
 * and the start of the next one's first. Boundaries are before each clip (at its start) and
 * after each chapter's last clip (at its end); an empty chapter offers one, where the
 * previous chapter ends. The nearest wins. Where two boundaries share a time (no card
 * between two chapters) the centre's side decides: before it the end of the earlier chapter,
 * at or after it the start of the later one. Between two boundaries equally far off, the
 * clip's own place wins, then the earlier.
 */
export function dropSlot(
  lay: Layout,
  map: CardMap,
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
  let cursor: Ms = 0
  for (const chapter of chapters) {
    const n = chapter.identities.length
    for (let position = 0; position < n; position += 1) {
      candidates.push({
        chapter,
        position,
        ms: trackX(map, lay.startsMs[flat + position]),
      })
    }
    if (n > 0) {
      const last = flat + n - 1
      cursor =
        trackX(map, lay.startsMs[last]) +
        ((lay.startsMs[last + 1] ?? lay.totalMs) - lay.startsMs[last])
    }
    candidates.push({ chapter, position: n, ms: cursor })
    flat += n
  }

  const isOwn = (c: Candidate) =>
    c.chapter === own && (c.position === ownAt || c.position === ownAt + 1)
  const nearest = Math.min(...candidates.map((c) => Math.abs(c.ms - trackMs)))
  const ties = candidates.filter((c) => Math.abs(c.ms - trackMs) === nearest)
  // Two times can tie (just before and just after the centre): the own place's, else the earlier.
  const earlier = ties[0].ms
  const ownTie = ties.find(isOwn)
  const at = ownTie !== undefined && ties.some((c) => c.ms !== earlier) ? ownTie.ms : earlier
  const group = ties.filter((c) => c.ms === at)
  // Boundaries at one time: the centre before it takes the earlier, at or after it the later.
  const best = trackMs < at ? group[0] : group[group.length - 1]

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
 * The orders after dropping `from.identity` at `slot`, resolved by identity in the full order
 * (which holds clips that are not drawn: missing, excluded): directly before
 * `slot.beforeIdentity`, or, at a chapter's end, after its last drawn clip (`drawn`, else the
 * order's end). The same `Orders` when that is where the clip already is (no edit) or the
 * clip is not in `from.chapter`.
 */
export function applyDrop(
  orders: Orders,
  from: { identity: string; chapter: ChapterKey },
  slot: Pick<DropSlot, 'chapter' | 'beforeIdentity'>,
  drawn?: ReadonlySet<string>,
): Orders {
  const source = orders.get(from.chapter)
  const at = source?.indexOf(from.identity) ?? -1
  const target = orders.get(slot.chapter)
  if (source === undefined || at === -1 || target === undefined) {
    return orders
  }
  const isDrawn = (identity: string) => drawn === undefined || drawn.has(identity)
  if (slot.chapter === from.chapter) {
    const successor = source.slice(at + 1).find(isDrawn) ?? null
    if (successor === slot.beforeIdentity) {
      return orders
    }
  }
  const rest = source.filter((identity) => identity !== from.identity)
  const base = slot.chapter === from.chapter ? rest : target
  let index = slot.beforeIdentity === null ? -1 : base.indexOf(slot.beforeIdentity)
  if (index === -1) {
    let lastDrawn = -1
    base.forEach((identity, i) => {
      if (isDrawn(identity)) {
        lastDrawn = i
      }
    })
    index = lastDrawn + 1
  }
  const next = new Map(orders)
  next.set(from.chapter, rest)
  next.set(slot.chapter, [...base.slice(0, index), from.identity, ...base.slice(index)])
  return next
}
