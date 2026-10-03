import { useDroppable } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { SortingStrategy } from '@dnd-kit/sortable'
import { CSS as DndCss } from '@dnd-kit/utilities'
import {
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode, RefObject } from 'react'

import type { Clip } from '../api/event'
import { CutsPanel, CutsToggle } from '../cuts/CutsPanel'
import type { CutHandlers, CutPanels } from '../cuts/CutsPanel'
import { keptCuts } from '../cuts/times'
import { ClipThumb } from '../events/ClipThumb'
import { ClipName, ClipStatusPills, clipNames, formatBytes, plural } from '../events/common'
import { formatInstant } from '../format'
import { watchName } from '../preview/playback'
import { Icon } from '../ui/Icon'
import { useGroupHeld, useReducedMotion } from './ChapterDrag'
import { ChapterTools } from './ChapterTools'
import type { ChapterToolsModel } from './ChapterTools'
import { cutsOf, keptOriginal, movedSet } from './draft'
import type { ChapterKey, Cuts, DraftCut } from './draft'
import { CHAPTER_DROP } from './dragSlots'
import { emptyChapterWords } from './emptyChapter'
import { groupWords } from './marks'

/*
 * One chapter's clips. Three ways to move a clip within the chapter: drag its
 * handle (pointer, pen or touch), lift it from the keyboard on its handle, or
 * press its Move up / Move down buttons. A drag can also take it into another
 * chapter (`ChapterDrag.tsx`, the one drag-and-drop context, around every
 * chapter); so can the chapter's Move clips dialog (`ChapterDialogs.tsx`). Its
 * row then says where it came from. Move up and Move down never leave the
 * chapter. The chapter's tools row (`ChapterTools.tsx`) sits between its header
 * and its column strip.
 *
 * A clip on disk that the chapter plays also has a Cuts control after its move
 * buttons, which shows its cuts panel under the row (`cuts/CutsPanel.tsx`), and a mark in
 * the top-right corner of its thumbnail: dragging any marked clip's handle moves every
 * marked clip together (`ChapterDrag.tsx`). While such a group is held no row makes room:
 * every row draws the line of the gap before it, and the held rows are dimmed.
 *
 * The chapter is a drop target as a whole (`ChapterDrop`): after its last clip,
 * or anywhere in it while it plays none. Two lists follow the played clips,
 * neither numbered nor movable, since neither is played: the missing clips the
 * operator removed (Save leaves them out of reel.yaml, and each has an Undo
 * until then), then the ignored clips.
 */

/**
 * Size and time as the read view shows them; absent (a missing clip) shows as
 * absent. Then the row's action, beside the status that explains it.
 */
function ClipFacts({ clip, action }: { clip: Clip; action?: ReactNode }) {
  return (
    <span className="clip-facts">
      <span className="clip-status">
        <ClipStatusPills clip={clip} />
      </span>
      <span className="clip-size">{clip.size == null ? '—' : formatBytes(clip.size)}</span>
      <span className="clip-mtime">
        {clip.mtime == null ? (
          '—'
        ) : (
          <time dateTime={clip.mtime}>{formatInstant(clip.mtime)}</time>
        )}
      </span>
      {action !== undefined && <span className="clip-action">{action}</span>}
    </span>
  )
}

const FROM = <Icon name="arrow-right" />
const CHECK = <Icon name="check" size={16} />

export type MarkHandler = (identity: string, on: boolean) => void

/**
 * The mark: a checkbox in the top-right corner of the thumbnail, a sibling of the Watch button
 * (a button cannot hold a control). The layer covers the thumbnail's box exactly, so the
 * corner is the thumbnail's whatever the row's layout; only the box takes presses. The native
 * input lies over the 24 px box, invisible: Space, `checked` and the focus ring are native, and
 * the check icon, not the colour, tells the state. aria-disabled while locked, never disabled.
 */
const MarkBox = memo(function MarkBox({
  identity,
  name,
  on,
  locked,
  onMark,
}: {
  identity: string
  name: string
  on: boolean
  locked: boolean
  onMark: MarkHandler
}) {
  return (
    <span className="clip-mark">
      <span className="clip-mark-ctl" data-on={on || undefined}>
        <input
          type="checkbox"
          className="clip-mark-input"
          aria-label={`Mark ${name}`}
          aria-disabled={locked || undefined}
          checked={on}
          onChange={(event) => {
            if (!locked) {
              onMark(identity, event.currentTarget.checked)
            }
          }}
        />
        <span className="clip-mark-box" aria-hidden="true">
          {on && CHECK}
        </span>
      </span>
    </span>
  )
})

/** A row's facts; memoised, so a move re-renders only the rows it renumbers. */
const RowBody = memo(function RowBody({
  eventId,
  clip,
  name,
  position,
  was,
  from = null,
  badge = null,
  action,
  onWatch,
  marked = null,
  locked = false,
  onMark,
}: {
  eventId: string
  clip: Clip
  /** The clip's name as its chapter names it (`clipNames`), as the read view's table does. */
  name: string
  position: number | null
  was: number | null
  /** The heading of the chapter it was moved in from, shown instead of `was`. */
  from?: string | null
  /** A badge after the name: a missing clip's cut count. */
  badge?: ReactNode
  /** A control after the facts: a missing clip's Remove, a removed one's Undo. */
  action?: ReactNode
  /** A clip with a Cuts panel: its thumbnail is a Watch button that opens its preview. */
  onWatch?: () => void
  /** Whether the clip is marked; null: it cannot be marked (no mark is shown). */
  marked?: boolean | null
  /** A save or a Move clips is pending: the mark ignores presses. */
  locked?: boolean
  onMark?: MarkHandler
}) {
  const thumb = <ClipThumb eventId={eventId} clip={clip} name={name} />
  return (
    <>
      <span className="clip-pos">{position}</span>
      {/* Not the drag handle: a press here never lifts the row. */}
      {onWatch === undefined ? (
        thumb
      ) : (
        <button
          type="button"
          className="clip-thumb-watch"
          aria-label={watchName(name)}
          onClick={onWatch}
        >
          {thumb}
        </button>
      )}
      {/* After the Watch button, so its corner paints over it. */}
      {marked !== null && onMark !== undefined && (
        <MarkBox identity={clip.identity} name={name} on={marked} locked={locked} onMark={onMark} />
      )}
      <span className="clip-file">
        <span className="clip-name">
          <ClipName name={name} />
        </span>
        {badge}
        {/* Moved in from another chapter: where from, cut short when long (chapters.css). */}
        {from !== null && position !== null && (
          <span className="badge clip-was clip-from" data-tone="info">
            {FROM}
            <span>from {from}</span>
          </span>
        )}
        {/* A moved clip at its old position (others moved around it) says only "moved". */}
        {was !== null && position !== null && (
          <span className="badge clip-was" data-tone="info">
            {position === was ? (
              'moved'
            ) : (
              <>
                <Icon name={position < was ? 'arrow-up' : 'arrow-down'} />
                was {was}
              </>
            )}
          </span>
        )}
      </span>
      <ClipFacts clip={clip} action={action} />
    </>
  )
})

type Step = (identity: string, from: number, to: number) => void

/** Sortable's strategy while a group is held: no row shifts. */
const NO_SHIFT: SortingStrategy = () => null

// Constant elements: React skips them on the re-render every row gets per drag step.
const GRIP = <Icon name="grip-vertical" />
const UP = <Icon name="arrow-up" />
const DOWN = <Icon name="arrow-down" />
const REMOVE = <Icon name="x" />
const UNDO = <Icon name="rotate-ccw" />
const SCISSORS = <Icon name="scissors" />

/** Move up and Move down; memoised, so a drag step re-renders neither. */
const MoveButtons = memo(function MoveButtons({
  identity,
  name,
  index,
  total,
  locked,
  onStep,
}: {
  identity: string
  name: string
  index: number
  total: number
  locked: boolean
  onStep: Step
}) {
  return (
    <span className="clip-moves">
      <button
        type="button"
        className="btn btn-ghost btn-icon move-up"
        aria-label={`Move ${name} up`}
        aria-disabled={locked || index === 0 || undefined}
        onClick={() => {
          if (!locked && index > 0) {
            onStep(identity, index, index - 1)
          }
        }}
      >
        {UP}
      </button>
      <button
        type="button"
        className="btn btn-ghost btn-icon move-down"
        aria-label={`Move ${name} down`}
        aria-disabled={locked || index === total - 1 || undefined}
        onClick={() => {
          if (!locked && index < total - 1) {
            onStep(identity, index, index + 1)
          }
        }}
      >
        {DOWN}
      </button>
    </span>
  )
})

const ClipRow = memo(function ClipRow({
  eventId,
  clip,
  name,
  position,
  total,
  was,
  from,
  locked,
  reducedMotion,
  cuts,
  typed,
  panels,
  resets,
  cutHandlers,
  marked,
  onMark,
  onStep,
  onRemove,
}: {
  eventId: string
  clip: Clip
  name: string
  /** 1-based, among the clips the chapter plays. */
  position: number
  total: number
  was: number | null
  from: string | null
  locked: boolean
  reducedMotion: boolean
  /** Its cuts as listed now (`cutsOf`): a stable array per clip. */
  cuts: readonly DraftCut[]
  /** Its cut panel holds a time typed but not added (the editor's `typed`). */
  typed: boolean
  panels: CutPanels
  /** Bumped by Reset: the panel is hidden and its fields emptied. */
  resets: number
  cutHandlers: CutHandlers
  /** The clip is marked (to move with the other marked clips). */
  marked: boolean
  onMark: MarkHandler
  onStep: Step
  onRemove: (identity: string) => void
}) {
  // The marked clips a held group stands for, or null: then no row makes room (a line shows
  // at every gap) and the held rows are dimmed.
  const group = useGroupHeld()
  const grouped = group !== null
  const held = group?.has(clip.identity) === true
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
    isSorting,
    newIndex,
    isOver,
    active,
    data,
  } = useSortable({
    id: clip.identity,
    disabled: locked,
    // No motion under reduced motion; dnd-kit's own transition otherwise.
    transition: reducedMotion ? null : undefined,
  })
  // Only a missing clip offers Remove; memoised, so a drag step leaves RowBody alone.
  const { identity, status } = clip
  const remove = useMemo(
    () =>
      status !== 'missing' ? undefined : (
        <button
          type="button"
          className="btn btn-ghost btn-compact clip-remove"
          aria-label={`Remove ${name} from reel.yaml`}
          aria-disabled={locked || undefined}
          onClick={() => {
            if (!locked) {
              onRemove(identity)
            }
          }}
        >
          {REMOVE}
          Remove
        </button>
      ),
    [identity, name, status, locked, onRemove],
  )
  // A clip on disk has a Cuts control; a missing one only says how many cuts it has. An
  // excluded clip is not in the movie, so its cuts do not apply: neither is shown. They
  // stay in the draft, and Save writes them back unchanged.
  const { excluded } = clip
  const cuttable = !excluded && (status === 'active' || status === 'new')
  const kept = keptCuts(cuts).length
  const badge = useMemo(
    () =>
      status !== 'missing' || excluded || kept === 0 ? null : (
        <span className="badge clip-cuts-badge" data-tone="idle">
          {SCISSORS}
          {plural(kept, 'cut', 'cuts')}
        </span>
      ),
    [status, excluded, kept],
  )
  // Shown or not lives in the editor's store too: Move clips, or a drag into another
  // chapter, mounts this row anew in its new chapter, and it opens as it was. Reset
  // empties the store and hides it.
  const [open, setOpen] = useState(() => panels.get(identity)?.open ?? false)
  const [seenResets, setSeenResets] = useState(resets)
  if (seenResets !== resets) {
    setSeenResets(resets)
    setOpen(false)
  }
  const onToggle = useCallback(() => {
    const held = panels.get(identity)
    panels.set(identity, { open: !open, start: held?.start ?? '', end: held?.end ?? '' })
    setOpen(!open)
  }, [identity, open, panels])
  // The thumbnail's Watch: shows the panel as the Cuts control does, then opens the
  // preview there. Stable, so RowBody's memo holds on every drag step.
  const onWatch = useCallback(() => {
    const held = panels.get(identity)
    panels.set(identity, { open: true, start: held?.start ?? '', end: held?.end ?? '' })
    setOpen(true)
    panels.previews.show(identity, 'thumb')
  }, [identity, panels])
  // Mounted on its first showing, and then only hidden: what was typed stays.
  const mounted = cuttable && (open || panels.get(identity) !== undefined)
  const panelId = `cuts-${useId()}`
  // The target of a clip dragged in from another chapter, or of a held group anywhere: a
  // line marks the gap above this row (drag.css). A clip within its own chapter makes the
  // rows make room instead.
  const dropBefore =
    isOver &&
    active !== null &&
    (grouped || active.data.current?.sortable?.containerId !== data.sortable.containerId)
  return (
    <li
      ref={setNodeRef}
      className="clip-item"
      data-identity={clip.identity}
      data-status={clip.status}
      data-excluded={clip.excluded || undefined}
      data-moved={was !== null || from !== null || undefined}
      data-dragging={isDragging || undefined}
      data-held={held || undefined}
      aria-description={held ? groupWords.held : undefined}
      data-drop-before={dropBefore || undefined}
      style={{ transform: DndCss.Translate.toString(transform), transition }}
    >
      <button
        type="button"
        ref={setActivatorNodeRef}
        className="btn btn-ghost btn-icon drag-handle"
        aria-label={`Reorder ${name}`}
        {...attributes}
        {...listeners}
      >
        {GRIP}
      </button>
      {/* While a clip is lifted, every row shows the place a drop would give it. */}
      <RowBody
        eventId={eventId}
        clip={clip}
        name={name}
        position={isSorting && !grouped ? newIndex + 1 : position}
        was={was}
        from={from}
        badge={badge}
        action={remove}
        onWatch={cuttable ? onWatch : undefined}
        marked={cuttable ? marked : null}
        locked={locked}
        onMark={onMark}
      />
      <MoveButtons
        identity={clip.identity}
        name={name}
        index={position - 1}
        total={total}
        locked={locked}
        onStep={onStep}
      />
      {cuttable && (
        <CutsToggle
          cuts={cuts}
          name={name}
          open={open}
          typed={typed}
          controls={mounted ? panelId : null}
          onToggle={onToggle}
        />
      )}
      {mounted && (
        <CutsPanel
          key={resets}
          id={panelId}
          eventId={eventId}
          identity={identity}
          mtime={clip.mtime ?? null}
          proxy={clip.proxy ?? null}
          duration={clip.duration ?? null}
          name={name}
          cuts={cuts}
          open={open}
          locked={locked}
          panels={panels}
          handlers={cutHandlers}
        />
      )}
    </li>
  )
})

/** An ignored clip: listed, dimmed, not numbered, no controls. */
const IgnoredRow = memo(function IgnoredRow({
  eventId,
  clip,
  name,
}: {
  eventId: string
  clip: Clip
  name: string
}) {
  return (
    <li className="clip-item" data-status={clip.status}>
      <span className="drag-slot" />
      <RowBody eventId={eventId} clip={clip} name={name} position={null} was={null} />
      <span className="clip-moves" />
    </li>
  )
})

/**
 * A missing clip the operator removed: listed like an ignored clip (RowBody gets
 * what IgnoredRow passes it), struck through, with its Undo after its facts.
 */
const RemovedRow = memo(function RemovedRow({
  eventId,
  clip,
  name,
  locked,
  onUndo,
}: {
  eventId: string
  clip: Clip
  name: string
  locked: boolean
  onUndo: (identity: string) => void
}) {
  const { identity } = clip
  const undo = useMemo(
    () => (
      <button
        type="button"
        className="btn btn-secondary btn-compact clip-undo"
        aria-label={`Undo removing ${name}`}
        aria-disabled={locked || undefined}
        onClick={() => {
          if (!locked) {
            onUndo(identity)
          }
        }}
      >
        {UNDO}
        Undo
      </button>
    ),
    [identity, name, locked, onUndo],
  )
  return (
    <li className="clip-item" data-status={clip.status} data-identity={identity} data-removed>
      <span className="drag-slot" />
      <RowBody
        eventId={eventId}
        clip={clip}
        name={name}
        position={null}
        was={null}
        action={undo}
      />
      <span className="clip-moves" />
    </li>
  )
})

export type MoveHandler = (chapter: ChapterKey, from: number, to: number) => void
export type RemoveHandler = (chapter: ChapterKey, identity: string) => void
export type RestoreHandler = (identity: string) => void

/** The button focus lands on once a row is in its new place, as a class name. */
type FocusTarget = 'move-up' | 'move-down' | 'clip-remove' | 'clip-undo'

/** Each clip's chapter when Edit mode opened, and that chapter's heading now. */
export type Origins = ReadonlyMap<string, { key: ChapterKey; heading: string }>

/**
 * The chapter as a drop target for a clip dragged in from another chapter
 * (`/chapter/<key>`, dragSlots.ts): its whole section, so a release anywhere in
 * it, past its last row, lands after that row. It shows the line after the last
 * row while it is the target, or, while the chapter plays no clip, the area that
 * takes one, drag or not. Its own component: it re-renders on every new target
 * (dnd-kit's context), and the chapter's 400-row list must not.
 */
const ChapterDrop = memo(function ChapterDrop({
  chapterKey,
  sectionRef,
  plays,
  words,
}: {
  chapterKey: ChapterKey
  sectionRef: RefObject<HTMLElement | null>
  plays: boolean
  /** What the area says while the chapter plays no clip. */
  words: string
}) {
  const { setNodeRef, isOver, active } = useDroppable({ id: `${CHAPTER_DROP}${chapterKey}` })
  // The section is the parent's element: its ref is attached only after this child's
  // layout effects have run, so the droppable takes it in a passive effect.
  useEffect(() => {
    setNodeRef(sectionRef.current)
  }, [setNodeRef, sectionRef])
  const across = isOver && active !== null
  const lineRef = useRef<HTMLSpanElement>(null)
  // At the list's end, measured against the section (`.edit-chapter` is positioned).
  useLayoutEffect(() => {
    const line = lineRef.current
    const list = sectionRef.current?.querySelector<HTMLElement>(':scope > .clip-order')
    if (line !== null && list != null) {
      line.style.top = `${list.offsetTop + list.offsetHeight}px`
    }
  })
  if (!plays) {
    return (
      <p className="chapter-drop" data-over={across || undefined}>
        {words}
      </p>
    )
  }
  // Before the list, so the list stays the section's last child (its last row's corners).
  return across ? <span ref={lineRef} className="chapter-drop-end" aria-hidden="true" /> : null
})

export const ClipOrderList = memo(function ClipOrderList({
  eventId,
  chapterKey,
  name: chapterName,
  heading,
  order,
  original,
  ignored,
  removed,
  clips,
  origins,
  lastMoved,
  locked,
  tools,
  cuts,
  baseCuts,
  typed,
  panels,
  resets,
  cutHandlers,
  marked,
  onMark,
  onMove,
  onRemove,
  onRestore,
  onAnnounce,
}: {
  /** The event, for its clips' thumbnail addresses. */
  eventId: string
  /**
   * The chapter's key for the session: its SortableContext id (the container a dragged clip
   * comes from or goes to), and its `/chapter/<key>` droppable.
   */
  chapterKey: ChapterKey
  /** Its name now ('' for the event's own chapter), by which it names its clips. */
  name: string
  heading: string
  /** The identities it plays, in the current order. */
  order: readonly string[]
  /** The same, as the page showed them when Edit mode opened. */
  original: readonly string[]
  ignored: readonly string[]
  /** The missing clips the operator removed, in their original order. */
  removed: readonly string[]
  clips: ReadonlyMap<string, Clip>
  origins: Origins
  lastMoved: string | null
  locked: boolean
  /** Its tools row (`ChapterTools`): what it shows and does. */
  tools: ChapterToolsModel
  /**
   * The draft's changed cuts and the read ones, never the draft itself: neither
   * changes on a metadata edit, so typing in a field re-renders no list.
   */
  cuts: Cuts
  baseCuts: Cuts
  /** The clips whose cut panel holds a time typed but not added. */
  typed: ReadonlySet<string>
  /** The editor's cut panel store and handlers (`cuts/CutsPanel.tsx`). */
  panels: CutPanels
  resets: number
  cutHandlers: CutHandlers
  /**
   * The marked clips this chapter plays: one set that keeps its identity while the chapter's
   * own marks are unchanged, so marking elsewhere re-renders no other list.
   */
  marked: ReadonlySet<string>
  onMark: MarkHandler
  onMove: MoveHandler
  onRemove: RemoveHandler
  onRestore: RestoreHandler
  /**
   * Speak button moves, removals and Undos through the editor's live region (dnd-kit speaks
   * the drags).
   */
  onAnnounce: (message: string) => void
}) {
  const headingId = useId()
  const removedId = useId()
  const ignoredId = useId()
  // The whole chapter: a row moves between the <ol> and the removed list, and
  // the <ol> is not rendered at all once every clip of the chapter is removed.
  const sectionRef = useRef<HTMLElement>(null)
  // The button a move, a removal or an Undo leaves focus on, once the row is in its new place.
  const focusAfter = useRef<{ identity: string; target: FocusTarget } | null>(null)
  // That button's row, to scroll into view whole once every layout effect has run.
  const scrollAfter = useRef<HTMLElement | null>(null)
  const reducedMotion = useReducedMotion()
  // A held group moves no row: the rows keep their places and only a line shows.
  const strategy = useGroupHeld() === null ? verticalListSortingStrategy : NO_SHIFT
  const items = useMemo(() => [...order], [order])
  // Against the original order without the clips it no longer holds: a removal, or a
  // clip moved to another chapter, moves nothing by itself (draft.ts `keptOriginal`).
  const kept = useMemo(() => keptOriginal(original, order), [original, order])
  const moved = useMemo(() => movedSet(kept, order, lastMoved), [kept, order, lastMoved])
  // Where a clip moved in from another chapter came from: that chapter's heading now.
  const fromOf = useCallback(
    (identity: string) => {
      const origin = origins.get(identity)
      return origin !== undefined && origin.key !== chapterKey ? origin.heading : null
    },
    [origins, chapterKey],
  )
  // Plays nothing: an added chapter, or one every clip it played has left. With no
  // removed or ignored clip either, nothing is listed at all, so no column strip.
  const plays = order.length > 0
  const empty = !plays && removed.length === 0 && ignored.length === 0
  const originalPosition = useMemo(
    () => new Map(original.map((identity, at) => [identity, at + 1])),
    [original],
  )
  // How the chapter names its clips, as the read view's table will once saved: by its
  // name now, from every clip it lists now or listed when Edit mode opened. A move
  // within it or a removal renames none; a clip from another folder moved in, or a
  // name that is no longer its folder's, names them all by their paths.
  const nameOf = useMemo(
    () => clipNames(chapterName, [...original, ...order, ...ignored, ...removed]),
    [chapterName, original, order, ignored, removed],
  )

  const onStep = useCallback<Step>(
    (identity, from, to) => {
      focusAfter.current = { identity, target: to < from ? 'move-up' : 'move-down' }
      onMove(chapterKey, from, to)
      onAnnounce(`${nameOf(identity)} moved to position ${to + 1} of ${order.length}.`)
    },
    [chapterKey, nameOf, onAnnounce, onMove, order.length],
  )

  // The pressed Remove or Undo leaves with its row: focus follows the clip to the control
  // that reverses it (the layout effect below).
  const onRemoveRow = useCallback(
    (identity: string) => {
      focusAfter.current = { identity, target: 'clip-undo' }
      onRemove(chapterKey, identity)
      onAnnounce(`${nameOf(identity)} will be removed from reel.yaml when you save.`)
    },
    [chapterKey, nameOf, onAnnounce, onRemove],
  )

  const onUndoRow = useCallback(
    (identity: string) => {
      focusAfter.current = { identity, target: 'clip-remove' }
      onRestore(identity)
    },
    [onRestore],
  )

  // After a move by button the row's DOM node may have been moved, which drops
  // its focus: put it back on the same button. At an end that button is
  // aria-disabled, not disabled, so it still takes focus. After a removal or an
  // Undo the row is a new node in the other list: focus its Undo or its Remove.
  // A drop's focus and scroll are ChapterDrag's, for every chapter.
  useLayoutEffect(() => {
    const section = sectionRef.current
    const request = focusAfter.current
    if (request === null || section === null) {
      return
    }
    focusAfter.current = null
    const row = [...section.querySelectorAll<HTMLElement>('.clip-item')].find(
      (item) => item.dataset.identity === request.identity,
    )
    const button = row?.querySelector<HTMLButtonElement>(`.${request.target}`)
    button?.focus({ preventScroll: true })
    scrollAfter.current = row ?? null
    // An Undo says where the clip is back, from the order it now has.
    if (request.target === 'clip-remove') {
      const at = order.indexOf(request.identity) + 1
      onAnnounce(`${nameOf(request.identity)} is back at position ${at} of ${order.length}.`)
    }
  }, [order, removed, nameOf, onAnnounce])

  // Focus alone does not scroll a button that already had it: keep its whole
  // row in view (the frame and every fact, not only the button), clear of the
  // header and the save bar (both in the page's scroll padding). A passive
  // effect, so a save bar the move brought is already measured (the editor
  // publishes its height in its own layout effect, after this list's).
  useEffect(() => {
    const row = scrollAfter.current
    scrollAfter.current = null
    row?.scrollIntoView({ block: 'nearest' })
  }, [order, removed])

  return (
    <section
      ref={sectionRef}
      className="panel edit-chapter"
      data-chapter-key={chapterKey}
      aria-labelledby={headingId}
    >
      <header className="panel-header">
        {/* Focused by script after Add chapter. */}
        <h2 id={headingId} tabIndex={-1}>
          {heading}
        </h2>
        {moved.size > 0 && (
          <span className="badge" data-tone="info">
            {plural(moved.size, 'clip', 'clips')} moved
          </span>
        )}
        {/* The clips it plays; the removed and ignored lists count their own. One line. */}
        <span className="panel-meta">{plural(order.length, 'clip', 'clips')}</span>
      </header>
      <ChapterTools chapterKey={chapterKey} heading={heading} headingId={headingId} {...tools} />
      {/* The column names, in the rows' own cells (edit.css places them by class). */}
      {!empty && (
        <div className="clip-order-head" aria-hidden="true">
          <span className="clip-pos">#</span>
          <span className="clip-file">File</span>
          <span className="clip-facts">
            <span className="clip-status">Status</span>
            <span className="clip-size">Size</span>
            <span className="clip-mtime">Modified</span>
          </span>
        </div>
      )}
      <ChapterDrop
        chapterKey={chapterKey}
        sectionRef={sectionRef}
        plays={plays}
        // Move clips is per chapter and absent on a lone one (ChapterTools): no pointing at it.
        words={emptyChapterWords(tools.moveClips === null, empty)}
      />
      {plays && (
        <SortableContext id={chapterKey} items={items} strategy={strategy}>
          <ol className="clip-order" aria-labelledby={headingId}>
            {order.map((identity, at) => {
              const clip = clips.get(identity)
              if (clip === undefined) {
                return null
              }
              return (
                <ClipRow
                  key={identity}
                  eventId={eventId}
                  clip={clip}
                  name={nameOf(identity)}
                  position={at + 1}
                  total={order.length}
                  was={moved.has(identity) ? (originalPosition.get(identity) ?? null) : null}
                  from={fromOf(identity)}
                  locked={locked}
                  reducedMotion={reducedMotion}
                  cuts={cutsOf(baseCuts, cuts, identity)}
                  typed={typed.has(identity)}
                  panels={panels}
                  resets={resets}
                  cutHandlers={cutHandlers}
                  marked={marked.has(identity)}
                  onMark={onMark}
                  onStep={onStep}
                  onRemove={onRemoveRow}
                />
              )
            })}
          </ol>
        </SortableContext>
      )}
      {removed.length > 0 && (
        <>
          <p className="removed-caption" id={removedId}>
            {plural(removed.length, 'clip', 'clips')} removed from reel.yaml when you save
          </p>
          <ul className="clip-order clip-removed" aria-labelledby={removedId}>
            {removed.map((identity) => {
              const clip = clips.get(identity)
              return clip === undefined ? null : (
                <RemovedRow
                  key={identity}
                  eventId={eventId}
                  clip={clip}
                  name={nameOf(identity)}
                  locked={locked}
                  onUndo={onUndoRow}
                />
              )
            })}
          </ul>
        </>
      )}
      {ignored.length > 0 && (
        <>
          <p className="ignored-caption" id={ignoredId}>
            {plural(ignored.length, 'ignored clip', 'ignored clips')}, not played
          </p>
          <ul className="clip-order clip-ignored" aria-labelledby={ignoredId}>
            {ignored.map((identity) => {
              const clip = clips.get(identity)
              return clip === undefined ? null : (
                <IgnoredRow key={identity} eventId={eventId} clip={clip} name={nameOf(identity)} />
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
})
