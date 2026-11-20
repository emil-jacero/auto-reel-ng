import type { ClipStatus } from '../api/event.ts'
import { CLIP_STATUS_LABEL, EXCLUDED_LABEL, chapterHeading } from '../events/labels.ts'
import type { ChapterKey } from './draft.ts'

/*
 * What the inspector's Clip tab says of one selected clip, and what it offers
 * (`clip-tab-and-player`, design D5), from the draft alone: so it is the same with the track
 * open, in Prepare, or for a clip the track does not draw. Pure: no DOM, no React.
 */

/**
 * Where the draft has the clip:
 * - `played`: a chapter plays it (a New clip too);
 * - `ignored`: ignored in a chapter, not played;
 * - `missing`: missing from disk, still listed by its chapter;
 * - `removed`: a missing clip the operator removed, until Save.
 */
export type ClipState = 'played' | 'ignored' | 'missing' | 'removed'

/** The state of a clip, or null when the draft holds it in no chapter's list at all. */
export function clipState(facts: {
  status: ClipStatus
  played: boolean
  removed: boolean
}): ClipState | null {
  if (facts.removed) {
    return 'removed'
  }
  if (facts.status === 'ignored') {
    return 'ignored'
  }
  if (!facts.played) {
    return null
  }
  return facts.status === 'missing' ? 'missing' : 'played'
}

/** What the tab offers a clip in `state`. Trims, cuts and poster are the track's, not listed here. */
export type Offers = {
  /** Move earlier and Move later. */
  step: boolean
  /** Move to… and Rotate: a clip on disk that a chapter plays. */
  edits: boolean
  /** The one button of the tab's end: Ignore clip, Include clip, Remove from reel.yaml or Undo. */
  action: 'ignore' | 'include' | 'remove' | 'undo' | null
}

const OFFERS: Record<ClipState, Offers> = {
  played: { step: true, edits: true, action: 'ignore' },
  ignored: { step: false, edits: false, action: 'include' },
  missing: { step: true, edits: false, action: 'remove' },
  removed: { step: false, edits: false, action: 'undo' },
}

export const NOTHING_OFFERED: Offers = { step: false, edits: false, action: null }

export function offersOf(state: ClipState | null): Offers {
  return state === null ? NOTHING_OFFERED : OFFERS[state]
}

/** The status in words (the header's second line). */
export function statusWords(
  state: ClipState | null,
  clip: { status: ClipStatus; excluded?: boolean },
): string {
  switch (state) {
    case 'removed':
      return 'Removed from reel.yaml when you save.'
    case 'ignored':
      return 'Ignored: not in the movie'
    case 'missing':
      return CLIP_STATUS_LABEL.missing
    default:
      return clip.excluded === true
        ? `${EXCLUDED_LABEL}: not in the movie`
        : CLIP_STATUS_LABEL[clip.status]
  }
}

/** A chapter as the place words need it. */
export type PlaceChapter = { key: ChapterKey; name: string; deleted: boolean }

/** Where the draft puts a clip: its chapter's heading and, when a chapter plays it, its place. */
export type DraftPlace = { chapter: string; n: number | null; of: number | null }

/**
 * Where `identity` stands, from the draft's orders (the chapters it lists, in order). A clip a
 * chapter does not play (ignored, or removed) is placed in the chapter that lists it among
 * `elsewhere`, with no position. Null when no listed chapter holds it.
 */
export function draftPlace(
  chapters: readonly PlaceChapter[],
  orders: ReadonlyMap<ChapterKey, readonly string[]>,
  elsewhere: readonly ReadonlyMap<ChapterKey, readonly string[]>[],
  identity: string,
): DraftPlace | null {
  const listed = chapters.filter((chapter) => !chapter.deleted)
  const named = listed.some((chapter) => chapter.name !== '')
  const heading = (chapter: PlaceChapter) => chapterHeading(chapter.name, named)
  for (const chapter of listed) {
    const order = orders.get(chapter.key) ?? []
    const at = order.indexOf(identity)
    if (at !== -1) {
      return { chapter: heading(chapter), n: at + 1, of: order.length }
    }
  }
  for (const chapter of listed) {
    if (elsewhere.some((lists) => (lists.get(chapter.key) ?? []).includes(identity))) {
      return { chapter: heading(chapter), n: null, of: null }
    }
  }
  return null
}

/** "Kvällen · clip 1 of 2", or the chapter's heading alone for a clip no chapter plays. */
export function draftPlaceWords(place: DraftPlace): string {
  return place.n === null ? place.chapter : `${place.chapter} · clip ${place.n} of ${place.of}`
}

/** The clip's file name: an identity is a path relative to the event folder. */
function baseName(identity: string): string {
  return identity.slice(identity.lastIndexOf('/') + 1)
}

/** Said after a step inside a chapter, as the bin's Move up and Move down say it. */
export function stepWords(name: string, to: number, of: number): string {
  return `${name} moved to position ${to + 1} of ${of}.`
}

/**
 * Said after a step into another chapter, as Alt and an arrow say it: "Moved s1710003.mp4. Before
 * s1710001.mp4." into the next chapter, "Moved s1710003.mp4. At the end of Main." into the previous.
 */
export function stepAcrossWords(
  identity: string,
  heading: string,
  before: string | null,
): string {
  const where = before === null ? `At the end of ${heading}` : `Before ${baseName(before)}`
  return `Moved ${baseName(identity)}. ${where}.`
}

/** Said after Move to…: the clip is at the end of the chosen chapter, as a drop on its band says it. */
export function moveToEndWords(identity: string, heading: string): string {
  return `Moved ${baseName(identity)}. At the end of ${heading}.`
}
