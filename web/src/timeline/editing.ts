import type { ClipCuts, ClipTurns } from '../cuts/ReadCuts'
import type { ClipState } from '../edit/clipInspector'
import type { ChapterKey, CutKey, Cuts, DraftCut } from '../edit/draft'
import type { ClipPreviews } from '../preview/previews'
import type { PosterPick } from '../edit/poster.ts'
import type { Turn, Way } from '../rotate/turn.ts'
import type { EdgeEdit } from './edgeTrim.ts'
import type { GroupSlot } from './clipDrag.ts'
import type { DropSlot } from './reorder.ts'

/*
 * What Edit mode gives the Timeline (`timeline-trim`): the draft's cuts to draw and play,
 * the way to change one, and the editor's state that decides whether the handles act.
 * The Timeline is shown only in Edit mode, so it always has one. Types only.
 */

/**
 * How an edit of a cut reached the editor: the clip's name as the track names it, whether
 * the live region says it (a drag's release and a typed time; a key's result is the
 * handle's value), and what it snapped to.
 */
export type TrimNote = { name: string; spoken: boolean; snap?: string | null }

/** The frame a chosen poster was taken from: an object URL and the clip's editorial turn. */
export type PosterSnapshot = { url: string; turn: Turn }

/**
 * Where the clip `identity` released at a client point would land on the track (`track-drag-edit`): the
 * nearest boundary to the point and the identities the track draws, or null when the point is
 * not over the track. `slot` is null when the track draws no clip to drop among.
 */
export type TrackPoint = { slot: DropSlot | null; drawn: ReadonlySet<string> }

/** The Track hands this over while it is mounted; the bin's drag asks it where a release lands. */
export type TrackBridge = {
  current: ((x: number, y: number, identity: string) => TrackPoint | null) | null
}

/**
 * The Timeline hands this over while it is mounted; the bin's rows ask it to open a clip's menu
 * (`plain-clip-bin` D2). It returns whether a menu opened: false for a clip the event does not list.
 */
export type MenuBridge = {
  current: ((open: ClipMenuOpen) => boolean) | null
}

/** What a clip's menu needs to know of a clip, from the draft as it stands (`plain-clip-bin` D5). */
export type MenuClip = {
  /** The clip's name as the bin names it. */
  name: string
  /** Where the draft has it: played, ignored, missing or removed; null when no chapter holds it. */
  state: ClipState | null
  /** The chapter that plays it, left out of Move to; null when none does. */
  own: ChapterKey | null
  /** Every chapter the draft lists, in order, for Move to. */
  chapters: readonly { key: ChapterKey; name: string }[]
}

/** The clips a menu may act on, and what the draft holds of each. */
export type MenuFacts = {
  /** The bin's order of the clips that can be selected together (played, then ignored): what targets are taken in. */
  order: readonly string[]
  /** The clip as the menu needs it; null for a clip the event does not list. */
  clip(identity: string): MenuClip | null
}

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
   * A clip edge tool's one edit (`clip-edge-trim`): add, trim or remove the clip's leading or
   * trailing cut, as `edgeEdit` gave it. `words` is what the live region says (a release, `Q`,
   * `W`); null for a key, whose result is the slider's value. Ignored while `locked`.
   */
  onEdge(identity: string, edit: EdgeEdit, words: string | null): void
  /**
   * Add a cut to a clip's draft, as the Cuts panel's Add does (`timeline-overlay-decisions`):
   * the span in seconds, the reason `manual` unless one is given (an approved suggestion's
   * kind). The editor ignores it while a save or a move of marked clips is pending.
   */
  onAdd(identity: string, span: { in: number; out: number }, reason?: string): void
  /** Remove a cut from a clip's draft, as the Cuts panel's Remove does (a cut read from the file stays listed, removed). */
  onRemove(identity: string, key: CutKey): void
  /** Rotate a clip left or right: one draft edit of its turn, as the rotate buttons make it. */
  onRotate(identity: string, way: Way): void
  /**
   * A clip dragged on the track and dropped at `slot` (`track-drag-edit`): the lists' own reorder
   * or move to another chapter, one draft edit ("1 clip moved"). `drawn` is the identities the
   * track draws (the other clips of the order keep their places). Ignored while locked.
   */
  onMove(identity: string, slot: DropSlot, drawn: ReadonlySet<string>): void
  /**
   * The clip ignored (`track-drag-edit` D5): one draft edit, out of its chapter's order into the
   * ignored clips, as dragging it onto the bin makes it. Ignored while locked.
   */
  onIgnore(identity: string): void
  /**
   * Several selected clips dropped on the track (`clip-multi-select`, D4): one draft edit,
   * `identities` as one run at `slot` (before `slot.beforeIdentity`, or at the chapter's end after
   * the last clip the track draws, `drawn`). Ignored while locked; a missing clip is left out.
   */
  onMoveMany(
    identities: readonly string[],
    dragged: string,
    slot: Pick<GroupSlot, 'chapter' | 'beforeIdentity' | 'place'>,
    drawn: ReadonlySet<string>,
  ): void
  /**
   * Several selected clips released over the bin, or Ignore clips: one draft edit that ignores
   * them all. Ignored while locked. Returns whether it ignored anything (it says so when not).
   */
  onIgnoreMany(identities: readonly string[]): boolean
  /**
   * An ignored clip included (the Clip tab's Include clip): back at the end of the chapter that
   * lists it, one draft edit. Ignored while locked, and for a clip that is not ignored.
   */
  onInclude(identity: string): void
  /**
   * Several ignored clips included, each at the end of its chapter in the bin's order: one draft
   * edit and one Undo step ("include of 2 clips"). Ignored while locked. Returns whether it
   * included anything (it says so when not).
   */
  onIncludeMany(identities: readonly string[]): boolean
  /** A missing clip removed from reel.yaml when the edits are saved, and its Undo: one draft edit each. */
  onRemoveClip(identity: string): void
  onRestoreClip(identity: string): void
  /** Move to… for one clip off the track: the clip at the end of the chapter, one draft edit. */
  onMoveToEnd(identity: string, to: ChapterKey): void
  /** What the clip menu needs of the draft now (read when it opens and while it is open). */
  menuFacts(): MenuFacts
  /**
   * Rotate every one of `identities` that is on disk and in a chapter a quarter `way`, each from
   * its own turn: one draft edit ("3 clips rotated right."), as Rotate marked makes it. Ignored
   * while locked.
   */
  onRotateMany(identities: readonly string[], way: Way): void
  /**
   * Move to… for several selected clips (`clip-multi-select` D5): the clips on disk that a chapter
   * plays go, in play order, to the end of `to`; one draft edit, applied in a transition, so the
   * move is pending (`locked`) until it lands. "Nothing moved." when they already are last.
   */
  onMoveSelection(identities: readonly string[], to: ChapterKey): void
  /** Whether a client point is over the clip bin (a track drag released there ignores the clip). */
  overBin(x: number, y: number): boolean
  /** Where the bin's drag lands on the track (the Track keeps it current while mounted). */
  trackAt: TrackBridge
  /** Where the bin's rows ask for a clip's menu (the Timeline keeps it current while mounted). */
  menuAt: MenuBridge
  /** A save is in flight, or a move of marked clips is pending: the handles and fields change nothing. */
  locked: boolean
  /**
   * Only the move of the selected clips (Move to…) is pending, no save: the words of an
   * unavailable control say the clips are moving, not that the page is saving.
   */
  moving: boolean
  /** Edit mode's one live region. */
  announce(words: string): void
  /** The editor's clip previews: one open at a time, and the Timeline's video makes room for it. */
  previews: ClipPreviews
  /** The cuts as read: replaced by a new read, which numbers a clip's cuts again (a cut selection ends). */
  baseline: Cuts
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

/**
 * A request for a clip's menu (`clip-context-menu`, D1): which clip, where the menu goes (the
 * pointer, or the block's visible part) and the element focus goes back to. The Timeline owns the
 * one menu; the track opens it, and the bin's rows through `MenuBridge`.
 */
export type ClipMenuOpen = {
  identity: string
  at: { x: number; y: number } | { box: DOMRectReadOnly }
  invoker: HTMLElement
}
