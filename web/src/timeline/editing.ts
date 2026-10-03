import type { ClipCuts } from '../cuts/ReadCuts'
import type { CutKey, DraftCut } from '../edit/draft'
import type { ClipPreviews } from '../preview/previews'

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

export type EditBinding = {
  /** The draft's cuts, the removed ones left out: what the track draws and Play skips. */
  cuts: ClipCuts
  /** A clip's cuts as its Cuts panel lists them: keys, reasons, removed ones in place. */
  listed(identity: string): readonly DraftCut[]
  /** One edit of the draft: the cut keeps its key, place and reason. */
  onTrim(identity: string, key: CutKey, span: { in: number; out: number }, note: TrimNote): void
  /** A save is in flight, or a Move clips is pending: the handles and fields change nothing. */
  locked: boolean
  /** Edit mode's one live region. */
  announce(words: string): void
  /** The draft's order or chapters differ from the saved ones, which the track shows. */
  orderChanged: boolean
  /** The editor's clip previews: one open at a time, and the Timeline's video makes room for it. */
  previews: ClipPreviews
  /** Changes when Reset puts the draft back: a selection and a drag do not survive it. */
  epoch: number
}
