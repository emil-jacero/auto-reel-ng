// The edits of a set of clips (`clip-multi-select` D2): the set travels in the action, not in
// the editor's state. Pure: `EventEditor`'s reducer
// calls `selectionStep` and `selectionLabel`, and the tests drive them without React.

import type { Baseline, ChapterKey, Draft } from './draft.ts'
import {
  groupOf,
  ignoreClip,
  includeClip,
  isIgnoredNow,
  listedChapters,
  moveGroup,
  moveToEnd,
} from './draft.ts'

/**
 * The four actions that carry the clips they act on, and `onDisk`: whether a clip is on disk
 * (active or NEW). A missing clip stays in its chapter's order, so the order alone cannot tell the
 * reducer to leave it out; the dispatcher knows the clips and ships the rule, as `rotate` does.
 */
export type SelectionEdit = { onDisk: (identity: string) => boolean } & (
  // Move to…: the clips, in page order, at the end of `to`.
  | { type: 'selection-move'; identities: readonly string[]; to: ChapterKey }
  // A group drag released on the track: the clips as one run at gap `gap` of `to`.
  | { type: 'selection-drop'; identities: readonly string[]; dragged: string; to: ChapterKey; gap: number }
  // Ignore every clip of the set, out of the chapter that plays it.
  | { type: 'ignore-many'; identities: readonly string[] }
  // Include every ignored clip of the set (`plain-clip-bin` D5), each at the end of the chapter
  // that lists it as ignored (`chapterOf`), in the order of `identities` (the bin's).
  | { type: 'include-many'; identities: readonly string[]; chapterOf: (identity: string) => ChapterKey | undefined }
)

/** What an Include clips that includes nothing says (no clip ignored, or its chapter deleted). */
export const NOTHING_INCLUDED = 'Nothing included.'

/** What a selection edit reads and writes of the editor's state. */
export type SelectionTarget = {
  baseline: Baseline
  draft: Draft
  lastMoved: string | null
}

const clipName = (identity: string): string => identity.slice(identity.lastIndexOf('/') + 1)

function listedKeys(draft: Draft): ChapterKey[] {
  return listedChapters(draft.chapters).map((chapter) => chapter.key)
}

/** The set's clips that are on disk, as a set. */
const wanted = (action: SelectionEdit): ReadonlySet<string> =>
  new Set(action.identities.filter(action.onDisk))

/**
 * The clips of an `include-many` that it includes, in the action's order, each with the chapter
 * it goes back into: on disk, ignored now, and listed by a chapter the draft keeps.
 */
export function includedBy(
  target: Pick<SelectionTarget, 'baseline' | 'draft'>,
  action: Extract<SelectionEdit, { type: 'include-many' }>,
): { identity: string; chapter: ChapterKey }[] {
  const kept = new Set(listedKeys(target.draft))
  const found: { identity: string; chapter: ChapterKey }[] = []
  for (const identity of new Set(action.identities)) {
    const chapter = action.chapterOf(identity)
    if (
      action.onDisk(identity) &&
      chapter !== undefined &&
      kept.has(chapter) &&
      isIgnoredNow(target.baseline, target.draft, identity)
    ) {
      found.push({ identity, chapter })
    }
  }
  return found
}

/**
 * `target` after the edit, or `target` itself when nothing changes. A clip that is not on disk
 * (missing) or that no listed chapter plays (ignored, removed, or unknown) is left out, so a stale
 * set can never move or ignore a clip it should not.
 */
export function selectionStep<T extends SelectionTarget>(target: T, action: SelectionEdit): T {
  const { draft } = target
  switch (action.type) {
    case 'selection-move': {
      const result = moveToEnd(draft, listedKeys(draft), wanted(action), action.to)
      return result.draft === draft
        ? target
        : { ...target, draft: result.draft, lastMoved: null }
    }
    case 'selection-drop': {
      const keys = listedKeys(draft)
      const group = groupOf(draft.orders, keys, wanted(action))
      if (group.length === 0 || !keys.includes(action.to)) {
        return target
      }
      const next = moveGroup(draft, group, action.to, action.gap)
      return next === draft
        ? target
        : { ...target, draft: next, lastMoved: action.dragged }
    }
    case 'ignore-many': {
      const set = wanted(action)
      let next = draft
      for (const key of listedKeys(draft)) {
        for (const identity of draft.orders.get(key) ?? []) {
          if (set.has(identity)) {
            next = ignoreClip(target.baseline, next, key, identity)
          }
        }
      }
      return next === draft ? target : { ...target, draft: next }
    }
    case 'include-many': {
      let next = draft
      for (const { identity, chapter } of includedBy(target, action)) {
        next = includeClip(target.baseline, next, chapter, identity, next.orders.get(chapter)?.length ?? 0)
      }
      return next === draft ? target : { ...target, draft: next }
    }
  }
}

/**
 * The step's name for Undo and Redo: "move of 3 clips", "ignore of a1.mp4", "include of 2 clips".
 * `before` is the state acted on.
 */
export function selectionLabel(
  action: SelectionEdit,
  before: Pick<SelectionTarget, 'baseline' | 'draft'>,
): string {
  if (action.type === 'include-many') {
    const found = includedBy(before, action)
    return found.length === 1
      ? `include of ${clipName(found[0]?.identity ?? '')}`
      : `include of ${found.length} clips`
  }
  const keys = listedKeys(before.draft)
  const group = groupOf(before.draft.orders, keys, wanted(action))
  const what = action.type === 'ignore-many' ? 'ignore' : 'move'
  return group.length === 1 ? `${what} of ${clipName(group[0])}` : `${what} of ${group.length} clips`
}
