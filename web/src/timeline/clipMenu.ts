import type { Selection } from '../edit/workspace/selection.ts'
import type { ChapterKey } from '../edit/draft.ts'
import type { Way } from '../rotate/turn.ts'

/*
 * The clip menu's items (`clip-context-menu`, design D2), as pure rules: which items a clip's menu
 * lists, in what order and groups, and which of them cannot act now and why. Every item is an
 * existing guarded draft edit; this module decides only what is listed and what is said. No DOM,
 * no React.
 */

export type ClipAction =
  | { kind: 'rotate'; way: Way }
  | { kind: 'cut' }
  | { kind: 'poster' }
  | { kind: 'move'; chapter: ChapterKey; name: string }
  | { kind: 'ignore' }

export type ClipMenuItem = {
  action: ClipAction
  label: string
  /** Items of one group sit together; a separator goes between groups. */
  group: 0 | 1 | 2 | 3
  /** Why the item cannot act now, or null when it can. */
  why: string | null
}

export type ClipMenuFacts = {
  /** `EditBinding.locked`: a save or a move of marked clips is pending. */
  locked: boolean
  /** `cutAtPlayhead`'s refusal now, or null. */
  cutWhy: string | null
  /** `posterWhyFor(clip)` now, or null. */
  posterWhy: string | null
  /** The chapters the Timeline draws but the clip's own, in their order. */
  others: readonly { key: ChapterKey; name: string }[]
}

export const MENU_LOCKED = 'Clip edits wait for the save or the move of marked clips to finish.'

/** The menu's lock note (while locked) and its items, in order. */
export function clipMenu(facts: ClipMenuFacts): { note: string | null; items: ClipMenuItem[] } {
  const lock = facts.locked ? MENU_LOCKED : null
  const item = (
    action: ClipAction,
    label: string,
    group: ClipMenuItem['group'],
    why: string | null = null,
  ): ClipMenuItem => ({ action, label, group, why: lock ?? why })
  return {
    note: lock,
    items: [
      item({ kind: 'rotate', way: 'left' }, 'Rotate left', 0),
      item({ kind: 'rotate', way: 'right' }, 'Rotate right', 0),
      item({ kind: 'cut' }, 'Cut at playhead', 1, facts.cutWhy),
      item({ kind: 'poster' }, 'Use frame as poster', 1, facts.posterWhy),
      ...facts.others.map((c) =>
        item({ kind: 'move', chapter: c.key, name: c.name }, `Move to ${c.name}`, 2),
      ),
      item({ kind: 'ignore' }, 'Ignore clip', 3),
    ],
  }
}

/**
 * Whether opening a clip's menu selects the clip: false when the clip, or a cut of it, is
 * selected already (a right-click on a clip keeps its cut selected), true for nothing, another
 * clip, a card or a suggestion.
 */
export function menuSelects(selection: Selection, identity: string): boolean {
  return !((selection.kind === 'clip' || selection.kind === 'cut') && selection.identity === identity)
}

/** The clip that takes focus when this one leaves the track: the next drawn, else the previous. */
export function focusAfter(drawn: readonly string[], identity: string): string | null {
  const at = drawn.indexOf(identity)
  if (at < 0) return null
  return drawn[at + 1] ?? drawn[at - 1] ?? null
}
