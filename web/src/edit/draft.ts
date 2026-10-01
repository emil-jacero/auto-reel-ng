import type { ClipStatus, EventDetail } from '../api/event'
import type { ReelDocument, ReelWriteBody } from '../api/reel'
import type { KnownReason } from '../cuts/times'

/*
 * The editor's model, as pure functions. It has no runtime imports, only
 * `import type` (erased by type stripping), so a scratch script can run it
 * under Node as it is.
 *
 * Two models meet here. The event detail is what the page shows: every
 * chapter with every clip, NEW, MISSING and IGNORED ones included. The
 * editorial document is what Save writes. The operator reorders the detail's
 * lists, moves clips between them and edits the chapter list itself; the write
 * body is always the document as read, with only the operator's edits applied,
 * so every section and chapter the operator did not touch goes back exactly as
 * it came (see "What a save writes" at `writtenFromView`).
 */

/**
 * A chapter's key for the Edit-mode session: `r0`, `r1`… for the chapters the
 * page showed, in that order; `a1`, `a2`… for the ones the operator added. Every
 * map below is keyed by it, never by a name, which a rename changes.
 */
export type ChapterKey = string

/** One chapter as the editor lists it. */
export type EditableChapter = {
  key: ChapterKey
  name: string
  /** The clips it plays, in the order the page shows them: all but the ignored ones. */
  movable: string[]
  /** Its ignored clips, in the order shown: listed after the others, never moved. */
  ignored: string[]
}

/** A chapter of the draft's chapter list. */
export type DraftChapter = {
  key: ChapterKey
  /** The name it was read with; null for a chapter added in this session. */
  readName: string | null
  /** Its name now: trimmed, '' only for the event's own chapter. */
  name: string
  /** Deleted on save; still listed, in place, with Undo. An added chapter is dropped instead. */
  deleted: boolean
}

/** Chapter key → the identities of its movable clips, in order. */
export type Orders = ReadonlyMap<ChapterKey, readonly string[]>

/** The missing clips the operator removed: identity → its chapter's key. */
export type Removals = ReadonlyMap<string, ChapterKey>

/** The four metadata fields as their inputs hold them: `''` for unset. */
export type MetadataDraft = { title: string; date: string; location: string; description: string }
export type MetadataField = keyof MetadataDraft
export const METADATA_FIELDS: readonly MetadataField[] = [
  'title',
  'date',
  'location',
  'description',
]

/**
 * A cut's key for the Edit-mode session: `r0`, `r1`… for a cut read from
 * `reel.yaml` (its index in the clip's `trims`); `a1`, `a2`… for one added here.
 */
export type CutKey = string

/** One cut of a clip as its panel lists it. */
export type DraftCut = {
  key: CutKey
  in: number
  out: number
  reason: string | null
  /** A read cut the save leaves out; still listed, in place, with Undo. An added one is dropped. */
  removed: boolean
}

/** Identity → its cuts as listed, in order. */
export type Cuts = ReadonlyMap<string, readonly DraftCut[]>

/** What the operator changed. */
export type Draft = {
  /** Every chapter in the order shown: the read ones (deleted ones in place) and the added ones. */
  chapters: readonly DraftChapter[]
  orders: Orders
  removed: Removals
  metadata: MetadataDraft
  /** The cuts of the clips whose cuts the operator changed, only those (`settled`). */
  cuts: Cuts
}

/** What Edit mode read: never changes during the session. */
export type Baseline = {
  read: ReelDocument
  chapters: readonly DraftChapter[]
  original: Orders
  /** Each clip's cuts as read (`readCuts`); a clip without cuts has no entry. */
  cuts: Cuts
}

/** The edits to the chapter list itself, as the save bar counts them. */
export type ChapterChanges = { added: number; renamed: number; deleted: number; reordered: boolean }

/** The editable view of the page's chapters; none without a detail (the needs-attention form). */
export function editableChapters(detail: EventDetail | null): EditableChapter[] {
  if (detail === null) {
    return []
  }
  return detail.chapters.map((chapter, index) => ({
    key: `r${index}`,
    name: chapter.name,
    movable: chapter.clips.filter((clip) => clip.status !== 'ignored').map((clip) => clip.identity),
    ignored: chapter.clips.filter((clip) => clip.status === 'ignored').map((clip) => clip.identity),
  }))
}

/** Each chapter's movable order, keyed by its key, in the order the chapters are shown. */
export function ordersOf(chapters: readonly EditableChapter[]): Orders {
  return new Map(chapters.map((chapter) => [chapter.key, chapter.movable]))
}

/** The chapter list as read: every chapter under its own name, none deleted. */
export function draftChapters(chapters: readonly EditableChapter[]): DraftChapter[] {
  return chapters.map((chapter) => ({
    key: chapter.key,
    readName: chapter.name,
    name: chapter.name,
    deleted: false,
  }))
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

/**
 * The chapters whose order differs from the original, by key: a key present in
 * only one of the two maps counts (an added chapter).
 */
function reordered(original: Orders, next: Orders): Set<ChapterKey> {
  const keys = new Set([...original.keys(), ...next.keys()])
  return new Set(
    [...keys].filter((key) => !sameOrder(original.get(key) ?? [], next.get(key) ?? [])),
  )
}

/** The chapters a save keeps: every one but the deleted ones, in the order shown. */
export function listedChapters(chapters: readonly DraftChapter[]): DraftChapter[] {
  return chapters.filter((chapter) => !chapter.deleted)
}

/**
 * What the operator did to the chapter list itself. A moved added chapter is
 * part of "added", not a reorder; a placeholder of a deleted one is no place.
 */
export function chapterChanges(
  baseline: Baseline,
  chapters: readonly DraftChapter[],
): ChapterChanges {
  const read = chapters.filter((chapter) => chapter.readName !== null)
  const kept = read.filter((chapter) => !chapter.deleted).map((chapter) => chapter.key)
  const keptKeys = new Set(kept)
  const asRead = baseline.chapters.map((chapter) => chapter.key).filter((key) => keptKeys.has(key))
  return {
    added: chapters.length - read.length,
    renamed: read.filter((chapter) => !chapter.deleted && chapter.name !== chapter.readName).length,
    deleted: read.filter((chapter) => chapter.deleted).length,
    reordered: !sameOrder(kept, asRead),
  }
}

/** Whether the chapter list itself changed: a save then writes every chapter from the view. */
export function isStructural(changes: ChapterChanges): boolean {
  return changes.added > 0 || changes.renamed > 0 || changes.deleted > 0 || changes.reordered
}

/**
 * What a save writes from the view rather than from the document: the chapters
 * it writes in the order shown, each under its current name, from its order now
 * (missing and NEW clips in place, ignored and removed ones left out). Every
 * trigger lives here, and only here (`buildWriteBody`, `adoptedNewCount` and
 * `isDirty` all ask it), so the count and the body cannot disagree:
 *
 * - a change to the chapter list (`isStructural`): every listed chapter, so
 *   every NEW clip is adopted where the page shows it, and a chapter's name then
 *   only decides where later clips go (D-12)
 * - an order or a cut changed while the document names no chapters: every
 *   listed chapter, as a first save seeds them, an empty one (only ignored
 *   clips) too
 * - otherwise the chapters whose order changed (reordered, a missing clip
 *   removed, a clip moved in or out), and the chapter that plays a NEW clip
 *   whose cuts changed; none for a metadata-only edit or a listed clip's cuts
 */
export function writtenFromView(baseline: Baseline, draft: Draft): DraftChapter[] {
  const listed = listedChapters(draft.chapters)
  if (isStructural(chapterChanges(baseline, draft.chapters))) {
    return listed
  }
  const changed = reordered(baseline.original, draft.orders)
  const cut = changedCuts(baseline, draft)
  if (changed.size === 0 && cut.size === 0) {
    return []
  }
  if (baseline.read.chapters.length === 0) {
    return listed
  }
  // A NEW clip whose cuts changed: reel.yaml holds a clip's cuts only while a chapter
  // lists it, so the chapter that plays it is written from the view, adopting it.
  const inDocument = new Set(baseline.read.chapters.flatMap((chapter) => chapter.clips))
  for (const identity of cut) {
    if (!inDocument.has(identity)) {
      const holder = listed.find((chapter) => draft.orders.get(chapter.key)?.includes(identity))
      if (holder !== undefined) {
        changed.add(holder.key)
      }
    }
  }
  return listed.filter((chapter) => changed.has(chapter.key))
}

/**
 * The PUT body: `read` with only the operator's edits applied.
 *
 * - `look` and `ignore` go back as read, and so does `clips` (per-clip
 *   properties), less the entries of the `removed` clips: the engine refuses
 *   properties for a clip no chapter lists. A moved clip keeps its entry: it is
 *   keyed by identity, not by chapter. A clip whose cuts changed gets its new
 *   `trims` (`withCuts`).
 * - A metadata field keeps its read value unless its draft says otherwise; an
 *   edited one is sent as typed, or unset when empty or whitespace-only.
 * - `chapters`, in the order shown: a chapter written from the view
 *   (`writtenFromView`) under its current name with its order now; every other
 *   chapter the document names exactly as read; a chapter shown only from disk
 *   and not written from the view stays unwritten. With nothing written from the
 *   view that is the document's own list, untouched.
 */
export function buildWriteBody(baseline: Baseline, draft: Draft): ReelWriteBody {
  const { read } = baseline
  const { metadata } = draft
  const changed = new Set(changedFields(read, metadata))
  const field = (name: MetadataField) =>
    changed.has(name) ? asSaved(metadata[name]) : (read.metadata[name] ?? null)

  const fromView = new Set(writtenFromView(baseline, draft).map((chapter) => chapter.key))
  const chapters =
    fromView.size === 0
      ? read.chapters
      : listedChapters(draft.chapters).flatMap((chapter) => {
          if (fromView.has(chapter.key)) {
            return [{ name: chapter.name, clips: [...(draft.orders.get(chapter.key) ?? [])] }]
          }
          // Not written from the view: unrenamed, so its read name finds it in the document.
          const authored = read.chapters.find((listed) => listed.name === chapter.readName)
          return authored === undefined ? [] : [authored]
        })

  return {
    metadata: {
      title: field('title'),
      date: field('date'),
      location: field('location'),
      description: field('description'),
    },
    look: read.look,
    chapters,
    clips: withCuts(baseline, draft),
    ignore: read.ignore,
  }
}

/**
 * The body's `clips`: as read, less the removed clips' entries, with each
 * changed clip's `trims` as its panel lists them (removed cuts left out). Its
 * title-clip choice, rotation and exclusion go back as read; an entry left with
 * none of those and no cut is left out, never written empty (`{}`). Every key is
 * listed by a chapter the body writes (`writtenFromView` adopts a NEW clip's).
 */
function withCuts(baseline: Baseline, draft: Draft): ReelWriteBody['clips'] {
  const clips = Object.fromEntries(
    Object.entries(baseline.read.clips).filter(([identity]) => !draft.removed.has(identity)),
  )
  for (const identity of changedCuts(baseline, draft)) {
    const trims = savedTrims(cutsOf(baseline.cuts, draft.cuts, identity))
    const entry = baseline.read.clips[identity]
    if (entry !== undefined) {
      if (trims.length === 0 && entry.title == null && entry.rotate == null && !entry.exclude) {
        delete clips[identity]
      } else {
        clips[identity] = { ...entry, trims }
      }
    } else if (trims.length > 0) {
      clips[identity] = { trims, exclude: false }
    }
  }
  return clips
}

/** How many NEW clips a save adds to `reel.yaml`: those in the chapters written from the view. */
export function adoptedNewCount(
  baseline: Baseline,
  draft: Draft,
  newClips: ReadonlySet<string>,
): number {
  return writtenFromView(baseline, draft).reduce(
    (count, chapter) =>
      count +
      (draft.orders.get(chapter.key) ?? []).filter((identity) => newClips.has(identity)).length,
    0,
  )
}

/**
 * Whether there is anything to save: a changed field, anything a save would
 * write from the view (an order that differs, a change to the chapter list), or
 * a clip whose saved cuts would differ.
 */
export function isDirty(baseline: Baseline, draft: Draft): boolean {
  return (
    changedFields(baseline.read, draft.metadata).length > 0 ||
    writtenFromView(baseline, draft).length > 0 ||
    changedCuts(baseline, draft).size > 0
  )
}

// A clip without cuts: one constant, so its row keeps its memoised props.
const NO_CUTS: readonly DraftCut[] = []

/** Each clip's cuts as read: `Baseline.cuts`, built once. */
export function readCuts(read: ReelDocument): Cuts {
  return new Map(
    Object.entries(read.clips).flatMap(([identity, entry]): [string, DraftCut[]][] =>
      entry.trims.length === 0
        ? []
        : [
            [
              identity,
              entry.trims.map((trim, index) => ({
                key: `r${index}`,
                in: trim.in,
                out: trim.out,
                reason: trim.reason ?? null,
                removed: false,
              })),
            ],
          ],
    ),
  )
}

/**
 * A clip's cuts as listed now: the draft's when the operator changed them, else
 * the read ones. Takes the two maps, not a `Draft`, so a list's props never change
 * on a metadata edit; both answers are stable references.
 */
export function cutsOf(base: Cuts, changed: Cuts, identity: string): readonly DraftCut[] {
  return changed.get(identity) ?? base.get(identity) ?? NO_CUTS
}

type SavedTrim = { in: number; out: number; reason: string | null }

/** The `trims` a list saves: its cuts that are not removed, as read or typed. */
function savedTrims(cuts: readonly DraftCut[]): SavedTrim[] {
  return cuts
    .filter((cut) => !cut.removed)
    .map(({ in: start, out, reason }) => ({ in: start, out, reason }))
}

/** Whether two lists of saved trims are the same: start, end and reason, in order. */
function sameTrims(a: readonly SavedTrim[], b: readonly SavedTrim[]): boolean {
  return (
    a.length === b.length &&
    a.every(
      (cut, at) => cut.in === b[at].in && cut.out === b[at].out && cut.reason === b[at].reason,
    )
  )
}

/**
 * `draft` with `identity`'s cuts set to `cuts`: a list back to the one read (the
 * same keys, none removed), or one that would save the read trims (a read cut
 * removed and the same span typed again), leaves `draft.cuts`, so an edit and its
 * reverse leave nothing to save, and nothing marked, without a special case.
 */
function settled(baseline: Baseline, draft: Draft, identity: string, cuts: DraftCut[]): Draft {
  const read = baseline.cuts.get(identity) ?? NO_CUTS
  const asRead =
    (cuts.length === read.length &&
      cuts.every((cut, at) => !cut.removed && cut.key === read[at].key)) ||
    sameTrims(savedTrims(cuts), savedTrims(read))
  const next = new Map(draft.cuts)
  if (asRead) {
    next.delete(identity)
  } else {
    next.set(identity, cuts)
  }
  return { ...draft, cuts: next }
}

/**
 * `draft` with a cut added to `identity` under the new key `key`, after every
 * listed cut (removed ones included) that starts at the same time or earlier.
 * The caller checked it (`checkCut`, `cuts/times.ts`) against the same list.
 */
export function addCut(
  baseline: Baseline,
  draft: Draft,
  identity: string,
  span: { in: number; out: number },
  key: CutKey,
): Draft {
  const cuts = cutsOf(baseline.cuts, draft.cuts, identity)
  if (cuts.some((cut) => cut.key === key)) {
    return draft
  }
  let at = cuts.length
  while (at > 0 && cuts[at - 1].in > span.in) {
    at -= 1
  }
  // D-K's value for a cut made by hand (`cuts/times.ts` names it "Cut by hand").
  const reason = 'manual' satisfies KnownReason
  const added: DraftCut = { key, in: span.in, out: span.out, reason, removed: false }
  return settled(baseline, draft, identity, [...cuts.slice(0, at), added, ...cuts.slice(at)])
}

/** `draft` with cut `key` of `identity` removed: a read one marked, an added one dropped. */
export function removeCut(baseline: Baseline, draft: Draft, identity: string, key: CutKey): Draft {
  const cuts = cutsOf(baseline.cuts, draft.cuts, identity)
  const cut = cuts.find((listed) => listed.key === key)
  if (cut === undefined || cut.removed) {
    return draft
  }
  const read = (baseline.cuts.get(identity) ?? NO_CUTS).some((listed) => listed.key === key)
  return settled(
    baseline,
    draft,
    identity,
    read
      ? cuts.map((listed) => (listed.key === key ? { ...listed, removed: true } : listed))
      : cuts.filter((listed) => listed.key !== key),
  )
}

/** `draft` with the removed cut `key` of `identity` back (the caller ran `checkRestore`). */
export function restoreCut(baseline: Baseline, draft: Draft, identity: string, key: CutKey): Draft {
  const cuts = cutsOf(baseline.cuts, draft.cuts, identity)
  if (!cuts.some((listed) => listed.key === key && listed.removed)) {
    return draft
  }
  return settled(
    baseline,
    draft,
    identity,
    cuts.map((listed) => (listed.key === key ? { ...listed, removed: false } : listed)),
  )
}

/**
 * The clips whose saved cuts would differ from the read ones (start, end and
 * reason of the cuts not removed, in order); a removed clip's are left out with it.
 */
export function changedCuts(baseline: Baseline, draft: Draft): ReadonlySet<string> {
  const changed = new Set<string>()
  for (const [identity, cuts] of draft.cuts) {
    if (draft.removed.has(identity)) {
      continue
    }
    if (!sameTrims(savedTrims(cuts), savedTrims(baseline.cuts.get(identity) ?? NO_CUTS))) {
      changed.add(identity)
    }
  }
  return changed
}

/**
 * The cuts added and the read cuts removed, as the save bar counts them: only on the
 * clips whose saved cuts would differ (`changedCuts`), so the counts never name a
 * change the save would not make.
 */
export function cutChanges(baseline: Baseline, draft: Draft): { added: number; removed: number } {
  let added = 0
  let removed = 0
  for (const identity of changedCuts(baseline, draft)) {
    const cuts = draft.cuts.get(identity) ?? NO_CUTS
    const read = new Set((baseline.cuts.get(identity) ?? NO_CUTS).map((cut) => cut.key))
    for (const cut of cuts) {
      if (cut.removed) {
        removed += 1
      } else if (!read.has(cut.key)) {
        added += 1
      }
    }
  }
  return { added, removed }
}

/** `order` with the clip at `from` moved to `to`. */
export function moveClip(order: readonly string[], from: number, to: number): string[] {
  const moved = [...order]
  const [clip] = moved.splice(from, 1)
  moved.splice(to, 0, clip)
  return moved
}

/** `orders` with `identity` taken out of `chapter`; null when the chapter does not list it. */
export function removeClip(orders: Orders, chapter: ChapterKey, identity: string): Orders | null {
  const order = orders.get(chapter)
  if (order === undefined || !order.includes(identity)) {
    return null
  }
  const next = new Map(orders)
  next.set(chapter, order.filter((listed) => listed !== identity))
  return next
}

/**
 * `orders` with `identity` put back in `chapter`, right after whichever of the
 * clips that came before it in `original` (the chapter's order when Edit mode
 * opened) comes last in the chapter's order now; first when none of them is
 * left. Without a move in between, the order is a subsequence of `original`,
 * so that is exactly its original place, whatever order removals are undone
 * in. After a move it follows its original predecessors wherever they went, so
 * the clips around it are not counted as moved.
 */
export function restoreClip(
  orders: Orders,
  chapter: ChapterKey,
  identity: string,
  original: readonly string[],
): Orders {
  const order = orders.get(chapter) ?? []
  if (order.includes(identity)) {
    return orders
  }
  const at = new Map(order.map((clip, index) => [clip, index]))
  const last = original
    .slice(0, Math.max(original.indexOf(identity), 0))
    .reduce((latest, clip) => Math.max(latest, at.get(clip) ?? -1), -1)
  const next = new Map(orders)
  next.set(chapter, [...order.slice(0, last + 1), identity, ...order.slice(last + 1)])
  return next
}

/** The chapter each clip was in when Edit mode opened. */
export function originOf(original: Orders): ReadonlyMap<string, ChapterKey> {
  return new Map(
    [...original].flatMap(([key, order]) =>
      order.map((identity): [string, ChapterKey] => [identity, key]),
    ),
  )
}

/**
 * A chapter's original order less every clip it no longer holds (removed, or
 * moved to another chapter): `movedSet`'s first argument. Its ranks then never
 * exceed the order's length, and the clips left behind are not counted as
 * moved for the ones that left.
 */
export function keptOriginal(original: readonly string[], order: readonly string[]): string[] {
  const held = new Set(order)
  return original.filter((identity) => held.has(identity))
}

function withChapters(draft: Draft, chapters: readonly DraftChapter[]): Draft {
  return { ...draft, chapters }
}

/** `draft` with an empty chapter `name` appended under the new key `key`. */
export function addChapter(draft: Draft, key: ChapterKey, name: string): Draft {
  if (draft.chapters.some((chapter) => chapter.key === key)) {
    return draft
  }
  return {
    ...draft,
    chapters: [...draft.chapters, { key, readName: null, name, deleted: false }],
    orders: new Map(draft.orders).set(key, []),
  }
}

/** `draft` with chapter `key` named `name` (the caller checked it: `checkName`). */
export function renameChapter(draft: Draft, key: ChapterKey, name: string): Draft {
  return withChapters(
    draft,
    draft.chapters.map((chapter) =>
      chapter.key === key && !chapter.deleted ? { ...chapter, name } : chapter,
    ),
  )
}

/**
 * `draft` with chapter `key` swapped with its nearest chapter that is not
 * deleted, one place up (-1) or down (1). A deleted placeholder keeps its
 * index, so a press always changes the order a save writes.
 */
export function moveChapter(draft: Draft, key: ChapterKey, delta: -1 | 1): Draft {
  const from = draft.chapters.findIndex((chapter) => chapter.key === key)
  if (from === -1 || draft.chapters[from].deleted) {
    return draft
  }
  let to = from + delta
  while (to >= 0 && to < draft.chapters.length && draft.chapters[to].deleted) {
    to += delta
  }
  if (to < 0 || to >= draft.chapters.length) {
    return draft
  }
  const chapters = [...draft.chapters]
  chapters[from] = draft.chapters[to]
  chapters[to] = draft.chapters[from]
  return withChapters(draft, chapters)
}

/**
 * `draft` with chapter `key` deleted (the caller checked it plays no clip). An
 * added chapter is dropped with its order. A read one stays in place, marked,
 * with its order and its removals, so `restoreChapter` brings both back.
 */
export function deleteChapter(draft: Draft, key: ChapterKey): Draft {
  const chapter = draft.chapters.find((listed) => listed.key === key)
  if (chapter === undefined || chapter.deleted) {
    return draft
  }
  if (chapter.readName === null) {
    const orders = new Map(draft.orders)
    orders.delete(key)
    return {
      ...draft,
      chapters: draft.chapters.filter((listed) => listed.key !== key),
      orders,
    }
  }
  return withChapters(
    draft,
    draft.chapters.map((listed) => (listed.key === key ? { ...listed, deleted: true } : listed)),
  )
}

/** `draft` with the deleted chapter `key` back in its place. */
export function restoreChapter(draft: Draft, key: ChapterKey): Draft {
  return withChapters(
    draft,
    draft.chapters.map((chapter) =>
      chapter.key === key && chapter.deleted ? { ...chapter, deleted: false } : chapter,
    ),
  )
}

/**
 * `draft` with `identities` moved from chapter `from` to chapter `to`. Only the
 * clips `from` plays are moved, so a repeated call moves nothing. A clip that
 * returns to the chapter it was in when Edit mode opened goes back after its
 * original predecessors, as an undone removal does (`restoreClip`); these are
 * placed one by one in their original order, so a move and its reverse leave
 * nothing to save. The others join the end, in the order they had.
 */
export function moveClips(
  draft: Draft,
  from: ChapterKey,
  to: ChapterKey,
  identities: readonly string[],
  original: Orders,
): Draft {
  const source = draft.orders.get(from)
  const target = draft.orders.get(to)
  if (from === to || source === undefined || target === undefined) {
    return draft
  }
  const picked = new Set(identities)
  const moving = source.filter((identity) => picked.has(identity))
  if (moving.length === 0) {
    return draft
  }
  const home = original.get(to) ?? []
  const homeAt = new Map(home.map((identity, index) => [identity, index]))
  const returning = moving
    .filter((identity) => homeAt.has(identity))
    .sort((a, b) => (homeAt.get(a) ?? 0) - (homeAt.get(b) ?? 0))
  let orders: Orders = new Map(draft.orders).set(
    from,
    source.filter((identity) => !picked.has(identity)),
  )
  for (const identity of returning) {
    orders = restoreClip(orders, to, identity, home)
  }
  const joining = moving.filter((identity) => !homeAt.has(identity))
  orders = new Map(orders).set(to, [...(orders.get(to) ?? []), ...joining])
  return { ...draft, orders }
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
