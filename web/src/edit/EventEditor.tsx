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
import { clipNames, folderName, plural } from '../events/common'
import { FAILURE_LABEL, UNANSWERED_CAUSE, notReachableHint } from '../events/labels'
import { FAILURE_LOOK } from '../events/tones'
import { eventName } from '../jobs/labels'
import { createClipPreviews } from '../preview/previews'
import { LIST_HREF } from '../route'
import { focusPageHeading } from '../shell/AppShell'
import { TimelineSection } from '../timeline/TimelineSection'
import type { EditBinding } from '../timeline/editing'
import type { Dismissals } from '../timeline/overlays/Dismissals'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { SkeletonRows } from '../ui/Skeleton'
import { keepToastsClearOf, toast } from '../ui/toast'
import { MoveClipsDialog, NameDialog } from './ChapterDialogs'
import type { MovableClip } from './ChapterDialogs'
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
import { AddChapter, DeletedChapter, NO_CLIPS_TO_MOVE } from './ChapterTools'
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
  moveClips,
  moveGroup,
  movedSet,
  ordersOf,
  originOf,
  readCuts,
  removeClip,
  removeCut,
  renameChapter,
  restoreChapter,
  restoreClip,
  restoreCut,
  trimCut,
} from './draft'
import type {
  Baseline,
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
  NO_MARKS,
  afterMove,
  clearMarks,
  countWords,
  markWords,
  pruneMarks,
  toggleMark,
} from './marks'
import { FIELD_LABEL, MetadataForm } from './MetadataForm'
import { SaveBar } from './SaveBar'
import type { Operation, Pressed, SaveProblem } from './SaveBar'
import { TitleCardContext } from './TitleCard'
import type { TitleCardModel } from './TitleCard'
import { holdWords, isSaveChord, LIFTED_WORDS, saveHold, saveKeyAction } from './saveShortcut'
import { inheritHint } from './MetadataForm'
import type { Resolved } from './MetadataForm'
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
 * deleted once empty, and clips moved between them with a chapter's Move clips
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
  | { type: 'clips-move'; from: ChapterKey; to: ChapterKey; identities: readonly string[] }
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
  | { type: 'name-unsent'; unsent: boolean }
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
  return { ...next, problem: next.problem?.kind === 'gone' ? next.problem : null, refusal: null }
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
  }
}

/** `state` with `draft`, unless the action changed nothing. */
function withDraft(state: Ready, draft: Draft): Ready {
  return draft === state.draft ? state : afterEdit({ ...state, draft })
}

/** `state` with `draft` and its marks less the clips just moved, unless nothing changed. */
function withMoved(state: Ready, draft: Draft, moved: readonly string[]): Ready {
  return draft === state.draft
    ? state
    : afterEdit({ ...state, draft, marked: afterMove(state.marked, moved) })
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
    case 'clips-move':
      if (!isListed(state.draft, action.from) || !isListed(state.draft, action.to)) {
        return state
      }
      return withMoved(
        state,
        moveClips(state.draft, action.from, action.to, action.identities, state.baseline.original),
        action.identities,
      )
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
    case 'reset':
      return {
        ...state,
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
    adopted > 0 && `adds ${plural(adopted, 'new clip', 'new clips')} to reel.yaml`,
  ].filter((part): part is string => part !== false)
  const text = parts.join(' · ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

// The read view's cuts, which Edit mode's Timeline does not use: its cuts are the draft's.
/** What `naming` holds while the main title card's field is open (a chapter key never is). */
const TITLE = 'title' as const

const NOT_READ = { cuts: null, failure: null } as const
const NOTHING = () => undefined

// A chapter with no removed clip: one constant, so its list keeps its memoised props.
const NONE_REMOVED: readonly string[] = []

/** The chapter's heading, as the read view names it. */
function chapterHeading(name: string, hasNamedChapter: boolean): string {
  return name !== '' ? name : hasNamedChapter ? OWN_CHAPTER_HEADING : 'Clips'
}

/** The chapter dialog open, if any: Add chapter or a chapter's Move clips. */
type ChapterDialog =
  | { kind: 'add' }
  | { kind: 'move'; key: ChapterKey }

/** Where focus goes once a chapter edit is on screen: a control of a chapter, by class. */
type ChapterFocus = {
  key: ChapterKey | null
  target: 'heading' | 'chapter-up' | 'chapter-down' | 'chapter-undo' | 'chapter-delete' | 'add'
}

/** The statuses of a clip on disk that the chapter plays: the ones Move clips offers. */
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
 * one on disk moves out with Move clips, a missing one goes with its Remove. Or it
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

/**
 * What Move clips offers for chapter `key`: its clips on disk, in play order, and
 * the other chapters; and how many clips it leaves out, and why.
 */
function moveDialogProps(
  draft: Draft,
  original: ReadonlyMap<ChapterKey, readonly string[]>,
  key: ChapterKey,
  ignored: readonly string[],
  removed: readonly string[],
  clips: ReadonlyMap<string, Clip>,
): {
  heading: string
  clips: MovableClip[]
  missing: number
  ignored: number
  targets: { key: ChapterKey; heading: string }[]
} {
  const chapter = draft.chapters.find((listed) => listed.key === key)
  const order = draft.orders.get(key) ?? []
  // Named as the chapter's rows name them (ClipOrderList `nameOf`).
  const nameOf = clipNames(chapter?.name ?? '', [
    ...(original.get(key) ?? []),
    ...order,
    ...ignored,
    ...removed,
  ])
  const offered = order.flatMap((identity, index) => {
    const clip = clips.get(identity)
    return clip !== undefined && onDisk(clip)
      ? [{ identity, name: nameOf(identity), status: clip.status, position: index + 1 }]
      : []
  })
  return {
    heading: headingIn(draft, key),
    clips: offered,
    missing: order.filter((identity) => clips.get(identity)?.status === 'missing').length,
    ignored: ignored.length,
    targets: listedChapters(draft.chapters)
      .filter((listed) => listed.key !== key)
      .map((listed) => ({ key: listed.key, heading: headingIn(draft, listed.key) })),
  }
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
  // A Move clips applied in a transition (`confirmMove`): until it lands, the page shows
  // the order from before it, so no control that acts on what is shown may act yet.
  const [movingFrom, setMovingFrom] = useState<ChapterKey | null>(null)
  const listsLocked = locked || movingFrom !== null
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
  // in its row, which Move clips mounts anew in another chapter. Reset empties it, and
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
  // The chapter a Move clips is leaving, set before the transition starts and cleared
  // when it lands: a press meanwhile would act on the order from before the move.
  const moving = useRef<ChapterKey | null>(null)
  // A clip lifted by the drag and not yet dropped (`ChapterDrag`'s `onLift`).
  const lifted = useRef(false)
  const onLift = useCallback((is: boolean) => {
    lifted.current = is
  }, [])
  useLayoutEffect(() => {
    latest.current = ready
    moving.current = movingFrom
  })
  /** Whether a chapter control may act now: not while a save or a Move clips is pending. */
  const idle = (current: Ready | null): current is Ready =>
    current !== null && current.pressed === null && moving.current === null

  /** The later-clips notes a chapter has once `draft` is the draft, for an announcement. */
  const notesIn = useCallback(
    (draft: Draft, key: ChapterKey): string => {
      const lines = laterClipNotes({ chapters: draft.chapters, folders, ignored: ignoredOf })
      return (lines.get(key) ?? []).map((line) => ` ${line}`).join('')
    },
    [folders, ignoredOf],
  )

  // The cut operations: one stable object, so the rows keep their memoised props. The
  // panel checks a cut and speaks it; a press while a save or a Move clips is pending
  // changes nothing here either.
  const cutHandlers = useMemo<CutHandlers>(
    () => ({
      onAdd: (identity, span, reason) => {
        const current = latest.current
        if (current !== null && current.pressed === null && moving.current === null) {
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
      if (current === null || current.pressed !== null || moving.current !== null) {
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
  const resetCount = ready?.resets ?? 0
  const editing = useMemo<EditBinding | null>(() => {
    if (baseCuts === undefined || draftCuts === undefined || detail === null) {
      return null
    }
    return {
      cuts: liveTrims(baseCuts, draftCuts),
      listed: (identity) => cutsOf(baseCuts, draftCuts, identity),
      onTrim,
      onAdd: cutHandlers.onAdd,
      locked: listsLocked,
      announce,
      orderChanged,
      previews: cutPanels.panels.previews,
      epoch: resetCount,
    }
  }, [
    baseCuts,
    draftCuts,
    detail,
    listsLocked,
    onTrim,
    cutHandlers,
    announce,
    orderChanged,
    cutPanels,
    resetCount,
  ])

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

  const onMoveClipsFrom = useCallback<ChapterHandler>(
    (key) => {
      const current = latest.current
      if (!idle(current)) {
        return
      }
      const order = current.draft.orders.get(key) ?? []
      if (!order.some((identity) => onDisk(clips.get(identity)))) {
        announce(NO_CLIPS_TO_MOVE)
        return
      }
      setRefusedDelete(null)
      setChapterDialog({ kind: 'move', key })
    },
    [announce, clips],
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
  // A clip Move clips does not offer (missing) never leaves its chapter by a drag either.
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
  // Not while a save or a Move clips is pending, and only a clip on disk; false when refused.
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

  // A mark or Clear marks: not while a save or a Move clips is pending, nor while a clip is
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

  // A group drop (`ChapterDrag`): the marked clips as one run at a gap of `to`, one edit.
  // False when it changes nothing or is refused (save or Move clips pending); the marks stay.
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

  // Each listed chapter's tools: what it offers, its notes and why it cannot go. A
  // chapter's object is kept while what it shows is unchanged, so its list re-renders
  // only when its own tools change.
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
        moveClips: !several
          ? null
          : order.some((identity) => onDisk(clips.get(identity)))
            ? 'offered'
            : 'empty',
        place: several ? { first: index === 0, last: index === listed.length - 1 } : null,
        deleteRefusal: refusal,
        refusalShown: refusedDelete === chapter.key && refusal != null,
        locked: listsLocked,
        moveClipsBusy: movingFrom === chapter.key,
        nameField,
        onMoveClips: onMoveClipsFrom,
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
    movingFrom,
    openName,
    nameField,
    onMoveClipsFrom,
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
    announce(`Chapter “${name}” added, ${placeIn(next, key)}. It has no clips.${notesIn(next, key)}`)
  }

  function confirmMove(identities: string[], to: ChapterKey): void {
    if (shownDialog === null || shownDialog.kind !== 'move') {
      return
    }
    const current = latest.current
    setChapterDialog(null)
    if (current === null) {
      return
    }
    // The dialog closes at once; the lists follow in a transition (a 400-clip chapter
    // re-renders every row), so the press is answered before that work is done. Until it
    // lands every control acting on the lists is unavailable, and the pressed Move clips
    // busy (`movingFrom`): the page still shows the order from before the move.
    const from = shownDialog.key
    moving.current = from
    setMovingFrom(from)
    startTransition(() => {
      dispatch({ type: 'clips-move', from, to, identities })
      setMovingFrom(null)
    })
    announce(
      `${plural(identities.length, 'clip', 'clips')} moved to “${headingIn(current.draft, to)}”.`,
    )
  }

  function submit(pressed: Pressed, operation: Operation): void {
    // Never a half-typed date (it would be sent as unset), never without a cut typed
    // but not added (it would be lost), and never a save of nothing.
    // Nor while a Move clips is pending: the draft shown is the one from before it.
    if (
      ready === null ||
      saving.current ||
      moving.current !== null ||
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
        moving: moving.current !== null,
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

          {editing !== null && detail !== null && (
            // Closed until opened; its cuts are the draft's, its clips and proxies the page's.
            <TimelineSection
              eventId={eventId}
              event={liveEvent ?? detail}
              read={NOT_READ}
              dismissals={dismissals}
              onFinished={onProxiesFinished ?? NOTHING}
              editing={editing}
            />
          )}

          {detail !== null && (
            <div className="edit-hint">
              <Icon name="info" />
              <p>
                {/* With one chapter, where chapters come from: once, they were not found. */}
                {listed.length > 1
                  ? 'Drag a clip by its handle, or use its arrows, to reorder it. Drag it into ' +
                    'another chapter to move it there; a chapter’s Move clips moves several ' +
                    'clips at once.'
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
                    onMark={onMark}
                    onMove={onMove}
                    onRemove={onRemove}
                    onRestore={onRestore}
                    onAnnounce={announce}
                  />
                )
              })}
            </ChapterDrag>
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

      {ready !== null && shownDialog !== null && shownDialog.kind === 'move' && (
        <MoveClipsDialog
          {...moveDialogProps(
            ready.draft,
            ready.baseline.original,
            shownDialog.key,
            ignoredOf.get(shownDialog.key) ?? NONE_REMOVED,
            removedByChapter.get(shownDialog.key) ?? NONE_REMOVED,
            clips,
          )}
          marked={marks}
          onConfirm={confirmMove}
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
