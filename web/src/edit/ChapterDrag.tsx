import './drag.css'

import {
  DndContext,
  DragOverlay,
  KeyboardCode,
  KeyboardSensor,
  PointerSensor,
  useDndContext,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type {
  Announcements,
  CollisionDetection,
  DragCancelEvent,
  DragEndEvent,
  DragStartEvent,
  KeyboardCoordinateGetter,
  Modifier,
  ScreenReaderInstructions,
  UniqueIdentifier,
} from '@dnd-kit/core'
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import type { ReactNode, RefObject } from 'react'
import { createPortal } from 'react-dom'

import { ClipName } from '../events/common'
import { Icon } from '../ui/Icon'
import type { MoveHandler } from './ClipOrderList'
import type { ChapterKey, Orders } from './draft'
import {
  CHAPTER_DROP,
  DELETED_DROP,
  clampScroll,
  dragModel,
  overIdOf,
  pointerTarget,
  slotOf,
  stepChapter,
  stepSlot,
} from './dragSlots'
import type { Slot, Span } from './dragSlots'

/*
 * The one drag-and-drop context of Edit mode: every chapter's clips, so a clip
 * can be dragged within its chapter (its other clips make room, as before) or
 * into another (dragSlots.ts says where it can land). It renders no element of
 * its own: the chapter lists come in as `children`, so its own state (the lifted
 * clip) and every drag update leave them alone, and only dnd-kit's consumers
 * re-render (each row's sortable shell, on a new target).
 *
 * Over another chapter nothing moves: the target shows (a line between two of its
 * rows, after its last, or its empty area marked; ClipOrderList.tsx) and a copy
 * of the clip follows the pointer, above every panel (`DragOverlay`, in <body>),
 * naming the chapter and the position. A drop there is one edit (`onDropInto`,
 * the editor's `clip-drop`); a drop within the chapter is a reorder (`onReorder`).
 * A missing clip never leaves its chapter, and a deleted chapter's placeholder
 * takes nothing. Every drag is spoken through dnd-kit's live region.
 */

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

function subscribeMotion(listener: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION)
  query.addEventListener('change', listener)
  return () => query.removeEventListener('change', listener)
}

/** Whether the system asks for reduced motion, kept current. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeMotion, () => window.matchMedia(REDUCED_MOTION).matches)
}

const INSTRUCTIONS =
  'Press Space or Enter to pick up a clip, the Up and Down arrows to move it, ' +
  'Space or Enter to drop it, Escape to cancel.'
const ACROSS =
  ' Past a chapter’s first or last clip, the arrows move it into the chapter before or after.' +
  ' Page Down and Page Up move it to the first position of the next or the previous chapter.'

/*
 * Auto-scroll while a clip is held near the window's top or bottom edge. dnd-kit scrolls
 * by `acceleration` times the pointer's depth into the edge zone (`threshold`, a share of
 * the window's height) per tick. The depth ratio is not capped (1 at the window's edge,
 * more beyond it), and with dnd-kit's default 5 ms timer the tick rate swung with page
 * load: the default acceleration (10) crossed a 400-clip chapter in about 40 s while the
 * rows re-rendered (the timer starved to a tick per frame or fewer), and 25 made the edge
 * cross several screens a second when it was not. A 20 ms `interval` caps the rate at 50
 * ticks a second, so at the edge the speed is at most 34 x 50 = 1,700 px/s, and about
 * 750 px/s measured on a 400-row page, where re-rendering holds it to ~22 ticks a
 * second. The speed still ramps from nothing at the zone's inner edge, so a slight hold
 * scrolls a little. One constant object: a new one per render would restart the interval.
 */
const AUTO_SCROLL = { acceleration: 34, interval: 20, threshold: { x: 0.2, y: 0.2 } } as const

/** The copy stays in its column at every width. */
const vertical: Modifier = ({ transform }) => ({ ...transform, x: 0 })

/** The lifted clip, as its row named it then, and whether a pointer (not the keyboard) holds it. */
type Lift = { identity: string; name: string; pointer: boolean }

/** What a release does: nothing, a reorder within the chapter, or a drop into another. */
type Drop =
  | { kind: 'none' }
  | { kind: 'reorder'; chapter: ChapterKey; from: number; to: number }
  | { kind: 'into'; from: ChapterKey; to: ChapterKey; at: number }

/** The drop the editor follows up once the orders show it: focus and scroll. */
type Dropped = { identity: string; to: ChapterKey; across: boolean }

/** A target in another chapter, as the copy's badge and the announcements say it. */
type Target = { heading: string; position: number; total: number }

const GRIP = <Icon name="grip-vertical" />
const INTO = <Icon name="arrow-right" />

/**
 * Bring a row's first line (its handle, name and Cuts control) the least distance inside
 * the page's scroll-padding box: below the page header and the chapter's sticky heading,
 * above a held save bar. Its top comes first when the line is taller than the box. The
 * row itself may be taller than the window (an open Cuts panel), so not the whole `li`.
 */
function firstLineIntoView(row: HTMLElement): void {
  const parts = [
    row.querySelector(':scope > .drag-handle'),
    row.querySelector('.clip-name'),
    row.querySelector(':scope > .cuts-toggle'),
  ].flatMap((part) => (part === null ? [] : [part.getBoundingClientRect()]))
  if (parts.length === 0) {
    return
  }
  const top = Math.min(...parts.map((box) => box.top))
  const bottom = Math.max(...parts.map((box) => box.bottom))
  const root = document.documentElement
  const style = getComputedStyle(root)
  const from = parseFloat(style.scrollPaddingTop) || 0
  const to = root.clientHeight - (parseFloat(style.scrollPaddingBottom) || 0)
  const by = top < from || bottom - top > to - from ? top - from : bottom > to ? bottom - to : 0
  if (by !== 0) {
    window.scrollBy({ top: by, behavior: 'instant' })
  }
}

/**
 * Bring a row back into view after a cancelled drag: the whole row when it fits between the
 * page's scroll padding, else its first line (`firstLineIntoView`).
 */
function rowIntoView(row: HTMLElement): void {
  const root = document.documentElement
  const style = getComputedStyle(root)
  const room =
    root.clientHeight -
    (parseFloat(style.scrollPaddingTop) || 0) -
    (parseFloat(style.scrollPaddingBottom) || 0)
  if (row.getBoundingClientRect().height <= room) {
    row.scrollIntoView({ block: 'nearest' })
  } else {
    firstLineIntoView(row)
  }
}

/** The copy that follows the pointer: the clip's name and, over another chapter, where it goes. */
function DragPreview({
  name,
  targetOf,
}: {
  name: string
  targetOf: (overId: UniqueIdentifier | null) => Target | null
}) {
  // Re-renders on every drag update (it is small): it reads the current target.
  const { over } = useDndContext()
  const target = targetOf(over?.id ?? null)
  return (
    <div className="clip-drag-preview" aria-hidden="true">
      <span className="clip-drag-grip">{GRIP}</span>
      <span className="clip-drag-name">
        <ClipName name={name} />
      </span>
      {target !== null && (
        <span className="badge clip-drag-target" data-tone="info">
          {INTO}
          <span>
            to “{target.heading}”, position {target.position} of {target.total}
          </span>
        </span>
      )}
    </div>
  )
}

export function ChapterDrag({
  orders,
  listed,
  staysHome,
  nameOf,
  headingOf,
  locked,
  onReorder,
  onDropInto,
  rootRef,
  children,
}: {
  /** The draft's orders, and the listed (not deleted) chapters in the order shown. */
  orders: Orders
  listed: readonly ChapterKey[]
  /** A clip not on disk (missing): it stays in its chapter. */
  staysHome: (identity: string) => boolean
  /** The clip's name as its row names it now (`nameNow`), and a chapter's heading (`headingIn`). */
  nameOf: (identity: string) => string
  headingOf: (key: ChapterKey) => string
  /** `listsLocked`: a save in flight or a Move clips pending. */
  locked: boolean
  onReorder: MoveHandler
  /** A drop into another chapter: false when the editor refused it (save or Move clips pending). */
  onDropInto: (identity: string, from: ChapterKey, to: ChapterKey, at: number) => boolean
  /** The editor's root, where the moved row is found after a drop. */
  rootRef: RefObject<HTMLElement | null>
  children: ReactNode
}): ReactNode {
  // The only state: the lifted clip, for the copy.
  const [lifted, setLifted] = useState<Lift | null>(null)
  const reducedMotion = useReducedMotion()
  const model = useMemo(() => dragModel(orders, listed), [orders, listed])

  // What the dnd-kit callbacks below read: they stay the same functions, so neither the
  // sensors nor the context's accessibility change while a clip is lifted.
  const current = useRef({ model, staysHome, nameOf, headingOf, locked })
  useLayoutEffect(() => {
    current.current = { model, staysHome, nameOf, headingOf, locked }
  })
  // The lifted clip; the slot the keyboard last stepped to (null: none yet, at the lift).
  const lift = useRef<Lift | null>(null)
  const slot = useRef<Slot | null>(null)
  // Set at the lift until the first target: the clip over itself, which says nothing new.
  const lifting = useRef(false)
  // Where the last drop released the clip (the announcement reads it, once `slot` is reset).
  const released = useRef<string | null>(null)
  // The clip whose drop the editor just refused: its drop is announced as unchanged.
  const refused = useRef<string | null>(null)
  // The drop to follow up, then its row, to scroll into view once the save bar is measured.
  const dropped = useRef<Dropped | null>(null)
  const scrollAfter = useRef<{ row: HTMLElement; across: boolean } | null>(null)
  // The clip whose drag was just cancelled: its row comes back into view.
  const cancelled = useRef<string | null>(null)

  /** The clip as lifted: its name then, the same through the drag. */
  const liftOf = useCallback((id: UniqueIdentifier): Lift => {
    const identity = String(id)
    return lift.current?.identity === identity
      ? lift.current
      : { identity, name: current.current.nameOf(identity), pointer: false }
  }, [])

  /** Its own chapter's order and its position there, 1-based. */
  const homeOf = useCallback((identity: string) => {
    const { model: now } = current.current
    const own = now.chapterOf.get(identity) ?? null
    const order = own === null ? [] : (now.orders.get(own) ?? [])
    return { own, order, position: order.indexOf(identity) + 1 }
  }, [])

  /** A target in another chapter, or null (none, a deleted placeholder, the own chapter). */
  const targetOf = useCallback(
    (overId: UniqueIdentifier | null): Target | null => {
      const identity = lift.current?.identity
      if (identity === undefined) {
        return null
      }
      const { model: now, headingOf: heading } = current.current
      const at = slotOf(now, identity, overId === null ? null : String(overId))
      if (at === null || at.chapter === homeOf(identity).own) {
        return null
      }
      return {
        heading: heading(at.chapter),
        position: at.index + 1,
        total: (now.orders.get(at.chapter) ?? []).length + 1,
      }
    },
    [homeOf],
  )

  /**
   * Where releasing `identity` drops it. A keyboard drag has its own slot: dnd-kit's `over`
   * follows it only after a render, which a quick Space (a key repeat, a script) can beat,
   * dropping the clip where it was before the key.
   */
  const releasedOver = useCallback((identity: string, over: UniqueIdentifier | null) => {
    return lift.current?.pointer === false && slot.current !== null
      ? overIdOf(current.current.model, identity, slot.current)
      : over === null
        ? null
        : String(over)
  }, [])

  /** What releasing `identity` over `overId` does; a lock or a stay-home clip refuses it. */
  const dropOf = useCallback(
    (identity: string, overId: UniqueIdentifier | null): Drop => {
      const { model: now, locked: held, staysHome: home } = current.current
      const { own, order } = homeOf(identity)
      const at = slotOf(now, identity, overId === null ? null : String(overId))
      if (held || own === null || at === null) {
        return { kind: 'none' }
      }
      if (at.chapter === own) {
        const from = order.indexOf(identity)
        return from === at.index
          ? { kind: 'none' }
          : { kind: 'reorder', chapter: own, from, to: at.index }
      }
      return home(identity)
        ? { kind: 'none' }
        : { kind: 'into', from: own, to: at.chapter, at: at.index }
    },
    [homeOf],
  )

  // The pointer decides (dragSlots.ts `pointerTarget`); the keyboard's slot is its own.
  const collisionDetection = useCallback<CollisionDetection>(
    ({ active, droppableRects, pointerCoordinates }) => {
      const identity = String(active.id)
      const { model: now, staysHome: home } = current.current
      if (pointerCoordinates === null) {
        // Before the first key the clip is over itself, as `closestCenter` gives.
        return [{ id: slot.current === null ? active.id : overIdOf(now, identity, slot.current) }]
      }
      const deleted: Span[] = []
      for (const [id, rect] of droppableRects) {
        if (String(id).startsWith(DELETED_DROP)) {
          deleted.push(rect)
        }
      }
      const target = pointerTarget(
        now,
        identity,
        home(identity),
        pointerCoordinates.y,
        (key) => droppableRects.get(`${CHAPTER_DROP}${key}`),
        deleted,
        (row) => droppableRects.get(row),
      )
      return target === null ? [] : [{ id: target }]
    },
    [],
  )

  /*
   * Up and Down step through the slots in page order (dragSlots.ts); Page Down and Page
   * Up jump to the first slot of the next or the previous chapter and are always
   * consumed, so the page does not scroll under the clip; every other key does nothing
   * here (Space, Enter and Tab drop, Escape cancels: the sensor's own). The copy goes
   * where the drop will be: in the own chapter on the target row's top, or its bottom
   * when moving down past the clip (sortable's rule); elsewhere centred on the gap's
   * line, or on an empty chapter's area. The sensor scrolls from there for the arrows;
   * it does not for the Page keys, so a target outside the window is scrolled to here
   * (a document-end clamp moves the copy instead of the page).
   */
  const coordinateGetter = useCallback<KeyboardCoordinateGetter>(
    (event, { active, context, currentCoordinates }) => {
      const page = event.code === 'PageDown' ? 1 : event.code === 'PageUp' ? -1 : 0
      const arrow = event.code === KeyboardCode.Down ? 1 : event.code === KeyboardCode.Up ? -1 : 0
      const delta = page || arrow
      if (delta === 0) {
        return undefined
      }
      event.preventDefault()
      const identity = String(active)
      const { model: now, staysHome: home } = current.current
      const { own, order } = homeOf(identity)
      if (own === null) {
        return undefined
      }
      const from = slot.current ?? { chapter: own, index: order.indexOf(identity) }
      const next = (page === 0 ? stepSlot : stepChapter)(
        now,
        identity,
        home(identity),
        from,
        delta,
      )
      if (next === null) {
        return undefined
      }
      const { droppableRects, droppableContainers, collisionRect } = context
      const height = collisionRect?.height ?? 0
      const rows = now.orders.get(next.chapter) ?? []
      let y: number | undefined
      if (next.chapter === own) {
        const row = droppableRects.get(rows[next.index])
        if (row !== undefined) {
          y = next.index > order.indexOf(identity) ? row.bottom - height : row.top
        }
      } else if (rows.length === 0) {
        const id = `${CHAPTER_DROP}${next.chapter}`
        const area = droppableContainers.get(id)?.node.current?.querySelector('.chapter-drop')
        const box = area?.getBoundingClientRect() ?? droppableRects.get(id)
        y = box === undefined ? undefined : (box.top + box.bottom) / 2 - height / 2
      } else {
        const line =
          next.index < rows.length
            ? droppableRects.get(rows[next.index])?.top
            : droppableRects.get(rows[rows.length - 1])?.bottom
        y = line === undefined ? undefined : line - height / 2
      }
      if (y === undefined) {
        return undefined
      }
      slot.current = next
      if (page !== 0 && (y < 0 || y + height > window.innerHeight)) {
        // The sensor scrolls only for the arrows: bring the target to the copy instead. The
        // browser clamps a scroll at either end of the document: the copy then moves the
        // part that was not scrolled, so it still lands on the line. Returning the
        // coordinates (the copy may not move) is what re-runs the collision detection, which
        // reads `slot.current`; otherwise a drop right after the key sees the old target.
        const scroller = document.scrollingElement ?? document.documentElement
        const { applied, left } = clampScroll(
          y - currentCoordinates.y,
          scroller.scrollTop,
          scroller.scrollHeight - scroller.clientHeight,
        )
        scroller.scrollBy({ top: applied, behavior: reducedMotion ? 'auto' : 'smooth' })
        return { x: currentCoordinates.x, y: currentCoordinates.y + left }
      }
      return { x: currentCoordinates.x, y }
    },
    [homeOf, reducedMotion],
  )

  const pointerOptions = useMemo(() => ({ activationConstraint: { distance: 6 } }), [])
  const keyboardOptions = useMemo(
    // It scrolls a lifted clip into view: at once under reduced motion.
    () => ({ coordinateGetter, scrollBehavior: reducedMotion ? 'auto' : 'smooth' }) as const,
    [coordinateGetter, reducedMotion],
  )
  const sensors = useSensors(
    useSensor(PointerSensor, pointerOptions),
    useSensor(KeyboardSensor, keyboardOptions),
  )

  /*
   * A missing clip's copy stops at its own list's edges (the list is the row's
   * parent, dnd-kit's container): it never leaves its chapter, as Move clips
   * never offers it.
   */
  const modifiers = useMemo<Modifier[]>(() => {
    const homeClamp: Modifier = ({ transform, active, draggingNodeRect, containerNodeRect }) => {
      if (
        active === null ||
        !current.current.staysHome(String(active.id)) ||
        draggingNodeRect === null ||
        containerNodeRect === null
      ) {
        return transform
      }
      const top = containerNodeRect.top - draggingNodeRect.top
      const bottom = containerNodeRect.bottom - draggingNodeRect.bottom
      return { ...transform, y: Math.min(Math.max(transform.y, top), bottom) }
    }
    return [vertical, homeClamp]
  }, [])

  const announcements = useMemo<Announcements>(() => {
    const name = (id: UniqueIdentifier) => liftOf(id).name
    const words = (id: UniqueIdentifier, overId: UniqueIdentifier | null) => {
      const target = targetOf(overId)
      if (target !== null) {
        return `“${target.heading}”, position ${target.position} of ${target.total}`
      }
      const { model: now } = current.current
      const { order } = homeOf(String(id))
      const at = slotOf(now, String(id), overId === null ? null : String(overId))
      return at === null ? null : `position ${at.index + 1} of ${order.length}`
    }
    const unchanged = (id: UniqueIdentifier) => {
      const { order, position } = homeOf(String(id))
      return `${name(id)} dropped at position ${position} of ${order.length}, unchanged.`
    }
    return {
      onDragStart: ({ active }) => {
        const identity = String(active.id)
        const { own, order, position } = homeOf(identity)
        const { model: now, staysHome: home, headingOf: heading } = current.current
        const stays =
          own !== null && home(identity) && now.listed.length > 1
            ? ` It is missing, so it stays in “${heading(own)}”.`
            : ''
        return `Picked up ${name(active.id)}, position ${position} of ${order.length}.${stays}`
      },
      onDragOver: ({ active, over }) => {
        // dnd-kit's live region keeps only the last words of a batch: the clip over its own
        // place right after the lift would replace "Picked up …" before it is heard.
        const first = lifting.current
        lifting.current = false
        if (first && over?.id === active.id) {
          return undefined
        }
        const place = over === null ? null : words(active.id, over.id)
        return place === null ? undefined : `${name(active.id)} is over ${place}.`
      },
      onDragEnd: ({ active, over }) => {
        const overId = released.current ?? (over === null ? null : String(over.id))
        released.current = null
        const drop = dropOf(String(active.id), overId)
        const wasRefused = refused.current === String(active.id)
        refused.current = null
        if (drop.kind === 'none' || overId === null || wasRefused) {
          return unchanged(active.id)
        }
        return `${name(active.id)} moved to ${words(active.id, overId)}.`
      },
      onDragCancel: ({ active }) => {
        const { order, position } = homeOf(String(active.id))
        const back = `position ${position} of ${order.length}`
        return `Move cancelled. ${name(active.id)} is back at ${back}.`
      },
    }
  }, [dropOf, homeOf, liftOf, targetOf])

  const several = listed.length > 1
  const accessibility = useMemo(() => {
    const screenReaderInstructions: ScreenReaderInstructions = {
      draggable: several ? INSTRUCTIONS + ACROSS : INSTRUCTIONS,
    }
    // Its instructions and live region go to <body>, outside the chapters' markup.
    return { announcements, screenReaderInstructions, container: document.body }
  }, [announcements, several])

  const onDragStart = useCallback(({ active, activatorEvent }: DragStartEvent) => {
    const identity = String(active.id)
    const next = {
      identity,
      name: current.current.nameOf(identity),
      pointer: !(activatorEvent instanceof KeyboardEvent),
    }
    lift.current = next
    slot.current = null
    lifting.current = true
    refused.current = null
    released.current = null
    dropped.current = null
    cancelled.current = null
    setLifted(next)
  }, [])

  const onDragEnd = useCallback(
    ({ active, over }: DragEndEvent) => {
      const identity = String(active.id)
      const overId = releasedOver(identity, over?.id ?? null)
      released.current = overId
      const drop = dropOf(identity, overId)
      slot.current = null
      setLifted(null)
      // Synchronous: the copy leaves in the commit that shows the clip in its place.
      if (drop.kind === 'reorder') {
        dropped.current = { identity, to: drop.chapter, across: false }
        onReorder(drop.chapter, drop.from, drop.to)
      } else if (drop.kind === 'into') {
        // Followed up only once the editor took it: a refused drop leaves no focus request
        // behind for a later edit to act on.
        if (onDropInto(identity, drop.from, drop.to, drop.at)) {
          dropped.current = { identity, to: drop.to, across: true }
        } else {
          refused.current = identity
        }
      }
    },
    [dropOf, onDropInto, onReorder, releasedOver],
  )

  // A keyboard drag scrolls the page after the copy, a step into another chapter by a
  // whole chapter's header: the focused handle may be out of the window when it is
  // cancelled (the passive effect below brings it back).
  const onDragCancel = useCallback(({ active }: DragCancelEvent) => {
    slot.current = null
    cancelled.current = String(active.id)
    setLifted(null)
  }, [])

  useEffect(() => {
    const identity = cancelled.current
    const root = rootRef.current
    if (lifted !== null || identity === null || root === null) {
      return
    }
    cancelled.current = null
    const row = [...root.querySelectorAll<HTMLElement>('.clip-item')].find(
      (item) => item.dataset.identity === identity,
    )
    if (row !== undefined) {
      rowIntoView(row)
    }
  }, [lifted, rootRef])

  /*
   * After a drop the row is in its place: a drop into another chapter unmounted
   * the focused handle with its old row, so focus goes to the handle of its new row
   * (dnd-kit restores focus only after a keyboard drag, a frame later, to the same
   * handle). Focus moved by script after a pointer drag shows no ring. A layout
   * effect, so no frame paints with focus on <body>.
   */
  useLayoutEffect(() => {
    const drop = dropped.current
    const root = rootRef.current
    if (drop === null || root === null) {
      return
    }
    const row = [
      ...root.querySelectorAll<HTMLElement>(`[data-chapter-key="${drop.to}"] .clip-item`),
    ].find((item) => item.dataset.identity === drop.identity)
    if (row === undefined) {
      return
    }
    dropped.current = null
    if (drop.across) {
      row.querySelector<HTMLElement>('.drag-handle')?.focus({ preventScroll: true })
    }
    scrollAfter.current = { row, across: drop.across }
  }, [orders, rootRef])

  // The row comes into view, clear of the header and the save bar (the page's scroll
  // padding): a passive effect, so a save bar the drop brought is already measured (the
  // editor publishes its height in its own layout effect, after this one). Within the
  // chapter its whole row, as before; in another chapter its first line, which is what
  // fits when the row holds an open Cuts panel.
  useEffect(() => {
    const after = scrollAfter.current
    scrollAfter.current = null
    if (after === null) {
      return
    }
    if (after.across) {
      firstLineIntoView(after.row)
    } else {
      after.row.scrollIntoView({ block: 'nearest' })
    }
  }, [orders])

  return (
    <DndContext
      id="edit-chapters"
      sensors={sensors}
      collisionDetection={collisionDetection}
      modifiers={modifiers}
      autoScroll={AUTO_SCROLL}
      accessibility={accessibility}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragCancel={onDragCancel}
    >
      {children}
      {/* Above every panel, the app header and the save bar; under the toasts. Compact:
          the row's width, its first line's height, never an open Cuts panel's. */}
      {createPortal(
        <DragOverlay
          className="clip-drag-overlay"
          style={{ height: 'auto' }}
          zIndex={25}
          dropAnimation={null}
          // dnd-kit slides it 250 ms on each keyboard step by default.
          transition={reducedMotion ? 'none' : undefined}
        >
          {lifted !== null && <DragPreview name={lifted.name} targetOf={targetOf} />}
        </DragOverlay>,
        document.body,
      )}
      {/* While a pointer holds a clip, a transparent layer under the copy takes the pointer:
          the rows under it show no hover, and the cursor is the grabbing hand everywhere.
          The copy takes no pointer events itself. dnd-kit listens on the document, and a
          wheel over the layer still scrolls the page. */}
      {lifted?.pointer === true &&
        createPortal(<div className="clip-drag-shield" aria-hidden="true" />, document.body)}
    </DndContext>
  )
}
