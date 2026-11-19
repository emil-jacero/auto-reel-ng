import { selectedClips } from '../edit/workspace/selection.ts'
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
  /**
   * The chapters Move to lists, in their order: the ones the Timeline draws but the clip's own for
   * one clip, every chapter it draws for several (`clip-multi-select` D7).
   */
  others: readonly { key: ChapterKey; name: string }[]
  /** The clips the menu acts on (`targets`): one, or two or more selected clips. */
  targets: readonly string[]
}

export const MENU_LOCKED = 'Clip edits wait for the save or the move of several clips to finish.'
export const CUT_ONE_WHY = 'Select one clip to cut at the playhead.'
export const POSTER_ONE_WHY = 'Select one clip to use a frame as poster.'

/**
 * The clips a menu opened on `identity` acts on (`clip-multi-select` D7): the selected clips, in
 * the order `drawn` gives, when it is one of two or more of them, else the clip alone.
 */
export function targets(
  selection: Selection,
  identity: string,
  drawn: readonly string[],
): string[] {
  const selected = new Set(selectedClips(selection))
  if (selected.size > 1 && selected.has(identity)) {
    const run = drawn.filter((id) => selected.has(id))
    if (run.length > 1 && run.includes(identity)) {
      return run
    }
  }
  return [identity]
}

/**
 * The menu's title when it acts on several clips ("3 clips"), else null: the clip's own name
 * heads it.
 */
export function menuTitle(count: number): string | null {
  return count > 1 ? `${count} clips` : null
}

/** The menu's title for several clips, its lock note (while locked) and its items, in order. */
export function clipMenu(facts: ClipMenuFacts): {
  title: string | null
  note: string | null
  items: ClipMenuItem[]
} {
  const lock = facts.locked ? MENU_LOCKED : null
  const many = facts.targets.length > 1
  const item = (
    action: ClipAction,
    label: string,
    group: ClipMenuItem['group'],
    why: string | null = null,
  ): ClipMenuItem => ({ action, label, group, why: lock ?? why })
  return {
    title: menuTitle(facts.targets.length),
    note: lock,
    items: [
      item({ kind: 'rotate', way: 'left' }, 'Rotate left', 0),
      item({ kind: 'rotate', way: 'right' }, 'Rotate right', 0),
      item({ kind: 'cut' }, 'Cut at playhead', 1, many ? CUT_ONE_WHY : facts.cutWhy),
      item({ kind: 'poster' }, 'Use frame as poster', 1, many ? POSTER_ONE_WHY : facts.posterWhy),
      ...facts.others.map((c) =>
        item({ kind: 'move', chapter: c.key, name: c.name }, `Move to ${c.name}`, 2),
      ),
      item({ kind: 'ignore' }, many ? `Ignore ${facts.targets.length} clips` : 'Ignore clip', 3),
    ],
  }
}

/**
 * Whether opening a clip's menu selects the clip: false when the clip, or a cut of it, is
 * selected already, alone or as one of several (a right-click on a clip keeps its cut, or its set,
 * selected), true for nothing, another clip, a card or a suggestion.
 */
export function menuSelects(selection: Selection, identity: string): boolean {
  if (selection.kind === 'clips') {
    return !selection.identities.includes(identity)
  }
  return !((selection.kind === 'clip' || selection.kind === 'cut') && selection.identity === identity)
}

/** The clip that takes focus when this one leaves the track: the next drawn, else the previous. */
export function focusAfter(drawn: readonly string[], identity: string): string | null {
  const at = drawn.indexOf(identity)
  if (at < 0) return null
  return drawn[at + 1] ?? drawn[at - 1] ?? null
}

/** What `menuOpenKey` reads of a keydown. */
export type OpenPress = { key: string; shiftKey: boolean; ctrlKey: boolean; altKey: boolean; metaKey: boolean }

/** Whether a keydown on a clip's block asks for its menu: Shift+F10 (alone) or the Menu key. */
export function menuOpenKey(press: OpenPress): boolean {
  if (press.key === 'ContextMenu') {
    return true
  }
  return press.key === 'F10' && press.shiftKey && !press.ctrlKey && !press.altKey && !press.metaKey
}

/**
 * The clip that takes focus when a group of clips leaves the track (`clip-multi-select` D7): the
 * one drawn after the last target, else the nearest one before it that stays.
 */
export function focusAfterMany(drawn: readonly string[], targets: readonly string[]): string | null {
  const gone = new Set(targets)
  let last = -1
  drawn.forEach((identity, at) => {
    if (gone.has(identity)) {
      last = at
    }
  })
  if (last < 0) {
    return null
  }
  for (let at = last + 1; at < drawn.length; at += 1) {
    if (!gone.has(drawn[at] as string)) {
      return drawn[at] as string
    }
  }
  for (let at = last - 1; at >= 0; at -= 1) {
    if (!gone.has(drawn[at] as string)) {
      return drawn[at] as string
    }
  }
  return null
}
