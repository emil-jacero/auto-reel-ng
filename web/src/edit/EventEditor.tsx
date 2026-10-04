import './edit.css'

import {
  startTransition,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react'

import type { Clip, EventDetail } from '../api/event'
import type { EventFailure, Problem } from '../api/events'
import { fetchReel, saveReel } from '../api/reel'
import type { ReelDocument, ReelReadResult, ReelSaveResult, ReelWriteBody } from '../api/reel'
import type { CutHandlers, CutPanels, PanelState } from '../cuts/CutsPanel'
import { keptCuts, trimmedWords } from '../cuts/times'
import { markEventsChanged } from '../events/changes'
import { clipNames, fileName, folderName, plural } from '../events/common'
import { FAILURE_LABEL, UNANSWERED_CAUSE, notReachableHint } from '../events/labels'
import { FAILURE_LOOK } from '../events/tones'
import { eventName } from '../jobs/labels'
import { createClipPreviews } from '../preview/previews'
import { groupTurnAnnouncement, rotatedCount, turnAnnouncement, turnsOf } from '../rotate/turn.ts'
import type { Turn, Way } from '../rotate/turn.ts'
import type { RotateHandler } from '../rotate/RotateButtons'
import type { ClipTurns } from '../cuts/ReadCuts'
import { LIST_HREF } from '../route'
import { focusPageHeading } from '../shell/AppShell'
import { TimelineSection } from '../timeline/TimelineSection'
import { cardSpecs } from '../timeline/cards'
import type { CardsBinding } from '../timeline/useCardSelection'
import { CardRowsContext } from './CardRow'
import { CardStylePanel } from './CardStylePanel'
import { TURNED_OFF, TURNED_ON, TitleCardsSwitch } from './TitleCardsSwitch'
import type { TitleCardsModel } from './TitleCardsSwitch'
import { titleCardsNow } from './decorators.ts'
import { cardsEnabled, cardsSource } from '../timeline/cards.ts'
import type { CardStyleModel } from './CardStylePanel'
import type { CardRowsModel } from './CardRow'
import { cardRowInfo } from './cardRows'
import type { CardEditing } from './card/editing.ts'
import { cardsChangedCount, cardsChangedWords } from './card/model.ts'
import type { CardDraft, CardField } from './card/model.ts'
import { draftSpec } from './card/specs.ts'
import { draftEventStyle, overrideWords, previewStyle, readStyle, styleRefusalOf } from './cardStyle.ts'
import type { StyleField, StyleRefusal, StyleValue } from './cardStyle.ts'
import type { EventStyle } from './card/specs.ts'
import type { EditBinding } from '../timeline/editing'
import type { Dismissals } from '../timeline/overlays/Dismissals'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { SkeletonRows } from '../ui/Skeleton'
import { keepToastsClearOf, toast } from '../ui/toast'
import { NameDialog } from './ChapterDialogs'
import {
  OWN_CHAPTER_HEADING,
  OWN_CHAPTER_NOTE,
  checkName,
  diskFolders,
  ignoredStaying,
  laterClipNotes,
  nameDialogNote,
} from './chapterNames'
import { ChapterDrag } from './ChapterDrag'
import { AddChapter, DeletedChapter } from './ChapterTools'
import type {
  ChapterHandler,
  ChapterMoveHandler,
  ChapterToolsModel,
  NameFieldHandlers,
} from './ChapterTools'
import { ClipOrderList } from './ClipOrderList'
import type {
  MarkHandler,
  MoveHandler,
  Origins,
  RemoveHandler,
  RestoreHandler,
} from './ClipOrderList'
import {
  addChapter,
  addCut,
  adoptedNewCount,
  buildWriteBody,
  cardRefusalOf,
  chapterChanges,
  changedFields,
  cutChanges,
  cutsOf,
  deleteChapter,
  detailMatchesDocument,
  draftChapters,
  editableChapters,
  groupOf,
  isDirty,
  keptOriginal,
  layoutChanged,
  listedChapters,
  liveTrims,
  metadataDraftOf,
  moveChapter,
  moveClip,
  moveClipTo,
  moveGroup,
  moveMarkedToEnd,
  movedSet,
  ordersOf,
  originOf,
  readCardOf,
  readCuts,
  removeClip,
  removeCut,
  renameChapter,
  resetCard,
  resetDecorators,
  resetStyle,
  setPoster,
  setStyleField,
  setTitleCardsOn,
  posterIsChanged,
  decoratorsChanged,
  styleIsChanged,
  styleOf,
  restoreChapter,
  restoreClip,
  restoreCut,
  rotateGroup,
  rotationChanges,
  setCardField,
  setCardLength,
  trimCut,
  turnOf,
} from './draft'
import type {
  Baseline,
  CardRefusal,
  ChapterChanges,
  ChapterKey,
  CutKey,
  Draft,
  DraftChapter,
  EditableChapter,
  MetadataField,
} from './draft'
import {
  CLEARED_WORDS,
  MARK_HINT,
  MOVE_REASON_WORDS,
  NOTHING_MOVED,
  NO_MARKS,
  afterMove,
  clearMarks,
  countWords,
  markWords,
  moveReason,
  movedWords,
  pruneMarks,
  toggleMark,
} from './marks'
import { FIELD_LABEL, inheritHint, MetadataForm } from './MetadataForm'
import type { Resolved } from './MetadataForm'
import { PosterPanel } from './PosterPanel'
import { POSTER_CHANGED, chosenWords } from './poster.ts'
import type { PosterPick } from './poster.ts'
import { SaveBar } from './SaveBar'
import type { Operation, Pressed, SaveProblem } from './SaveBar'
import { TitleCardContext } from './TitleCard'
import type { TitleCardModel } from './TitleCard'
import { holdWords, isSaveChord, LIFTED_WORDS, saveHold, saveKeyAction } from './saveShortcut'
import {
  discardAndLeave,
  keepEditing,
  setSaving,
  usePendingLeave,
  useUnsavedGuard,
} from './unsaved'

/**
 * Edit mode: the event's chapters, clip order and metadata, saved explicitly.
 *
 * It reads `reel.yaml` (the document and its ETag) next to the detail the page
 * already shows, and saves one whole-document PUT under `If-Match` per explicit
 * Save. The body is always the document as read with only the operator's
 * edits applied (`draft.ts`). While a save is in flight the editor is locked
 * and the pressed control is busy; every failure keeps the edits and says why.
 *
 * The chapters themselves are edited here too: added, renamed, moved up or down,
 * deleted once empty, and clips moved between them with Move marked to…
 * dialog (`ChapterTools.tsx`, `ChapterDialogs.tsx`) or dragged one at a time
 * into another chapter (`ChapterDrag.tsx`, around every chapter). What a name
 * means for clips added later (D-12) is said beside the chapter
 * (`chapterNames.ts`). So are each clip's cuts, in a panel under its row
 * (`cuts/CutsPanel.tsx`): a cut typed but not added holds Save back, as a date
 * typed in part does, and so does a name typed in a chapter's title and not kept.
 * A chapter is renamed at its title (`InlineName.tsx`, one field open at a time:
 * `naming`); the event's own chapter shows the main title card, which edits the
 * draft's title as the metadata form's Title field does (`TitleCard.tsx`).
 *
 * `event` is the page's detail, read once at mount: a later re-read of the page
 * never changes the order shown or the draft. It is null for the needs-attention
 * form, which edits only the metadata. `onSaved` and `onReload` both mean
 * "leave Edit mode, then read the event again".
 */

type ReadFailure = {
  cause: string
  detail: string | null
  failure?: EventFailure
  notFound?: boolean
}

type Ready = {
  status: 'ready'
  /** What Edit mode read: the document, its chapters and their orders. */
  baseline: Baseline
  /**
   * The operator's edits: the chapter list, each chapter's order, the missing
   * clips taken out of their chapter's order (Save leaves them out of reel.yaml),
   * and the fields.
   */
  draft: Draft
  etag: string
  /** The clip moved last: it takes the "moved" badge when a swap could give it to either. */
  lastMoved: string | null
  /** Chapters added so far in this session: the next one's key is `a${added + 1}`. */
  added: number
  /** The date input holds a date typed only in part (its value reads as ''). */
  dateIncomplete: boolean
  /** The clips whose cut fields hold typed text not added as a cut: never saved. */
  typed: ReadonlySet<string>
  /** An open name field (`InlineName`) holds text not yet kept: unfinished, like a typed cut. */
  nameUnsent: boolean
  /**
   * The clips marked to move together (edit/marks.ts). Beside the draft, not in it: marking
   * is no edit, so it never makes the page dirty. Ended by Reset and by a re-read.
   */
  marked: ReadonlySet<string>
  /** Cuts added so far in this session: the next one's key is `a${nextCut + 1}`. */
  nextCut: number
  /** Bumped by Reset, which remounts the fields (a partial date has no value to reset). */
  resets: number
  /** Non-null while a save is in flight: the editor is locked. */
  pressed: Pressed | null
  problem: SaveProblem | null
  /** The service's explanation of an unusable date or title, shown at those fields. */
  refusal: string | null
  /** The last refused save's naming of a title card and its field, shown at that field. */
  cardRefusal: CardRefusal | null
  /** The last refused save's naming of a card-style field (`look.title_card.<field>`), shown at that field. */
  styleRefusal: StyleRefusal | null
  /** Bumped by every failed answer, so focus moves to what explains it. */
  answers: number
}

type State =
  | { status: 'loading' }
  // `retrying`: Try again's read runs, and the failure stays shown with its button busy.
  | ({ status: 'failed'; retrying?: true } & ReadFailure)
  // The page's chapters no longer agree with the document just read.
  | { status: 'changed' }
  | Ready

type Action =
  | { type: 'reading' }
  | { type: 'retrying' }
  | { type: 'read-failed'; failure: ReadFailure }
  | { type: 'read'; document: ReelDocument; etag: string; chapters: EditableChapter[] | null }
  | { type: 'move'; chapter: ChapterKey; from: number; to: number }
  | { type: 'remove'; chapter: ChapterKey; identity: string }
  | { type: 'restore'; identity: string }
  | { type: 'chapter-add'; key: ChapterKey; name: string }
  | { type: 'chapter-rename'; key: ChapterKey; name: string }
  | { type: 'chapter-move'; key: ChapterKey; delta: -1 | 1 }
  | { type: 'chapter-delete'; key: ChapterKey }
  | { type: 'chapter-restore'; key: ChapterKey }
  | { type: 'marked-move'; to: ChapterKey }
  | { type: 'clip-drop'; from: ChapterKey; to: ChapterKey; identity: string; at: number }
  | { type: 'group-drop'; dragged: string; to: ChapterKey; gap: number }
  | { type: 'mark'; identity: string; on: boolean }
  | { type: 'marks-clear' }
  | { type: 'field'; field: MetadataField; value: string }
  | { type: 'date-validity'; incomplete: boolean }
  | {
      type: 'cut-add'
      identity: string
      span: { in: number; out: number }
      key: CutKey
      /** Why: an approved suggestion's kind. Absent: a cut made by hand. */
      reason?: string
    }
  | { type: 'cut-remove'; identity: string; key: CutKey }
  | { type: 'cut-restore'; identity: string; key: CutKey }
  | { type: 'cut-trim'; identity: string; key: CutKey; span: { in: number; out: number } }
  | { type: 'cut-typed'; identity: string; typed: boolean }
  // The caller took the clips that are on disk; `rotateGroup` checks that a chapter plays them.
  | { type: 'rotate'; identities: readonly string[]; way: Way }
  | { type: 'name-unsent'; unsent: boolean }
  // A title card's length from the Timeline (`title-card-duration-drag`); `resolved` is the one read.
  | { type: 'card-length'; key: ChapterKey; seconds: number; resolved: number }
  | { type: 'card-field'; key: ChapterKey; field: CardField; value: CardDraft[CardField] }
  | { type: 'card-reset'; key: ChapterKey }
  | { type: 'style-field'; field: StyleField; value: StyleValue | null }
  | { type: 'style-reset' }
  // The Title cards switch (`title-card-toggle`); `readEnabled` is the service's answer for the document as read.
  | { type: 'title-cards'; on: boolean; readEnabled: boolean }
  | { type: 'title-cards-reset' }
  // The event's poster (`poster.ts`): a chosen frame, or `null` for the default frame.
  | { type: 'poster'; pick: PosterPick | null }
  | { type: 'reset' }
  | { type: 'save-start'; pressed: Pressed }
  | { type: 'save-failed'; problem: SaveProblem | null; refusal: string | null }

/**
 * An edit that brings the draft back to what was read retires the last save's
 * failure: there is nothing left to save. A vanished event stays said.
 */
function afterEdit(next: Ready): Ready {
  const dirty = isDirty(next.baseline, next.draft) || unfinished(next)
  if (dirty || (next.problem === null && next.refusal === null)) {
    return next
  }
  return {
    ...next,
    problem: next.problem?.kind === 'gone' ? next.problem : null,
    refusal: null,
    cardRefusal: null,
    styleRefusal: null,
  }
}

/** Typed but not sendable: a date typed in part, a name not kept, or a cut typed and not added. */
function unfinished(ready: Ready): boolean {
  return ready.dateIncomplete || ready.nameUnsent || ready.typed.size > 0
}

const NONE_TYPED: ReadonlySet<string> = new Set()

/** The draft as read: nothing changed. */
function initialDraft(baseline: Baseline): Draft {
  return {
    chapters: baseline.chapters,
    orders: baseline.original,
    removed: new Map(),
    metadata: metadataDraftOf(baseline.read),
    cuts: new Map(),
    rotations: new Map(),
    cards: new Map(),
  }
}

/** A card refusal stays until the field it names (any field, for one naming none) is edited. */
function afterCardEdit(state: Ready, draft: Draft, key: ChapterKey, field: CardField | null): Ready {
  const refusal = state.cardRefusal
  const retired =
    refusal !== null && refusal.key === key && (field === null || refusal.field === field || refusal.field === null)
  const next = withDraft(state, draft)
  return retired ? { ...next, cardRefusal: null } : next
}

/** `state` with `draft`, unless the action changed nothing. */
function withDraft(state: Ready, draft: Draft): Ready {
  return draft === state.draft ? state : afterEdit({ ...state, draft })
}

/** Whether `key` is a chapter of the draft that a save keeps (not deleted). */
function isListed(draft: Draft, key: ChapterKey): boolean {
  return draft.chapters.some((chapter) => chapter.key === key && !chapter.deleted)
}

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case 'reading':
      return { status: 'loading' }
    case 'retrying':
      return state.status === 'failed' ? { ...state, retrying: true } : { status: 'loading' }
    case 'read-failed':
      return { status: 'failed', ...action.failure }
    case 'read': {
      if (action.chapters === null) {
        return { status: 'changed' }
      }
      const baseline: Baseline = {
        read: action.document,
        chapters: draftChapters(action.chapters),
        original: ordersOf(action.chapters),
        cuts: readCuts(action.document),
      }
      return {
        status: 'ready',
        baseline,
        draft: initialDraft(baseline),
        etag: action.etag,
        lastMoved: null,
        added: 0,
        dateIncomplete: false,
        typed: NONE_TYPED,
        nameUnsent: false,
        marked: NO_MARKS,
        nextCut: 0,
        resets: 0,
        pressed: null,
        problem: null,
        refusal: null,
        cardRefusal: null,
        styleRefusal: null,
        answers: 0,
      }
    }
  }
  // Every edit below is refused while a save is in flight.
  if (state.status !== 'ready' || (state.pressed !== null && action.type !== 'save-failed')) {
    return state
  }
  switch (action.type) {
    case 'move': {
      const { draft } = state
      const order = draft.orders.get(action.chapter)
      if (order === undefined || action.from === action.to) {
        return state
      }
      const orders = new Map(draft.orders)
      orders.set(action.chapter, moveClip(order, action.from, action.to))
      return afterEdit({ ...state, draft: { ...draft, orders }, lastMoved: order[action.from] })
    }
    case 'remove': {
      const { draft } = state
      const orders = removeClip(draft.orders, action.chapter, action.identity)
      if (orders === null) {
        return state
      }
      const removed = new Map(draft.removed).set(action.identity, action.chapter)
      return afterEdit({ ...state, draft: { ...draft, orders, removed } })
    }
    case 'restore': {
      const { draft } = state
      const chapter = draft.removed.get(action.identity)
      // Never into a deleted chapter: it plays no clip until its Undo.
      if (chapter === undefined || !isListed(draft, chapter)) {
        return state
      }
      // Back after the clips it followed when Edit mode opened (draft.ts, `restoreClip`).
      const original = state.baseline.original.get(chapter) ?? []
      const orders = restoreClip(draft.orders, chapter, action.identity, original)
      const removed = new Map(draft.removed)
      removed.delete(action.identity)
      return afterEdit({ ...state, draft: { ...draft, orders, removed } })
    }
    case 'chapter-add':
      // The key the caller took from the counter, so it can focus the new chapter.
      if (action.key !== `a${state.added + 1}`) {
        return state
      }
      return {
        ...withDraft(state, addChapter(state.draft, action.key, action.name)),
        added: state.added + 1,
      }
    case 'chapter-rename':
      return withDraft(state, renameChapter(state.draft, action.key, action.name))
    case 'chapter-move':
      return withDraft(state, moveChapter(state.draft, action.key, action.delta))
    case 'chapter-delete':
      // The caller checked that the chapter plays no clip (`deleteRefusal`).
      return (state.draft.orders.get(action.key) ?? []).length > 0
        ? state
        : withDraft(state, deleteChapter(state.draft, action.key))
    case 'chapter-restore':
      return withDraft(state, restoreChapter(state.draft, action.key))
    case 'marked-move': {
      // Move marked to…: the state's own marks, in page order, at the end of `to` (`moveMarkedToEnd`).
      const listed = listedChapters(state.draft.chapters).map((chapter) => chapter.key)
      const result = moveMarkedToEnd(state.draft, listed, state.marked, action.to)
      return result.draft === state.draft
        ? state
        : afterEdit({
            ...state,
            draft: result.draft,
            lastMoved: null,
            marked: afterMove(state.marked, result.moved),
          })
    }
    case 'clip-drop': {
      // A drag into another chapter, at the place it was dropped (`moveClipTo`).
      const { from, to, identity, at } = action
      if (from === to || !isListed(state.draft, from) || !isListed(state.draft, to)) {
        return state
      }
      const draft = moveClipTo(state.draft, from, to, identity, at)
      return draft === state.draft
        ? state
        : afterEdit({ ...state, draft, lastMoved: identity, marked: afterMove(state.marked, [identity]) })
    }
    case 'group-drop': {
      // The whole marked group, in page order, as one run at the gap (`moveGroup`). The group
      // is taken from the state's marks, not shipped by the drag, so a drag can never move a
      // clip the state does not hold marked. A no-op drop keeps the state, marks included.
      const listed = listedChapters(state.draft.chapters).map((chapter) => chapter.key)
      const group = groupOf(state.draft.orders, listed, state.marked)
      if (group.length === 0 || !isListed(state.draft, action.to)) {
        return state
      }
      const draft = moveGroup(state.draft, group, action.to, action.gap)
      return draft === state.draft
        ? state
        : afterEdit({ ...state, draft, lastMoved: action.dragged, marked: afterMove(state.marked, group) })
    }
    case 'mark': {
      const marked = toggleMark(state.marked, action.identity, action.on)
      return marked === state.marked ? state : { ...state, marked }
    }
    case 'marks-clear':
      return state.marked.size === 0 ? state : { ...state, marked: clearMarks(state.marked) }
    case 'field':
      return afterEdit({
        ...state,
        draft: {
          ...state.draft,
          metadata: { ...state.draft.metadata, [action.field]: action.value },
        },
        // A refusal is about the date or title that was sent; editing them retires it.
        refusal: action.field === 'title' || action.field === 'date' ? null : state.refusal,
      })
    case 'date-validity':
      return action.incomplete === state.dateIncomplete
        ? state
        : afterEdit({ ...state, dateIncomplete: action.incomplete })
    case 'cut-add':
      // The key the caller took from the counter, as for an added chapter.
      if (action.key !== `a${state.nextCut + 1}`) {
        return state
      }
      return {
        ...withDraft(
          state,
          addCut(
            state.baseline,
            state.draft,
            action.identity,
            action.span,
            action.key,
            action.reason,
          ),
        ),
        nextCut: state.nextCut + 1,
      }
    case 'cut-remove':
      return withDraft(state, removeCut(state.baseline, state.draft, action.identity, action.key))
    case 'cut-restore':
      return withDraft(state, restoreCut(state.baseline, state.draft, action.identity, action.key))
    case 'cut-trim':
      return withDraft(
        state,
        trimCut(state.baseline, state.draft, action.identity, action.key, action.span),
      )
    case 'rotate':
      return withDraft(
        state,
        rotateGroup(state.baseline, state.draft, action.identities, action.way, () => true),
      )
    case 'cut-typed': {
      if (state.typed.has(action.identity) === action.typed) {
        return state
      }
      const typed = new Set(state.typed)
      if (action.typed) {
        typed.add(action.identity)
      } else {
        typed.delete(action.identity)
      }
      return afterEdit({ ...state, typed })
    }
    case 'name-unsent':
      return action.unsent === state.nameUnsent
        ? state
        : afterEdit({ ...state, nameUnsent: action.unsent })
    case 'card-length':
      return afterCardEdit(
        state,
        setCardLength(state.baseline, state.draft, action.key, action.seconds, action.resolved),
        action.key,
        'duration',
      )
    case 'card-field':
      return afterCardEdit(
        state,
        setCardField(state.baseline, state.draft, action.key, action.field, action.value),
        action.key,
        action.field,
      )
    case 'card-reset':
      return afterCardEdit(state, resetCard(state.draft, action.key), action.key, null)
    case 'style-field': {
      const next = withDraft(state, setStyleField(state.baseline, state.draft, action.field, action.value))
      const refusal = state.styleRefusal
      const retired = refusal !== null && (refusal.field === null || refusal.field === action.field)
      return retired ? { ...next, styleRefusal: null } : next
    }
    case 'style-reset':
      return { ...withDraft(state, resetStyle(state.draft)), styleRefusal: null }
    case 'title-cards':
      return withDraft(
        state,
        setTitleCardsOn(state.baseline, state.draft, action.readEnabled, action.on),
      )
    case 'title-cards-reset':
      return withDraft(state, resetDecorators(state.draft))
    case 'poster':
      return withDraft(state, setPoster(state.baseline, state.draft, action.pick))
    case 'reset':
      return {
        ...state,
        cardRefusal: null,
        styleRefusal: null,
        draft: initialDraft(state.baseline),
        lastMoved: null,
        dateIncomplete: false,
        typed: NONE_TYPED,
        nameUnsent: false,
        marked: NO_MARKS,
        nextCut: 0,
        resets: state.resets + 1,
        problem: null,
        refusal: null,
      }
    case 'save-start':
      // The problem stays until the answer replaces it: a pressed Retry keeps its place.
      return { ...state, pressed: action.pressed }
    case 'save-failed':
      return {
        ...state,
        pressed: null,
        problem: action.problem,
        refusal: action.refusal,
        cardRefusal:
          action.problem?.kind === 'refused' ? cardRefusalOf(state.draft, action.problem.detail) : null,
        styleRefusal:
          action.problem?.kind === 'refused' ? styleRefusalOf(action.problem.detail) : null,
        answers: state.answers + 1,
      }
  }
}

/** What a failed read's alert says, to tell a repeated failure from a new one. */
function failureWords(failure: ReadFailure): string {
  const kind = failure.failure === undefined ? '' : FAILURE_LABEL[failure.failure]
  return [failure.cause, kind, failure.detail ?? ''].join('\n')
}

/** A failed read in the words the page uses for a failed event read. */
function readFailure(
  result: Exclude<ReelReadResult, { kind: 'ok' }>,
  eventId: string,
): ReadFailure {
  // No answer gets the way to recover, never the browser's own error text; an
  // unexpected answer keeps the request and the status it received.
  if (result.kind === 'unreachable') {
    return { cause: UNANSWERED_CAUSE.unreachable, detail: notReachableHint('Try again') }
  }
  if (result.kind === 'unpublished') {
    return { cause: UNANSWERED_CAUSE.unpublished, detail: result.message }
  }
  const problem = result.problem
  if (problem.status === 404) {
    return {
      cause: `No event “${folderName(eventId)}” under the project root.`,
      detail: null,
      notFound: true,
    }
  }
  if (problem.status === 502) {
    return {
      cause: 'This event could not be read.',
      detail: problem.detail,
      failure: problem.failure ?? undefined,
    }
  }
  return { cause: problem.title, detail: problem.detail }
}

type Failed = { problem: SaveProblem | null; refusal: string | null }

/** A refused write, by the answer's status (never its prose). */
function saveFailure(problem: Problem, operation: Operation): Failed {
  switch (problem.status) {
    case 400:
      return problem.failure === 'unusable_metadata'
        ? { problem: null, refusal: problem.detail }
        : { problem: { kind: 'refused', detail: problem.detail }, refusal: null }
    case 404:
      return { problem: { kind: 'gone', detail: problem.detail }, refusal: null }
    case 412:
      return { problem: { kind: 'conflict' }, refusal: null }
    default:
      return {
        problem: {
          kind: 'disk',
          title: 'reel.yaml could not be saved.',
          failure: problem.failure ?? null,
          detail: problem.detail,
          retry: operation,
        },
        refusal: null,
      }
  }
}

/**
 * One save: a PUT of `body` under `If-Match`. The overwrite first re-reads the
 * document, for its current tag only, and then writes the same body.
 */
async function send(
  eventId: string,
  body: ReelWriteBody,
  etag: string,
  operation: Operation,
): Promise<{ saved: true } | ({ saved: false } & Failed)> {
  let ifMatch = etag
  if (operation === 'overwrite') {
    const latest = await fetchReel(eventId, new AbortController().signal)
    if (latest.kind === 'unreachable' || latest.kind === 'unpublished') {
      return {
        saved: false,
        problem: { kind: latest.kind, detail: latest.message, retry: operation },
        refusal: null,
      }
    }
    if (latest.kind === 'problem') {
      const problem = latest.problem
      if (problem.status === 404) {
        return { saved: false, problem: { kind: 'gone', detail: problem.detail }, refusal: null }
      }
      return {
        saved: false,
        problem: {
          kind: 'disk',
          title: 'reel.yaml could not be read, so nothing was saved.',
          failure: problem.failure ?? null,
          detail: problem.detail,
          retry: operation,
        },
        refusal: null,
      }
    }
    ifMatch = latest.etag
  }
  const result: ReelSaveResult = await saveReel(eventId, body, ifMatch)
  switch (result.kind) {
    case 'saved':
      return { saved: true }
    case 'problem':
      return { saved: false, ...saveFailure(result.problem, operation) }
    case 'unreachable':
    case 'unpublished':
      return {
        saved: false,
        problem: { kind: result.kind, detail: result.message, retry: operation },
        refusal: null,
      }
  }
}

const CHANGED_DETAIL =
  'Its clips or chapters no longer match what the page shows. ' +
  'Read it again to edit what is on disk now.'

/** A metadata value, or null when unset: absent, empty or spaces only, as the service reads it. */
function nonBlank(value: string | null | undefined): string | null {
  return value != null && value.trim() !== '' ? value : null
}

/**
 * The title or date a save leaves the event with, as far as the page knows it:
 * the value written; else, for a field reel.yaml left unset and still leaves
 * unset, the value the page resolved from the folder name. A field the operator
 * emptied is resolved by the service, from the folder name: null, never a guess.
 */
function savedValue(
  field: 'title' | 'date',
  read: ReelDocument,
  body: ReelWriteBody,
  resolved: Resolved | null,
): string | null {
  const written = nonBlank(body.metadata[field])
  if (written !== null) {
    return written
  }
  return nonBlank(read.metadata[field]) === null ? nonBlank(resolved?.[field]) : null
}

/** "Title", "Title and date", "Title, date and location": the changed fields in words. */
function fieldWords(fields: readonly MetadataField[]): string {
  const words = fields.map((field, index) =>
    index === 0 ? FIELD_LABEL[field] : FIELD_LABEL[field].toLowerCase(),
  )
  return words.length <= 1
    ? words.join('')
    : `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

/**
 * What the save bar lists: the changed fields, what is typed but not sendable,
 * the chapter edits, the moves, the removals, the cuts, and what a save adds.
 * `typed` names the one clip holding a typed cut, or counts the clips.
 */
function summarize(
  changed: readonly MetadataField[],
  dateIncomplete: boolean,
  typed: string | number,
  nameUnsent: boolean,
  chapters: ChapterChanges,
  moved: number,
  removed: number,
  cuts: { added: number; removed: number; trimmed: number },
  rotated: number,
  cardsChanged: number,
  styleChanged: boolean,
  titleCards: boolean | null,
  poster: boolean,
  adopted: number,
): string {
  // An incomplete date reads as '' but is not a date left empty: it is named as such.
  const fields = dateIncomplete ? changed.filter((field) => field !== 'date') : changed
  const parts = [
    fields.length > 0 && `${fieldWords(fields)} changed`,
    dateIncomplete && 'date incomplete',
    typeof typed === 'string'
      ? `cut typed on ${typed}, not added`
      : typed > 0 && `cuts typed on ${typed} clips, not added`,
    nameUnsent && 'name typed, not kept',
    chapters.added > 0 && `${plural(chapters.added, 'chapter', 'chapters')} added`,
    chapters.renamed > 0 && `${plural(chapters.renamed, 'chapter', 'chapters')} renamed`,
    chapters.deleted > 0 && `${plural(chapters.deleted, 'chapter', 'chapters')} deleted`,
    chapters.reordered && 'chapter order changed',
    moved > 0 && `${plural(moved, 'clip', 'clips')} moved`,
    removed > 0 && `${plural(removed, 'missing clip', 'missing clips')} removed`,
    cuts.added > 0 && `${plural(cuts.added, 'cut', 'cuts')} added`,
    cuts.removed > 0 && `${plural(cuts.removed, 'cut', 'cuts')} removed`,
    cuts.trimmed > 0 && `${plural(cuts.trimmed, 'cut', 'cuts')} trimmed`,
    rotated > 0 && rotatedCount(rotated),
    cardsChangedWords(cardsChanged) ?? false,
    styleChanged && CARD_STYLE_CHANGED,
    titleCards !== null && (titleCards ? TURNED_ON : TURNED_OFF),
    poster && POSTER_CHANGED,
    adopted > 0 && `adds ${plural(adopted, 'new clip', 'new clips')} to reel.yaml`,
  ].filter((part): part is string => part !== false)
  const text = parts.join(' · ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const CARD_STYLE_CHANGED = 'card style changed'

/** What `naming` holds while the main title card's field is open (a chapter key never is). */
const TITLE = 'title' as const

// The read view's cuts, which Edit mode's Timeline does not use: its cuts are the draft's.
const NOT_READ = { cuts: null, turns: null, failure: null, look: null } as const
const NOTHING = () => undefined

// A chapter with no removed clip: one constant, so its list keeps its memoised props.
const NONE_REMOVED: readonly string[] = []

/** The chapter's heading, as the read view names it. */
function chapterHeading(name: string, hasNamedChapter: boolean): string {
  return name !== '' ? name : hasNamedChapter ? OWN_CHAPTER_HEADING : 'Clips'
}

/** The chapter dialog open, if any: Add chapter. */
type ChapterDialog = { kind: 'add' }

/** Where focus goes once a chapter edit is on screen: a control of a chapter, by class. */
type ChapterFocus = {
  key: ChapterKey | null
  target: 'heading' | 'chapter-up' | 'chapter-down' | 'chapter-undo' | 'chapter-delete' | 'add'
}

/** The statuses of a clip on disk that the chapter plays: the ones that can be marked and moved. */
function onDisk(clip: Clip | undefined): boolean {
  return clip?.status === 'active' || clip?.status === 'new'
}

/** A clip that can carry a mark: on disk and not excluded (the rows with a Cuts control). */
function canMark(clip: Clip | undefined): boolean {
  return onDisk(clip) && clip?.excluded !== true
}

/**
 * The name the row of `identity` gives it in `draft` now (ClipOrderList's `nameOf`
 * inputs): a move, or a chapter's rename, renames it in the save bar as in its row.
 */
function nameNow(
  draft: Draft,
  original: ReadonlyMap<ChapterKey, readonly string[]>,
  identity: string,
  ignoredOf: ReadonlyMap<ChapterKey, readonly string[]>,
  removedOf: ReadonlyMap<ChapterKey, readonly string[]>,
): string {
  const chapter = draft.chapters.find((listed) =>
    (draft.orders.get(listed.key) ?? []).includes(identity),
  )
  if (chapter === undefined) {
    return identity
  }
  return clipNames(chapter.name, [
    ...(original.get(chapter.key) ?? []),
    ...(draft.orders.get(chapter.key) ?? []),
    ...(ignoredOf.get(chapter.key) ?? []),
    ...(removedOf.get(chapter.key) ?? []),
  ])(identity)
}

/** A chapter's heading in `draft` (`Main`, `Clips` or its name), for an announcement. */
function headingIn(draft: Draft, key: ChapterKey): string {
  const named = listedChapters(draft.chapters).some((chapter) => chapter.name !== '')
  const chapter = draft.chapters.find((listed) => listed.key === key)
  return chapter === undefined ? '' : chapterHeading(chapter.name, named)
}

/** "chapter 2 of 3": its place among the chapters a save keeps. */
function placeIn(draft: Draft, key: ChapterKey): string {
  const kept = listedChapters(draft.chapters)
  return `chapter ${kept.findIndex((chapter) => chapter.key === key) + 1} of ${kept.length}`
}

/**
 * Why a chapter cannot be deleted, or null when it can. It still plays a clip:
 * one on disk moves out with Move marked to…, a missing one goes with its Remove. Or it
 * is the event's own chapter and lists an ignored clip the page would list under
 * it again after the save (`ignoredStaying`): it would come back holding only that.
 */
function deleteRefusal(
  chapters: readonly DraftChapter[],
  chapter: DraftChapter,
  heading: string,
  order: readonly string[],
  ignored: readonly string[],
  clips: ReadonlyMap<string, Clip>,
): string | null {
  if (order.length > 0) {
    const missing = order.filter((identity) => clips.get(identity)?.status === 'missing').length
    const present = order.length - missing
    if (present === 0) {
      return (
        `“${heading}” still lists ${plural(missing, 'missing clip', 'missing clips')}. ` +
        `Remove ${missing === 1 ? 'it' : 'them'} first.`
      )
    }
    const plays = `“${heading}” still plays ${plural(order.length, 'clip', 'clips')}. `
    if (missing === 0) {
      return `${plays}Move ${present === 1 ? 'it' : 'them'} to another chapter first.`
    }
    const gone = missing === 1 ? 'the missing one' : `the ${missing} missing ones`
    return (
      `${plays}Move the ${present === 1 ? 'clip' : `${present} clips`} on disk to another ` +
      `chapter and remove ${gone} first.`
    )
  }
  const staying = chapter.name === '' ? ignoredStaying(chapters, ignored) : 0
  if (staying > 0) {
    return (
      `“${heading}” still lists ${plural(staying, 'ignored clip', 'ignored clips')} that no ` +
      'other chapter will take, so it stays.'
    )
  }
  return null
}

/** Whether two tools objects show the same: the same notes, controls and handlers. */
function sameTools(a: ChapterToolsModel, b: ChapterToolsModel): boolean {
  return (Object.keys(a) as (keyof ChapterToolsModel)[]).every((field) =>
    field === 'notes'
      ? a.notes.join('\n') === b.notes.join('\n')
      : field === 'place'
        ? a.place?.first === b.place?.first && a.place?.last === b.place?.last
        : a[field] === b[field],
  )
}

const NO_CHANGES: ChapterChanges = { added: 0, renamed: 0, deleted: 0, reordered: false }
const NO_ORIGINS: Origins = new Map()

/** Above this share of the window's height the save bar rests in the page instead of being held. */
const HELD_BAR_MAX_SHARE = 0.4
/**
 * Below this window height (in rem) the save bar rests in the page whatever its
 * size: a held bar of up to two fifths, the sticky header and chapter heading and
 * the tallest clip row (141 px at 320 px wide) need about 27rem together.
 */
const HELD_BAR_MIN_WINDOW_REM = 28

/** Whether all of `element` lies inside the window. */
function inWindow(element: HTMLElement): boolean {
  const box = element.getBoundingClientRect()
  return box.top >= 0 && box.bottom <= document.documentElement.clientHeight
}

/**
 * Scroll `element` the least distance into view when part of it is hidden. A
 * control of `bar` is measured against the window's edges. Any other is measured
 * against the page's scroll padding, which keeps clear of the sticky header and
 * chapter heading and of a held bar; the scroll itself honours that padding too.
 */
function keepInView(element: HTMLElement, bar: HTMLElement | null): void {
  const root = document.documentElement
  const box = element.getBoundingClientRect()
  let top = 0
  let bottom = root.clientHeight
  if (bar === null || !bar.contains(element)) {
    const style = getComputedStyle(root)
    top = parseFloat(style.scrollPaddingTop)
    bottom -= parseFloat(style.scrollPaddingBottom)
  }
  if (box.top < top || box.bottom > bottom) {
    element.scrollIntoView({ block: 'nearest' })
  }
}

/**
 * Hold the bar at the window's bottom while it takes at most two fifths of the
 * window and the window is at least 28rem tall. Otherwise (a failed save in a
 * short window, any bar at 400 % zoom) it would hide the editor, so it rests in
 * the page after it (`data-rests`). Only a held bar takes room at the window's
 * bottom: its height goes in front of the page's bottom scroll padding then (an
 * inline `scroll-padding-bottom` on <html>, absent while it rests; not a custom
 * property, whose change restyles every row: the first edit cost ~100 ms more on
 * 400 rows). A held bar that starts to rest takes its focused control to the page's
 * end, so the page follows it there.
 */
function placeBar(bar: HTMLElement): void {
  const root = document.documentElement
  const rested = bar.hasAttribute('data-rests')
  const rem = parseFloat(getComputedStyle(root).fontSize)
  const rests =
    root.clientHeight < HELD_BAR_MIN_WINDOW_REM * rem ||
    bar.offsetHeight > root.clientHeight * HELD_BAR_MAX_SHARE
  bar.toggleAttribute('data-rests', rests)
  if (rests) {
    root.style.removeProperty('scroll-padding-bottom')
  } else {
    const padding = `calc(${bar.offsetHeight}px + var(--scroll-pad-bottom))`
    root.style.setProperty('scroll-padding-bottom', padding)
  }
  const focused = document.activeElement
  if (rests && !rested && focused instanceof HTMLElement && bar.contains(focused)) {
    focused.scrollIntoView({ block: 'nearest' })
  }
}

export function EventEditor({
  eventId,
  event,
  heading = 'Details',
  liveEvent = null,
  dismissals,
  cards,
  onProxiesFinished,
  onSaved,
  onReload,
}: {
  eventId: string
  event: EventDetail | null
  /** The metadata section's heading. */
  heading?: string
  /**
   * The event as the page last read it, a proxy job's end included: the Timeline lays out
   * its clips and proxies from it. `event` stays the snapshot the draft is built from.
   */
  liveEvent?: EventDetail | null
  /** The suggestions dismissed on this page visit (`useDismissals`, kept by the page). */
  dismissals: Dismissals
  /** The page's one card selection (`useCardSelection`), shared with the Timeline's blocks. */
  cards: CardsBinding
  /** A proxy job the Timeline followed has ended: the page reads the event again. */
  onProxiesFinished?: () => void
  onSaved: () => void
  onReload: () => void
}) {
  // Read once: the draft is never re-initialised from a newer detail.
  const [detail] = useState(event)
  const [state, dispatch] = useReducer(reduce, { status: 'loading' })
  const [announcement, setAnnouncement] = useState('')
  const [overwriteAsked, setOverwriteAsked] = useState(false)
  const leaveQuestion = usePendingLeave()
  const detailsId = useId()
  const inFlight = useRef<AbortController | null>(null)
  // A second press while a save is in flight sends nothing.
  const saving = useRef(false)
  const mounted = useRef(false)
  const barRef = useRef<HTMLDivElement>(null)
  const alertRef = useRef<HTMLDivElement>(null)
  // A pointer press is under way: the focus it gives is not scrolled (onFocus below).
  const pointerPressed = useRef(false)
  const refusalRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const keepEditingRef = useRef<HTMLButtonElement>(null)
  // What the failure's alert said when Try again was pressed (`failureWords`), until the
  // answer comes; a press meanwhile sends nothing.
  const retried = useRef<string | null>(null)
  const detailsHeadingRef = useRef<HTMLHeadingElement>(null)
  const readAgainRef = useRef<HTMLButtonElement>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  const [chapterDialog, setChapterDialog] = useState<ChapterDialog | null>(null)
  // The chapter whose Delete was pressed while refused: its reason shows until the next edit.
  const [refusedDelete, setRefusedDelete] = useState<ChapterKey | null>(null)
  // Where a chapter edit leaves focus, once it is on screen (the effects below).
  const focusAfter = useRef<ChapterFocus | null>(null)
  // The part of the page to scroll into view once focus is there.
  const scrollAfter = useRef<HTMLElement | null>(null)

  const chapters = useMemo(() => editableChapters(detail), [detail])
  const clips = useMemo(
    () =>
      new Map<string, Clip>(
        (detail?.chapters ?? []).flatMap((chapter) =>
          chapter.clips.map((clip): [string, Clip] => [clip.identity, clip]),
        ),
      ),
    [detail],
  )
  const newClips = useMemo(
    () => new Set([...clips.values()].filter((c) => c.status === 'new').map((c) => c.identity)),
    [clips],
  )
  const folders = useMemo(() => diskFolders(clips.values()), [clips])
  const ignoredOf = useMemo(
    () => new Map(chapters.map((chapter) => [chapter.key, chapter.ignored])),
    [chapters],
  )
  const resolved = useMemo<Resolved | null>(
    () =>
      detail === null
        ? null
        : {
            title: detail.title ?? null,
            date: detail.date ?? null,
            location: detail.location ?? null,
          },
    [detail],
  )

  // Try again keeps the failure, and its button, shown while it reads (`retry`).
  const readReel = useCallback((retry = false) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    dispatch({ type: retry ? 'retrying' : 'reading' })
    fetchReel(eventId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        if (result.kind === 'ok') {
          const agrees = detail === null || detailMatchesDocument(detail, result.document)
          dispatch({
            type: 'read',
            document: result.document,
            etag: result.etag,
            chapters: agrees ? chapters : null,
          })
        } else {
          dispatch({ type: 'read-failed', failure: readFailure(result, eventId) })
        }
      })
      .catch((error: unknown) => {
        // An abort is an unmount or a superseding read, not a failure.
        if (controller.signal.aborted) {
          return
        }
        dispatch({
          type: 'read-failed',
          failure: { cause: 'reel.yaml could not be read.', detail: String(error) },
        })
      })
  }, [chapters, detail, eventId])

  // Depends on the event id only (`detail` and `chapters` never change).
  useEffect(() => {
    readReel()
    return () => inFlight.current?.abort()
  }, [readReel])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const ready = state.status === 'ready' ? state : null
  const locked = ready !== null && ready.pressed !== null
  // A Move marked to… applied in a transition (`onMoveMarked`): until it lands, the page shows
  // the order from before it, so no control that acts on what is shown may act yet.
  const [movePending, setMovePending] = useState(false)
  // The chapter chosen in the Move marked to… picker; '' for none.
  const [moveTo, setMoveTo] = useState<ChapterKey | ''>('')
  const listsLocked = locked || movePending
  const changed = ready === null ? [] : changedFields(ready.baseline.read, ready.draft.metadata)
  const chapterEdits =
    ready === null ? NO_CHANGES : chapterChanges(ready.baseline, ready.draft.chapters)
  let movedCount = 0
  if (ready !== null) {
    // Against each original order without the clips it no longer holds: a removal, or a
    // clip moved out, moves nothing by itself; a clip moved in counts once, where it is.
    for (const [key, order] of ready.draft.orders) {
      const original = ready.baseline.original.get(key) ?? []
      movedCount += movedSet(keptOriginal(original, order), order, ready.lastMoved).size
    }
  }
  const adopted = ready === null ? 0 : adoptedNewCount(ready.baseline, ready.draft, newClips)
  const cardsChanged =
    ready === null
      ? 0
      : cardsChangedCount(
          listedChapters(ready.draft.chapters).map((chapter) => chapter.key),
          ready.draft.cards,
          (key) => readCardOf(ready.baseline, key),
        )
  // Edits to save, and edits at all (a date typed in part, or a cut typed and not added,
  // is one, but cannot be saved).
  const edited = ready !== null && isDirty(ready.baseline, ready.draft)
  const dirty = edited || (ready !== null && unfinished(ready))
  // While there are edits; a vanished event keeps its alert even without any.
  const showBar = ready !== null && (dirty || ready.problem?.kind === 'gone')

  useUnsavedGuard(dirty)
  // The page and the navigation guard hold every way out while a save is in flight.
  useEffect(() => {
    setSaving(locked)
    return () => setSaving(false)
  }, [locked])

  // The bar is in the page from the start and `hidden` while clean, so none of this exists
  // until it is shown (a hidden bar has no box to place, observe or keep toasts clear of).
  // Held or resting (`placeBar`), and the held bar's height, for the bottom scroll
  // padding (focus never hides under it); absent while the bar rests, which holds no
  // room at the window's bottom. Decided in the commit that shows the bar, so the
  // scroll a move or a drop makes right after (a passive effect) already clears it;
  // it wraps when narrow,
  // so a ResizeObserver follows later changes, and a zoom or a resized window
  // changes the window's height alone, so `resize` does too. Registered, the bar has
  // the toasts place themselves above it while it is held at the window's bottom,
  // below it once it rests (at the page's end, or for its height).
  useLayoutEffect(() => {
    const bar = barRef.current
    if (!showBar || bar === null) {
      return
    }
    const root = document.documentElement
    const place = () => placeBar(bar)
    const focusedInBar = () => {
      const focused = document.activeElement
      return focused instanceof HTMLElement && bar.contains(focused) ? focused : null
    }
    // Whether the bar's focused control was wholly in the window before this resize:
    // noted on every scroll and every focus move into the bar, and after each resize.
    let shown = false
    const note = () => {
      const focused = focusedInBar()
      shown = focused !== null && inWindow(focused)
    }
    // A zoom or a resized window: a resting bar's focused control that was in the
    // window stays there at every step, as the bar moves with the page's end. Not
    // after the operator scrolled it away, and not for a `resize` that changed no
    // size (a phone's URL bar fires them). Only here: a commit or the bar's own
    // resize never scrolls the page.
    let width = root.clientWidth
    let height = root.clientHeight
    const follow = () => {
      if (root.clientWidth === width && root.clientHeight === height) {
        return
      }
      width = root.clientWidth
      height = root.clientHeight
      placeBar(bar)
      const focused = focusedInBar()
      if (shown && focused !== null && bar.hasAttribute('data-rests')) {
        keepInView(focused, bar)
      }
      note()
    }
    place()
    note()
    const release = keepToastsClearOf(bar)
    const observer = new ResizeObserver(place)
    observer.observe(bar)
    window.addEventListener('resize', follow)
    window.addEventListener('scroll', note, { passive: true })
    bar.addEventListener('focusin', note)
    return () => {
      bar.removeEventListener('focusin', note)
      window.removeEventListener('scroll', note)
      window.removeEventListener('resize', follow)
      observer.disconnect()
      release()
      root.style.removeProperty('scroll-padding-bottom')
    }
  }, [showBar])

  // Every commit can change what the bar says (an answer, the summary, a pressed
  // control), so its place is decided again before paint, and before the answer's
  // focus scroll below measures the page.
  useLayoutEffect(() => {
    if (showBar && barRef.current !== null) {
      placeBar(barRef.current)
    }
  })

  // After a failed answer focus stays on the pressed control, which the save bar's
  // alert describes. An unusable date or title moves it to the message at those
  // fields; a pressed control that went with its alert (another kind of failure
  // replaced it) hands focus to the new alert, never to <body>. The answer may
  // grow the bar: in a short window held at its top the sticky bar cannot rise
  // above the editor, and its last row falls below the window; a bar that rests
  // for its height (`placeBar`) sits at the page's end. Whatever holds focus then
  // is scrolled into view, and the rest of the bar comes with it.
  const answers = ready?.answers ?? 0
  useEffect(() => {
    if (answers === 0) {
      return
    }
    if (refusalRef.current !== null) {
      refusalRef.current.focus()
    } else if (document.activeElement === null || document.activeElement === document.body) {
      alertRef.current?.focus()
    }
    const focused = document.activeElement
    if (focused instanceof HTMLElement && focused !== document.body) {
      keepInView(focused, barRef.current)
    }
  }, [answers])

  // After Reset the heading has focus (the bar went with its buttons) but the page may have
  // shrunk and scrolled, or sit far from the heading at the top. The scroll waits for the
  // commit that dropped the edits, because only then is the page's length and scroll
  // position final; it moves the least distance, and none when the heading is in view
  // (`keepInView`: under the sticky header counts as out). Before paint, so the operator
  // never sees the heading go by.
  const resets = ready?.resets ?? 0
  const seenResets = useRef(resets)
  useLayoutEffect(() => {
    if (resets === seenResets.current) {
      return
    }
    seenResets.current = resets
    const heading = document.querySelector<HTMLElement>('main:not([hidden]) h1')
    if (heading !== null && document.activeElement === heading) {
      keepInView(heading, null)
    }
  }, [resets])

  // Every announcement changes the region, a repeated one too: cleared, then set a frame later.
  const announce = useCallback((message: string) => {
    setAnnouncement('')
    window.requestAnimationFrame(() => setAnnouncement(message))
  }, [])

  // Try again's answer. A failure keeps focus on Try again. The same failure is
  // said again through the live region, since its alert's text did not change and
  // the alert's role does not repeat it; a new one is said once, by its alert. A
  // read moves focus to the fields' heading, a changed event to Read again, and the
  // failure said before leaves the live region. A layout effect: a read unmounts
  // the focused button, and no frame may paint with focus on <body>.
  useLayoutEffect(() => {
    if (retried.current === null || state.status === 'loading') {
      return
    }
    if (state.status === 'failed') {
      if (state.retrying === true) {
        return
      }
      if (failureWords(state) === retried.current) {
        // The cause and its kind, as the alert's title says them.
        announce(
          state.failure === undefined
            ? state.cause
            : `${state.cause} ${FAILURE_LABEL[state.failure]}`,
        )
      }
    } else {
      setAnnouncement('')
      if (state.status === 'ready') {
        detailsHeadingRef.current?.focus()
      } else {
        readAgainRef.current?.focus()
      }
    }
    retried.current = null
  }, [state, announce])

  const onMove = useCallback<MoveHandler>(
    (chapter, from, to) => dispatch({ type: 'move', chapter, from, to }),
    [],
  )

  // Only a clip the page read as missing: a clip on disk is never removed from reel.yaml here.
  const onRemove = useCallback<RemoveHandler>(
    (chapter, identity) => {
      if (clips.get(identity)?.status === 'missing') {
        dispatch({ type: 'remove', chapter, identity })
      }
    },
    [clips],
  )

  const onRestore = useCallback<RestoreHandler>(
    (identity) => dispatch({ type: 'restore', identity }),
    [],
  )

  // Each clip's cut panel, shown or not and its fields as typed, by identity: here, not
  // in its row, which Move marked to… mounts anew in another chapter. Reset empties it, and
  // closes every clip preview (one open at a time, `preview/previews.ts`).
  const [cutPanels] = useState(() => {
    const held = new Map<string, PanelState>()
    const previews = createClipPreviews()
    const panels: CutPanels = {
      get: (identity) => held.get(identity),
      set: (identity, next) => {
        held.set(identity, next)
      },
      previews,
    }
    return {
      panels,
      clear: () => {
        held.clear()
        previews.hideAll()
      },
    }
  })

  // Each chapter's removed clips, in its original order; one shared empty list for the rest.
  const removals = ready?.draft.removed
  const removedByChapter = useMemo(
    () =>
      new Map(
        chapters.map((chapter) => {
          const gone = chapter.movable.filter((identity) => removals?.get(identity) === chapter.key)
          return [chapter.key, gone.length === 0 ? NONE_REMOVED : gone]
        }),
      ),
    [chapters, removals],
  )

  // The chapter list now, and how the event's own chapter is headed: `Main` while a
  // chapter a save keeps has a name, else `Clips`.
  const draftList = ready?.draft.chapters
  const orders = ready?.draft.orders
  const originals = ready?.baseline.original
  const listed = useMemo(() => listedChapters(draftList ?? []), [draftList])
  const hasNamedChapter = listed.some((chapter) => chapter.name !== '')
  const notes = useMemo(
    () => laterClipNotes({ chapters: draftList ?? [], folders, ignored: ignoredOf }),
    [draftList, folders, ignoredOf],
  )
  const origins = useMemo<Origins>(() => {
    if (originals === undefined || draftList === undefined) {
      return NO_ORIGINS
    }
    const headings = new Map(
      draftList.map((chapter) => [chapter.key, chapterHeading(chapter.name, hasNamedChapter)]),
    )
    return new Map(
      [...originOf(originals)].map(([identity, key]) => [
        identity,
        { key, heading: headings.get(key) ?? '' },
      ]),
    )
  }, [originals, draftList, hasNamedChapter])

  // The state the chapter handlers below act on: they stay the same functions, so
  // a chapter's tools keep their memoised props and typing in a field re-renders no list.
  const latest = useRef<Ready | null>(null)
  // A Move marked to… is pending, set before the transition starts and cleared when it
  // lands: a press meanwhile would act on the order from before the move.
  const moving = useRef(false)
  // A clip lifted by the drag and not yet dropped (`ChapterDrag`'s `onLift`).
  const lifted = useRef(false)
  const onLift = useCallback((is: boolean) => {
    lifted.current = is
  }, [])
  useLayoutEffect(() => {
    latest.current = ready
    moving.current = movePending
  })
  /** Whether a chapter control may act now: not while a save or a move of marked clips is pending. */
  const idle = (current: Ready | null): current is Ready =>
    current !== null && current.pressed === null && !moving.current

  /** The later-clips notes a chapter has once `draft` is the draft, for an announcement. */
  const notesIn = useCallback(
    (draft: Draft, key: ChapterKey): string => {
      const lines = laterClipNotes({ chapters: draft.chapters, folders, ignored: ignoredOf })
      return (lines.get(key) ?? []).map((line) => ` ${line}`).join('')
    },
    [folders, ignoredOf],
  )

  // The cut operations: one stable object, so the rows keep their memoised props. The
  // panel checks a cut and speaks it; a press while a save or a move of marked clips is pending
  // changes nothing here either.
  const cutHandlers = useMemo<CutHandlers>(
    () => ({
      onAdd: (identity, span, reason) => {
        const current = latest.current
        if (current !== null && current.pressed === null && !moving.current) {
          dispatch({ type: 'cut-add', identity, span, key: `a${current.nextCut + 1}`, reason })
        }
      },
      onRemove: (identity, key) => dispatch({ type: 'cut-remove', identity, key }),
      onRestore: (identity, key) => dispatch({ type: 'cut-restore', identity, key }),
      onTyped: (identity, typed) => dispatch({ type: 'cut-typed', identity, typed }),
      onAnnounce: announce,
    }),
    [announce],
  )

  // A cut trimmed on the Timeline: the same draft edit as a cut made in the Cuts panel, with
  // the same guard. A key's result is the handle's value; a drag's release and a typed time
  // are said once.
  const onTrim = useCallback<EditBinding['onTrim']>(
    (identity, key, span, note) => {
      const current = latest.current
      if (current === null || current.pressed !== null || moving.current) {
        return
      }
      const next = trimCut(current.baseline, current.draft, identity, key, span)
      if (next === current.draft) {
        return
      }
      dispatch({ type: 'cut-trim', identity, key, span })
      if (note.spoken) {
        const after = cutsOf(current.baseline.cuts, next.cuts, identity)
        const number = after.findIndex((cut) => cut.key === key) + 1
        announce(trimmedWords(number, note.name, span, keptCuts(after), note.snap))
      }
    },
    [announce],
  )

  // What the Timeline gets of the draft (`timeline/editing.ts`); null for the needs-attention form.
  const baseCuts = ready?.baseline.cuts
  const draftCuts = ready?.draft.cuts
  const orderChanged = ready !== null && layoutChanged(ready.baseline, ready.draft)
  // The clips' turns as saved, and as the draft has them: what every picture shows (`rotate/`).
  const readClips = ready?.baseline.read.clips
  const baseTurns = useMemo<ClipTurns>(
    () => (readClips === undefined ? new Map() : turnsOf(readClips)),
    [readClips],
  )
  const draftRotations = ready?.draft.rotations
  const draftTurns = useMemo<ClipTurns>(() => {
    if (draftRotations === undefined || draftRotations.size === 0) {
      return baseTurns
    }
    const turns = new Map(baseTurns)
    for (const [identity, turn] of draftRotations) {
      if (turn === 0) {
        turns.delete(identity)
      } else {
        turns.set(identity, turn)
      }
    }
    return turns
  }, [baseTurns, draftRotations])
  // The title cards' lengths (`title-card-duration-drag`): a drag or a key on the Timeline is one
  // edit of the card's `duration` in the draft (`title-card-inspector`), keyed there by the
  // chapter's saved name and here by its key; the same guard as a trim.
  const liveDetail = liveEvent ?? detail
  const savedSpecs = useMemo(() => (liveDetail === null ? [] : cardSpecs(liveDetail)), [liveDetail])
  const savedSpecsRef = useRef(savedSpecs)
  savedSpecsRef.current = savedSpecs
  const onCardDuration = useCallback<EditBinding['onCardDuration']>(
    (chapter, seconds, words) => {
      const current = latest.current
      if (current === null || current.pressed !== null || moving.current) {
        return
      }
      const held = current.draft.chapters.find(
        (candidate) => candidate.readName === chapter && !candidate.deleted,
      )
      const resolved = savedSpecsRef.current.find((spec) => spec.chapter === chapter)?.card?.duration
      if (held === undefined || resolved === undefined) {
        return
      }
      const next = setCardLength(current.baseline, current.draft, held.key, seconds, resolved)
      if (next === current.draft) {
        return
      }
      dispatch({ type: 'card-length', key: held.key, seconds, resolved })
      if (words !== null) {
        announce(words)
      }
    },
    [announce],
  )
  // Use as poster: the frame the Timeline's video showed, kept as an object URL until the draft
  // no longer needs it (another frame, Use default, Reset, a re-read, leaving).
  const [posterFrame, setPosterFrame] = useState<
    { url: string; turn: Turn; pick: PosterPick } | null
  >(null)
  const dropFrame = useCallback(() => {
    setPosterFrame((was) => {
      if (was !== null) {
        URL.revokeObjectURL(was.url)
      }
      return null
    })
  }, [])
  const frameRef = useRef(posterFrame)
  frameRef.current = posterFrame
  useEffect(
    () => () => {
      if (frameRef.current !== null) {
        URL.revokeObjectURL(frameRef.current.url)
      }
    },
    [],
  )
  const posterBaseline = ready?.baseline
  const posterResets = ready?.resets
  useEffect(() => dropFrame(), [posterBaseline, posterResets, dropFrame])
  const onPoster = useCallback<EditBinding['onPoster']>(
    (pick, snapshot) => {
      const current = latest.current
      if (current === null || current.pressed !== null || moving.current) {
        URL.revokeObjectURL(snapshot.url)
        return
      }
      setPosterFrame((was) => {
        if (was !== null) {
          URL.revokeObjectURL(was.url)
        }
        return { ...snapshot, pick }
      })
      dispatch({ type: 'poster', pick })
      announce(chosenWords(fileName(pick.clip), pick.at))
    },
    [announce],
  )
  const onUseDefault = useCallback(() => {
    const current = latest.current
    if (current === null || current.pressed !== null || moving.current) {
      return
    }
    dropFrame()
    dispatch({ type: 'poster', pick: null })
    announce('Poster set to the default frame, the first clip. Not saved.')
  }, [announce, dropFrame])
  const resetCount = ready?.resets ?? 0
  const readLook = ready?.baseline.read.look
  const editing = useMemo<EditBinding | null>(() => {
    if (baseCuts === undefined || draftCuts === undefined || detail === null) {
      return null
    }
    return {
      cuts: liveTrims(baseCuts, draftCuts),
      turns: draftTurns,
      listed: (identity) => cutsOf(baseCuts, draftCuts, identity),
      onTrim,
      onPoster,
      onAdd: cutHandlers.onAdd,
      locked: listsLocked,
      announce,
      orderChanged,
      previews: cutPanels.panels.previews,
      epoch: resetCount,
      look: readLook,
      onCardDuration,
    }
  }, [
    readLook,
    baseCuts,
    draftCuts,
    draftTurns,
    detail,
    listsLocked,
    onTrim,
    onPoster,
    cutHandlers,
    announce,
    orderChanged,
    cutPanels,
    resetCount,
    onCardDuration,
  ])

  // The card rows (`CardRow.tsx`) and the Timeline's blocks: each chapter's saved card, matched by
  // the name it was read with, as the draft would have it drawn (`card/specs.ts`).
  const savedStyle = useMemo<EventStyle | null>(() => {
    const style = liveDetail?.title_card
    return style == null
      ? null
      : {
          duration: style.duration,
          background: style.background,
          font_family: style.font_family,
          title_font_size: style.title_font_size,
          subtitle_font_size: style.subtitle_font_size,
          text_color: style.text_color,
          position: style.position,
        }
  }, [liveDetail])
  // The event style the cards inherit now: the saved resolved style under the draft's edits of
  // `look.title_card` (`cardStyle.ts`), so a card, a row and a preview see it before a save.
  const baselineNow = ready?.baseline
  const draftStyleNow = ready?.draft.style
  // The draft holds a style only while it differs from the one read.
  const styleEdited = draftStyleNow !== undefined
  const eventStyle = useMemo<EventStyle | null>(
    () =>
      baselineNow === undefined || draftStyleNow === undefined
        ? savedStyle
        : draftEventStyle(draftStyleNow, readStyle(baselineNow.read.look), savedStyle),
    [baselineNow, draftStyleNow, savedStyle],
  )
  const styleForPreview = useMemo(
    () => (baselineNow === undefined ? undefined : previewStyle(baselineNow.read.look, draftStyleNow)),
    [baselineNow, draftStyleNow],
  )
  const draftChapters = ready?.draft.chapters
  const draftCards = ready?.draft.cards
  const draftEventTitle = ready?.draft.metadata.title ?? ''
  const specs = useMemo(() => {
    if (baselineNow === undefined || draftChapters === undefined || draftCards === undefined) {
      return savedSpecs
    }
    return savedSpecs.map((spec) => {
      const chapter = draftChapters.find((candidate) => candidate.readName === spec.chapter)
      const card = chapter === undefined ? undefined : draftCards.get(chapter.key)
      if (chapter === undefined || (card === undefined && !styleEdited)) {
        return spec
      }
      const typed = draftEventTitle.trim() === '' ? (resolved?.title ?? '') : draftEventTitle
      return draftSpec(
        spec,
        eventStyle,
        readCardOf(baselineNow, chapter.key),
        card,
        spec.chapter === '' ? typed : chapter.name,
        styleEdited,
      )
    })
  }, [
    savedSpecs,
    draftChapters,
    draftCards,
    baselineNow,
    eventStyle,
    styleEdited,
    draftEventTitle,
    resolved,
  ])
  const { retain: retainCard, select: selectCard, clear: clearCard, selected: selectedCard } = cards
  // The selection ends with its chapter: deleted in the draft, it is gone from the list.
  useEffect(() => {
    if (draftChapters !== undefined) {
      retainCard(
        draftChapters.flatMap((chapter) =>
          chapter.readName !== null && !chapter.deleted ? [chapter.readName] : [],
        ),
      )
    }
  }, [draftChapters, retainCard])
  // A refused save that names a card opens that card, so the message is at its field.
  const refusedCard = ready?.cardRefusal ?? null
  const refusedAnswer = ready?.answers ?? 0
  useEffect(() => {
    if (refusedCard === null || draftChapters === undefined) {
      return
    }
    const chapter = draftChapters.find((candidate) => candidate.key === refusedCard.key)
    if (chapter?.readName != null) {
      selectCard(chapter.readName)
    }
    // Once per answer: selecting another card afterwards is the operator's.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refusedAnswer])
  // The Title cards switch: the draft's position while it differs from what the service said.
  const draftDecorators = ready?.draft.decorators
  const switchDraft = draftDecorators === undefined ? null : titleCardsNow(draftDecorators, false)
  const cardEditing = useMemo<CardEditing | null>(() => {
    if (baselineNow === undefined || draftChapters === undefined || draftCards === undefined) {
      return null
    }
    const keyOf = (saved: string) =>
      draftChapters.find((chapter) => chapter.readName === saved && !chapter.deleted)
    return {
      specs,
      style: eventStyle,
      styleError: liveDetail?.title_card_error ?? null,
      previewStyle: styleForPreview,
      view: (saved) => {
        const chapter = keyOf(saved)
        if (chapter === undefined) {
          return null
        }
        return {
          key: chapter.key,
          name: chapter.name,
          opening: saved === '',
          card: draftCards.get(chapter.key) ?? readCardOf(baselineNow, chapter.key),
          read: readCardOf(baselineNow, chapter.key),
          eventTitle: draftEventTitle,
          folderTitle: resolved?.title ?? null,
          refusal:
            refusedCard !== null && refusedCard.key === chapter.key
              ? { field: refusedCard.field, message: refusedCard.message }
              : null,
        }
      },
      set: (saved, field, value) => {
        const chapter = keyOf(saved)
        if (chapter !== undefined && idle(latest.current)) {
          dispatch({ type: 'card-field', key: chapter.key, field, value })
        }
      },
      reset: (saved) => {
        const chapter = keyOf(saved)
        if (chapter !== undefined && idle(latest.current)) {
          dispatch({ type: 'card-reset', key: chapter.key })
        }
      },
      announce,
      titleCardsDraft: switchDraft,
      locked: listsLocked,
    }
  }, [
    switchDraft,
    baselineNow,
    draftChapters,
    draftCards,
    specs,
    eventStyle,
    styleForPreview,
    liveDetail,
    draftEventTitle,
    resolved,
    refusedCard,
    announce,
    listsLocked,
  ])
  const rowsState = cardsEnabled(liveDetail?.title_cards, switchDraft)
  const rowsEnabled = rowsState === 'invalid' ? null : rowsState === 'on'
  const cardRows = useMemo<CardRowsModel>(
    () => ({
      rowOf: (key) => {
        const chapter = draftChapters?.find((candidate) => candidate.key === key)
        return chapter === undefined
          ? null
          : cardRowInfo(
              chapter,
              specs,
              baselineNow === undefined || draftCards === undefined
                ? undefined
                : overrideWords(draftCards.get(chapter.key) ?? readCardOf(baselineNow, chapter.key)),
              rowsEnabled,
            )
      },
      selected: selectedCard,
      select: selectCard,
      clear: clearCard,
    }),
    [draftChapters, draftCards, baselineNow, specs, selectedCard, selectCard, clearCard, rowsEnabled],
  )

  // "Card style for this event": the draft's style against the one read, and what the cards inherit.
  const styleModel: CardStyleModel | null =
    ready === null || detail === null
      ? null
      : {
          eventId,
          read: readStyle(ready.baseline.read.look),
          style: styleOf(ready.baseline, ready.draft),
          resolved: savedStyle,
          error: liveDetail?.title_card_error ?? null,
          refusal: ready.styleRefusal,
          previewStyle: styleForPreview,
          eventTitle: draftEventTitle,
          folderTitle: resolved?.title ?? null,
          locked: listsLocked,
          onSet: (field, value) => {
            if (idle(latest.current)) {
              dispatch({ type: 'style-field', field, value })
            }
          },
          onReset: () => {
            if (idle(latest.current)) {
              dispatch({ type: 'style-reset' })
              announce('Changes to the card style undone.')
            }
          },
        }

  // "Title cards: On / Off": the service's answer under the draft's switch.
  const answer = liveDetail?.title_cards ?? null
  const titleCardsModel: TitleCardsModel | null =
    ready === null || detail === null
      ? null
      : {
          answer,
          error: liveDetail?.title_cards_error ?? null,
          on: titleCardsNow(ready.draft.decorators, answer?.enabled ?? false),
          source: cardsSource(answer, switchDraft),
          changed: decoratorsChanged(ready.draft),
          locked: listsLocked,
          onSet: (on) => {
            if (answer !== null && idle(latest.current)) {
              dispatch({ type: 'title-cards', on, readEnabled: answer.enabled })
              announce(on ? `${TURNED_ON}.` : `${TURNED_OFF}.`)
            }
          },
          onReset: () => {
            if (idle(latest.current)) {
              dispatch({ type: 'title-cards-reset' })
              announce('Change to the title cards undone.')
            }
          },
        }

  const onAddChapter = useCallback(() => {
    if (idle(latest.current)) {
      setRefusedDelete(null)
      setChapterDialog({ kind: 'add' })
    }
  }, [])

  // The one open name field (`InlineName`): a chapter's title, or the main title card's 'title'.
  // Opening another replaces it; Reset, a save, Delete or Move chapter of its chapter, the leave
  // question and a re-read close it, keeping nothing.
  const [naming, setNaming] = useState<ChapterKey | typeof TITLE | null>(null)
  const closeNaming = useCallback((key: ChapterKey | typeof TITLE) => {
    setNaming((open) => (open === key ? null : open))
  }, [])
  const onNameUnsent = useCallback((unsent: boolean) => {
    dispatch({ type: 'name-unsent', unsent })
  }, [])

  // A name is kept as the existing edit (D5): a chapter's by `chapter-rename`, the title by the
  // metadata form's own `field` action, so the form's Title shows it and Reset undoes it.
  const keepChapterName = useCallback(
    (key: ChapterKey, name: string) => {
      const current = latest.current
      closeNaming(key)
      if (!idle(current)) {
        return
      }
      const before = headingIn(current.draft, key)
      const next = renameChapter(current.draft, key, name)
      if (next === current.draft) {
        return
      }
      dispatch({ type: 'chapter-rename', key, name })
      announce(`“${before}” renamed to “${name}”.${notesIn(next, key)}`)
    },
    [announce, notesIn, closeNaming],
  )
  const nameField = useMemo<NameFieldHandlers>(
    () => ({
      open: (key) => {
        if (idle(latest.current)) {
          setRefusedDelete(null)
          setNaming(key)
        }
      },
      check: (key, typed) => checkName(latest.current?.draft.chapters ?? [], typed, key),
      notes: (key, typed) =>
        latest.current === null
          ? []
          : nameDialogNote(
              { chapters: latest.current.draft.chapters, folders, ignored: ignoredOf },
              key,
              typed,
            ),
      keep: keepChapterName,
      drop: closeNaming,
      unsent: onNameUnsent,
    }),
    [folders, ignoredOf, keepChapterName, closeNaming, onNameUnsent],
  )

  const onMoveChapter = useCallback<ChapterMoveHandler>(
    (key, delta) => {
      const current = latest.current
      if (!idle(current)) {
        return
      }
      const next = moveChapter(current.draft, key, delta)
      if (next === current.draft) {
        return
      }
      setRefusedDelete(null)
      closeNaming(key)
      // The section moves in the DOM, which drops its focus: put it back (effects below).
      focusAfter.current = { key, target: delta < 0 ? 'chapter-up' : 'chapter-down' }
      dispatch({ type: 'chapter-move', key, delta })
      announce(`“${headingIn(next, key)}” moved to ${placeIn(next, key)}.`)
    },
    [announce, closeNaming],
  )

  const onDeleteChapter = useCallback<ChapterHandler>(
    (key) => {
      const current = latest.current
      const chapter = current?.draft.chapters.find((listedChapter) => listedChapter.key === key)
      if (!idle(current) || chapter === undefined) {
        return
      }
      const heading = headingIn(current.draft, key)
      const refusal = deleteRefusal(
        current.draft.chapters,
        chapter,
        heading,
        current.draft.orders.get(key) ?? [],
        ignoredOf.get(key) ?? [],
        clips,
      )
      if (refusal !== null) {
        // Nothing changes, focus stays on Delete; the reason shows and is said.
        setRefusedDelete(key)
        announce(refusal)
        return
      }
      setRefusedDelete(null)
      closeNaming(key)
      const next = deleteChapter(current.draft, key)
      dispatch({ type: 'chapter-delete', key })
      if (chapter.readName === null) {
        focusAfter.current = { key: null, target: 'add' }
        announce(`Chapter “${chapter.name}” removed.`)
      } else {
        focusAfter.current = { key, target: 'chapter-undo' }
        announce(`“${heading}” will be deleted when you save.${notesIn(next, key)}`)
      }
    },
    [announce, clips, ignoredOf, notesIn, closeNaming],
  )

  const onUndoDelete = useCallback<ChapterHandler>(
    (key) => {
      const current = latest.current
      if (!idle(current)) {
        return
      }
      const next = restoreChapter(current.draft, key)
      setRefusedDelete(null)
      focusAfter.current = { key, target: 'chapter-delete' }
      dispatch({ type: 'chapter-restore', key })
      announce(`“${headingIn(next, key)}” is back, ${placeIn(next, key)}.`)
    },
    [announce],
  )

  // The drag across chapters (`ChapterDrag`): what it reads, and its drop. It speaks
  // through dnd-kit's live region, as a drag within a chapter does.
  const listedKeys = useMemo(() => listed.map((chapter) => chapter.key), [listed])
  // A clip that cannot be marked (missing) never leaves its chapter by a drag either.
  const staysHome = useCallback((identity: string) => !onDisk(clips.get(identity)), [clips])
  // Asked only while a clip is lifted: the draft then is the latest one.
  const nameOfClip = useCallback(
    (identity: string) => {
      const current = latest.current
      return current === null
        ? identity
        : nameNow(current.draft, current.baseline.original, identity, ignoredOf, removedByChapter)
    },
    [ignoredOf, removedByChapter],
  )
  const headingOfChapter = useCallback(
    (key: ChapterKey) => (latest.current === null ? '' : headingIn(latest.current.draft, key)),
    [],
  )
  // Not while a save or a move of marked clips is pending, and only a clip on disk; false when refused.
  // Synchronous, not in a transition: the dragged copy leaves in the commit that shows the
  // clip in place.
  const onDropInto = useCallback(
    (identity: string, from: ChapterKey, to: ChapterKey, at: number) => {
      if (!idle(latest.current) || !onDisk(clips.get(identity))) {
        return false
      }
      dispatch({ type: 'clip-drop', from, to, identity, at })
      return true
    },
    [clips],
  )

  // Marks (edit/marks.ts): the clips a chapter plays that are on disk can be marked. The marks
  // in force are the state's, less any clip that cannot carry one (defensive: a mark is only
  // ever made on such a clip).
  const markable = useMemo(
    () =>
      new Set(
        [...(orders?.values() ?? [])].flatMap((order) =>
          order.filter((identity) => canMark(clips.get(identity))),
        ),
      ),
    [orders, clips],
  )
  const readMarks = ready?.marked
  const marks = useMemo(
    () => (readMarks === undefined ? NO_MARKS : pruneMarks(readMarks, markable)),
    [readMarks, markable],
  )
  // Each listed chapter's marked clips: one set per chapter that keeps its identity while the
  // chapter's own marks are unchanged, so marking in one chapter re-renders no other list.
  const marksCache = useRef(new Map<ChapterKey, ReadonlySet<string>>())
  const marksIn = useMemo(() => {
    const result = new Map<ChapterKey, ReadonlySet<string>>()
    for (const key of listedKeys) {
      const order = orders?.get(key) ?? NONE_REMOVED
      const mine = marks.size === 0 ? [] : order.filter((identity) => marks.has(identity))
      const previous = marksCache.current.get(key) ?? NO_MARKS
      result.set(
        key,
        previous.size === mine.length && mine.every((identity) => previous.has(identity))
          ? previous
          : new Set(mine),
      )
    }
    marksCache.current = result
    return result
  }, [listedKeys, orders, marks])
  const markLineRef = useRef<HTMLDivElement>(null)
  const rotateHintId = useId()

  // A mark or Clear marks: not while a save or a move of marked clips is pending, nor while a clip is
  // lifted (the group a drag lifted is the group it drops). Spoken once through the live region.
  const onMark = useCallback<MarkHandler>(
    (identity, on) => {
      const current = latest.current
      if (!idle(current) || lifted.current || (on && !canMark(clips.get(identity)))) {
        return
      }
      const marked = toggleMark(current.marked, identity, on)
      if (marked === current.marked) {
        return
      }
      dispatch({ type: 'mark', identity, on })
      announce(markWords(nameOfClip(identity), on, marked.size))
    },
    [clips, announce, nameOfClip],
  )
  const onClearMarks = useCallback(() => {
    const current = latest.current
    if (!idle(current) || lifted.current || current.marked.size === 0) {
      return
    }
    dispatch({ type: 'marks-clear' })
    announce(CLEARED_WORDS)
    // The button leaves with the count: focus goes to the line, not to <body>.
    markLineRef.current?.focus({ preventScroll: true })
  }, [announce])

  // Rotate left / right (`rotate/`): a clip on disk, not while a save or a move of marked clips is pending
  // nor while a clip is lifted. One draft edit, spoken once with the turn the clip now has.
  const onRotate = useCallback<RotateHandler>(
    (identity, way) => {
      const current = latest.current
      if (!idle(current) || lifted.current || !onDisk(clips.get(identity))) {
        return
      }
      const next = rotateGroup(current.baseline, current.draft, [identity], way, () => true)
      if (next === current.draft) {
        return
      }
      dispatch({ type: 'rotate', identities: [identity], way })
      announce(turnAnnouncement(nameOfClip(identity), turnOf(current.baseline, next, identity), way))
    },
    [clips, announce, nameOfClip],
  )
  // Rotate marked left / right: every marked clip on disk, each from its own turn, one edit.
  // The marks stay.
  const onRotateMarked = useCallback(
    (way: Way) => {
      const current = latest.current
      if (!idle(current) || lifted.current) {
        return
      }
      const group = groupOf(current.draft.orders, listedKeys, current.marked).filter((identity) =>
        onDisk(clips.get(identity)),
      )
      if (rotateGroup(current.baseline, current.draft, group, way, () => true) === current.draft) {
        return
      }
      dispatch({ type: 'rotate', identities: group, way })
      announce(groupTurnAnnouncement(group.length, way))
    },
    [clips, announce, listedKeys],
  )

  // A group drop (`ChapterDrag`): the marked clips as one run at a gap of `to`, one edit.
  // False when it changes nothing or is refused (save or move of marked clips pending); the marks stay.
  const onDropGroup = useCallback(
    (dragged: string, to: ChapterKey, gap: number) => {
      const current = latest.current
      if (!idle(current) || !isListed(current.draft, to)) {
        return false
      }
      const group = groupOf(current.draft.orders, listedKeys, current.marked)
      if (group.length < 2 || !group.includes(dragged)) {
        return false
      }
      if (moveGroup(current.draft, group, to, gap) === current.draft) {
        return false
      }
      dispatch({ type: 'group-drop', dragged, to, gap })
      return true
    },
    [listedKeys],
  )

  // Move marked to…: the marked clips, in page order, at the end of the chosen chapter, one
  // edit by the drag's own (`moveMarkedToEnd`). Applied in a transition (a 400-clip chapter
  // re-renders every row); until it lands every control acting on the lists is unavailable.
  const onMoveMarked = useCallback(() => {
    const current = latest.current
    if (!idle(current) || lifted.current || moveTo === '' || current.marked.size === 0) {
      return
    }
    const { moved } = moveMarkedToEnd(current.draft, listedKeys, current.marked, moveTo)
    if (moved.length === 0) {
      announce(NOTHING_MOVED)
      return
    }
    moving.current = true
    setMovePending(true)
    startTransition(() => {
      dispatch({ type: 'marked-move', to: moveTo })
      setMovePending(false)
    })
    announce(movedWords(moved.length, headingIn(current.draft, moveTo)))
  }, [announce, listedKeys, moveTo])
  // The chosen chapter leaves the picker when it is deleted (or the event stops listing it).
  useEffect(() => {
    if (moveTo !== '' && !listedKeys.includes(moveTo)) {
      setMoveTo('')
    }
  }, [listedKeys, moveTo])
  const moveReasonId = useId()
  const moveSelectId = useId()
  const moveWhy = moveReason(marks.size, moveTo !== '')

  // The main title card's line (TitleCard.tsx): the draft's title, edited in place of the form's.
  const draftTitle = ready?.draft.metadata.title ?? ''
  const draftMetadata = ready?.draft.metadata
  const readDocument = ready?.baseline.read
  const titleChanged = changed.includes('title')
  const titleCard = useMemo<TitleCardModel>(
    () => ({
      draftTitle,
      resolvedTitle: resolved?.title ?? null,
      changed: titleChanged,
      open: naming === TITLE,
      locked: listsLocked,
      inheritHint: (typed) =>
        readDocument === undefined || draftMetadata === undefined
          ? null
          : inheritHint('title', readDocument, { ...draftMetadata, title: typed }, resolved),
      onOpen: () => {
        if (idle(latest.current)) {
          setNaming(TITLE)
        }
      },
      onKeep: (title) => {
        const current = latest.current
        closeNaming(TITLE)
        if (!idle(current) || current.draft.metadata.title === title) {
          return
        }
        dispatch({ type: 'field', field: 'title', value: title })
        announce(
          title.trim() === ''
            ? 'Title cleared. It inherits from the folder name.'
            : `Title set to “${title.trim()}”.`,
        )
      },
      onDrop: () => closeNaming(TITLE),
      onUnsent: onNameUnsent,
    }),
    [
      draftTitle,
      draftMetadata,
      readDocument,
      resolved,
      titleChanged,
      naming,
      listsLocked,
      announce,
      closeNaming,
      onNameUnsent,
    ],
  )

  // The open name field, if its chapter is still listed (an undone deletion brings it back closed).
  const openName =
    naming === TITLE || (naming !== null && listed.some((chapter) => chapter.key === naming))
      ? naming
      : null
  // Each listed chapter's tools: what it offers, its notes and why it cannot go. A
  // chapter's object is kept while what it shows is unchanged, so its list re-renders
  // only when its own tools change.
  const toolsCache = useRef(new Map<ChapterKey, ChapterToolsModel>())
  const tools = useMemo(() => {
    const result = new Map<ChapterKey, ChapterToolsModel>()
    const several = listed.length > 1
    listed.forEach((chapter, index) => {
      const heading = chapterHeading(chapter.name, hasNamedChapter)
      const order = orders?.get(chapter.key) ?? NONE_REMOVED
      const lines = [
        chapter.name === '' && several && OWN_CHAPTER_NOTE,
        chapter.readName === null && 'New chapter.',
        chapter.readName !== null &&
          chapter.name !== chapter.readName &&
          `Renamed from “${chapter.readName}”.`,
        ...(notes.get(chapter.key) ?? []),
      ].filter((line): line is string => line !== false)
      const refusal = several
        ? deleteRefusal(
            listed,
            chapter,
            heading,
            order,
            ignoredOf.get(chapter.key) ?? [],
            clips,
          )
        : undefined
      const model: ChapterToolsModel = {
        notes: lines,
        naming: openName === chapter.key,
        place: several ? { first: index === 0, last: index === listed.length - 1 } : null,
        deleteRefusal: refusal,
        refusalShown: refusedDelete === chapter.key && refusal != null,
        locked: listsLocked,
        nameField,
        onMoveChapter,
        onDelete: onDeleteChapter,
      }
      const previous = toolsCache.current.get(chapter.key)
      result.set(
        chapter.key,
        previous !== undefined && sameTools(previous, model) ? previous : model,
      )
    })
    toolsCache.current = result
    return result
  }, [
    listed,
    hasNamedChapter,
    orders,
    notes,
    ignoredOf,
    clips,
    refusedDelete,
    listsLocked,
    openName,
    nameField,
    onMoveChapter,
    onDeleteChapter,
  ])

  // The unsaved-changes question closes an open chapter dialog first, as a cancel: in
  // the same commit, so the question's dialog opens over the page, not over it.
  const shownDialog = leaveQuestion === 0 ? chapterDialog : null
  useEffect(() => {
    if (leaveQuestion !== 0) {
      setChapterDialog(null)
      setNaming(null)
    }
  }, [leaveQuestion])
  // A save starting and a re-read close the open name field too, keeping nothing.
  const savePending = ready?.pressed != null
  const readBaseline = ready?.baseline
  useEffect(() => {
    setNaming(null)
  }, [savePending, readBaseline])

  // Focus after a chapter edit, once its result is on screen (`focusAfter`): a layout
  // effect, so no frame paints with focus on <body> after a section moved. The new
  // chapter's heading is the exception, focused by the passive effect below: closing
  // the name dialog returns focus to Add chapter from the dialog's own passive
  // cleanup, which runs after every layout effect of the commit and would undo it.
  useLayoutEffect(() => {
    const request = focusAfter.current
    const root = editorRef.current
    if (request === null || request.target === 'heading' || root === null) {
      return
    }
    focusAfter.current = null
    const target =
      request.target === 'add'
        ? root.querySelector<HTMLElement>('.chapter-add-button')
        : root.querySelector<HTMLElement>(
            `[data-chapter-key="${request.key}"] .${request.target}`,
          )
    target?.focus({ preventScroll: true })
    scrollAfter.current = target?.closest<HTMLElement>('.chapter-tools') ?? target
  })

  // The new chapter's heading takes focus here, after the dialog's cleanup; then the
  // part of the page focus went to comes into view, clear of the header and the bar.
  useEffect(() => {
    const request = focusAfter.current
    const root = editorRef.current
    if (request !== null && request.target === 'heading' && root !== null) {
      focusAfter.current = null
      const section = root.querySelector<HTMLElement>(`[data-chapter-key="${request.key}"]`)
      section?.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true })
      scrollAfter.current = section
    }
    const element = scrollAfter.current
    scrollAfter.current = null
    element?.scrollIntoView({ block: 'nearest' })
  })

  function closeChapterDialog(): void {
    setChapterDialog(null)
  }

  function confirmName(name: string): void {
    const current = latest.current
    if (current === null || shownDialog === null || shownDialog.kind !== 'add') {
      return
    }
    setChapterDialog(null)
    const key = `a${current.added + 1}`
    const next = addChapter(current.draft, key, name)
    focusAfter.current = { key, target: 'heading' }
    dispatch({ type: 'chapter-add', key, name })
    announce(
      `Chapter “${name}” added, ${placeIn(next, key)}. It has no clips.${notesIn(next, key)}`,
    )
  }

  function submit(pressed: Pressed, operation: Operation): void {
    // Never a half-typed date (it would be sent as unset), never without a cut typed
    // but not added (it would be lost), and never a save of nothing.
    // Nor while a move of marked clips is pending: the draft shown is the one from before it.
    if (
      ready === null ||
      saving.current ||
      moving.current ||
      unfinished(ready) ||
      !edited
    ) {
      return
    }
    saving.current = true
    dispatch({ type: 'save-start', pressed })
    const { read } = ready.baseline
    const body = buildWriteBody(ready.baseline, ready.draft)
    const name = eventName(
      eventId,
      savedValue('title', read, body, resolved),
      savedValue('date', read, body, resolved),
    )
    send(eventId, body, ready.etag, operation)
      .catch((error: unknown) => {
        // An error in this page: send() returns a missing or unexpected answer as a value.
        console.error('Edit mode: the save stopped on an error', error)
        return {
          saved: false as const,
          problem: { kind: 'page' as const, retry: operation },
          refusal: null,
        }
      })
      .then((outcome) => {
        saving.current = false
        if (outcome.saved) {
          // Even after an unmount: the list learns of the save, and the page, if it is
          // still shown, reads the event again (its exit does nothing once it is gone).
          toast.success(`Saved ${name}`)
          markEventsChanged()
          onSaved()
        } else if (mounted.current) {
          dispatch({ type: 'save-failed', problem: outcome.problem, refusal: outcome.refusal })
        }
      })
  }

  // Ctrl+S (Cmd+S on a Mac) saves from wherever focus is, so Save is not a Tab stop per control
  // away. A listener on `document`, not on the editor: focus may be on <body> or in the header. It
  // calls `submit`, never the button's click, so it works with the bar hidden or rested, and it
  // asks `saveHold` first, the rule the button uses, which `submit` alone does not know (a
  // conflict or a vanished event). Registered once per ready/not-ready; the latest handler is
  // reached through a ref, so typing in a field does not re-register it.
  const onSaveKey = useRef<(event: KeyboardEvent) => void>(() => undefined)
  useLayoutEffect(() => {
    onSaveKey.current = (event) => {
      const current = latest.current
      if (current === null) {
        return
      }
      // preventDefault always, so the browser's Save page never opens over the editor.
      event.preventDefault()
      const hold = saveHold(edited, unfinished(current), current.problem)
      const action = saveKeyAction({
        repeat: event.repeat,
        saving: saving.current,
        pressed: current.pressed !== null,
        moving: moving.current,
        lifted: lifted.current,
        dialogOpen: document.querySelector('dialog[open]') !== null,
        hold,
      })
      if (action === 'lifted') {
        announce(LIFTED_WORDS)
        return
      }
      if (action === 'announce' && hold !== null) {
        announce(
          holdWords(hold, current.dateIncomplete, current.typed.size > 0, current.nameUnsent),
        )
        return
      }
      if (action !== 'save') {
        return
      }
      announce('Saving…')
      submit('save', 'save')
    }
  })
  const listening = ready !== null
  useEffect(() => {
    if (!listening) {
      return undefined
    }
    const listener = (event: KeyboardEvent) => {
      if (isSaveChord(event)) {
        onSaveKey.current(event)
      }
    }
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [listening])

  const retrying = state.status === 'failed' && state.retrying === true
  const hasIgnored = chapters.some((chapter) => chapter.ignored.length > 0)
  const hasMissing = [...clips.values()].some((clip) => clip.status === 'missing')
  const clipCount = chapters.reduce((sum, chapter) => sum + chapter.movable.length, 0)

  return (
    <div
      ref={editorRef}
      className="event-editor"
      // Keyboard focus that lands partly hidden comes into view whole: for a text area
      // the browser scrolls only its caret into view. Focus from a pointer press is
      // left alone (a text field matches :focus-visible even then), so a press never
      // moves its control, or the caret, from under the pointer.
      onPointerDownCapture={() => {
        pointerPressed.current = true
        window.setTimeout(() => {
          pointerPressed.current = false
        }, 0)
      }}
      onFocus={(event) => {
        if (
          !pointerPressed.current &&
          event.target instanceof HTMLElement &&
          event.target.matches(':focus-visible')
        ) {
          keepInView(event.target, barRef.current)
        }
      }}
    >
      {/* The one live region for the reel read, the button moves, removals and Undos; dnd-kit
          speaks the drags. */}
      <p role="status" className="visually-hidden">
        {state.status === 'loading' || retrying ? 'Reading reel.yaml…' : announcement}
      </p>

      {state.status === 'loading' && (
        <div className="panel" aria-hidden="true">
          <div className="panel-header">
            <span className="edit-reading">Reading reel.yaml…</span>
          </div>
          <SkeletonRows rows={4} />
        </div>
      )}

      {state.status === 'failed' && (
        <Alert
          tone="err"
          title={
            <>
              {state.cause}{' '}
              {state.failure !== undefined && (
                <Pill
                  tone={FAILURE_LOOK[state.failure].tone}
                  icon={FAILURE_LOOK[state.failure].icon}
                >
                  {FAILURE_LABEL[state.failure]}
                </Pill>
              )}
            </>
          }
          detail={state.detail}
          action={
            <>
              {/* Busy, not disabled, while it reads: it keeps keyboard focus. */}
              <button
                type="button"
                className="btn btn-secondary"
                aria-disabled={retrying || undefined}
                aria-busy={retrying || undefined}
                onClick={() => {
                  if (retried.current === null && state.status === 'failed') {
                    retried.current = failureWords(state)
                    // Cleared, so the region says nothing stale once the answer comes.
                    setAnnouncement('')
                    readReel(true)
                  }
                }}
              >
                <Icon name="refresh" />
                Try again
              </button>
              {state.notFound === true && (
                <a className="btn btn-ghost" href={LIST_HREF}>
                  <Icon name="chevron-left" />
                  Back to the event list
                </a>
              )}
            </>
          }
        />
      )}

      {state.status === 'changed' && (
        <Alert
          tone="warn"
          title="This event changed on disk since the page was read."
          detail={CHANGED_DETAIL}
          action={
            <button ref={readAgainRef} type="button" className="btn btn-primary" onClick={onReload}>
              <Icon name="refresh" />
              Read again
            </button>
          }
        />
      )}

      {ready !== null && (
        <>
          <section className="panel edit-details" aria-labelledby={detailsId}>
            <header className="panel-header">
              {/* Focused by script after Try again reads the document. */}
              <h2 ref={detailsHeadingRef} id={detailsId} tabIndex={-1}>
                {heading}
              </h2>
            </header>
            <div className="panel-body">
              <p className="edit-lede">
                {detail === null ? (
                  <>
                    Save writes these to <code>reel.yaml</code>. A field left empty keeps inheriting
                    from the folder name.
                  </>
                ) : (
                  <>
                    What <code>reel.yaml</code> says. An empty field inherits from the folder name.
                  </>
                )}
              </p>
              <MetadataForm
                key={ready.resets}
                read={ready.baseline.read}
                draft={ready.draft.metadata}
                resolved={resolved}
                changed={changed}
                locked={locked}
                dateIncomplete={ready.dateIncomplete}
                refusal={ready.refusal}
                refusalRef={refusalRef}
                onChange={(field, value) => dispatch({ type: 'field', field, value })}
                onDateValidity={(incomplete) => dispatch({ type: 'date-validity', incomplete })}
              />
            </div>
          </section>

          {detail !== null && (
            <PosterPanel
              eventId={eventId}
              event={liveEvent ?? detail}
              read={ready.baseline.read}
              draft={ready.draft.poster}
              orders={ready.draft.orders}
              frame={posterFrame}
              locked={locked}
              onUseDefault={onUseDefault}
            />
          )}

          {editing !== null && detail !== null && (
            // Closed until opened; its cuts are the draft's, its clips and proxies the page's.
            <TimelineSection
              eventId={eventId}
              event={liveEvent ?? detail}
              read={NOT_READ}
              dismissals={dismissals}
              onFinished={onProxiesFinished ?? NOTHING}
              editing={editing}
              cards={cards}
              cardEditing={cardEditing}
            />
          )}

          {titleCardsModel !== null && <TitleCardsSwitch model={titleCardsModel} />}

          {styleModel !== null && <CardStylePanel model={styleModel} />}

          {detail !== null && (
            <div className="edit-hint">
              <Icon name="info" />
              <p>
                {/* With one chapter, where chapters come from: once, they were not found. */}
                {listed.length > 1
                  ? 'Drag a clip by its handle, or use its arrows, to reorder it. Drag it into ' +
                    'another chapter to move it there; mark clips and use Move marked to… to move several ' +
                    'at once.'
                  : 'Drag a clip by its handle, or use its arrows. To split the event into ' +
                    'chapters, use Add chapter below the chapters; clips can then be dragged ' +
                    'between them.'}
                {hasIgnored && ' Ignored clips are not played and cannot be moved.'}
                {hasMissing &&
                  ' A missing clip is not on disk and stays in its chapter: restore the file, or ' +
                    'remove it from reel.yaml.'}
                {adopted > 0 ? (
                  <strong>
                    {' '}
                    Saving adds {plural(adopted, 'new clip', 'new clips')} to reel.yaml.
                  </strong>
                ) : (
                  newClips.size > 0 &&
                  ' A new clip joins reel.yaml once its chapter’s order, one of its cuts, or ' +
                    'the list of chapters is saved.'
                )}
              </p>
            </div>
          )}

          {detail !== null && (
            // How clips are marked, and, once any is, how many and Clear marks. Its slot keeps
            // its height and room either way, so the first mark moves no row.
            <div ref={markLineRef} className="mark-line" tabIndex={-1}>
              <p>{MARK_HINT}</p>
              <span className="mark-line-slot">
                <span className="mark-count" hidden={marks.size === 0}>
                  {countWords(marks.size)}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  hidden={marks.size === 0}
                  aria-disabled={listsLocked || undefined}
                  onClick={onClearMarks}
                >
                  Clear marks
                </button>
              </span>
              <span className="mark-rotate" role="group" aria-label="Marked clips">
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  aria-disabled={listsLocked || marks.size === 0 || undefined}
                  aria-describedby={marks.size === 0 ? rotateHintId : undefined}
                  onClick={() => onRotateMarked('left')}
                >
                  <Icon name="rotate-ccw" />
                  Rotate marked left
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  aria-disabled={listsLocked || marks.size === 0 || undefined}
                  aria-describedby={marks.size === 0 ? rotateHintId : undefined}
                  onClick={() => onRotateMarked('right')}
                >
                  <Icon name="rotate-cw" />
                  Rotate marked right
                </button>
                <span id={rotateHintId} className="visually-hidden">
                  Mark clips to rotate them together.
                </span>
              </span>
              {listedKeys.length > 1 && (
                <span className="mark-move" role="group" aria-label="Move marked clips">
                  <label htmlFor={moveSelectId}>Move marked to…</label>
                  <select
                    id={moveSelectId}
                    className="field-input"
                    aria-label="Chapter to move the marked clips to"
                    value={moveTo}
                    aria-disabled={listsLocked || undefined}
                    onChange={(event) => {
                      if (!listsLocked) {
                        setMoveTo(event.currentTarget.value)
                      }
                    }}
                  >
                    <option value="">Choose a chapter</option>
                    {listed.map((chapter) => (
                      <option key={chapter.key} value={chapter.key}>
                        {chapterHeading(chapter.name, hasNamedChapter)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    aria-disabled={listsLocked || moveWhy !== null || undefined}
                    aria-busy={movePending || undefined}
                    aria-describedby={moveReasonId}
                    onClick={onMoveMarked}
                  >
                    <Icon name="arrow-right" />
                    Move
                  </button>
                  <span id={moveReasonId} className="mark-move-why">
                    {moveWhy === null ? '' : MOVE_REASON_WORDS[moveWhy]}
                  </span>
                </span>
              )}
            </div>
          )}

          {detail !== null && clipCount === 0 && !hasIgnored && (
            <p className="empty-state">
              <Icon name="film" size={20} />
              No clips.
            </p>
          )}

          {detail !== null && (
            <TitleCardContext.Provider value={titleCard}>
              <CardRowsContext.Provider value={cardRows}>
              <ChapterDrag
                orders={ready.draft.orders}
                listed={listedKeys}
                staysHome={staysHome}
                nameOf={nameOfClip}
                headingOf={headingOfChapter}
                locked={listsLocked}
                onReorder={onMove}
                onDropInto={onDropInto}
                marked={marks}
                onDropGroup={onDropGroup}
                onLift={onLift}
                rootRef={editorRef}
              >
                {ready.draft.chapters.map((chapter) => {
                  const heading = chapterHeading(chapter.name, hasNamedChapter)
                  const model = tools.get(chapter.key)
                  return chapter.deleted || model === undefined ? (
                    <DeletedChapter
                      key={chapter.key}
                      chapterKey={chapter.key}
                      heading={heading}
                      notes={notes.get(chapter.key) ?? NONE_REMOVED}
                      locked={listsLocked}
                      onUndo={onUndoDelete}
                    />
                  ) : (
                    <ClipOrderList
                      key={chapter.key}
                      eventId={eventId}
                      chapterKey={chapter.key}
                      name={chapter.name}
                      heading={heading}
                      order={ready.draft.orders.get(chapter.key) ?? NONE_REMOVED}
                      original={ready.baseline.original.get(chapter.key) ?? NONE_REMOVED}
                      ignored={ignoredOf.get(chapter.key) ?? NONE_REMOVED}
                      removed={removedByChapter.get(chapter.key) ?? NONE_REMOVED}
                      clips={clips}
                      origins={origins}
                      lastMoved={ready.lastMoved}
                      locked={listsLocked}
                      tools={model}
                      cuts={ready.draft.cuts}
                      baseCuts={ready.baseline.cuts}
                      typed={ready.typed}
                      panels={cutPanels.panels}
                      resets={ready.resets}
                      cutHandlers={cutHandlers}
                      marked={marksIn.get(chapter.key) ?? NO_MARKS}
                      turns={ready.draft.rotations}
                      baseTurns={baseTurns}
                      onMark={onMark}
                      onRotate={onRotate}
                      onMove={onMove}
                      onRemove={onRemove}
                      onRestore={onRestore}
                      onAnnounce={announce}
                    />
                  )
                })}
              </ChapterDrag>
              </CardRowsContext.Provider>
            </TitleCardContext.Provider>
          )}

          {detail !== null && <AddChapter locked={listsLocked} onAdd={onAddChapter} />}

          {/*
            In the page from the moment Edit mode is ready, `hidden` while there is nothing to
            say: the first edit then builds nothing. The summary is only worked out while shown.
          */}
          <SaveBar
            shown={showBar}
            barRef={barRef}
            alertRef={alertRef}
            edited={edited}
            problem={ready.problem}
            pressed={ready.pressed}
            summary={
              showBar
                ? summarize(
                    changed,
                    ready.dateIncomplete,
                    ready.typed.size === 1
                      ? nameNow(
                          ready.draft,
                          ready.baseline.original,
                          [...ready.typed][0],
                          ignoredOf,
                          removedByChapter,
                        )
                      : ready.typed.size,
                    ready.nameUnsent,
                    chapterEdits,
                    movedCount,
                    ready.draft.removed.size,
                    cutChanges(ready.baseline, ready.draft),
                    rotationChanges(ready.baseline, ready.draft),
                    cardsChanged,
                    styleIsChanged(ready.baseline, ready.draft),
                    ready.draft.decorators === undefined ? null : titleCardsNow(ready.draft.decorators, false),
                    posterIsChanged(ready.baseline, ready.draft),
                    adopted,
                  )
                : ''
            }
            unfinished={unfinished(ready)}
            onReset={() => {
              // The panels' fields go first, so the remounted panels start empty.
              cutPanels.clear()
              setNaming(null)
              dispatch({ type: 'reset' })
              // The bar leaves with its buttons: focus goes to the page's heading now; the
              // effect on `resets` scrolls it into view once the page has settled.
              focusPageHeading({ preventScroll: true })
            }}
            onSave={() => submit('save', 'save')}
            onRetry={(operation) => submit('retry', operation)}
            onReload={onReload}
            onOverwrite={() => setOverwriteAsked(true)}
          />
        </>
      )}

      {ready !== null && shownDialog !== null && shownDialog.kind === 'add' && (
        <NameDialog
          notes={{ chapters: ready.draft.chapters, folders, ignored: ignoredOf }}
          onConfirm={confirmName}
          onCancel={closeChapterDialog}
        />
      )}

      {/* Keyed by the question, so one asked again before a render opens afresh. */}
      <Dialog
        key={leaveQuestion}
        open={leaveQuestion !== 0}
        title="Discard unsaved changes?"
        onClose={keepEditing}
        initialFocus={keepEditingRef}
      >
        <p>Your changes to this event have not been saved. Discarding them cannot be undone.</p>
        <div className="dialog-actions">
          <button
            ref={keepEditingRef}
            type="button"
            className="btn btn-secondary"
            onClick={keepEditing}
          >
            Keep editing
          </button>
          <button type="button" className="btn btn-danger" onClick={discardAndLeave}>
            Discard
          </button>
        </div>
      </Dialog>

      <Dialog
        open={overwriteAsked}
        title="Overwrite the other change?"
        onClose={() => setOverwriteAsked(false)}
        initialFocus={cancelRef}
      >
        <p>
          Your version replaces everything saved since you started editing, including changes to
          chapters you did not touch.
        </p>
        <div className="dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="btn btn-secondary"
            onClick={() => setOverwriteAsked(false)}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => {
              // Closing returns focus to Overwrite with mine, which then shows it is busy.
              setOverwriteAsked(false)
              submit('overwrite', 'overwrite')
            }}
          >
            Overwrite
          </button>
        </div>
      </Dialog>
    </div>
  )
}
