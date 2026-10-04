/*
 * The chapter header bar's Edit Titlecard button (`edit-mode-declutter`), as pure words and
 * state: the same for the event's own chapter and every other, a draft-added one included.
 * The button is the page-level handle of the chapter's card: it shares the card selection with
 * the Timeline's blocks and opens the card dialog. No DOM, no React.
 */

/** The button's visible words. */
export const EDIT_TITLECARD = 'Edit Titlecard'

/** The button's accessible name: it names the chapter by its heading (Main and Clips included). */
export function editTitlecardName(heading: string): string {
  return `Edit title card for ${heading}`
}

/**
 * The selection id of a chapter: the name it was read with (`""` is the event's own chapter),
 * or for a chapter added in this Edit mode, which has no saved card, an id of its draft key.
 */
export function cardIdOf(chapter: { readName: string | null; key: string }): string {
  return chapter.readName ?? `\u0000added:${chapter.key}`
}

/** What the button shows and does now. */
export type BarButton = {
  /** The card is selected (`aria-pressed`). */
  pressed: boolean
  /** A save or a move is pending: the button says so and opens nothing. */
  unavailable: boolean
}

export function barButton(selected: string | null, id: string, locked: boolean): BarButton {
  return { pressed: selected === id, unavailable: locked }
}

/** A chapter's section content: its header bar and its clips; the notes are the only thing between. */
export type BarContent = { name: string; button: string; count: string; editsName: false }

export function barContent(heading: string, clips: number): BarContent {
  return {
    name: heading,
    button: editTitlecardName(heading),
    count: `${clips} ${clips === 1 ? 'clip' : 'clips'}`,
    editsName: false,
  }
}
