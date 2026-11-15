/*
 * The workspace's one selection (`editor-selection`, design D1), as pure rules: nothing, a clip,
 * a cut, a title card or a suggestion. Setting a new one replaces the old, so at most one thing
 * is ever selected. No DOM, no React.
 */

import type { TabId } from '../card/tabs.ts'
import type { ChapterKey, DraftCut } from '../draft'

export type Selection =
  | { kind: 'none' }
  | { kind: 'clip'; identity: string }
  | { kind: 'cut'; identity: string; key: string }
  | { kind: 'card'; chapter: ChapterKey }
  | { kind: 'suggestion'; id: string }

export const NO_SELECTION: Selection = { kind: 'none' }

/** What the event holds now (the draft's, in Edit mode), as far as a selection's target goes. */
export type World = {
  /** Identities of the clips the event lists. */
  clips: ReadonlySet<string>
  /** Identity → its cuts as listed; a removed cut is gone. */
  cuts: ReadonlyMap<string, readonly Pick<DraftCut, 'key' | 'removed'>[]>
  /** Keys of the chapters the draft lists, deleted ones left out. */
  chapters: ReadonlySet<ChapterKey>
  /** Ids of the suggestions the last read lists. */
  suggestions: ReadonlySet<string>
}

/** The selection after a Refresh, a Save or an edit: itself while its target stands, else none. */
export function keptSelection(sel: Selection, world: World): Selection {
  switch (sel.kind) {
    case 'none':
      return sel
    case 'clip':
      return world.clips.has(sel.identity) ? sel : NO_SELECTION
    case 'cut': {
      const cut = world.cuts.get(sel.identity)?.find((c) => c.key === sel.key)
      return cut !== undefined && !cut.removed ? sel : NO_SELECTION
    }
    case 'card':
      return world.chapters.has(sel.chapter) ? sel : NO_SELECTION
    case 'suggestion':
      return world.suggestions.has(sel.id) ? sel : NO_SELECTION
  }
}

/** The inspector tab a selection shows: a cut is edited in its clip's tab; nothing shows Event. */
export function inspectorTab(sel: Selection): 'clip' | 'card' | 'suggestion' | 'event' {
  switch (sel.kind) {
    case 'clip':
    case 'cut':
      return 'clip'
    case 'card':
      return 'card'
    case 'suggestion':
      return 'suggestion'
    case 'none':
      return 'event'
  }
}

/** Whether two selections name the same target (a setter keeps the old object when they do). */
export function sameSelection(a: Selection, b: Selection): boolean {
  switch (a.kind) {
    case 'none':
      return b.kind === 'none'
    case 'clip':
      return b.kind === 'clip' && b.identity === a.identity
    case 'cut':
      return b.kind === 'cut' && b.identity === a.identity && b.key === a.key
    case 'card':
      return b.kind === 'card' && b.chapter === a.chapter
    case 'suggestion':
      return b.kind === 'suggestion' && b.id === a.id
  }
}

/**
 * `keptSelection` for a caller that knows only part of the world (the draft's chapters, or the
 * drawn marks): a selection of a kind the part says nothing about is kept as it is.
 */
export function keptIn(sel: Selection, part: Partial<World>): Selection {
  const knows =
    (sel.kind === 'clip' && part.clips !== undefined) ||
    (sel.kind === 'cut' && part.cuts !== undefined) ||
    (sel.kind === 'card' && part.chapters !== undefined) ||
    (sel.kind === 'suggestion' && part.suggestions !== undefined)
  if (!knows) {
    return sel
  }
  return keptSelection(sel, {
    clips: new Set(),
    cuts: new Map(),
    chapters: new Set(),
    suggestions: new Set(),
    ...part,
  })
}

/**
 * The selection with the request that showed its card (`opened`: the Edit Titlecard button, a card
 * block or the Event tab's button asked to see the editor, on `tab` if given, with focus in its
 * first field; a card is also selected by a duration handle, which asks nothing), and a
 * count (`again`) of the requests to see the target again: a press on the clip that was already
 * selected (the track scrolls back to it) or the opening of a card (a hand-picked inspector tab
 * gives way).
 */
export type SelectionState = {
  sel: Selection
  opened: { tab: TabId | null } | null
  again: number
}

export const NOTHING: SelectionState = { sel: NO_SELECTION, opened: null, again: 0 }

/** Selects `next`, which ends whatever was selected (and its request); the same target changes nothing. */
export function selectState(was: SelectionState, next: Selection): SelectionState {
  if (!sameSelection(was.sel, next)) {
    return { sel: next, opened: null, again: was.again }
  }
  // Pressing the selected clip again asks to see it; any other kind is already shown.
  return next.kind === 'clip' ? { ...was, again: was.again + 1 } : was
}

/** Nothing is selected. */
export function clearState(was: SelectionState): SelectionState {
  return was.sel.kind === 'none' && was.opened === null ? was : { ...NOTHING, again: was.again }
}

/** The selection ends when its target is gone from `part` of the world. */
export function keepState(was: SelectionState, part: Partial<World>): SelectionState {
  return keptIn(was.sel, part) === was.sel ? was : clearState(was)
}

/**
 * Selects the card and asks to see its editor, also when it is selected; on `tab` if given. Every
 * request counts as a press (`again`): opening a card asks to see it, so a hand-picked inspector
 * tab gives way and focus goes into the editor again.
 */
export function openState(was: SelectionState, chapter: ChapterKey, tab?: TabId): SelectionState {
  return { sel: { kind: 'card', chapter }, opened: { tab: tab ?? null }, again: was.again + 1 }
}
