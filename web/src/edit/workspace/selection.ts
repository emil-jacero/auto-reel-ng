/*
 * The workspace's one selection (`editor-selection`, design D1), as pure rules: nothing, a clip,
 * a cut, a title card or a suggestion. Setting a new one replaces the old, so at most one thing
 * is ever selected. No DOM, no React.
 */

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
