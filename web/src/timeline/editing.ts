import type { ClipCuts, ClipTurns } from '../cuts/ReadCuts'
import type { CutKey, DraftCut } from '../edit/draft'
import type { ClipPreviews } from '../preview/previews'
import type { PosterPick } from '../edit/poster.ts'
import type { Turn } from '../rotate/turn.ts'

/*
 * What Edit mode gives the Timeline (`timeline-trim`): the draft's cuts to draw and play,
 * the way to change one, and the editor's state that decides whether the handles act.
 * `null` is the read view, which draws the cuts as saved and writes nothing. Types only.
 */

/**
 * How an edit of a cut reached the editor: the clip's name as the track names it, whether
 * the live region says it (a drag's release and a typed time; a key's result is the
 * handle's value), and what it snapped to.
 */
export type TrimNote = { name: string; spoken: boolean; snap?: string | null }

/** The frame a chosen poster was taken from: an object URL and the clip's editorial turn. */
export type PosterSnapshot = { url: string; turn: Turn }

export type EditBinding = {
  /** The draft's cuts, the removed ones left out: what the track draws and Play skips. */
  cuts: ClipCuts
  /** The draft's turns (`rotate`): what the video and the filmstrip tiles show. */
  turns: ClipTurns
  /** A clip's cuts as its Cuts panel lists them: keys, reasons, removed ones in place. */
  listed(identity: string): readonly DraftCut[]
  /** One edit of the draft: the cut keeps its key, place and reason. */
  onTrim(identity: string, key: CutKey, span: { in: number; out: number }, note: TrimNote): void
  /**
   * Add a cut to a clip's draft, as the Cuts panel's Add does (`timeline-overlay-decisions`):
   * the span in seconds, the reason `manual` unless one is given (an approved suggestion's
   * kind). The editor ignores it while a save or a move of marked clips is pending.
   */
  onAdd(identity: string, span: { in: number; out: number }, reason?: string): void
  /** A save is in flight, or a move of marked clips is pending: the handles and fields change nothing. */
  locked: boolean
  /** Edit mode's one live region. */
  announce(words: string): void
  /** The draft's order or chapters differ from the saved ones, which the track shows. */
  orderChanged: boolean
  /** The editor's clip previews: one open at a time, and the Timeline's video makes room for it. */
  previews: ClipPreviews
  /** Changes when Reset puts the draft back: a selection and a drag do not survive it. */
  epoch: number
  /**
   * One edit of the draft: the card of the chapter (saved name) takes `seconds`. `words` is
   * what the live region says (a drag's release); null for a key, whose result is the
   * handle's value. Ignored while a save or a move of marked clips is pending.
   */
  onCardDuration(chapter: string, seconds: number, words: string | null): void
  /**
   * Use as poster (`event-poster-gui`): the draft's poster becomes `pick` and `snapshot` (the
   * frame the video showed, an object URL the editor owns from now on) is the poster area's
   * draft picture, `turn` being the clip's editorial turn. Ignored while a save or a Move
   * clips is pending. The editor announces it.
   */
  onPoster(pick: PosterPick, snapshot: PosterSnapshot): void
  /** The document's `look` as read: the title decorator decides whether the render draws cards. */
  look: unknown
}
