import './edit.css'

import {
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
import { markEventsChanged } from '../events/changes'
import { folderName, plural } from '../events/common'
import { FAILURE_LABEL, UNANSWERED_CAUSE } from '../events/labels'
import { FAILURE_LOOK } from '../events/tones'
import { LIST_HREF } from '../route'
import { focusPageHeading } from '../shell/AppShell'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { SkeletonRows } from '../ui/Skeleton'
import { keepToastsClearOf, toast } from '../ui/toast'
import { ClipOrderList } from './ClipOrderList'
import type { MoveHandler, RemoveHandler, RestoreHandler } from './ClipOrderList'
import {
  adoptedNewCount,
  buildWriteBody,
  changedFields,
  detailMatchesDocument,
  editableChapters,
  isDirty,
  metadataDraftOf,
  moveClip,
  movedSet,
  ordersOf,
  removeClip,
  restoreClip,
} from './draft'
import type { EditableChapter, MetadataDraft, MetadataField, Orders, Removals } from './draft'
import { FIELD_LABEL, MetadataForm } from './MetadataForm'
import { SaveBar } from './SaveBar'
import type { Operation, Pressed, SaveProblem } from './SaveBar'
import type { Resolved } from './MetadataForm'
import {
  discardAndLeave,
  keepEditing,
  setSaving,
  usePendingLeave,
  useUnsavedGuard,
} from './unsaved'

/**
 * Edit mode: the event's clip order and metadata, saved explicitly.
 *
 * It reads `reel.yaml` (the document and its ETag) next to the detail the page
 * already shows, and saves one whole-document PUT under `If-Match` per explicit
 * Save. The body is always the document as read with only the operator's
 * edits applied (`draft.ts`). While a save is in flight the editor is locked
 * and the pressed control is busy; every failure keeps the edits and says why.
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
  read: ReelDocument
  etag: string
  original: Orders
  orders: Orders
  /** The clip moved last: it takes the "moved" badge when a swap could give it to either. */
  lastMoved: string | null
  /** The missing clips taken out of their chapter's order, which Save leaves out of reel.yaml. */
  removed: Removals
  metadata: MetadataDraft
  /** The date input holds a date typed only in part (its value reads as ''). */
  dateIncomplete: boolean
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
  | { type: 'move'; chapter: string; from: number; to: number }
  | { type: 'remove'; chapter: string; identity: string }
  | { type: 'restore'; identity: string }
  | { type: 'field'; field: MetadataField; value: string }
  | { type: 'date-validity'; incomplete: boolean }
  | { type: 'reset' }
  | { type: 'save-start'; pressed: Pressed }
  | { type: 'save-failed'; problem: SaveProblem | null; refusal: string | null }

/**
 * An edit that brings the draft back to what was read retires the last save's
 * failure: there is nothing left to save. A vanished event stays said.
 */
function afterEdit(next: Ready): Ready {
  const dirty = isDirty(next.read, next.original, next.orders, next.metadata) || next.dateIncomplete
  if (dirty || (next.problem === null && next.refusal === null)) {
    return next
  }
  return { ...next, problem: next.problem?.kind === 'gone' ? next.problem : null, refusal: null }
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
      const original = ordersOf(action.chapters)
      return {
        status: 'ready',
        read: action.document,
        etag: action.etag,
        original,
        orders: original,
        lastMoved: null,
        removed: new Map(),
        metadata: metadataDraftOf(action.document),
        dateIncomplete: false,
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
      const order = state.orders.get(action.chapter)
      if (order === undefined || action.from === action.to) {
        return state
      }
      const orders = new Map(state.orders)
      orders.set(action.chapter, moveClip(order, action.from, action.to))
      return afterEdit({ ...state, orders, lastMoved: order[action.from] })
    }
    case 'remove': {
      const orders = removeClip(state.orders, action.chapter, action.identity)
      if (orders === null) {
        return state
      }
      const removed = new Map(state.removed).set(action.identity, action.chapter)
      return afterEdit({ ...state, orders, removed })
    }
    case 'restore': {
      const chapter = state.removed.get(action.identity)
      if (chapter === undefined) {
        return state
      }
      // Back after the clips it followed when Edit mode opened (draft.ts, `restoreClip`).
      const original = state.original.get(chapter) ?? []
      const orders = restoreClip(state.orders, chapter, action.identity, original)
      const removed = new Map(state.removed)
      removed.delete(action.identity)
      return afterEdit({ ...state, orders, removed })
    }
    case 'field':
      return afterEdit({
        ...state,
        metadata: { ...state.metadata, [action.field]: action.value },
        // A refusal is about the date or title that was sent; editing them retires it.
        refusal: action.field === 'title' || action.field === 'date' ? null : state.refusal,
      })
    case 'date-validity':
      return action.incomplete === state.dateIncomplete
        ? state
        : afterEdit({ ...state, dateIncomplete: action.incomplete })
    case 'reset':
      return {
        ...state,
        orders: state.original,
        lastMoved: null,
        removed: new Map(),
        metadata: metadataDraftOf(state.read),
        dateIncomplete: false,
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

/** A failed read in the words the page uses for a failed event read. */
function readFailure(
  result: Exclude<ReelReadResult, { kind: 'ok' }>,
  eventId: string,
): ReadFailure {
  if (result.kind === 'unreachable' || result.kind === 'unpublished') {
    return { cause: UNANSWERED_CAUSE[result.kind], detail: result.message }
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

// A toast's text is a string: these keep its line breaks out of the name's date.
const NO_BREAK_SPACE = '\u00a0'
const WORD_JOINER = '\u2060' // invisible; no line break before or after it

/**
 * How a toast names an event, in the render toasts' format: its title, then its
 * date, since titles repeat; with no title, its folder name, which starts with
 * the date. The "·" never ends or starts a line, and the date never breaks at its
 * hyphens.
 */
function eventName(eventId: string, title: string | null, date: string | null): string {
  if (title === null) {
    return `“${folderName(eventId)}”`
  }
  if (date === null) {
    return `“${title}”`
  }
  const unbroken = date.split('-').join(`-${WORD_JOINER}`)
  return `“${title}”${NO_BREAK_SPACE}·${NO_BREAK_SPACE}${unbroken}`
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
  const written = body.metadata[field]
  if (written != null) {
    return written
  }
  return read.metadata[field] == null ? (resolved?.[field] ?? null) : null
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

/** What the save bar lists: the changed fields, the moves, the removals, and what a save adds. */
function summarize(
  changed: readonly MetadataField[],
  dateIncomplete: boolean,
  moved: number,
  removed: number,
  adopted: number,
): string {
  // An incomplete date reads as '' but is not a date left empty: it is named as such.
  const fields = dateIncomplete ? changed.filter((field) => field !== 'date') : changed
  const parts = [
    fields.length > 0 && `${fieldWords(fields)} changed`,
    dateIncomplete && 'date incomplete',
    moved > 0 && `${plural(moved, 'clip', 'clips')} moved`,
    removed > 0 && `${plural(removed, 'missing clip', 'missing clips')} removed`,
    adopted > 0 && `adds ${plural(adopted, 'new clip', 'new clips')} to reel.yaml`,
  ].filter((part): part is string => part !== false)
  const text = parts.join(' · ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

// A chapter with no removed clip: one constant, so its list keeps its memoised props.
const NONE_REMOVED: readonly string[] = []

/** The chapter's heading, as the read view names it. */
function chapterHeading(name: string, hasNamedChapter: boolean): string {
  return name !== '' ? name : hasNamedChapter ? 'Main' : 'Clips'
}

export function EventEditor({
  eventId,
  event,
  heading = 'Details',
  onSaved,
  onReload,
}: {
  eventId: string
  event: EventDetail | null
  /** The metadata section's heading. */
  heading?: string
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
  const refusalRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const keepEditingRef = useRef<HTMLButtonElement>(null)
  // Try again was pressed and its answer is still to come; a press meanwhile sends nothing.
  const retried = useRef(false)
  const detailsHeadingRef = useRef<HTMLHeadingElement>(null)
  const readAgainRef = useRef<HTMLButtonElement>(null)

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
  const changed = ready === null ? [] : changedFields(ready.read, ready.metadata)
  let movedCount = 0
  if (ready !== null) {
    // Against each original order without its removed clips: a removal alone moves nothing.
    for (const [name, original] of ready.original) {
      const kept = original.filter((identity) => !ready.removed.has(identity))
      movedCount += movedSet(kept, ready.orders.get(name) ?? kept, ready.lastMoved).size
    }
  }
  const adopted =
    ready === null ? 0 : adoptedNewCount(ready.read, ready.original, ready.orders, newClips)
  // Edits to save, and edits at all (a date typed in part is one, but cannot be saved).
  const edited = ready !== null && isDirty(ready.read, ready.original, ready.orders, ready.metadata)
  const dirty = edited || (ready?.dateIncomplete ?? false)
  // While there are edits; a vanished event keeps its alert even without any.
  const showBar = ready !== null && (dirty || ready.problem?.kind === 'gone')

  useUnsavedGuard(dirty)
  // The page and the navigation guard hold every way out while a save is in flight.
  useEffect(() => {
    setSaving(locked)
    return () => setSaving(false)
  }, [locked])

  // The bar's height, for the bottom scroll padding (focus never hides under it),
  // and the toast region's offset when no bar is registered. Published in the
  // commit that shows the bar, so the scroll a move or a drop makes right after (a
  // passive effect) already clears it; it wraps when narrow, so a ResizeObserver
  // follows later changes. Registered, the bar has the toasts place themselves
  // above it while it is held at the window's bottom, below it once it rests.
  useLayoutEffect(() => {
    const bar = barRef.current
    if (!showBar || bar === null) {
      return
    }
    const root = document.documentElement
    const publish = () => root.style.setProperty('--toast-inset-bottom', `${bar.offsetHeight}px`)
    publish()
    const release = keepToastsClearOf(bar)
    const observer = new ResizeObserver(publish)
    observer.observe(bar)
    return () => {
      observer.disconnect()
      release()
      root.style.removeProperty('--toast-inset-bottom')
    }
  }, [showBar])

  // After a failed answer focus stays on the pressed control, which the save bar's
  // alert describes. An unusable date or title moves it to the message at those
  // fields; a pressed control that went with its alert (another kind of failure
  // replaced it) hands focus to the new alert, never to <body>. The answer may
  // grow the bar: in a short window held at its top the sticky bar cannot rise
  // above the editor, and its last row falls below the window. Whatever holds
  // focus then is scrolled into view, and the rest of the bar comes with it.
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
      const box = focused.getBoundingClientRect()
      if (box.top < 0 || box.bottom > document.documentElement.clientHeight) {
        focused.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [answers])

  // Every announcement changes the region, a repeated one too: cleared, then set a frame later.
  const announce = useCallback((message: string) => {
    setAnnouncement('')
    window.requestAnimationFrame(() => setAnnouncement(message))
  }, [])

  // Try again's answer. A failure keeps focus on Try again and is said again (the
  // alert's text did not change, so its role does not repeat it); a read moves
  // focus to the fields' heading, a changed event to Read again, and the failure
  // said before leaves the live region. A layout effect: a read unmounts the
  // focused button, and no frame may paint with focus on <body>.
  useLayoutEffect(() => {
    if (!retried.current || state.status === 'loading') {
      return
    }
    if (state.status === 'failed') {
      if (state.retrying === true) {
        return
      }
      // The cause and its kind, as the alert's title says them.
      announce(
        state.failure === undefined ? state.cause : `${state.cause} ${FAILURE_LABEL[state.failure]}`,
      )
    } else {
      setAnnouncement('')
      if (state.status === 'ready') {
        detailsHeadingRef.current?.focus()
      } else {
        readAgainRef.current?.focus()
      }
    }
    retried.current = false
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

  // Each chapter's removed clips, in its original order; one shared empty list for the rest.
  const removals = ready?.removed
  const removedByChapter = useMemo(
    () =>
      new Map(
        chapters.map((chapter) => {
          const listed = chapter.movable.filter((identity) => removals?.has(identity) === true)
          return [chapter.name, listed.length === 0 ? NONE_REMOVED : listed]
        }),
      ),
    [chapters, removals],
  )

  function submit(pressed: Pressed, operation: Operation): void {
    // Never a half-typed date (it would be sent as unset) and never a save of nothing.
    if (ready === null || saving.current || ready.dateIncomplete || !edited) {
      return
    }
    saving.current = true
    dispatch({ type: 'save-start', pressed })
    const body = buildWriteBody(
      ready.read,
      ready.original,
      ready.orders,
      ready.metadata,
      new Set(ready.removed.keys()),
    )
    const name = eventName(
      eventId,
      savedValue('title', ready.read, body, resolved),
      savedValue('date', ready.read, body, resolved),
    )
    send(eventId, body, ready.etag, operation)
      .catch((error: unknown) => {
        // An error in this page: send() returns a missing or unexpected answer as a value.
        console.error('Edit mode: the save stopped on an error', error)
        return {
          saved: false as const,
          problem: {
            kind: 'disk' as const,
            title: 'The save stopped on an error in this page.',
            failure: null,
            detail: String(error),
            retry: operation,
          },
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

  const retrying = state.status === 'failed' && state.retrying === true
  const hasNamedChapter = chapters.some((chapter) => chapter.name !== '')
  const hasIgnored = chapters.some((chapter) => chapter.ignored.length > 0)
  const hasMissing = [...clips.values()].some((clip) => clip.status === 'missing')
  const clipCount = chapters.reduce((sum, chapter) => sum + chapter.movable.length, 0)

  return (
    <div className="event-editor">
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
                  if (!retried.current) {
                    retried.current = true
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
                read={ready.read}
                draft={ready.metadata}
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
            <div className="edit-hint">
              <Icon name="info" />
              <p>
                Drag a clip by its handle, or use its arrows. Clips stay in their chapter.
                {hasIgnored && ' Ignored clips are not played and cannot be moved.'}
                {hasMissing &&
                  ' A missing clip is not on disk: restore the file, or remove it from reel.yaml.'}
                {adopted > 0 ? (
                  <strong>
                    {' '}
                    Saving this order adds {plural(adopted, 'new clip', 'new clips')} to reel.yaml.
                  </strong>
                ) : (
                  newClips.size > 0 &&
                  ' A new clip joins reel.yaml once its chapter’s order is saved.'
                )}
              </p>
            </div>
          )}

          {detail !== null && clipCount === 0 && !hasIgnored && (
            <p className="empty-state">
              <Icon name="film" size={20} />
              No clips.
            </p>
          )}

          {detail !== null &&
            chapters.map((chapter, index) => (
              <ClipOrderList
                key={chapter.name}
                eventId={eventId}
                index={index}
                chapter={chapter.name}
                heading={chapterHeading(chapter.name, hasNamedChapter)}
                order={ready.orders.get(chapter.name) ?? chapter.movable}
                original={chapter.movable}
                ignored={chapter.ignored}
                removed={removedByChapter.get(chapter.name) ?? NONE_REMOVED}
                clips={clips}
                lastMoved={ready.lastMoved}
                locked={locked}
                onMove={onMove}
                onRemove={onRemove}
                onRestore={onRestore}
                onAnnounce={announce}
              />
            ))}

          {showBar && (
            <SaveBar
              barRef={barRef}
              alertRef={alertRef}
              edited={edited}
              problem={ready.problem}
              pressed={ready.pressed}
              summary={summarize(
                changed,
                ready.dateIncomplete,
                movedCount,
                ready.removed.size,
                adopted,
              )}
              dateIncomplete={ready.dateIncomplete}
              onReset={() => {
                dispatch({ type: 'reset' })
                // The bar leaves with its buttons: focus goes to the page's heading, in place.
                focusPageHeading({ preventScroll: true })
              }}
              onSave={() => submit('save', 'save')}
              onRetry={(operation) => submit('retry', operation)}
              onReload={onReload}
              onOverwrite={() => setOverwriteAsked(true)}
            />
          )}
        </>
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
