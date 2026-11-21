import './edit.css'

import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'

import type { Clip, EventDetail } from '../api/event'
import type { EventFailure, Problem } from '../api/events'
import { fetchReel, saveReel } from '../api/reel'
import type { ReelDocument, ReelReadResult, ReelSaveResult, ReelWriteBody } from '../api/reel'
import type { CutHandlers } from '../cuts/CutsPanel'
import { createCutPanels } from '../cuts/panelStore'
import { keptCuts, trimmedWords } from '../cuts/times'
import { markEventsChanged } from '../events/changes'
import { fileName, folderName, namesIn, plural } from '../events/common'
import { FAILURE_LABEL, UNANSWERED_CAUSE, notReachableHint } from '../events/labels'
import { FAILURE_LOOK } from '../events/tones'
import { eventName } from '../jobs/labels'
import { groupTurnAnnouncement, rotatedCount, turnAnnouncement, turnsOf } from '../rotate/turn.ts'
import type { Turn, Way } from '../rotate/turn.ts'
import type { RotateHandler } from '../rotate/RotateButtons'
import type { ClipTurns } from '../cuts/ReadCuts'
import { LIST_HREF } from '../route'
import { focusPageHeading } from '../shell/AppShell'
import { TimelineSection } from '../timeline/TimelineSection'
import { cardSpecs } from '../timeline/cards'
import type { SelectionBinding } from './workspace/useSelection.ts'
import { lastClip, pressClip, selectedClips } from './workspace/selection.ts'
import type { Press } from './workspace/selection.ts'
import { CardButtonContext } from './EditTitlecard'
import type { CardButtonModel } from './EditTitlecard'
import { cardIdOf } from './chapterBar.ts'
import { TURNED_OFF, TURNED_ON, whereWords } from './card/EventTab'
import type { CardStyleModel, TitleCardsModel } from './card/EventTab'
import { titleCardsNow } from './decorators.ts'
import { cardsSource } from '../timeline/cards.ts'
import type { CardEditing, NameBinding } from './card/editing.ts'
import { anyTitle, nameLabel, settleWords } from './card/nameField.ts'
import { cardsChangedCount, cardsChangedWords } from './card/model.ts'
import type { CardDraft, CardField } from './card/model.ts'
import { draftSpec } from './card/specs.ts'
import { draftEventStyle, previewStyle, readStyle, styleRefusalOf } from './cardStyle.ts'
import type { StyleField, StyleRefusal, StyleValue } from './cardStyle.ts'
import type { EventStyle } from './card/specs.ts'
import type { EditBinding, TrackBridge } from '../timeline/editing'
import { applyDrop, includeIndex } from '../timeline/reorder'
import { MOVE_LOCKED } from '../timeline/clipDrag'
import { focusAfterMany } from '../timeline/clipMenu'
import type { EdgeEdit } from '../timeline/edgeTrim.ts'
import type { Dismissals } from '../timeline/overlays/Dismissals'
import type { AnalysisBinding } from '../analysis/useEventAnalysis'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { HelpPanel, HelpToggle, useSectionHelp } from '../ui/help/HelpToggle'
import { clipsHelpLines, newClipsLine } from './clipsHelp.ts'
import { ignoredGroups, useWideBin } from './wideBin.ts'
import { Pill } from '../ui/Pill'
import { SkeletonRows } from '../ui/Skeleton'
import { keepToastsClearOf, toast } from '../ui/toast'
import { TopBar } from './workspace/TopBar'
import type { WorkspaceFrame } from './workspace/TopBar'
import { Workspace } from './workspace/Workspace'
import { titleCardsWords } from './workspace/inspectorTabs.ts'
import { useInspectorTab } from './workspace/useInspectorTab.ts'
import { TAB_NAME } from './card/tabs.ts'
import { NameDialog } from './ChapterDialogs'
import {
  OWN_CHAPTER_HEADING,
  checkName,
  diskFolders,
  ignoredStaying,
  laterClipNotes,
  nameDialogNote,
} from './chapterNames'
import { BinPlayer } from './BinPlayer'
import { setBinPlayerShown, useBinPlayerShown } from './binPlayerPref.ts'
import { ChapterDrag } from './ChapterDrag'
import { ChapterList } from './ChapterList'
import type { ChapterRowModel } from './ChapterList'
import type { ChapterHandler, ChapterMoveHandler, ChapterToolsModel } from './ChapterTools'
import { ClipGroupTab } from './ClipGroupTab'
import { ClipInspector } from './ClipInspector'
import {
  clipState,
  draftPlace,
  moveToEndWords,
  offersOf,
  statusWords,
  stepAcrossWords,
  stepWords as clipStepWords,
} from './clipInspector.ts'
import { ClipOrderList, IgnoredBin } from './ClipOrderList'
import { stepMove } from './stepMove.ts'
import { selectionLabel, selectionStep } from './selectionEdit.ts'
import type { SelectionEdit } from './selectionEdit.ts'
import type {
  MarkHandler,
  IncludeHandler,
  MoveHandler,
  Origins,
  RemoveHandler,
  RestoreHandler,
} from './ClipOrderList'
import {
  addChapter,
  addCut,
  adoptedNewCount,
  applyEdgeEdit,
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
  listedChapters,
  liveTrims,
  metadataDraftOf,
  moveChapter,
  moveClip,
  moveClipTo,
  moveGroup,
  moveMarkedToEnd,
  movedSet,
  ignoreChanges,
  ignoreClip,
  ignoredLists,
  includeClip,
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
  withIgnoreStatus,
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
  MOVE_REASON_WORDS,
  MOVING_WORDS,
  NOTHING_IGNORED,
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
import { canRedo, canUndo, cleared, record, redo, redoLabel, undo, undoLabel } from './history'
import type { History } from './history'
import {
  buttonName,
  isTextTarget,
  nothingWords,
  stepWords,
  undoChord,
  undoKeyAction,
} from './undoShortcut'
import type { Operation, Pressed, SaveProblem } from './SaveBar'
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
 * typed in part does, and so does a refused name in the card dialog's Name field.
 * A chapter is renamed in that dialog (`card/NameField.tsx`, opened by the chapter's Edit
 * Titlecard button), the event's own chapter's name being the draft's title as the metadata
 * form's Title field edits it.
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

/**
 * What travels with the draft through the history: the counters that name added chapters and cuts,
 * so that an undone add and the next one never share a key. Not transient state (a save in flight,
 * problems, marks, typed text), which belongs to no step.
 */
type Step = { draft: Draft; nextCut: number; added: number }

const stepOf = (ready: Ready): Step => ({
  draft: ready.draft,
  nextCut: ready.nextCut,
  added: ready.added,
})

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
  /** The card dialog's Name field holds a refused name: unfinished, like a typed cut. */
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
  /**
   * The undo history (`editor-undo`): the draft and its counters at each step. Beside the
   * draft, which stays what the editor reads; Undo and Redo put a step back into both.
   */
  history: History<Step>
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
  // Ignore a clip (out of `chapter`'s order) or include one (into it, at `at`): one draft edit (`track-drag-edit` D5).
  | { type: 'ignore'; chapter: ChapterKey; identity: string; include: false }
  | { type: 'ignore'; chapter: ChapterKey; identity: string; include: true; at: number }
  | { type: 'chapter-add'; key: ChapterKey; name: string }
  | { type: 'chapter-rename'; key: ChapterKey; name: string }
  | { type: 'chapter-move'; key: ChapterKey; delta: -1 | 1 }
  | { type: 'chapter-delete'; key: ChapterKey }
  | { type: 'chapter-restore'; key: ChapterKey }
  | { type: 'marked-move'; to: ChapterKey }
  | { type: 'clip-drop'; from: ChapterKey; to: ChapterKey; identity: string; at: number }
  | { type: 'group-drop'; dragged: string; to: ChapterKey; gap: number }
  // A set of clips, shipped in the action (`clip-multi-select` D2); the marks stay as they are.
  | SelectionEdit
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
  // A clip edge tool's one edit (`clip-edge-trim`); `key` is the next `a<n>`, taken by an add.
  | { type: 'cut-edge'; identity: string; edit: EdgeEdit; key: CutKey }
  | { type: 'cut-typed'; identity: string; typed: boolean }
  // The caller took the clips that are on disk; `rotateGroup` checks that a chapter plays them.
  | { type: 'rotate'; identities: readonly string[]; way: Way }
  | { type: 'name-unsent'; unsent: boolean }
  // A title card's length from the Timeline (`title-card-duration-drag`); `resolved` is the one read.
  | { type: 'card-length'; key: ChapterKey; seconds: number; resolved: number; typed?: boolean }
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
  | { type: 'undo' }
  | { type: 'redo' }
  // Focus left a field: the next edit to it is a new step (`history.ts`, coalescing).
  | { type: 'break' }
  | { type: 'save-start'; pressed: Pressed }
  | { type: 'save-failed'; problem: SaveProblem | null; refusal: string | null }

/**
 * An edit that brings the draft back to what was read retires the last save's
 * failure: there is nothing left to save. A vanished event stays said.
 */
/** The key of a poster pick in the kept snapshot frames. */
const frameKey = (pick: PosterPick): string => `${pick.clip}@${pick.at}`

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

/** The file name of a clip identity, for a step's label. */
const clipName = (identity: string): string => identity.slice(identity.lastIndexOf('/') + 1)

/**
 * The step an edit makes, as Undo and Redo name it ("move of s1710002.mp4"), and the key that
 * folds typing in one field into one step (null: every edit its own step). `before` is the state
 * the action acts on.
 */
function describeEdit(action: Action, before: Ready): { label: string; key: string | null } {
  switch (action.type) {
    case 'move':
      return {
        label: `move of ${clipName(before.draft.orders.get(action.chapter)?.[action.from] ?? '')}`,
        key: null,
      }
    case 'clip-drop':
      return { label: `move of ${clipName(action.identity)}`, key: null }
    case 'marked-move':
    case 'group-drop':
      return { label: 'move of marked clips', key: null }
    case 'selection-move':
    case 'selection-drop':
    case 'ignore-many':
      return { label: selectionLabel(action, before), key: null }
    case 'remove':
      return { label: `removal of ${clipName(action.identity)}`, key: null }
    case 'restore':
      return { label: `restore of ${clipName(action.identity)}`, key: null }
    case 'ignore':
      return {
        label: `${action.include ? 'include' : 'ignore'} of ${clipName(action.identity)}`,
        key: null,
      }
    case 'chapter-add':
      return { label: `chapter “${action.name}” added`, key: null }
    case 'chapter-rename':
      return { label: 'chapter rename', key: `chapter-name:${action.key}` }
    case 'chapter-move':
      return { label: 'chapter move', key: null }
    case 'chapter-delete':
      return { label: 'chapter delete', key: null }
    case 'chapter-restore':
      return { label: 'chapter restore', key: null }
    case 'field':
      return { label: FIELD_LABEL[action.field].toLowerCase(), key: `field:${action.field}` }
    case 'cut-add':
      return { label: 'cut added', key: null }
    case 'cut-remove':
      return { label: 'cut removed', key: null }
    case 'cut-restore':
      return { label: 'cut restored', key: null }
    case 'cut-trim':
      return { label: 'cut trim', key: null }
    case 'cut-edge':
      return {
        label:
          action.edit.kind === 'add'
            ? 'cut added'
            : action.edit.kind === 'remove'
              ? 'cut removed'
              : 'cut trim',
        key: null,
      }
    case 'rotate':
      return {
        label:
          action.identities.length === 1
            ? `rotation of ${clipName(action.identities[0])}`
            : `rotation of ${action.identities.length} clips`,
        key: null,
      }
    case 'card-length':
      // Typed in the inspector: successive keystrokes fold into one step. A handle drag or arrow
      // press is its own step each time (`typed` unset).
      return {
        label: 'title card length',
        key: action.typed === true ? `card:${action.key}:duration` : null,
      }
    case 'card-field':
      return { label: `title card ${action.field}`, key: `card:${action.key}:${action.field}` }
    case 'card-reset':
      return { label: 'title card reset', key: null }
    case 'style-field':
      return { label: `card style ${action.field}`, key: `style:${action.field}` }
    case 'style-reset':
      return { label: 'card style reset', key: null }
    case 'title-cards':
      return { label: action.on ? 'title cards on' : 'title cards off', key: null }
    case 'title-cards-reset':
      return { label: 'title cards reset', key: null }
    case 'poster':
      return { label: action.pick === null ? 'poster reset' : 'poster', key: null }
    case 'reset':
      return { label: 'Reset', key: null }
    default:
      return { label: 'edit', key: null }
  }
}

/**
 * The reducer with the undo history around it (`editor-undo` D1): an action that changes the
 * draft is recorded as a step; Undo and Redo move along the steps and put the draft and its
 * counters back. A read starts a new history (`step`'s 'read'), so a Save or a Reload latest,
 * which both end in a re-read, clears it.
 */
function reduce(state: State, action: Action): State {
  if (action.type === 'undo' || action.type === 'redo') {
    if (state.status !== 'ready' || state.pressed !== null) {
      return state
    }
    const history = action.type === 'undo' ? undo(state.history) : redo(state.history)
    if (history === state.history) {
      return state
    }
    const { draft, nextCut, added } = history.present
    return afterEdit({
      ...state,
      draft,
      nextCut,
      added,
      history,
      lastMoved: null,
      // A date typed in part is replaced by the restored one.
      dateIncomplete:
        draft.metadata.date !== state.draft.metadata.date ? false : state.dateIncomplete,
    })
  }
  if (action.type === 'break') {
    return state.status === 'ready' && state.history.key !== undefined
      ? { ...state, history: { ...state.history, key: undefined, at: undefined } }
      : state
  }
  const next = step(state, action)
  if (state.status !== 'ready' || next.status !== 'ready' || next.draft === state.draft) {
    return next
  }
  // A Reset with nothing edited is no step (typed text alone is not in the draft).
  if (action.type === 'reset' && !isDirty(state.baseline, state.draft)) {
    return { ...next, history: { ...state.history, present: stepOf(next) } }
  }
  const { label, key } = describeEdit(action, state)
  return {
    ...next,
    history: record(state.history, stepOf(next), label, key ?? undefined),
  }
}

function step(state: State, action: Action): State {
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
      const draft = initialDraft(baseline)
      return {
        status: 'ready',
        baseline,
        draft,
        history: cleared({ draft, nextCut: 0, added: 0 }),
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
    case 'ignore':
      return withDraft(
        state,
        action.include
          ? includeClip(state.baseline, state.draft, action.chapter, action.identity, action.at)
          : ignoreClip(state.baseline, state.draft, action.chapter, action.identity),
      )
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
    case 'selection-move':
    case 'selection-drop':
    case 'ignore-many': {
      const next = selectionStep(state, action)
      return next === state ? state : afterEdit(next)
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
    case 'cut-edge': {
      if (action.edit.kind === 'add' && action.key !== `a${state.nextCut + 1}`) {
        return state
      }
      const draft = applyEdgeEdit(state.baseline, state.draft, action.identity, action.edit, action.key)
      if (draft === state.draft) {
        return state
      }
      const next = withDraft(state, draft)
      return action.edit.kind === 'add' ? { ...next, nextCut: state.nextCut + 1 } : next
    }
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
    case 'undo':
    case 'redo':
    case 'break':
      // Handled around this reducer (`reduce`).
      return state
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
  ignores: { ignored: number; included: number } = { ignored: 0, included: 0 },
): string {
  // An incomplete date reads as '' but is not a date left empty: it is named as such.
  const fields = dateIncomplete ? changed.filter((field) => field !== 'date') : changed
  const parts = [
    fields.length > 0 && `${fieldWords(fields)} changed`,
    dateIncomplete && 'date incomplete',
    typeof typed === 'string'
      ? `cut typed on ${typed}, not added`
      : typed > 0 && `cuts typed on ${typed} clips, not added`,
    nameUnsent && 'name refused',
    chapters.added > 0 && `${plural(chapters.added, 'chapter', 'chapters')} added`,
    chapters.renamed > 0 && `${plural(chapters.renamed, 'chapter', 'chapters')} renamed`,
    chapters.deleted > 0 && `${plural(chapters.deleted, 'chapter', 'chapters')} deleted`,
    chapters.reordered && 'chapter order changed',
    moved > 0 && `${plural(moved, 'clip', 'clips')} moved`,
    removed > 0 && `${plural(removed, 'missing clip', 'missing clips')} removed`,
    ignores.ignored > 0 && `${plural(ignores.ignored, 'clip', 'clips')} ignored`,
    ignores.included > 0 && `${plural(ignores.included, 'clip', 'clips')} included`,
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

const NOTHING = () => undefined

// A chapter with no removed clip: one constant, so its list keeps its memoised props.
const NONE_REMOVED: readonly string[] = []
const NO_CLIPS: ReadonlySet<string> = new Set()

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

/** The clips of `identities` that a listed chapter of `draft` plays, in page order. */
function playedOf(draft: Draft, identities: readonly string[]): string[] {
  const listed = listedChapters(draft.chapters).map((chapter) => chapter.key)
  return groupOf(draft.orders, listed, new Set(identities))
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
  const chapter =
    draft.chapters.find((listed) => (draft.orders.get(listed.key) ?? []).includes(identity)) ??
    // An ignored clip is named by the chapter that lists it among its ignored clips.
    draft.chapters.find((listed) => (ignoredOf.get(listed.key) ?? []).includes(identity)) ??
    // A removed one, by the chapter whose removed list holds it.
    draft.chapters.find((listed) => (removedOf.get(listed.key) ?? []).includes(identity))
  if (chapter === undefined) {
    return identity
  }
  return namesIn(
    chapter.name,
    original.get(chapter.key) ?? [],
    draft.orders.get(chapter.key) ?? [],
    ignoredOf.get(chapter.key) ?? [],
    removedOf.get(chapter.key) ?? [],
  )(identity)
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
  // In the workspace a pane scrolls on its own: measured against the pane and its padding.
  const pane = element.closest<HTMLElement>('[data-ws-scroll]')
  if (pane !== null && getComputedStyle(pane).overflowY !== 'visible') {
    const box = element.getBoundingClientRect()
    const room = pane.getBoundingClientRect()
    const style = getComputedStyle(pane)
    const top = room.top + (parseFloat(style.scrollPaddingTop) || 0)
    const bottom = room.bottom - (parseFloat(style.scrollPaddingBottom) || 0)
    if (box.top < top || box.bottom > bottom) {
      element.scrollIntoView({ block: 'nearest' })
    }
    return
  }
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

/** The first of the matches that is on screen: each chapter's buttons exist twice (bar and row),
 * and below 960 px the bar's copy is `display: none` and cannot take focus. */
function firstShown(matches: NodeListOf<HTMLElement>): HTMLElement | null {
  const list = Array.from(matches)
  return (
    list.find((el) => (el.checkVisibility ? el.checkVisibility() : true)) ?? list[0] ?? null
  )
}

export function EventEditor({
  eventId,
  event,
  heading = 'Details',
  liveEvent = null,
  dismissals,
  analysis,
  cards,
  onProxiesFinished,
  onSaved,
  onReload,
  workspace,
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
  /** The page's one analysis read and Re-analyze (`useEventAnalysis`); absent, the Timeline has no lane. */
  analysis?: AnalysisBinding
  /** The page's one selection (`useSelection`), shared with the Timeline's blocks. */
  cards: SelectionBinding
  /** A proxy job the Timeline followed has ended: the page reads the event again. */
  onProxiesFinished?: () => void
  onSaved: () => void
  onReload: () => void
  /** Edit mode's workspace (`editor-workspace-layout`): absent, the editor is stacked in the page. */
  workspace?: WorkspaceFrame
}) {
  const inWorkspace = workspace !== undefined
  // From 960 px the bin lists the ignored clips after the chapters (compact-bin-tools D6).
  const wideBin = useWideBin()
  const ignoredApart = inWorkspace && wideBin
  // Read once: the draft is never re-initialised from a newer detail.
  const [detail] = useState(event)
  const [state, dispatch] = useReducer(reduce, { status: 'loading' })
  const [announcement, setAnnouncement] = useState('')
  const [overwriteAsked, setOverwriteAsked] = useState(false)
  const leaveQuestion = usePendingLeave()
  const detailsId = useId()
  const titleCardsId = useId()
  const detailsHelp = useSectionHelp('details')
  const clipsHelp = useSectionHelp('clips')
  const inFlight = useRef<AbortController | null>(null)
  // A second press while a save is in flight sends nothing.
  const saving = useRef(false)
  const mounted = useRef(false)
  const barRef = useRef<HTMLDivElement>(null)
  const alertRef = useRef<HTMLDivElement>(null)
  // A pointer press is under way: the focus it gives is not scrolled (onFocus below).
  const pointerPressed = useRef(false)
  const refusalRef = useRef<HTMLDivElement>(null)
  // The workspace inspector's shown tab, and a refusal at the Details fields waiting for its
  // Event tab to be drawn before it takes focus.
  const [inspectorTab, setInspectorTab] = useInspectorTab(cards)
  const refusalWaits = useRef(false)
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
  // The page's clips as the draft has them: a clip ignored here is `ignored`, a clip included
  // here is played (`track-drag-edit`); the same read while the draft has no ignore edit.
  const ignoreEdits = state.status === 'ready' ? state.draft.ignoreEdits : undefined
  const detailNow = useMemo(
    () => (detail === null ? null : withIgnoreStatus(detail, ignoreEdits)),
    [detail, ignoreEdits],
  )
  const clips = useMemo(
    () =>
      new Map<string, Clip>(
        (detailNow?.chapters ?? []).flatMap((chapter) =>
          chapter.clips.map((clip): [string, Clip] => [clip.identity, clip]),
        ),
      ),
    [detailNow],
  )
  const newClips = useMemo(
    () => new Set([...clips.values()].filter((c) => c.status === 'new').map((c) => c.identity)),
    [clips],
  )
  const folders = useMemo(() => diskFolders(clips.values()), [clips])
  const readIgnored = useMemo(
    () => new Map(chapters.map((chapter) => [chapter.key, chapter.ignored])),
    [chapters],
  )
  const ignoredBaseline = state.status === 'ready' ? state.baseline : null
  const ignoredDraft = state.status === 'ready' ? state.draft : null
  const ignoredOf = useMemo(
    () =>
      ignoredBaseline === null || ignoredDraft === null
        ? readIgnored
        : ignoredLists(ignoredBaseline, ignoredDraft, readIgnored),
    // The lists change with an ignore edit and with a deleted chapter, not with every edit.
    [readIgnored, ignoredBaseline, ignoredDraft?.ignoreEdits, ignoredDraft?.chapters],
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
  // Which move is pending: Move marked to… (the bin's) or Move to… of the selected clips (the Clip
  // tab's and the menu's). Either locks the lists; only the one pressed shows busy, and the words
  // of an unavailable control name a save or a move, never the other set.
  const [markedPending, setMarkedPending] = useState(false)
  const [selectionPending, setSelectionPending] = useState(false)
  const movePending = markedPending || selectionPending
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
      // A clip included here is counted as included, not as moved.
      const played = order.filter((identity) => ready.draft.ignoreEdits?.get(identity) !== 'include')
      movedCount += movedSet(keptOriginal(original, played), played, ready.lastMoved).size
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
    // The workspace's bar is in its top bar: never held or resting, no toasts to keep clear.
    if (!showBar || bar === null || inWorkspace) {
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
  }, [showBar, inWorkspace])

  // Every commit can change what the bar says (an answer, the summary, a pressed
  // control), so its place is decided again before paint, and before the answer's
  // focus scroll below measures the page.
  useLayoutEffect(() => {
    if (showBar && barRef.current !== null && !inWorkspace) {
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
    // In the workspace a refusal at the Details fields is in the inspector's Event tab, hidden
    // while another tab shows: the Event tab is shown first, and the refusal takes focus once it
    // is drawn (below).
    if (refusalRef.current?.closest('.ws-insp-panel[hidden]') != null) {
      refusalWaits.current = true
      setInspectorTab('event')
      return
    }
    // In the workspace a top bar that rests at the page's top (a short window, a large zoom)
    // leaves the window as the page scrolls: a save started by Ctrl+S from a pane further down
    // would leave its explanation out of sight. The explanation takes focus then, and comes
    // into view with it.
    const topBar = inWorkspace ? (barRef.current?.closest<HTMLElement>('.ws-top') ?? null) : null
    const before = document.activeElement
    const alert = alertRef.current
    const unseen =
      topBar !== null &&
      topBar.hasAttribute('data-rests') &&
      !(before instanceof HTMLElement && topBar.contains(before)) &&
      alert !== null &&
      !inWindow(alert)
    if (refusalRef.current !== null) {
      refusalRef.current.focus()
    } else if (before === null || before === document.body || unseen) {
      alert?.focus()
    }
    const focused = document.activeElement
    if (focused instanceof HTMLElement && focused !== document.body) {
      keepInView(focused, barRef.current)
    }
  }, [answers, inWorkspace])
  useLayoutEffect(() => {
    if (!refusalWaits.current || inspectorTab !== 'event') {
      return
    }
    refusalWaits.current = false
    const refusal = refusalRef.current
    if (refusal !== null) {
      refusal.focus()
      keepInView(refusal, barRef.current)
    }
  }, [inspectorTab])

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
  const [cutPanels] = useState(createCutPanels)

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

  // A clip edge tool's edit (`clip-edge-trim`): a release, a key or Q/W is one draft edit, with
  // the same guard as a trim; `words` is said once (null: a key, whose result is the slider's value).
  const onEdge = useCallback<EditBinding['onEdge']>(
    (identity, edit, words) => {
      const current = latest.current
      if (current === null || current.pressed !== null || moving.current) {
        return
      }
      const key = `a${current.nextCut + 1}`
      if (applyEdgeEdit(current.baseline, current.draft, identity, edit, key) === current.draft) {
        return
      }
      dispatch({ type: 'cut-edge', identity, edit, key })
      if (words !== null) {
        announce(words)
      }
    },
    [announce],
  )

  // A clip block dropped on the track (`track-drag-edit`): the lists' own reducer action, so the top
  // bar says "1 clip moved"; the same guard as a trim, and nothing when the slot is its own place.
  const onMoveClip = useCallback<EditBinding['onMove']>(
    (identity, slot, drawn) => {
      const current = latest.current
      if (!idle(current)) {
        return
      }
      const orders = current.draft.orders
      let chapter: ChapterKey | undefined
      for (const [key, order] of orders) {
        if (order.includes(identity)) {
          chapter = key
        }
      }
      if (chapter === undefined) {
        return
      }
      const next = applyDrop(orders, { identity, chapter }, slot, drawn)
      if (next === orders) {
        return
      }
      if (chapter === slot.chapter) {
        const from = orders.get(chapter)?.indexOf(identity) ?? -1
        const to = next.get(chapter)?.indexOf(identity) ?? -1
        if (from < 0 || to < 0) {
          return
        }
        dispatch({ type: 'move', chapter, from, to })
      } else {
        const at = next.get(slot.chapter)?.indexOf(identity) ?? -1
        if (at < 0) {
          return
        }
        dispatch({ type: 'clip-drop', from: chapter, to: slot.chapter, identity, at })
      }
      announce(`Moved ${identity.slice(identity.lastIndexOf('/') + 1)}. ${slot.words}.`)
    },
    [announce],
  )

  // A clip ignored (`track-drag-edit` D5): out of its chapter's order into the ignored clips, one
  // draft edit, as the bin's drop and the Clip tab's button make it. The same guard as a trim.
  const onIgnoreClip = useCallback(
    (identity: string) => {
      const current = latest.current
      if (!idle(current)) {
        return
      }
      let chapter: ChapterKey | undefined
      for (const [key, order] of current.draft.orders) {
        if (order.includes(identity)) {
          chapter = key
        }
      }
      if (
        chapter === undefined ||
        ignoreClip(current.baseline, current.draft, chapter, identity) === current.draft
      ) {
        return
      }
      dispatch({ type: 'ignore', chapter, identity, include: false })
      announce(`Ignored ${identity.slice(identity.lastIndexOf('/') + 1)}. Not saved.`)
    },
    [announce],
  )

  // A group of selected clips dropped on the track (`clip-multi-select`, D4): the clips ship in the
  // action with `onDisk`, so a missing clip is not moved (`selectionStep`); one draft edit, one Undo.
  // The gap is the index of the clip the run goes before in the chapter's full order, as a drop of
  // one clip finds it (`includeIndex`).
  const onMoveMany = useCallback<EditBinding['onMoveMany']>(
    (identities, dragged, slot, drawn) => {
      const current = latest.current
      if (!idle(current)) {
        return
      }
      const gap = includeIndex(current.draft.orders, slot, drawn)
      if (gap === null) {
        return
      }
      const action: SelectionEdit = {
        type: 'selection-drop',
        identities,
        dragged,
        to: slot.chapter,
        gap,
        onDisk: (identity) => onDisk(clips.get(identity)),
      }
      if (selectionStep(current, action) === current) {
        announce(NOTHING_MOVED)
        return
      }
      const count = playedOf(current.draft, identities.filter(action.onDisk)).length
      dispatch(action)
      announce(`Moved ${plural(count, 'clip', 'clips')}. ${slot.place}. Not saved.`)
    },
    [announce, clips],
  )

  // A group of selected clips released over the bin: every one that is on disk and played is ignored,
  // one draft edit (`ignore-many`).
  const onIgnoreMany = useCallback<EditBinding['onIgnoreMany']>(
    (identities) => {
      const current = latest.current
      if (!idle(current)) {
        return false
      }
      const action: SelectionEdit = {
        type: 'ignore-many',
        identities,
        onDisk: (identity) => onDisk(clips.get(identity)),
      }
      if (selectionStep(current, action) === current) {
        announce(NOTHING_IGNORED)
        return false
      }
      const count = playedOf(current.draft, identities.filter(action.onDisk)).length
      dispatch(action)
      announce(`Ignored ${plural(count, 'clip', 'clips')}. Not saved.`)
      return true
    },
    [announce, clips],
  )

  // Rotate left / right of the selected clips (`clip-multi-select` D5): every clip on disk that a
  // chapter plays, each from its own turn, one edit and one Undo step; the clips come in the call,
  // not from the marks, so the marks are untouched.
  const onRotateMany = useCallback<EditBinding['onRotateMany']>(
    (identities, way) => {
      const current = latest.current
      if (!idle(current) || lifted.current) {
        return
      }
      const keys = listedChapters(current.draft.chapters).map((chapter) => chapter.key)
      const group = groupOf(current.draft.orders, keys, new Set(identities)).filter((identity) =>
        onDisk(clips.get(identity)),
      )
      if (rotateGroup(current.baseline, current.draft, group, way, () => true) === current.draft) {
        return
      }
      dispatch({ type: 'rotate', identities: group, way })
      announce(groupTurnAnnouncement(group.length, way))
    },
    [announce, clips],
  )

  // Move to… of the selected clips (`clip-multi-select` D5): at the end of `to`, in play order, as
  // Move marked to… does it, applied in a transition so the move is pending (`movePending`, which
  // locks every control that acts on the lists) until it lands.
  const onMoveSelection = useCallback<EditBinding['onMoveSelection']>(
    (identities, to) => {
      const current = latest.current
      if (!idle(current) || lifted.current) {
        return
      }
      const keys = listedChapters(current.draft.chapters).map((chapter) => chapter.key)
      const action: SelectionEdit = {
        type: 'selection-move',
        identities,
        to,
        onDisk: (identity) => onDisk(clips.get(identity)),
      }
      const wanted = new Set(identities.filter(action.onDisk))
      const { moved } = moveMarkedToEnd(current.draft, keys, wanted, to)
      if (moved.length === 0) {
        announce(NOTHING_MOVED)
        return
      }
      moving.current = true
      setSelectionPending(true)
      startTransition(() => {
        dispatch(action)
        setSelectionPending(false)
      })
      announce(movedWords(moved.length, headingIn(current.draft, to)))
    },
    [announce, clips],
  )

  // An ignored clip included without a drag: at the end of its chapter's play order, the same
  // draft edit as the track drop, with the same guard.
  const onIncludeClip = useCallback<IncludeHandler>(
    (chapter, identity) => {
      const current = latest.current
      if (!idle(current)) {
        announce(MOVE_LOCKED)
        return
      }
      const at = current.draft.orders.get(chapter)?.length
      if (
        at === undefined ||
        includeClip(current.baseline, current.draft, chapter, identity, at) === current.draft
      ) {
        return
      }
      dispatch({ type: 'ignore', chapter, identity, include: true, at })
      announce(`Included ${identity.slice(identity.lastIndexOf('/') + 1)}. Not saved.`)
    },
    [announce],
  )

  // The Track hands over where a release at a point lands on it; a track drag asks whether a
  // point is over the bin (the workspace's bin column: the player above its lists is the bin's too).
  const trackAt = useRef<TrackBridge['current']>(null)
  const overBin = useCallback((x: number, y: number) => {
    const box = document.querySelector('.ws-binbox')?.getBoundingClientRect()
    return box !== undefined && x >= box.left && x < box.right && y >= box.top && y < box.bottom
  }, [])
  const overTrack = useCallback((x: number, y: number) => trackAt.current?.(x, y, '') != null, [])
  // A clip of the bin released at a client point (`ChapterDrag`): over the track it is included
  // when ignored, else moved to the slot; false when the point is not over the track. The bin's
  // own drop then does not run.
  const onDropOnTrack = useCallback(
    (identity: string, x: number, y: number): boolean => {
      const target = trackAt.current?.(x, y, identity) ?? null
      if (target === null) {
        return false
      }
      const current = latest.current
      if (!idle(current)) {
        announce(MOVE_LOCKED)
        return true
      }
      const { slot } = target
      if (slot === null) {
        return true
      }
      const { baseline, draft } = current
      const name = identity.slice(identity.lastIndexOf('/') + 1)
      if ([...draft.orders.values()].some((order) => order.includes(identity))) {
        // Played already (a NEW clip, say): a move, which a missing clip never makes.
        if (onDisk(clips.get(identity))) {
          onMoveClip(identity, slot, target.drawn)
        }
        return true
      }
      const at = includeIndex(draft.orders, slot, target.drawn)
      if (at === null || includeClip(baseline, draft, slot.chapter, identity, at) === draft) {
        return true
      }
      dispatch({ type: 'ignore', chapter: slot.chapter, identity, include: true, at })
      announce(`Included ${name}. ${slot.words}. Not saved.`)
      return true
    },
    [announce, clips, onMoveClip],
  )

  // What the Timeline gets of the draft (`timeline/editing.ts`); null for the needs-attention form.
  const baseCuts = ready?.baseline.cuts
  const draftCuts = ready?.draft.cuts
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
  const liveNow = useMemo(
    () => (liveDetail === null ? null : withIgnoreStatus(liveDetail, ignoreEdits)),
    [liveDetail, ignoreEdits],
  )
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
  // Frames are kept by pick for as long as the history can reach the pick (Undo and Redo bring a
  // pick back), and let go on a re-read or leaving.
  const [frames, setFrames] = useState<Map<string, { url: string; turn: Turn }>>(() => new Map())
  const framesRef = useRef(frames)
  framesRef.current = frames
  const dropFrames = useCallback(() => {
    setFrames((was) => {
      if (was.size === 0) {
        return was
      }
      for (const held of was.values()) {
        URL.revokeObjectURL(held.url)
      }
      return new Map()
    })
  }, [])
  useEffect(
    () => () => {
      for (const held of framesRef.current.values()) {
        URL.revokeObjectURL(held.url)
      }
    },
    [],
  )
  const posterBaseline = ready?.baseline
  useEffect(() => dropFrames(), [posterBaseline, dropFrames])
  const draftPoster = ready === null ? undefined : ready.draft.poster
  const posterFrame = useMemo(() => {
    const pick = draftPoster === undefined || draftPoster === null ? null : draftPoster
    const held = pick === null ? undefined : frames.get(frameKey(pick))
    return pick === null || held === undefined ? null : { ...held, pick }
  }, [frames, draftPoster])
  const onPoster = useCallback<EditBinding['onPoster']>(
    (pick, snapshot) => {
      const current = latest.current
      if (current === null || current.pressed !== null || moving.current) {
        URL.revokeObjectURL(snapshot.url)
        return
      }
      setFrames((was) => {
        const next = new Map(was)
        const key = frameKey(pick)
        const old = was.get(key)
        if (old !== undefined) {
          URL.revokeObjectURL(old.url)
        }
        next.set(key, { url: snapshot.url, turn: snapshot.turn })
        return next
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
    dispatch({ type: 'poster', pick: null })
    announce('Poster set to the default frame, the first clip. Not saved.')
  }, [announce])
  const resetCount = ready?.resets ?? 0
  const readLook = ready?.baseline.read.look
  // The rotate action is made further down (it names the clip); the Timeline's binding calls it
  // through this stable hand-over.
  const rotateRef = useRef<RotateHandler>(() => undefined)
  const rotateClip = useCallback<RotateHandler>((identity, way) => rotateRef.current(identity, way), [])
  const editing = useMemo<EditBinding | null>(() => {
    if (baseCuts === undefined || draftCuts === undefined || detail === null) {
      return null
    }
    return {
      cuts: liveTrims(baseCuts, draftCuts),
      turns: draftTurns,
      listed: (identity) => cutsOf(baseCuts, draftCuts, identity),
      onTrim,
      onEdge,
      onMove: onMoveClip,
      onIgnore: onIgnoreClip,
      onMoveMany,
      onIgnoreMany,
      onRotateMany,
      onMoveSelection,
      overBin,
      trackAt,
      onPoster,
      onAdd: cutHandlers.onAdd,
      onRemove: cutHandlers.onRemove,
      onRotate: rotateClip,
      locked: listsLocked,
      moving: selectionPending && !locked,
      announce,
      previews: cutPanels.panels.previews,
      baseline: baseCuts,
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
    selectionPending,
    locked,
    onTrim,
    onEdge,
    onMoveClip,
    onIgnoreClip,
    onMoveMany,
    onIgnoreMany,
    onRotateMany,
    onMoveSelection,
    overBin,
    onPoster,
    rotateClip,
    cutHandlers,
    announce,
    cutPanels,
    resetCount,
    onCardDuration,
  ])

  // The dialog's cards and the Timeline's blocks: each chapter's saved card, matched by
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
  const { keep: keepSelection, open: openCard, selected: selectedCard } = cards
  // The bin's rows read the clips the selection holds, a stable set per chapter while they are
  // the same, so a press redraws only the chapters whose rows change. They follow the selection in
  // a low-priority render (`useDeferredValue`): the track and the inspector paint first, and a
  // Shift range over 400 rows redraws the bin after that, in slices, not in the press's frame
  // (`clip-multi-select`, the 100 ms gate).
  const binSelection = useDeferredValue(cards.selection)
  const selectedSet = useMemo(() => new Set(selectedClips(binSelection)), [binSelection])
  const selectedCache = useRef(new Map<string, ReadonlySet<string>>())
  const selectedIn = (
    chapter: ChapterKey,
    order: readonly string[],
    ...also: readonly (readonly string[])[]
  ): ReadonlySet<string> => {
    // The clips a chapter lists but does not play (ignored, removed) are selectable rows too.
    const next =
      selectedSet.size === 0
        ? []
        : [order, ...also].flatMap((list) => list.filter((identity) => selectedSet.has(identity)))
    if (next.length === 0) {
      selectedCache.current.delete(chapter)
      return NO_CLIPS
    }
    const was = selectedCache.current.get(chapter)
    if (was !== undefined && was.size === next.length && next.every((identity) => was.has(identity))) {
      return was
    }
    const made: ReadonlySet<string> = new Set(next)
    selectedCache.current.set(chapter, made)
    return made
  }
  // The clip pressed last, for the chapter that plays it only: the other chapters' rows get null,
  // so a press redraws no more of them than the set does.
  const leadId = lastClip(binSelection)
  const leadIn = (order: readonly string[]): string | null =>
    leadId !== null && order.includes(leadId) ? leadId : null
  // A press on a bin row (its click or its name): a Shift press ranges over the rows' page order,
  // the clips the bin lets be selected (on disk, not excluded) of every chapter that is listed.
  const binPress = useRef<(identity: string, press: Press) => void>(() => undefined)
  binPress.current = (identity, press) => {
    const order =
      ready === null
        ? []
        : ready.draft.chapters.flatMap((chapter) =>
            chapter.deleted
              ? []
              : (ready.draft.orders.get(chapter.key) ?? NONE_REMOVED).filter((candidate) => {
                  const clip = clips.get(candidate)
                  return (
                    clip !== undefined &&
                    !clip.excluded &&
                    (clip.status === 'active' || clip.status === 'new')
                  )
                }),
          )
    // Only a clip the track draws joins a set: an ignored, a missing or an excluded clip is selected
    // alone (its Clip tab edits that one clip), and a press with a modifier while one is selected
    // starts a new selection rather than add to it.
    const joins = (candidate: string) => canMark(clips.get(candidate))
    const alone =
      press !== 'alone' &&
      (!joins(identity) || selectedClips(cards.selection).some((held) => !joins(held)))
    cards.set(pressClip(cards.selection, identity, alone ? 'alone' : press, order))
  }
  const selectClip = useCallback((identity: string, press: Press) => binPress.current(identity, press), [])
  // A row's Watch (its thumbnail): the clip alone is selected, the player is shown, and Play takes
  // keyboard focus once the player shows the clip. Nothing plays, nothing loads.
  const [watchAsk, setWatchAsk] = useState(0)
  const watchClip = useCallback((identity: string) => {
    setBinPlayerShown(true)
    binPress.current(identity, 'alone')
    setWatchAsk((asked) => asked + 1)
  }, [])
  // A clip that left the event ends its selection (`keptSelection`). The clips the event lists, not
  // the ones the track draws: the Clip tab also shows an ignored or a missing clip. A set keeps only
  // the clips that can still join one (the rule `binPress` joins by), so a clip that stops being
  // played (an ignore, an undo) leaves it, and the group tab never shows a group of one or none.
  useEffect(() => {
    if (detail !== null) {
      keepSelection({
        clips: new Set(clips.keys()),
        joinable: new Set([...clips].filter(([, clip]) => canMark(clip)).map(([identity]) => identity)),
      })
    }
  }, [detail, clips, keepSelection])
  // A clip or cut selection ending (Escape, a clear) while focus was in the Clip tab, which then
  // unmounts: the Timeline puts focus on the clip's block, and for a clip it does not draw
  // (ignored, missing, removed, or any clip in Prepare) it is put on the clip's bin row, so it
  // never drops onto the page body. The Timeline's layout effect runs first, so a block wins.
  const heldIdentity =
    cards.selection.kind === 'cut' ? cards.selection.identity : lastClip(cards.selection)
  const wasHeld = useRef<string | null>(null)
  useLayoutEffect(() => {
    const was = wasHeld.current
    wasHeld.current = heldIdentity
    if (was === null || heldIdentity !== null) {
      return
    }
    const active = document.activeElement
    if (active !== null && active !== document.body) {
      return
    }
    Array.from(document.querySelectorAll<HTMLElement>('li.clip-item[data-identity]'))
      .find((row) => row.dataset.identity === was && row.closest('[hidden]') === null)
      ?.focus({ preventScroll: true })
  }, [heldIdentity])
  // The Clip tab's slot for the Timeline's track-only part (`ClipInspector`), once it is mounted.
  const [clipSlot, setClipSlot] = useState<HTMLElement | null>(null)
  // The selection ends with its chapter: deleted in the draft, it is gone from the list.
  useEffect(() => {
    if (draftChapters !== undefined) {
      keepSelection({
        chapters: new Set(
          draftChapters.flatMap((chapter) => (chapter.deleted ? [] : [cardIdOf(chapter)])),
        ),
      })
    }
  }, [draftChapters, keepSelection])
  // A refused save that names a card opens that card, so the message is at its field.
  const refusedCard = ready?.cardRefusal ?? null
  const refusedAnswer = ready?.answers ?? 0
  useEffect(() => {
    if (refusedCard === null || draftChapters === undefined) {
      return
    }
    const chapter = draftChapters.find((candidate) => candidate.key === refusedCard.key)
    if (chapter !== undefined) {
      openCard(cardIdOf(chapter))
    }
    // Once per answer: selecting another card afterwards is the operator's.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refusedAnswer])
  // The Title cards switch: the draft's position while it differs from what the service said.
  const draftDecorators = ready?.draft.decorators
  const switchDraft = draftDecorators === undefined ? null : titleCardsNow(draftDecorators, false)
  // "Card style for this event": the draft's style against the one read, and what the cards inherit.
  const styleModel = useMemo<CardStyleModel | null>(
    () =>
      ready === null || detail === null
        ? null
        : {
            read: readStyle(ready.baseline.read.look),
            style: styleOf(ready.baseline, ready.draft),
            resolved: savedStyle,
            error: liveDetail?.title_card_error ?? null,
            refusal: ready.styleRefusal,
            locked: listsLocked,
            onSet: (field: StyleField, value: StyleValue | null) => {
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
          },
    // `idle` and `latest` are stable by construction (a ref and a closure over refs).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ready?.baseline, ready?.draft, ready?.styleRefusal, savedStyle, liveDetail, listsLocked, detail, announce],
  )

  // "Title cards: On / Off": the service's answer under the draft's switch.
  const answer = liveDetail?.title_cards ?? null
  const switchModel = useMemo<TitleCardsModel | null>(
    () =>
      ready === null || detail === null
        ? null
        : {
            answer,
            error: liveDetail?.title_cards_error ?? null,
            on: titleCardsNow(ready.draft.decorators, answer?.enabled ?? false),
            source: cardsSource(answer, switchDraft),
            changed: decoratorsChanged(ready.draft),
            locked: listsLocked,
            onSet: (on: boolean) => {
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
          },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ready?.draft, answer, liveDetail, switchDraft, listsLocked, detail, announce],
  )

  // The dialog's Name field (`edit-mode-declutter`): a chapter's name, or for the event's own
  // chapter the title the Details form edits. The editor's one name rule: `checkName`.
  const onNameRefused = useCallback((refused: boolean) => {
    dispatch({ type: 'name-unsent', unsent: refused })
  }, [])
  const titleChanged = changed.includes('title')
  const draftMetadata = ready?.draft.metadata
  const readDocument = ready?.baseline.read
  const nameFor = useCallback(
    (saved: string): NameBinding | null => {
      const chapter = draftChapters?.find(
        (candidate) => cardIdOf(candidate) === saved && !candidate.deleted,
      )
      if (chapter === undefined || draftMetadata === undefined || readDocument === undefined) {
        return null
      }
      const key = chapter.key
      const event = chapter.name === ''
      return {
        event,
        label: nameLabel(event, chapter.name),
        value: event ? draftMetadata.title : chapter.name,
        check: (typed) =>
          event ? anyTitle(typed) : checkName(latest.current?.draft.chapters ?? [], typed, key),
        notes: (typed) =>
          latest.current === null || event
            ? []
            : nameDialogNote(
                { chapters: latest.current.draft.chapters, folders, ignored: ignoredOf },
                key,
                typed,
              ),
        placeholder: resolved?.title ?? '',
        hint: (typed) =>
          inheritHint('title', readDocument, { ...draftMetadata, title: typed }, resolved),
        fileNameChanged: titleChanged,
        write: (name) => {
          const current = latest.current
          if (!idle(current)) {
            return
          }
          if (event) {
            if (current.draft.metadata.title !== name) {
              dispatch({ type: 'field', field: 'title', value: name })
            }
            return
          }
          if (renameChapter(current.draft, key, name) !== current.draft) {
            dispatch({ type: 'chapter-rename', key, name })
          }
        },
        refused: onNameRefused,
        settled: (was) => {
          const current = latest.current
          if (current === null) {
            return
          }
          const nowName = event
            ? current.draft.metadata.title
            : (current.draft.chapters.find((candidate) => candidate.key === key)?.name ?? '')
          const words = settleWords(
            event ? 'event' : 'chapter',
            was,
            nowName,
            event ? '' : notesIn(current.draft, key),
          )
          if (words !== null) {
            announce(words)
          }
        },
      }
    },
    [
      draftChapters,
      draftMetadata,
      readDocument,
      folders,
      ignoredOf,
      resolved,
      titleChanged,
      notesIn,
      announce,
      onNameRefused,
    ],
  )

  // The draft's first card that the dialog can show: where the Event tab opens the dialog's
  // event-wide tab.
  const firstCard = useMemo(() => {
    const first = draftChapters?.find((chapter) => !chapter.deleted)
    return first === undefined ? null : cardIdOf(first)
  }, [draftChapters])

  const cardEditing = useMemo<CardEditing | null>(() => {
    if (
      baselineNow === undefined ||
      draftChapters === undefined ||
      draftCards === undefined ||
      styleModel === null ||
      switchModel === null
    ) {
      return null
    }
    const keyOf = (saved: string) =>
      draftChapters.find((chapter) => cardIdOf(chapter) === saved && !chapter.deleted)
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
          name: chapterHeading(chapter.name, hasNamedChapter),
          opening: chapter.name === '',
          card: draftCards.get(chapter.key) ?? readCardOf(baselineNow, chapter.key),
          read: readCardOf(baselineNow, chapter.key),
          eventTitle: draftEventTitle,
          folderTitle: resolved?.title ?? null,
          refusal:
            refusedCard !== null && refusedCard.key === chapter.key
              ? { field: refusedCard.field, message: refusedCard.message }
              : null,
          added: chapter.readName === null,
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
      name: nameFor,
      setLength: (saved, seconds) => {
        const chapter = keyOf(saved)
        const resolvedLength =
          chapter?.readName == null
            ? undefined
            : savedSpecsRef.current.find((spec) => spec.chapter === chapter.readName)?.card?.duration
        if (chapter === undefined || !idle(latest.current)) {
          return
        }
        if (resolvedLength === undefined) {
          dispatch({ type: 'card-field', key: chapter.key, field: 'duration', value: seconds })
        } else {
          dispatch({
            type: 'card-length',
            key: chapter.key,
            seconds,
            resolved: resolvedLength,
            typed: true,
          })
        }
      },
      styleModel,
      switchModel,
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    hasNamedChapter,
    nameFor,
    styleModel,
    switchModel,
  ])
  const cardButtons = useMemo<CardButtonModel>(
    () => ({ selected: selectedCard, open: openCard }),
    [selectedCard, openCard],
  )

  const onAddChapter = useCallback(() => {
    if (idle(latest.current)) {
      setRefusedDelete(null)
      setChapterDialog({ kind: 'add' })
    }
  }, [])

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
      // The section moves in the DOM, which drops its focus: put it back (effects below).
      focusAfter.current = { key, target: delta < 0 ? 'chapter-up' : 'chapter-down' }
      dispatch({ type: 'chapter-move', key, delta })
      announce(`“${headingIn(next, key)}” moved to ${placeIn(next, key)}.`)
    },
    [announce],
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
    [announce, clips, ignoredOf, notesIn],
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
  const markLineRef = useRef<HTMLDivElement | null>(null)
  // Where the bin's player puts its Show player while hidden: the toolbar's first row.
  const [showSlot, setShowSlot] = useState<HTMLElement | null>(null)
  const playerShown = useBinPlayerShown()
  const rotateHintId = useId()
  // The bin's toolbar as drawn: it grows with the reason line or the Clips help, and the chapter
  // headings and the scroll padding follow (`--bin-toolbar-measured` on its parent, workspace.css).
  // A callback ref: the bin mounts its slots on its own schedule, not with `detail`.
  const stopMeasuring = useRef<(() => void) | null>(null)
  const placeMarkLine = useCallback((line: HTMLDivElement | null) => {
    markLineRef.current = line
    stopMeasuring.current?.()
    stopMeasuring.current = null
    const bin = line?.parentElement
    if (!line || !bin || typeof ResizeObserver === 'undefined') {
      return
    }
    const measure = () => bin.style.setProperty('--bin-toolbar-measured', `${line.offsetHeight}px`)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(line)
    stopMeasuring.current = () => {
      observer.disconnect()
      bin.style.removeProperty('--bin-toolbar-measured')
    }
  }, [])

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
  // Handed over after the commit, never during a render.
  useLayoutEffect(() => {
    rotateRef.current = onRotate
  }, [onRotate])
  // The Clip tab's Move earlier and Move later (`clip-tab-and-player` D6): one place in the chapter's
  // play order, as Move up and Move down, or into the next chapter at an edge, as Alt and an arrow.
  // The same draft edits and the same words; a step that cannot be made says why.
  const onStepClip = useCallback(
    (identity: string, way: -1 | 1) => {
      const current = latest.current
      if (!idle(current)) {
        announce(MOVE_LOCKED)
        return
      }
      const lists = listedChapters(current.draft.chapters).map((chapter) => ({
        key: chapter.key,
        identities: current.draft.orders.get(chapter.key) ?? NONE_REMOVED,
      }))
      if (!lists.some((list) => list.identities.includes(identity))) {
        return
      }
      const step = stepMove(lists, identity, way, (id) => onDisk(clips.get(id)))
      if (step.kind === 'edge') {
        announce(step.words)
      } else if (step.kind === 'move') {
        dispatch({ type: 'move', chapter: step.chapter, from: step.from, to: step.to })
        const length = lists.find((list) => list.key === step.chapter)?.identities.length ?? 0
        announce(clipStepWords(nameOfClip(identity), step.to, length))
      } else {
        dispatch({ type: 'clip-drop', from: step.from, to: step.to, identity, at: step.at })
        announce(stepAcrossWords(identity, headingIn(current.draft, step.to), step.before))
      }
    },
    [announce, clips, nameOfClip],
  )

  // Move to… of one clip (the Clip tab's): at the end of the chosen chapter, the edit a drop on its
  // band makes. Only a clip on disk that a chapter plays moves.
  const onMoveClipToEnd = useCallback(
    (identity: string, to: ChapterKey) => {
      const current = latest.current
      if (!idle(current)) {
        announce(MOVE_LOCKED)
        return
      }
      const from = [...current.draft.orders].find(([, order]) => order.includes(identity))?.[0]
      const target = current.draft.orders.get(to)
      if (
        from === undefined ||
        from === to ||
        target === undefined ||
        !isListed(current.draft, to) ||
        !onDisk(clips.get(identity))
      ) {
        return
      }
      dispatch({ type: 'clip-drop', from, to, identity, at: target.length })
      announce(moveToEndWords(identity, headingIn(current.draft, to)))
    },
    [announce, clips],
  )

  // Remove from reel.yaml and its Undo, from the Clip tab: the row controls' edits and words (a
  // missing clip only). The row's own focus handling does not run: the tab's button keeps focus.
  const onRemoveClipFromTab = useCallback(
    (identity: string) => {
      const current = latest.current
      if (!idle(current)) {
        announce(MOVE_LOCKED)
        return
      }
      const chapter = [...current.draft.orders].find(([, order]) => order.includes(identity))?.[0]
      if (chapter === undefined || clips.get(identity)?.status !== 'missing') {
        return
      }
      dispatch({ type: 'remove', chapter, identity })
      announce(`${nameOfClip(identity)} will be removed from reel.yaml when you save.`)
    },
    [announce, clips, nameOfClip],
  )
  const onRestoreClipFromTab = useCallback(
    (identity: string) => {
      const current = latest.current
      if (!idle(current)) {
        announce(MOVE_LOCKED)
        return
      }
      const chapter = current.draft.removed.get(identity)
      if (chapter === undefined || !isListed(current.draft, chapter)) {
        return
      }
      const orders = restoreClip(
        current.draft.orders,
        chapter,
        identity,
        current.baseline.original.get(chapter) ?? [],
      )
      const order = orders.get(chapter) ?? NONE_REMOVED
      dispatch({ type: 'restore', identity })
      announce(
        `${nameOfClip(identity)} is back at position ${order.indexOf(identity) + 1} of ${order.length}.`,
      )
    },
    [announce, nameOfClip],
  )

  // Ignore clips ignored the group (the Clip tab's): nothing stays selected, and focus goes to the
  // clip that stays next to the ones ignored on the track, or to the track.
  const groupFocus = useRef<string | null | undefined>(undefined)
  const onGroupIgnored = useCallback(
    (identities: readonly string[]) => {
      const current = latest.current
      const drawn =
        current === null
          ? []
          : listedChapters(current.draft.chapters)
              .flatMap((chapter) => current.draft.orders.get(chapter.key) ?? NONE_REMOVED)
              .filter((identity) => onDisk(clips.get(identity)))
      groupFocus.current = focusAfterMany(drawn, identities)
      cards.clear()
    },
    [cards.clear, clips],
  )
  useLayoutEffect(() => {
    const next = groupFocus.current
    if (next === undefined || cards.selection.kind !== 'none') {
      return
    }
    groupFocus.current = undefined
    const active = document.activeElement
    if (active !== null && active !== document.body) {
      return
    }
    const block = Array.from(
      document.querySelectorAll<HTMLElement>('.tl-clip-press[data-identity]'),
    ).find((candidate) => candidate.dataset.identity === next)
    ;(block ?? document.querySelector<HTMLElement>('.tl-viewport'))?.focus({ preventScroll: true })
  })

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
    setMarkedPending(true)
    startTransition(() => {
      dispatch({ type: 'marked-move', to: moveTo })
      setMarkedPending(false)
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
  const moveLabelId = useId()
  // The reason line shows only once Move is pressed while it cannot act; it goes when Move can.
  const [moveReasonShown, setMoveReasonShown] = useState(false)
  const moveWhy = moveReason(marks.size, moveTo !== '', listsLocked)
  useEffect(() => {
    if (moveWhy === null) {
      setMoveReasonShown(false)
    }
  }, [moveWhy])
  const moveWhyWords =
    moveWhy === null
      ? ''
      : moveWhy === 'busy' && selectionPending && !locked
        ? MOVING_WORDS
        : MOVE_REASON_WORDS[moveWhy]
  const onMovePressed = () => {
    if (moveWhy !== null) {
      setMoveReasonShown(true)
      announce(moveWhyWords)
      return
    }
    onMoveMarked()
  }

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
        cardId: cardIdOf(chapter),
        place: several ? { first: index === 0, last: index === listed.length - 1 } : null,
        deleteRefusal: refusal,
        refusalShown: refusedDelete === chapter.key && refusal != null,
        locked: listsLocked,
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
    onMoveChapter,
    onDeleteChapter,
  ])

  // The unsaved-changes question closes an open chapter dialog first, as a cancel: in
  // the same commit, so the question's dialog opens over the page, not over it.
  const shownDialog = leaveQuestion === 0 ? chapterDialog : null
  useEffect(() => {
    if (leaveQuestion !== 0) {
    }
  }, [leaveQuestion])

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
    // The Chapters list's control (the Event tab: the one place the chapter tools are).
    const inList = (selector: string) =>
      firstShown(root.querySelectorAll<HTMLElement>(`.edit-chapters ${selector}`))
    const target =
      request.target === 'add'
        ? inList('.chapter-add-button')
        : inList(`[data-chapter-key="${request.key}"] .${request.target}`)
    target?.focus({ preventScroll: true })
    scrollAfter.current =
      target?.closest<HTMLElement>('.chapter-row, .chapter-tools') ?? target
  })

  // The new chapter's heading takes focus here, after the dialog's cleanup; then the
  // part of the page focus went to comes into view, clear of the header and the bar.
  useEffect(() => {
    const request = focusAfter.current
    const root = editorRef.current
    if (request !== null && request.target === 'heading' && root !== null) {
      focusAfter.current = null
      // Its row in the Chapters list (focusable, `tabIndex=-1`).
      const row = root.querySelector<HTMLElement>(
        `.edit-chapters .chapter-row[data-chapter-key="${request.key}"]`,
      )
      row?.focus({ preventScroll: true })
      scrollAfter.current = row
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
        nameRefused: current.nameUnsent,
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

  // Undo and Redo (`editor-undo`): the buttons in the workspace's top bar and Ctrl/Cmd+Z,
  // Ctrl/Cmd+Shift+Z and Ctrl+Y. Never while a save is in flight, a clip is lifted or a move of
  // marked clips is pending (the draft shown is not the draft held).
  const onHistory = useCallback(
    (chord: 'undo' | 'redo') => {
      const current = latest.current
      if (current === null || current.pressed !== null || moving.current || lifted.current) {
        return
      }
      const label = chord === 'undo' ? undoLabel(current.history) : redoLabel(current.history)
      if (label === undefined) {
        return
      }
      dispatch({ type: chord })
      announce(stepWords(chord, label))
      // The step may remove the element that has focus (an added chapter's heading): once the
      // draft has re-rendered, a focus left on <body> goes to the details heading.
      const held = document.activeElement
      if (held !== null && held !== document.body) {
        requestAnimationFrame(() => {
          const now = document.activeElement
          if (now === null || now === document.body) {
            detailsHeadingRef.current?.focus()
          }
        })
      }
    },
    [announce],
  )
  // A pointer press that has not ended is a drag in progress (a track or handle drag, a list
  // drag): the keys wait for its release, which is the one step it records.
  const pointerHeld = useRef(false)
  const onUndoKey = useRef<(event: KeyboardEvent) => void>(() => undefined)
  useLayoutEffect(() => {
    onUndoKey.current = (event) => {
      const current = latest.current
      const chord = undoChord(event)
      if (current === null || chord === null) {
        return
      }
      const action = undoKeyAction({
        chord,
        repeat: event.repeat,
        inTextField: isTextTarget(event.target instanceof HTMLElement ? event.target : null),
        pointerHeld: pointerHeld.current,
        lifted: lifted.current,
        saving: current.pressed !== null || saving.current,
        moving: moving.current,
        dialogOpen: document.querySelector('dialog[open]') !== null,
        canUndo: canUndo(current.history),
        canRedo: canRedo(current.history),
      })
      if (action === 'ignore') {
        return
      }
      // The browser's own Undo would act on the page, not the draft.
      event.preventDefault()
      if (action === 'nothing') {
        announce(nothingWords(chord))
        return
      }
      onHistory(action)
    }
  })
  // Only in the workspace, where the Undo and Redo buttons show what the keys do.
  const undoListening = listening && inWorkspace
  useEffect(() => {
    if (!undoListening) {
      return undefined
    }
    const keydown = (event: KeyboardEvent) => onUndoKey.current(event)
    // Primary-button presses only: a right-click's release goes to the context menu, not the page.
    const down = (event: PointerEvent) => {
      pointerHeld.current = event.button === 0
    }
    const up = () => {
      pointerHeld.current = false
    }
    document.addEventListener('keydown', keydown)
    document.addEventListener('pointerdown', down, true)
    document.addEventListener('pointerup', up, true)
    document.addEventListener('pointercancel', up, true)
    document.addEventListener('lostpointercapture', up, true)
    document.addEventListener('contextmenu', up, true)
    window.addEventListener('blur', up)
    return () => {
      document.removeEventListener('keydown', keydown)
      document.removeEventListener('pointerdown', down, true)
      document.removeEventListener('pointerup', up, true)
      document.removeEventListener('pointercancel', up, true)
      document.removeEventListener('lostpointercapture', up, true)
      document.removeEventListener('contextmenu', up, true)
      window.removeEventListener('blur', up)
      pointerHeld.current = false
    }
  }, [undoListening])

  const retrying = state.status === 'failed' && state.retrying === true
  const hasIgnored = chapters.some((chapter) => chapter.ignored.length > 0)
  const hasMissing = [...clips.values()].some((clip) => clip.status === 'missing')
  const newClipsText = newClipsLine(adopted, newClips.size > 0, plural(adopted, 'new clip', 'new clips'))
  const clipCount = chapters.reduce((sum, chapter) => sum + chapter.movable.length, 0)

  // The inspector's Clip tab (`clip-tab-and-player` D5), built from the draft and the read, so it is
  // there with no track (Prepare) and for a clip the track does not draw: the clips of a set, or the
  // one clip (or cut's clip) selected. Null while no clip is selected.
  let clipTab: ReactNode = null
  const tabSelection = cards.selection
  if (ready !== null && detail !== null && editing !== null) {
    const { draft, baseline } = ready
    const nameFor = (identity: string) =>
      nameNow(draft, baseline.original, identity, ignoredOf, removedByChapter)
    const lists = listedChapters(draft.chapters)
    const chapterChoices = lists.map((chapter) => ({
      key: chapter.key,
      name: chapterHeading(chapter.name, hasNamedChapter),
    }))
    const held = new Set(selectedClips(tabSelection))
    const played =
      tabSelection.kind === 'clips'
        ? lists
            .flatMap((chapter) => draft.orders.get(chapter.key) ?? NONE_REMOVED)
            .filter((identity) => held.has(identity))
        : []
    // A set the draft no longer plays two clips of (the effect above trims it a render later) is
    // never shown as a group of one or none: the one clip left gets its own tab, none gets no tab.
    if (tabSelection.kind === 'clips' && played.length >= 2) {
      // Only the five names the tab shows are worked out: a range over 400 clips costs no more.
      clipTab = (
        <ClipGroupTab
          clips={played.map((identity, at) => ({
            identity,
            name: at < 5 ? nameFor(identity) : identity,
          }))}
          chapters={chapterChoices}
          editing={editing}
          onIgnored={onGroupIgnored}
        />
      )
    } else {
      const identity =
        tabSelection.kind === 'cut'
          ? tabSelection.identity
          : tabSelection.kind === 'clips'
            ? (played[0] ?? null)
            : lastClip(tabSelection)
      const clip = identity === null ? undefined : clips.get(identity)
      if (identity !== null && clip !== undefined) {
        const own = lists.find((chapter) => (draft.orders.get(chapter.key) ?? []).includes(identity))
        const state = clipState({
          status: clip.status,
          played: own !== undefined,
          removed: draft.removed.has(identity),
        })
        const offers = offersOf(state)
        const steps = lists.map((chapter) => ({
          key: chapter.key,
          identities: draft.orders.get(chapter.key) ?? NONE_REMOVED,
        }))
        const edge = (way: -1 | 1): string | null => {
          if (!offers.step || own === undefined) {
            return null
          }
          const step = stepMove(steps, identity, way, (id) => onDisk(clips.get(id)))
          return step.kind === 'edge' ? step.words : null
        }
        const ignoredIn = [...ignoredOf].find(([, identities]) => identities.includes(identity))?.[0]
        clipTab = (
          <ClipInspector
            identity={identity}
            name={nameFor(identity)}
            place={draftPlace(draft.chapters, draft.orders, [ignoredOf, removedByChapter], identity)}
            state={state}
            status={statusWords(state, clip)}
            chapters={chapterChoices}
            own={own?.key ?? null}
            editing={editing}
            edges={{ earlier: edge(-1), later: edge(1) }}
            onStep={(way) => onStepClip(identity, way)}
            onMoveTo={(to) => onMoveClipToEnd(identity, to)}
            onEnd={() => {
              if (offers.action === 'ignore') {
                editing.onIgnore(identity)
              } else if (offers.action === 'include' && ignoredIn !== undefined) {
                onIncludeClip(ignoredIn, identity)
              } else if (offers.action === 'remove') {
                onRemoveClipFromTab(identity)
              } else if (offers.action === 'undo') {
                onRestoreClipFromTab(identity)
              }
            }}
            slot={setClipSlot}
          />
        )
      }
    }
  }

  // The editor's parts, placed by the layout: stacked in the page, or in the workspace's panes.
  const parts =
    ready === null
      ? null
      : {
          details: <>
          <section className="panel edit-details" aria-labelledby={detailsId}>
            <header className="panel-header">
              {/* Focused by script after Try again reads the document. */}
              <h2 ref={detailsHeadingRef} id={detailsId} tabIndex={-1}>
                {heading}
              </h2>
              <HelpToggle help={detailsHelp} section="Details" />
            </header>
            <HelpPanel help={detailsHelp}>
              <p>
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
            </HelpPanel>
            <div className="panel-body">
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
          </>,
          // The Chapters list (the Event tab, after Details): built from the draft, so it is there
          // with no track and in Prepare.
          chapters: <>
          {detail !== null && (
            <CardButtonContext.Provider value={cardButtons}>
              <ChapterList
                rows={ready.draft.chapters.map(
                  (chapter): ChapterRowModel => ({
                    chapter,
                    heading: chapterHeading(chapter.name, hasNamedChapter),
                    played: (ready.draft.orders.get(chapter.key) ?? NONE_REMOVED).length,
                    removed: (removedByChapter.get(chapter.key) ?? NONE_REMOVED).length,
                    ignored: (ignoredOf.get(chapter.key) ?? NONE_REMOVED).length,
                  }),
                )}
                tools={tools}
                notes={notes}
                locked={listsLocked}
                onAdd={onAddChapter}
                onUndo={onUndoDelete}
              />
            </CardButtonContext.Provider>
          )}
          </>,
          poster: <>
          {detail !== null && (
            <PosterPanel
              eventId={eventId}
              event={liveNow ?? detail}
              read={ready.baseline.read}
              draft={ready.draft.poster}
              orders={ready.draft.orders}
              frame={posterFrame}
              locked={locked}
              onUseDefault={onUseDefault}
            />
          )}
          </>,
          // The workspace's Event tab: the way to the docked card editor's "All title cards in this
          // event" tab (card style, Title cards On / Off), on the draft's first card (the
          // opening card, or the first chapter's in an event without root clips or with the
          // default chapter deleted), and the switch's state in words. Not a section and no
          // control of its own: the docked editor stays the one place.
          titleCards: <>
          {/* The editor is the Timeline section's: shown with it. */}
          {editing !== null && cardEditing !== null && detail !== null && firstCard !== null && (
            <div className="ws-cards">
              <button
                type="button"
                className="btn btn-secondary"
                aria-describedby={`${titleCardsId}-state`}
                onClick={() => cards.open(firstCard, 'event')}
              >
                {TAB_NAME.event}
              </button>
              <p id={`${titleCardsId}-state`} className="ws-cards-state">
                {titleCardsWords(cardEditing.switchModel)}
                {cardEditing.switchModel.answer !== null && (
                  <span className="ws-cards-where"> {whereWords(cardEditing.switchModel)}.</span>
                )}
              </p>
            </div>
          )}
          </>,
          timeline: <>
          {editing !== null && cardEditing !== null && detail !== null && (
            // Open from the start; its chapters, order and cuts are the draft's, its clips' facts
            // and proxies the page's (the draft's maps keep their identity until an edit).
            <TimelineSection
              eventId={eventId}
              event={liveNow ?? detail}
              dismissals={dismissals}
              analysis={analysis}
              onFinished={onProxiesFinished ?? NOTHING}
              editing={editing}
              chapters={ready.draft.chapters}
              orders={ready.draft.orders}
              cards={cards}
              cardEditing={cardEditing}
            />
          )}
          </>,
          // The bin's player: the one clip preview, above the bin's scroll box.
          player: <>
          {detail !== null && (
            <BinPlayer
              eventId={eventId}
              selection={cards.selection}
              clips={clips}
              nameOf={(identity) =>
                nameNow(ready.draft, ready.baseline.original, identity, ignoredOf, removedByChapter)
              }
              cutsOf={(identity) => cutsOf(ready.baseline.cuts, ready.draft.cuts, identity)}
              turnOf={(identity) => draftTurns.get(identity) ?? 0}
              locked={listsLocked}
              panels={cutPanels.panels}
              onTyped={cutHandlers.onTyped}
              focusAsk={watchAsk}
              showSlot={showSlot}
              onAnnounce={announce}
            />
          )}
          </>,
          bin: <>
          {detail !== null && newClipsText !== null && !inWorkspace && (
            <div className="edit-hint">
              <Icon name="info" />
              <p>{adopted > 0 ? <strong>{newClipsText}</strong> : newClipsText}</p>
            </div>
          )}

          {detail !== null && (
            // How clips are marked, and, once any is, how many and Clear marks. Its slot keeps
            // its height and room either way, so the first mark moves no row.
            <div
              ref={placeMarkLine}
              className="mark-line"
              data-player={playerShown ? 'shown' : 'hidden'}
              tabIndex={-1}
            >
              <div className="mark-head">
                <span className="mark-lead">
                  <HelpToggle help={clipsHelp} section="Clips" />
                  <span ref={setShowSlot} className="mark-lead-player" />
                </span>
                <span className="mark-line-slot">
                  <span className="mark-count" hidden={marks.size === 0}>
                    {countWords(marks.size)}
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    hidden={marks.size === 0}
                    title="Clear marks"
                    aria-disabled={listsLocked || undefined}
                    onClick={onClearMarks}
                  >
                    <span className="mark-clear-icon">
                      <Icon name="x" />
                    </span>
                    <span className="mark-clear-words">Clear marks</span>
                  </button>
                </span>
              </div>
              <HelpPanel help={clipsHelp}>
                {clipsHelpLines({
                  several: listed.length > 1,
                  hasIgnored,
                  hasMissing,
                  ownChapter: listed.some((chapter) => chapter.name === ''),
                  hasNewClip: inWorkspace && newClips.size > 0,
                }).map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </HelpPanel>
              <div className="mark-actions">
                <span className="mark-rotate" role="group" aria-label="Marked clips">
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    aria-disabled={listsLocked || marks.size === 0 || undefined}
                    aria-describedby={marks.size === 0 ? rotateHintId : undefined}
                    title="Rotate marked left"
                    onClick={() => onRotateMarked('left')}
                  >
                    <Icon name="rotate-ccw" />
                    <span className="mark-words">Rotate marked left</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    aria-disabled={listsLocked || marks.size === 0 || undefined}
                    aria-describedby={marks.size === 0 ? rotateHintId : undefined}
                    title="Rotate marked right"
                    onClick={() => onRotateMarked('right')}
                  >
                    <Icon name="rotate-cw" />
                    <span className="mark-words">Rotate marked right</span>
                  </button>
                  <span id={rotateHintId} className="visually-hidden">
                    Mark clips to rotate them together.
                  </span>
                </span>
                {listedKeys.length > 1 && (
                  <span className="mark-move" role="group" aria-labelledby={moveLabelId}>
                    <label id={moveLabelId} htmlFor={moveSelectId} className="mark-move-label">
                      Move marked to…
                    </label>
                    <select
                      id={moveSelectId}
                      className="field-input"
                      aria-label="Chapter to move the marked clips to"
                      value={moveTo}
                      aria-disabled={listsLocked || undefined}
                      aria-describedby={moveReasonId}
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
                      aria-busy={markedPending || undefined}
                      aria-describedby={moveReasonId}
                      title={moveWhy === null ? undefined : moveWhyWords}
                      onClick={onMovePressed}
                    >
                      <Icon name="arrow-right" />
                      Move
                    </button>
                  </span>
                )}
              </div>
              {listedKeys.length > 1 && (
                <p id={moveReasonId} className={moveReasonShown ? 'mark-move-why' : 'visually-hidden'}>
                  {moveWhyWords}
                </p>
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
            <CardButtonContext.Provider value={cardButtons}>
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
                overTrack={overTrack}
                onDropOutside={onDropOnTrack}
                rootRef={editorRef}
              >
                {ready.draft.chapters.map((chapter) =>
                  // A deleted chapter is listed in the Chapters list only, with its Undo.
                  chapter.deleted ? null : (
                    <ClipOrderList
                      key={chapter.key}
                      eventId={eventId}
                      chapterKey={chapter.key}
                      name={chapter.name}
                      heading={chapterHeading(chapter.name, hasNamedChapter)}
                      order={ready.draft.orders.get(chapter.key) ?? NONE_REMOVED}
                      original={ready.baseline.original.get(chapter.key) ?? NONE_REMOVED}
                      ignored={ignoredOf.get(chapter.key) ?? NONE_REMOVED}
                      removed={removedByChapter.get(chapter.key) ?? NONE_REMOVED}
                      clips={clips}
                      origins={origins}
                      lastMoved={ready.lastMoved}
                      locked={listsLocked}
                      alone={listed.length < 2}
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
                      onInclude={onIncludeClip}
                      onAnnounce={announce}
                      compact={inWorkspace}
                      selectedClips={selectedIn(
                        chapter.key,
                        ready.draft.orders.get(chapter.key) ?? NONE_REMOVED,
                        ignoredOf.get(chapter.key) ?? NONE_REMOVED,
                        removedByChapter.get(chapter.key) ?? NONE_REMOVED,
                      )}
                      leadClip={leadIn(ready.draft.orders.get(chapter.key) ?? NONE_REMOVED)}
                      onSelectClip={selectClip}
                      onWatchClip={watchClip}
                      ignoredApart={ignoredApart}
                    />
                  ),
                )}
                {detail !== null && ignoredApart && (
                  <IgnoredBin
                    eventId={eventId}
                    groups={ignoredGroups(ready.draft.chapters, ignoredOf, (name) =>
                      chapterHeading(name, hasNamedChapter),
                    )}
                    clips={clips}
                    locked={listsLocked}
                    onInclude={onIncludeClip}
                    selectedClips={selectedSet}
                    onSelectClip={selectClip}
                    nameOf={(group) =>
                      namesIn(
                        group.name,
                        ready.baseline.original.get(group.key) ?? [],
                        ready.draft.orders.get(group.key) ?? [],
                        group.identities,
                        removedByChapter.get(group.key) ?? [],
                      )
                    }
                  />
                )}
              </ChapterDrag>
            </CardButtonContext.Provider>
          )}

          </>,
          saveBar: <>
          {/*
            In the page from the moment Edit mode is ready, `hidden` while there is nothing to
            say: the first edit then builds nothing. The summary is only worked out while shown.
          */}
          <SaveBar
            variant={inWorkspace ? 'top' : 'page'}
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
                    ignoreChanges(ready.draft),
                  )
                : ''
            }
            unfinished={unfinished(ready)}
            onReset={() => {
              // The panels' fields go first, so the remounted panels start empty.
              cutPanels.clear()
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
          </>,
        }

  return (
    <div
      ref={editorRef}
      className={workspace === undefined ? 'event-editor' : 'event-editor event-editor-ws'}
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
      // Leaving a field ends the typing run its edits were folded into (`history.ts`).
      onBlur={() => dispatch({ type: 'break' })}
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

      {workspace === undefined ? (
        <>
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
          {parts !== null && (
            <>
              {parts.details}
              {parts.chapters}
              {parts.poster}
              {parts.timeline}
              {parts.player}
              {parts.bin}
              {parts.saveBar}
            </>
          )}
        </>
      ) : (
        <Workspace
          top={
            <TopBar
              frame={workspace}
              saveBar={parts?.saveBar ?? null}
              history={
                ready === null
                  ? null
                  : {
                      undo: buttonName('Undo', undoLabel(ready.history)),
                      redo: buttonName('Redo', redoLabel(ready.history)),
                      canUndo: canUndo(ready.history) && ready.pressed === null,
                      canRedo: canRedo(ready.history) && ready.pressed === null,
                      onUndo: () => onHistory('undo'),
                      onRedo: () => onHistory('redo'),
                    }
              }
            />
          }
          viewer={<>
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
            </>}
          player={parts?.player ?? null}
          bin={parts?.bin ?? null}
          clip={clipTab}
          clipSlot={clipSlot}
          event={
            <>
              {parts?.details}
              {parts?.chapters}
              {parts?.poster}
              {parts?.titleCards}
              {workspace.aside}
            </>
          }
          timeline={parts?.timeline ?? null}
          tab={inspectorTab}
          onTab={setInspectorTab}
        />
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
