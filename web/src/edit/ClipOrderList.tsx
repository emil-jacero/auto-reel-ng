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
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from 'react'

import type { Clip } from '../api/event'
import { formatBytes, plural } from '../events/common'
import { CLIP_STATUS_LABEL } from '../events/labels'
import { CLIP_STATUS_LOOK } from '../events/tones'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { movedSet } from './draft'

/*
 * One chapter's clips, reorderable within the chapter only. Three ways to move
 * a clip: drag its handle (pointer, pen or touch), lift it from the keyboard on
 * its handle, or press its Move up / Move down buttons.
 *
 * Each chapter has its own DndContext, so a clip cannot be dropped into another
 * chapter by construction, and the modifier below keeps a dragged row inside
 * its own list. The ignored clips follow in a separate list: they are not
 * played, so they are neither numbered nor movable.
 */

/** The identity's last segment: the file name inside its chapter folder. */
function fileName(identity: string): string {
  return identity.split('/').pop() ?? identity
}

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

/** Size and time as the read view shows them; absent (a missing clip) shows as absent. */
function ClipFacts({ clip }: { clip: Clip }) {
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
          <time dateTime={clip.mtime}>{new Date(clip.mtime).toLocaleString()}</time>
        )}
      </span>
    </span>
  )
}

/** A row's facts; memoised, so a move re-renders only the rows it renumbers. */
const RowBody = memo(function RowBody({
  clip,
  position,
  was,
}: {
  clip: Clip
  position: number | null
  was: number | null
}) {
  const name = fileName(clip.identity)
  return (
    <>
      <span className="clip-pos">{position}</span>
      <span className="clip-file">
        <span className="clip-name">{name}</span>
        {/* Hidden while a drag would put the clip back where it was. */}
        {was !== null && position !== null && position !== was && (
          <span className="badge clip-was" data-tone="info">
            <Icon name={position < was ? 'arrow-up' : 'arrow-down'} />
            was {was}
          </span>
        )}
      </span>
      <ClipFacts clip={clip} />
    </>
  )
})

type Step = (identity: string, from: number, to: number) => void

// Constant elements: React skips them on the re-render every row gets per drag step.
const GRIP = <Icon name="grip-vertical" />
const UP = <Icon name="arrow-up" />
const DOWN = <Icon name="arrow-down" />

/** Move up and Move down; memoised, so a drag step re-renders neither. */
const MoveButtons = memo(function MoveButtons({
  identity,
  index,
  total,
  locked,
  onStep,
}: {
  identity: string
  index: number
  total: number
  locked: boolean
  onStep: Step
}) {
  const name = fileName(identity)
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
  clip,
  position,
  total,
  was,
  locked,
  reducedMotion,
  onStep,
}: {
  clip: Clip
  /** 1-based, among the clips the chapter plays. */
  position: number
  total: number
  was: number | null
  locked: boolean
  reducedMotion: boolean
  onStep: Step
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
  return (
    <li
      ref={setNodeRef}
      className="clip-item"
      data-identity={clip.identity}
      data-status={clip.status}
      data-moved={was !== null || undefined}
      data-dragging={isDragging || undefined}
      style={{ transform: DndCss.Translate.toString(transform), transition }}
    >
      <button
        type="button"
        ref={setActivatorNodeRef}
        className="btn btn-ghost btn-icon drag-handle"
        aria-label={`Reorder ${fileName(clip.identity)}`}
        {...attributes}
        {...listeners}
      >
        {GRIP}
      </button>
      {/* While a clip is lifted, every row shows the place a drop would give it. */}
      <RowBody clip={clip} position={isSorting ? newIndex + 1 : position} was={was} />
      <MoveButtons
        identity={clip.identity}
        index={position - 1}
        total={total}
        locked={locked}
        onStep={onStep}
      />
    </li>
  )
})

/** An ignored clip: listed, dimmed, not numbered, no controls. */
const IgnoredRow = memo(function IgnoredRow({ clip }: { clip: Clip }) {
  return (
    <li className="clip-item" data-status={clip.status}>
      <span className="drag-slot" />
      <RowBody clip={clip} position={null} was={null} />
      <span className="clip-moves" />
    </li>
  )
})

export type MoveHandler = (chapter: string, from: number, to: number) => void

export const ClipOrderList = memo(function ClipOrderList({
  index,
  chapter,
  heading,
  order,
  original,
  ignored,
  clips,
  lastMoved,
  locked,
  onMove,
  onAnnounce,
}: {
  /** The chapter's place on the page: the DndContext id, for stable description ids. */
  index: number
  chapter: string
  heading: string
  /** The identities it plays, in the current order. */
  order: readonly string[]
  /** The same, as the page showed them when Edit mode opened. */
  original: readonly string[]
  ignored: readonly string[]
  clips: ReadonlyMap<string, Clip>
  lastMoved: string | null
  locked: boolean
  onMove: MoveHandler
  /** Speak a button move through the editor's live region (dnd-kit speaks the drags). */
  onAnnounce: (message: string) => void
}) {
  const headingId = useId()
  const ignoredId = useId()
  const listRef = useRef<HTMLOListElement>(null)
  // The button a move by button leaves focus on, once the row is in its new place.
  const focusAfterMove = useRef<{ identity: string; up: boolean } | null>(null)
  const reducedMotion = useReducedMotion()
  const items = useMemo(() => [...order], [order])
  const moved = useMemo(() => movedSet(original, order, lastMoved), [original, order, lastMoved])
  const originalPosition = useMemo(
    () => new Map(original.map((identity, at) => [identity, at + 1])),
    [original],
  )

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const announcements = useMemo<Announcements>(() => {
    const total = order.length
    const name = (id: UniqueIdentifier) => fileName(String(id))
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
  }, [order])

  const onDragEnd = useCallback(
    ({ active, over }: DragEndEvent) => {
      if (over === null || over.id === active.id) {
        return
      }
      const from = order.indexOf(String(active.id))
      const to = order.indexOf(String(over.id))
      if (from !== -1 && to !== -1) {
        onMove(chapter, from, to)
      }
    },
    [chapter, onMove, order],
  )

  const onStep = useCallback<Step>(
    (identity, from, to) => {
      focusAfterMove.current = { identity, up: to < from }
      onMove(chapter, from, to)
      onAnnounce(`${fileName(identity)} moved to position ${to + 1} of ${order.length}.`)
    },
    [chapter, onAnnounce, onMove, order.length],
  )

  // After a move by button the row's DOM node may have been moved, which drops
  // its focus: put it back on the same button. At an end that button is
  // aria-disabled, not disabled, so it still takes focus.
  useLayoutEffect(() => {
    const request = focusAfterMove.current
    const list = listRef.current
    if (request === null || list === null) {
      return
    }
    focusAfterMove.current = null
    const row = [...list.children].find(
      (child) => child instanceof HTMLElement && child.dataset.identity === request.identity,
    )
    row?.querySelector<HTMLButtonElement>(request.up ? '.move-up' : '.move-down')?.focus()
  }, [order])

  return (
    <section className="panel edit-chapter" aria-labelledby={headingId}>
      <header className="panel-header">
        <h2 id={headingId}>{heading}</h2>
        {moved.size > 0 && (
          <span className="badge" data-tone="info">
            {plural(moved.size, 'clip', 'clips')} moved
          </span>
        )}
        <span className="panel-meta">
          {plural(order.length, 'clip', 'clips')}
          {ignored.length > 0 && ` · ${ignored.length} ignored`}
        </span>
      </header>
      <div className="clip-order-head" aria-hidden="true">
        <span />
        <span>#</span>
        <span>File</span>
        <span>Status</span>
        <span>Size</span>
        <span>Modified</span>
        <span />
      </div>
      {order.length > 0 && (
        <DndContext
          id={`chapter-${index}`}
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
            <ol ref={listRef} className="clip-order" aria-labelledby={headingId}>
              {order.map((identity, at) => {
                const clip = clips.get(identity)
                if (clip === undefined) {
                  return null
                }
                return (
                  <ClipRow
                    key={identity}
                    clip={clip}
                    position={at + 1}
                    total={order.length}
                    was={moved.has(identity) ? (originalPosition.get(identity) ?? null) : null}
                    locked={locked}
                    reducedMotion={reducedMotion}
                    onStep={onStep}
                  />
                )
              })}
            </ol>
          </SortableContext>
        </DndContext>
      )}
      {ignored.length > 0 && (
        <>
          <p className="ignored-caption" id={ignoredId}>
            Ignored, not played
          </p>
          <ul className="clip-order clip-ignored" aria-labelledby={ignoredId}>
            {ignored.map((identity) => {
              const clip = clips.get(identity)
              return clip === undefined ? null : <IgnoredRow key={identity} clip={clip} />
            })}
          </ul>
        </>
      )}
    </section>
  )
})
