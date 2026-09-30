import type { ClipStatus, EventDetail } from '../api/event'
import type { ReelDocument, ReelWriteBody } from '../api/reel'

/*
 * The editor's model, as pure functions. It has no runtime imports, only
 * `import type` (erased by type stripping), so a scratch script can run it
 * under Node as it is.
 *
 * Two models meet here. The event detail is what the page shows: every
 * chapter with every clip, NEW, MISSING and IGNORED ones included. The
 * editorial document is what Save writes. The operator reorders the detail's
 * lists; the write body is always the document as read, with only the
 * operator's edits applied, so every section and chapter the operator did not
 * touch goes back exactly as it came.
 */

/** One chapter as the editor lists it. */
export type EditableChapter = {
  name: string
  /** The clips it plays, in the order the page shows them: all but the ignored ones. */
  movable: string[]
  /** Its ignored clips, in the order shown: listed after the others, never moved. */
  ignored: string[]
}

/** Chapter name → the identities of its movable clips, in order. */
export type Orders = ReadonlyMap<string, readonly string[]>

/** The four metadata fields as their inputs hold them: `''` for unset. */
export type MetadataDraft = { title: string; date: string; location: string; description: string }
export type MetadataField = keyof MetadataDraft
export const METADATA_FIELDS: readonly MetadataField[] = [
  'title',
  'date',
  'location',
  'description',
]

/** The editable view of the page's chapters; none without a detail (the needs-attention form). */
export function editableChapters(detail: EventDetail | null): EditableChapter[] {
  if (detail === null) {
    return []
  }
  return detail.chapters.map((chapter) => ({
    name: chapter.name,
    movable: chapter.clips.filter((clip) => clip.status !== 'ignored').map((clip) => clip.identity),
    ignored: chapter.clips.filter((clip) => clip.status === 'ignored').map((clip) => clip.identity),
  }))
}

/** Each chapter's movable order, keyed by name, in the order the chapters are shown. */
export function ordersOf(chapters: readonly EditableChapter[]): Orders {
  return new Map(chapters.map((chapter) => [chapter.name, chapter.movable]))
}

// The statuses of a clip the document lists: on disk (active) or not (missing).
const LISTED: ReadonlySet<ClipStatus> = new Set<ClipStatus>(['active', 'missing'])

/**
 * Whether the page's chapters are the reconcile view of `read`: the document's
 * chapters first, by name and in its order, each listing exactly its clips
 * before any clip only disk has; later chapters holding only disk-only clips;
 * and every ignored clip, and no new one, in the document's `ignore`. False when
 * `reel.yaml` changed between the page's read and the document's.
 */
export function detailMatchesDocument(detail: EventDetail, read: ReelDocument): boolean {
  if (detail.chapters.length < read.chapters.length) {
    return false
  }
  const ignored = new Set(read.ignore)
  return detail.chapters.every((chapter, index) => {
    const authored = index < read.chapters.length ? read.chapters[index] : null
    if (authored !== null && authored.name !== chapter.name) {
      return false
    }
    const listed = authored?.clips ?? []
    const head = chapter.clips.slice(0, listed.length)
    if (
      head.length !== listed.length ||
      head.some((clip, k) => clip.identity !== listed[k] || !LISTED.has(clip.status))
    ) {
      return false
    }
    return chapter.clips
      .slice(listed.length)
      .every((clip) =>
        clip.status === 'ignored'
          ? ignored.has(clip.identity)
          : clip.status === 'new' && !ignored.has(clip.identity),
      )
  })
}

/** The form's starting values: what `reel.yaml` itself says, `''` where it says nothing. */
export function metadataDraftOf(read: ReelDocument): MetadataDraft {
  const metadata = read.metadata
  return {
    title: metadata.title ?? '',
    date: metadata.date ?? '',
    location: metadata.location ?? '',
    description: metadata.description ?? '',
  }
}

/** A field's value as saved: unset (`null`, it inherits) when empty or whitespace-only. */
function asSaved(value: string): string | null {
  return value.trim() === '' ? null : value
}

/** The fields whose draft says something other than what was read, in form order. */
export function changedFields(read: ReelDocument, draft: MetadataDraft): MetadataField[] {
  return METADATA_FIELDS.filter(
    (field) => asSaved(draft[field]) !== asSaved(read.metadata[field] ?? ''),
  )
}

function sameOrder(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((identity, index) => identity === b[index])
}

/** The chapters whose order differs from the original, in the order shown. */
function reordered(original: Orders, next: Orders): string[] {
  return [...original.keys()].filter(
    (name) => !sameOrder(original.get(name) ?? [], next.get(name) ?? []),
  )
}

/**
 * The chapters Save writes from the operator's order rather than from the
 * document: the reordered ones; or, when the document names no chapters, every
 * chapter shown with a clip to play, as a first save would seed them.
 */
function writtenFromView(read: ReelDocument, original: Orders, next: Orders): string[] {
  const changed = reordered(original, next)
  if (changed.length === 0 || read.chapters.length > 0) {
    return changed
  }
  return [...original.keys()].filter((name) => (next.get(name) ?? []).length > 0)
}

/**
 * The PUT body: `read` with only the operator's edits applied.
 *
 * - `look`, `clips` (per-clip properties) and `ignore` go back as read.
 * - A metadata field keeps its read value unless its draft says otherwise; an
 *   edited one is sent as typed, or unset when empty or whitespace-only.
 * - With no chapter reordered, `chapters` go back as read. Otherwise every
 *   chapter the document names keeps its place and list, except a reordered one,
 *   which takes the order shown (its ignored clips excluded, its missing and new
 *   ones kept where they stand); a reordered chapter the document does not name
 *   is appended. When the document names none, every chapter shown is written.
 */
export function buildWriteBody(
  read: ReelDocument,
  original: Orders,
  next: Orders,
  metadata: MetadataDraft,
): ReelWriteBody {
  const changed = new Set(changedFields(read, metadata))
  const field = (name: MetadataField) =>
    changed.has(name) ? asSaved(metadata[name]) : (read.metadata[name] ?? null)

  const fromView = writtenFromView(read, original, next)
  const listFor = (name: string) => ({ name, clips: [...(next.get(name) ?? [])] })
  const chapters =
    fromView.length === 0
      ? read.chapters
      : read.chapters.length === 0
        ? fromView.map(listFor)
        : [
            ...read.chapters.map((chapter) =>
              fromView.includes(chapter.name) ? listFor(chapter.name) : chapter,
            ),
            ...fromView
              .filter((name) => !read.chapters.some((chapter) => chapter.name === name))
              .map(listFor),
          ]

  return {
    metadata: {
      title: field('title'),
      date: field('date'),
      location: field('location'),
      description: field('description'),
    },
    look: read.look,
    chapters,
    clips: read.clips,
    ignore: read.ignore,
  }
}

/** How many NEW clips a save adds to `reel.yaml`: those in the chapters written from the view. */
export function adoptedNewCount(
  read: ReelDocument,
  original: Orders,
  next: Orders,
  newClips: ReadonlySet<string>,
): number {
  return writtenFromView(read, original, next).reduce(
    (count, name) =>
      count + (next.get(name) ?? []).filter((identity) => newClips.has(identity)).length,
    0,
  )
}

/** Whether there is anything to save: a changed field, or an order that differs. */
export function isDirty(
  read: ReelDocument,
  original: Orders,
  next: Orders,
  metadata: MetadataDraft,
): boolean {
  return changedFields(read, metadata).length > 0 || reordered(original, next).length > 0
}

/** `order` with the clip at `from` moved to `to`. */
export function moveClip(order: readonly string[], from: number, to: number): string[] {
  const moved = [...order]
  const [clip] = moved.splice(from, 1)
  moved.splice(to, 0, clip)
  return moved
}

/**
 * The clips kept in place: a longest run of `order` whose original positions
 * increase, so that moving one clip from position 1 to 5 moves one clip, not
 * five. Among equally long runs it prefers, in turn, the one keeping the most
 * clips at their original index (so a clip that never left its place is not
 * counted as moved) and the one without `lastMoved` (a swap of two neighbours
 * counts the clip the operator moved last). A maximum-weight increasing run over
 * a Fenwick tree of original positions, O(n log n); the three preferences are
 * digits of one weight.
 */
function keptInPlace(
  order: readonly string[],
  position: ReadonlyMap<string, number>,
  lastMoved: string | null,
): Set<string> {
  const size = order.length
  const digit = size + 1
  // tree[k]: the best run ending at an original position in k's Fenwick range.
  const tree = Array.from({ length: size + 1 }, () => ({ score: 0, end: -1 }))
  const score: number[] = []
  const previous: number[] = []
  let best = -1
  order.forEach((identity, index) => {
    const rank = position.get(identity)
    if (rank === undefined) {
      return
    }
    let below = { score: 0, end: -1 }
    for (let k = rank; k > 0; k -= k & -k) {
      below = tree[k].score > below.score ? tree[k] : below
    }
    const weight = digit * digit + (rank === index ? digit : 0) + (identity === lastMoved ? 0 : 1)
    score[index] = below.score + weight
    previous[index] = below.end
    for (let k = rank + 1; k <= size; k += k & -k) {
      if (score[index] > tree[k].score) {
        tree[k] = { score: score[index], end: index }
      }
    }
    if (best === -1 || score[index] > score[best]) {
      best = index
    }
  })
  const kept = new Set<string>()
  for (let index = best; index !== -1; index = previous[index]) {
    kept.add(order[index])
  }
  return kept
}

/**
 * The clips counted as moved: those outside the run kept in place (see
 * `keptInPlace`). A clip counted as moved can still sit at its original index
 * (a clip between others that swapped around it); the page marks it as moved
 * without an old position.
 */
export function movedSet(
  original: readonly string[],
  next: readonly string[],
  lastMoved: string | null,
): Set<string> {
  const position = new Map(original.map((identity, index) => [identity, index]))
  const kept = keptInPlace(next, position, lastMoved)
  return new Set(next.filter((identity) => !kept.has(identity)))
}
