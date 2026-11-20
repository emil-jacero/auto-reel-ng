import type { ChapterKey } from './draft.ts'

/*
 * Move earlier and Move later (`clip-tab-and-player`, design D6), as one pure rule. No DOM, no
 * React. A step goes over the chapter's listed clips, missing ones included and ignored ones not:
 * the bin's play order, as Move up and Move down. At a chapter's edge the clip goes where Alt and
 * an arrow put it (`stepSlot`, `applyDrop`): before the next chapter's first clip on disk, or
 * after the previous chapter's last clip on disk.
 */

/** A listed chapter and the clips it lists, in play order (missing included, ignored not). */
export type StepChapter = { key: ChapterKey; identities: readonly string[] }

/**
 * - `move`: a step inside `chapter`; `from` and `to` are indices in its order (`to` is the index
 *   the clip takes once it has left its old place: the lists' `moveClip` semantics).
 * - `clip-drop`: a step into another listed chapter; `at` is the gap index there (0 is before its
 *   first clip, its length is after the last) and `before` the clip on disk that then follows the
 *   moved one, null at the chapter's end: the one the announcement names.
 * - `edge`: no step; `words` give the reason.
 */
export type StepResult =
  | { kind: 'move'; chapter: ChapterKey; from: number; to: number }
  | { kind: 'clip-drop'; from: ChapterKey; to: ChapterKey; at: number; before: string | null }
  | { kind: 'edge'; words: string }

/** The clip's file name: an identity is a path relative to the event folder. */
function baseName(identity: string): string {
  return identity.slice(identity.lastIndexOf('/') + 1)
}

/** The edge reasons, named once for a caller and a test. First and last are Alt+Arrow's words. */
export const EDGE_WORDS = {
  missing: 'A missing clip stays in its chapter, so it cannot move past its first or last clip.',
  first: (identity: string) => `${baseName(identity)} is already the first clip.`,
  last: (identity: string) => `${baseName(identity)} is already the last clip.`,
} as const

/**
 * Where `identity` goes one step earlier (`way` -1) or later (1). A missing clip stays in its
 * chapter (it has no file to play in another), so at its edge it gets `edge`, as does the first
 * clip of the first listed chapter going earlier and the last of the last going later. `onDisk`
 * says which clips have a file: across a chapter edge only those count, as for Alt and an arrow.
 * Throws when no chapter lists `identity`.
 */
export function stepMove(
  chapters: readonly StepChapter[],
  identity: string,
  way: -1 | 1,
  onDisk: (identity: string) => boolean,
): StepResult {
  const at = chapters.findIndex((chapter) => chapter.identities.includes(identity))
  if (at === -1) {
    throw new Error(`${identity} is in no listed chapter`)
  }
  const own = chapters[at]
  const from = own.identities.indexOf(identity)
  const to = from + way
  if (to >= 0 && to < own.identities.length) {
    return { kind: 'move', chapter: own.key, from, to }
  }
  if (!onDisk(identity)) {
    return { kind: 'edge', words: EDGE_WORDS.missing }
  }
  const next = chapters[at + way]
  if (next === undefined) {
    const words = way === -1 ? EDGE_WORDS.first(identity) : EDGE_WORDS.last(identity)
    return { kind: 'edge', words }
  }
  if (way === -1) {
    // After the previous chapter's last clip on disk (before any clip after it that is missing).
    let last = next.identities.length - 1
    while (last >= 0 && !onDisk(next.identities[last])) {
      last -= 1
    }
    return { kind: 'clip-drop', from: own.key, to: next.key, at: last + 1, before: null }
  }
  // Before the next chapter's first clip on disk; with none, the start of its list.
  const first = next.identities.findIndex(onDisk)
  return {
    kind: 'clip-drop',
    from: own.key,
    to: next.key,
    at: Math.max(first, 0),
    before: first === -1 ? null : next.identities[first],
  }
}
