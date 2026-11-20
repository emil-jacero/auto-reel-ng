import type { ChapterKey } from "./draft.ts";

/*
 * Move earlier and Move later (`clip-tab-and-player`, design D6), as one pure rule. No DOM, no
 * React. A step goes over the chapter's listed clips, missing ones included and ignored ones not:
 * the bin's play order, as Move up and Move down. At a chapter's edge the clip goes to the end of
 * the previous listed chapter, or the start of the next, as Alt and an arrow do.
 */

/** A listed chapter and the clips it lists, in play order (missing included, ignored not). */
export type StepChapter = { key: ChapterKey; identities: readonly string[] };

/**
 * - `move`: a step inside `chapter`; `from` and `to` are indices in its order (`to` is the index
 *   the clip takes once it has left its old place: the lists' `moveClip` semantics).
 * - `clip-drop`: a step into another listed chapter; `at` is the gap index there (0 is before its
 *   first clip, its length is after the last).
 * - `edge`: no step; `words` give the reason.
 */
export type StepResult =
  | { kind: "move"; chapter: ChapterKey; from: number; to: number }
  | { kind: "clip-drop"; from: ChapterKey; to: ChapterKey; at: number }
  | { kind: "edge"; words: string };

/** The edge reasons, so a caller and a test name them once. */
export const EDGE_WORDS = {
  missing:
    "A missing clip stays in its chapter, so it cannot move past its first or last clip.",
  first: "This is the first clip of the event.",
  last: "This is the last clip of the event.",
} as const;

/**
 * Where `identity` goes one step earlier (`way` -1) or later (1). A missing clip stays in its
 * chapter (it has no file to play in another), so at its edge it gets `edge`, as does the first
 * clip of the first listed chapter going earlier and the last of the last going later. Throws when
 * no chapter lists `identity`.
 */
export function stepMove(
  chapters: readonly StepChapter[],
  identity: string,
  way: -1 | 1,
  missing: boolean,
): StepResult {
  const at = chapters.findIndex((chapter) =>
    chapter.identities.includes(identity),
  );
  if (at === -1) {
    throw new Error(`${identity} is in no listed chapter`);
  }
  const own = chapters[at];
  const from = own.identities.indexOf(identity);
  const to = from + way;
  if (to >= 0 && to < own.identities.length) {
    return { kind: "move", chapter: own.key, from, to };
  }
  if (missing) {
    return { kind: "edge", words: EDGE_WORDS.missing };
  }
  const next = chapters[at + way];
  if (next === undefined) {
    return {
      kind: "edge",
      words: way === -1 ? EDGE_WORDS.first : EDGE_WORDS.last,
    };
  }
  return {
    kind: "clip-drop",
    from: own.key,
    to: next.key,
    at: way === -1 ? next.identities.length : 0,
  };
}
