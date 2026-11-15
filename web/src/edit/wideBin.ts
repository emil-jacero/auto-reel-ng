import { useSyncExternalStore } from 'react'

import type { ChapterKey, DraftChapter } from './draft'

/*
 * The clip bin from 960 px (compact-bin-tools D6): the clips the event ignores leave their
 * chapters and are listed together after the last chapter, so the rows of the clips a chapter
 * plays use the pane's height. Below 960 px the page is stacked and each chapter lists its
 * ignored clips as before. `ignoredGroups` is pure; `useWideBin` reads the window.
 */

/** The width from which the bin is a pane of the workspace beside the viewer. */
export const WIDE_BIN = '(width >= 960px)'

function subscribeWide(listener: () => void): () => void {
  const query = window.matchMedia(WIDE_BIN)
  query.addEventListener('change', listener)
  return () => query.removeEventListener('change', listener)
}

/** Whether the window is at least 960 CSS pixels wide, kept current. */
export function useWideBin(): boolean {
  return useSyncExternalStore(subscribeWide, () => window.matchMedia(WIDE_BIN).matches)
}

/** One chapter's ignored clips, for the block after the chapters. */
export type IgnoredGroup = {
  key: ChapterKey
  /** The chapter's name now (`''` for the event's own chapter). */
  name: string
  /** The chapter's heading (`Main`, `Clips` or its name), for the caption. */
  heading: string
  /** The identities, in the order the chapter lists them. */
  identities: readonly string[]
}

/**
 * The ignored clips by chapter, in the chapters' order: a deleted chapter is skipped and a
 * chapter with none is left out. `[]` when the event ignores no clip.
 */
export function ignoredGroups(
  chapters: readonly Pick<DraftChapter, 'key' | 'name' | 'deleted'>[],
  ignoredOf: ReadonlyMap<ChapterKey, readonly string[]>,
  headingOf: (name: string) => string,
): IgnoredGroup[] {
  const groups: IgnoredGroup[] = []
  for (const chapter of chapters) {
    const identities = ignoredOf.get(chapter.key) ?? []
    if (!chapter.deleted && identities.length > 0) {
      groups.push({
        key: chapter.key,
        name: chapter.name,
        heading: headingOf(chapter.name),
        identities,
      })
    }
  }
  return groups
}
