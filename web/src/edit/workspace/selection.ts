/*
 * The workspace's one selection (`editor-selection`, design D1), as pure rules: nothing, one clip
 * or a set of clips, a cut, a title card or a suggestion. Setting a new one replaces the old, so at
 * most one thing (or one set of clips) is ever selected. No DOM, no React.
 */

import type { TabId } from '../card/tabs.ts'
import type { ChapterKey, DraftCut } from '../draft'

export type Selection =
  | { kind: 'none' }
  /** One clip: every single-clip reader is unchanged. */
  | { kind: 'clip'; identity: string }
  /**
   * Two or more clips, in press order (a range in `order`). `anchor` is the clip a Shift press
   * ranges from (the clip pressed last without Shift), `last` the clip pressed last. Never fewer
   * than two identities: `pressClip` and `keptSelection` normalise a set of one to `clip` and an
   * empty one to `none`.
   */
  | { kind: 'clips'; identities: readonly string[]; anchor: string; last: string }
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
    case 'clips': {
      const kept = sel.identities.filter((identity) => world.clips.has(identity))
      if (kept.length === sel.identities.length) {
        return sel
      }
      return clipsOf(kept, sel.anchor, world.clips.has(sel.last) ? sel.last : (kept[kept.length - 1] ?? sel.last))
    }
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
    case 'clips':
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
    case 'clips':
      return (
        b.kind === 'clips' &&
        b.anchor === a.anchor &&
        b.last === a.last &&
        b.identities.length === a.identities.length &&
        b.identities.every((identity, index) => identity === a.identities[index])
      )
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
    ((sel.kind === 'clip' || sel.kind === 'clips') && part.clips !== undefined) ||
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
 * The selection of `identities`, normalised: none for none, `clip` for one, else `clips` with the
 * given anchor and last clip (a clip alone is its own anchor).
 */
function clipsOf(identities: readonly string[], anchor: string, last: string): Selection {
  if (identities.length === 0) {
    return NO_SELECTION
  }
  if (identities.length === 1) {
    return { kind: 'clip', identity: identities[0] as string }
  }
  return { kind: 'clips', identities, anchor, last }
}

/** How a press on a clip changes the selection: replaces it, adds or takes out, or ranges from the anchor. */
export type Press = 'alone' | 'toggle' | 'range'

/**
 * The selection after a press on `identity`. `alone` selects it only. `toggle` (Ctrl or Cmd) adds
 * it to the clips selected, or takes it out when it was one of them; from a cut, a card, a
 * suggestion or nothing it starts a set of the clip alone. `range` (Shift) selects the clips of
 * `order` (the drawn order on the track, the bin's rows in the bin) from the anchor to the clip,
 * keeping the anchor. A range whose anchor is not in `order` (it left the track), or from a
 * selection without one, is the clip alone.
 */
export function pressClip(
  sel: Selection,
  identity: string,
  press: Press,
  order: readonly string[],
): Selection {
  const alone: Selection = { kind: 'clip', identity }
  const held = selectedClips(sel)
  switch (press) {
    case 'alone':
      return alone
    case 'toggle': {
      const next = held.includes(identity)
        ? held.filter((candidate) => candidate !== identity)
        : [...held, identity]
      return clipsOf(next, identity, identity)
    }
    case 'range': {
      const anchor = sel.kind === 'clip' ? sel.identity : sel.kind === 'clips' ? sel.anchor : null
      const from = anchor === null ? -1 : order.indexOf(anchor)
      const to = order.indexOf(identity)
      if (anchor === null || from < 0 || to < 0) {
        return alone
      }
      return clipsOf(order.slice(Math.min(from, to), Math.max(from, to) + 1), anchor, identity)
    }
  }
}

/** The clips the selection holds: none, one, or the set. A cut is not a clip selection. */
export function selectedClips(sel: Selection): readonly string[] {
  switch (sel.kind) {
    case 'clip':
      return [sel.identity]
    case 'clips':
      return sel.identities
    default:
      return []
  }
}

/** The clip pressed last, or null when no clip is selected. */
export function lastClip(sel: Selection): string | null {
  switch (sel.kind) {
    case 'clip':
      return sel.identity
    case 'clips':
      return sel.last
    default:
      return null
  }
}

/**
 * What the selection's polite status says for the change from `was` to `now` (design D6), or null
 * when it says nothing new: a change to a set is the count ("3 clips selected."), and a set that
 * gains or loses exactly one clip names it first ("s1710003.mp4 added. 3 clips selected."). A set
 * of two that loses one, which is then the clip alone, still names it ("s1710003.mp4 taken out. 1
 * clip selected."). Any other change to one clip or to another kind keeps today's words, which
 * are none.
 */
export function selectionWords(
  was: Selection,
  now: Selection,
  nameOf: (identity: string) => string,
): string | null {
  const before = selectedClips(was)
  const after = selectedClips(now)
  if (after.length < 1 || (now.kind !== 'clips' && !(was.kind === 'clips' && before.length === 2))) {
    return null
  }
  const count = after.length === 1 ? '1 clip selected.' : `${after.length} clips selected.`
  if (before.length === after.length && before.every((identity) => after.includes(identity))) {
    return null
  }
  if (before.length > 0 && after.length === before.length + 1 && before.every((i) => after.includes(i))) {
    const added = after.find((identity) => !before.includes(identity))
    return added === undefined ? count : `${nameOf(added)} added. ${count}`
  }
  if (before.length > 0 && after.length === before.length - 1 && after.every((i) => before.includes(i))) {
    const out = before.find((identity) => !after.includes(identity))
    return out === undefined ? count : `${nameOf(out)} taken out. ${count}`
  }
  return now.kind === 'clips' ? count : null
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
  opened: { tab: TabId | null; focus: boolean } | null
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
  const kept = keptIn(was.sel, part)
  if (kept === was.sel) {
    return was
  }
  // A set that lost some of its clips stays, with the rest.
  return kept.kind === 'none' ? clearState(was) : { ...was, sel: kept, opened: null }
}

/**
 * Selects the card and asks to see its editor, also when it is selected; on `tab` if given. Every
 * request counts as a press (`again`): opening a card asks to see it, so a hand-picked inspector
 * tab gives way and focus goes into the editor again. `focus` false shows the editor and leaves
 * focus where it is: a press on the card's block on the track.
 */
export function openState(
  was: SelectionState,
  chapter: ChapterKey,
  tab?: TabId,
  focus = true,
): SelectionState {
  return { sel: { kind: 'card', chapter }, opened: { tab: tab ?? null, focus }, again: was.again + 1 }
}

/**
 * The request to see the selected card has been handled (its tab shown, focus moved): it ends, so
 * a remount of the editor (a layout switch) does not take focus again. The selection stays.
 */
export function consumeState(was: SelectionState): SelectionState {
  return was.opened === null ? was : { ...was, opened: null }
}
