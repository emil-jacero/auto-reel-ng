import type { CardSpec } from '../../timeline/cards.ts'
import type { CardDraft, CardField } from './model.ts'
import type { EventStyle } from './specs.ts'

/*
 * What Edit mode gives the inspector (`title-card-inspector`): the draft's cards to show and a
 * way to change one, by the card's chapter as the page saved it (the selection's key). Types
 * only, as `timeline/editing.ts` is for the Timeline.
 */

/** The selected card as the draft has it. */
export type CardView = {
  /** The chapter's key in the draft. */
  key: string
  /** The chapter's name now (a rename moves it; the selection keeps the saved one). */
  name: string
  /** The event's own chapter, whose card opens the movie. */
  opening: boolean
  /** The overrides now, and as read. */
  card: CardDraft
  read: CardDraft
  /** The draft event title and the one the page resolved from the folder name (an empty title follows it). */
  eventTitle: string
  folderTitle: string | null
  /** The service's refusal of the last save for this card, and the field it names. */
  refusal: { field: CardField | null; message: string } | null
}

export type CardEditing = {
  /** Each chapter's card as the draft would have it drawn: the Timeline's blocks and the rows use these. */
  specs: readonly CardSpec[]
  /** The event-wide style an unset field inherits, the draft's edits laid over the saved; null when unknown. */
  style: EventStyle | null
  styleError: string | null
  /** The draft event style as a save would write it (`look.title_card`) while it is not the saved one; else none. */
  previewStyle: { [key: string]: unknown } | undefined
  /** The card of the chapter saved as `saved`; null when the draft has no such card to edit. */
  view(saved: string): CardView | null
  set<F extends CardField>(saved: string, field: F, value: CardDraft[F]): void
  /** Put the card back as read. */
  reset(saved: string): void
  announce(words: string): void
  /** The Title cards switch while it differs from the state read (true: on); null: as the service said. */
  titleCardsDraft: boolean | null
  /** A save is in flight, or a move of marked clips is pending. */
  locked: boolean
}
