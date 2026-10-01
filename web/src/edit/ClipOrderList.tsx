import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type {
  Announcements,
  DragEndEvent,
  Modifier,
  ScreenReaderInstructions,
  UniqueIdentifier,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS as DndCss } from '@dnd-kit/utilities'
import {
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from 'react'
import type { ReactNode } from 'react'

import type { Clip } from '../api/event'
import { ClipThumb } from '../events/ClipThumb'
import { ClipName, clipNames, formatBytes, plural } from '../events/common'
import { CLIP_STATUS_LABEL } from '../events/labels'
import { CLIP_STATUS_LOOK } from '../events/tones'
import { formatInstant } from '../format'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { ChapterTools } from './ChapterTools'
import type { ChapterToolsModel } from './ChapterTools'
import { keptOriginal, movedSet } from './draft'
import type { ChapterKey } from './draft'

/*
 * One chapter's clips, reorderable within the chapter only. Three ways to move
 * a clip: drag its handle (pointer, pen or touch), lift it from the keyboard on
 * its handle, or press its Move up / Move down buttons. A clip changes chapter
 * only through the chapter's Move clips dialog (`ChapterDialogs.tsx`); its row
 * then says where it came from. The chapter's tools row (`ChapterTools.tsx`)
 * sits between its header and its column strip.
 *
 * Each chapter has its own DndContext, so a clip cannot be dropped into another
 * chapter by construction, and the modifier below keeps a dragged row inside
 * its own list. Two lists follow, neither numbered nor movable, since neither
 * is played: the missing clips the operator removed (Save leaves them out of
 * reel.yaml, and each has an Undo until then), then the ignored clips.
 */

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

function subscribeMotion(listener: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION)
  query.addEventListener('change', listener)
  return () => query.removeEventListener('change', listener)
}

/** Whether the system asks for reduced motion, kept current. */
function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeMotion, () => window.matchMedia(REDUCED_MOTION).matches)
}

/**
 * Up and down only, and never past the chapter's own list: a dragged row stops
 * at its chapter's edge. Without the clamp, the collision detection would pick
 * the chapter's nearest clip while the pointer is over another chapter, and a
 * release there would move the clip to the end of its own. The container is
 * the row's parent element, the chapter's <ol>.
 */
const withinChapter: Modifier = ({ transform, draggingNodeRect, containerNodeRect }) => {
  if (draggingNodeRect === null || containerNodeRect === null) {
    return { ...transform, x: 0 }
  }
  const top = containerNodeRect.top - draggingNodeRect.top
  const bottom = containerNodeRect.bottom - draggingNodeRect.bottom
  return { ...transform, x: 0, y: Math.min(Math.max(transform.y, top), bottom) }
}

const MODIFIERS = [withinChapter]

const INSTRUCTIONS: ScreenReaderInstructions = {
  draggable:
    'Press Space or Enter to pick up a clip, the Up and Down arrows to move it, ' +
    'Space or Enter to drop it, Escape to cancel.',
}

/**
 * Size and time as the read view shows them; absent (a missing clip) shows as
 * absent. Then the row's action, beside the status that explains it.
 */
function ClipFacts({ clip, action }: { clip: Clip; action?: ReactNode }) {
  const look = CLIP_STATUS_LOOK[clip.status]
  return (
    <span className="clip-facts">
      <span className="clip-status">
        <Pill tone={look.tone} icon={look.icon}>
          {CLIP_STATUS_LABEL[clip.status]}
        </Pill>
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

/** A row's facts; memoised, so a move re-renders only the rows it renumbers. */
const RowBody = memo(function RowBody({
  eventId,
  clip,
  name,
  position,
  was,
  from = null,
  action,
}: {
  eventId: string
  clip: Clip
  /** The clip's name as its chapter names it (`clipNames`), as the read view's table does. */
  name: string
  position: number | null
  was: number | null
  /** The heading of the chapter it was moved in from, shown instead of `was`. */
  from?: string | null
  /** A control after the facts: a missing clip's Remove, a removed one's Undo. */
  action?: ReactNode
}) {
  return (
    <>
      <span className="clip-pos">{position}</span>
      <ClipThumb eventId={eventId} clip={clip} name={name} />
      <span className="clip-file">
        <span className="clip-name">
          <ClipName name={name} />
        </span>
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

// Constant elements: React skips them on the re-render every row gets per drag step.
const GRIP = <Icon name="grip-vertical" />
const UP = <Icon name="arrow-up" />
const DOWN = <Icon name="arrow-down" />
const REMOVE = <Icon name="x" />
const UNDO = <Icon name="rotate-ccw" />

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
  onStep: Step
  onRemove: (identity: string) => void
}) {
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
  return (
    <li
      ref={setNodeRef}
      className="clip-item"
      data-identity={clip.identity}
      data-status={clip.status}
      data-moved={was !== null || from !== null || undefined}
      data-dragging={isDragging || undefined}
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
        position={isSorting ? newIndex + 1 : position}
        was={was}
        from={from}
        action={remove}
      />
      <MoveButtons
        identity={clip.identity}
        name={name}
        index={position - 1}
        total={total}
        locked={locked}
        onStep={onStep}
      />
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
  onMove,
  onRemove,
  onRestore,
  onAnnounce,
}: {
  /** The event, for its clips' thumbnail addresses. */
  eventId: string
  /** The chapter's key for the session: the DndContext id, for stable description ids. */
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
  // The clip a drop just moved: its row is scrolled into view as a button move's is.
  const dropped = useRef<string | null>(null)
  const reducedMotion = useReducedMotion()
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
  // Nothing to list: an added chapter, or one every clip has left.
  const empty = order.length === 0 && removed.length === 0 && ignored.length === 0
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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
      // It scrolls a lifted clip into view: at once under reduced motion.
      scrollBehavior: reducedMotion ? 'auto' : 'smooth',
    }),
  )

  const announcements = useMemo<Announcements>(() => {
    const total = order.length
    const name = (id: UniqueIdentifier) => nameOf(String(id))
    const at = (id: UniqueIdentifier) => order.indexOf(String(id)) + 1
    return {
      onDragStart: ({ active }) =>
        `Picked up ${name(active.id)}, position ${at(active.id)} of ${total}.`,
      onDragOver: ({ active, over }) =>
        over === null
          ? undefined
          : `${name(active.id)} is over position ${at(over.id)} of ${total}.`,
      onDragEnd: ({ active, over }) =>
        over === null || over.id === active.id
          ? `${name(active.id)} dropped at position ${at(active.id)} of ${total}, unchanged.`
          : `${name(active.id)} moved to position ${at(over.id)} of ${total}.`,
      onDragCancel: ({ active }) =>
        `Move cancelled. ${name(active.id)} is back at position ${at(active.id)} of ${total}.`,
    }
  }, [nameOf, order])

  const onDragEnd = useCallback(
    ({ active, over }: DragEndEvent) => {
      if (over === null || over.id === active.id) {
        return
      }
      const from = order.indexOf(String(active.id))
      const to = order.indexOf(String(over.id))
      if (from !== -1 && to !== -1) {
        dropped.current = String(active.id)
        onMove(chapterKey, from, to)
      }
    },
    [chapterKey, onMove, order],
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
  // After a drop dnd-kit puts focus back on the handle itself, a frame later; only
  // the row's scroll is needed, as for a button move (the first drop brings the
  // save bar in, and focus alone does not scroll a handle already in the window).
  useLayoutEffect(() => {
    const section = sectionRef.current
    const rowOf = (identity: string) =>
      section === null
        ? undefined
        : [...section.querySelectorAll<HTMLElement>('.clip-item')].find(
            (item) => item.dataset.identity === identity,
          )
    const drop = dropped.current
    dropped.current = null
    if (drop !== null) {
      scrollAfter.current = rowOf(drop) ?? null
    }
    const request = focusAfter.current
    if (request === null || section === null) {
      return
    }
    focusAfter.current = null
    const row = rowOf(request.identity)
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
      {empty && (
        <p className="chapter-empty">
          No clips. Move clips here with another chapter’s Move clips. A chapter without clips is
          left out of the movie.
        </p>
      )}
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
      {order.length > 0 && (
        <DndContext
          id={`chapter-${chapterKey}`}
          sensors={sensors}
          collisionDetection={closestCenter}
          modifiers={MODIFIERS}
          // Its instructions and live region go to <body>, outside the chapter's markup.
          accessibility={{
            announcements,
            screenReaderInstructions: INSTRUCTIONS,
            container: document.body,
          }}
          onDragEnd={onDragEnd}
        >
          <SortableContext items={items} strategy={verticalListSortingStrategy}>
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
                    onStep={onStep}
                    onRemove={onRemoveRow}
                  />
                )
              })}
            </ol>
          </SortableContext>
        </DndContext>
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
