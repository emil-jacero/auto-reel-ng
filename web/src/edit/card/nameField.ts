import { NAME_REFUSAL, stripLikePython } from '../chapterNames.ts'
import { decideName } from '../inlineName.ts'
import type { NameCheck } from '../inlineName.ts'

/*
 * The editor's Name field (`edit-mode-declutter`), as pure rules over the existing name rules:
 * `chapterNames.checkName` decides what a chapter may be called and `inlineName.decideName`
 * whether typing changes anything; nothing is re-implemented here. The field writes every
 * accepted name to the draft as it is typed, holds a refused one in the field with the refusal
 * in words, announces a rename once when it settles, and tells why when a refused name is left
 * behind. For the event's own chapter the name is the event's title, which any text may be.
 */

/** The event's title: any text is kept as typed, as the Details form keeps it. */
export function anyTitle(typed: string): NameCheck {
  return { ok: true, name: typed }
}

/** What typing a name does to the draft. */
export type NameStep =
  | { kind: 'write'; name: string }
  | { kind: 'same' }
  | { kind: 'refused'; words: string }

/** Write, ignore or refuse `typed` for a name that is `current` in the draft now. */
export function nameStep(
  typed: string,
  current: string,
  check: (typed: string) => NameCheck,
): NameStep {
  const decision = decideName(typed, current, check)
  switch (decision.kind) {
    case 'keep':
      return { kind: 'write', name: decision.name }
    case 'unchanged':
      return { kind: 'same' }
    case 'refused':
      return { kind: 'refused', words: NAME_REFUSAL[decision.refusal](decision.clash ?? '') }
  }
}

/**
 * What the live region says once when the field settles (Enter is pressed, focus leaves it, or the
 * selection leaves the card): a rename from the name the field opened or last settled with, or nothing when the
 * name is the same (typing the old name back is no edit). `notes` follows a chapter's words.
 */
export function settleWords(
  kind: 'chapter' | 'event',
  settledWith: string,
  now: string,
  notes = '',
): string | null {
  if (kind === 'chapter') {
    return stripLikePython(settledWith) === stripLikePython(now)
      ? null
      : `“${settledWith}” renamed to “${now}”.${notes}`
  }
  if (settledWith === now) {
    return null
  }
  return now.trim() === ''
    ? 'Title cleared. It inherits from the folder name.'
    : `Title set to “${now.trim()}”.`
}

/** What is said when a refused name is left behind (Escape, another selection): the draft keeps the last accepted one. */
export function notChangedWords(refusal: string | null): string | null {
  return refusal === null ? null : `Name not changed. ${refusal}`
}

/**
 * What a change of the name in the draft means to the field: `none` (it did not change), `own`
 * (the field wrote it as typed) or `external` (Undo changes to this card, the Details form's
 * Title: the field shows it).
 */
export function draftChange(
  seen: string,
  now: string,
  written: string | null,
): 'none' | 'own' | 'external' {
  if (seen === now) {
    return 'none'
  }
  return written === now ? 'own' : 'external'
}

/** The Name field's accessible name. */
export function nameLabel(opening: boolean, name: string): string {
  return opening ? 'Title of the event' : `Name of chapter ${name}`
}

/**
 * The card's own title (`card.title`) is shown, as "Card title (overrides the name)", only for
 * a card whose draft has one; nothing adds one.
 */
export function cardTitleShown(card: { title: string | null }): boolean {
  return card.title !== null
}
