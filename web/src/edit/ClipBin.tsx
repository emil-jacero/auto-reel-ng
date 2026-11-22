import './clipBin.css'

import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { KeyboardEvent, MouseEvent, PointerEvent } from 'react'
import { createPortal } from 'react-dom'

import type { Clip } from '../api/event'
import { ClipThumb } from '../events/ClipThumb'
import { ClipName, ClipStatusPills } from '../events/common'
import type { ClipTurns } from '../cuts/ReadCuts'
import type { Turn } from '../rotate/turn.ts'
import { lastInput, pointerHeld } from './workspace/modality.ts'
import { shortcutsEnabled } from './workspace/shortcutSwitch.ts'
import { blockYieldsSpace } from './workspace/shortcuts.ts'
import { pressOf } from './workspace/selection.ts'
import type { Press } from './workspace/selection.ts'
import { HelpPanel, HelpToggle } from '../ui/help/HelpToggle'
import type { SectionHelp } from '../ui/help/HelpToggle'
import { Icon } from '../ui/Icon'
import type { ClipMenuOpen } from '../timeline/editing'
import { listKey, stepTo } from './binKeys.ts'
import { pastSlop, pointerDrags, rowDrags } from './binDrag.ts'
import {
  binOrder,
  ignoredCaption,
  removedCaption,
  rowLength,
  rowPlace,
  rowWords,
} from './binList.ts'
import type { BinRow } from './binList.ts'

/*
 * The clip bin's list (`plain-clip-bin`, design D2): every clip of the event as one plain list,
 * in play order, then the ignored clips and the missing clips removed until Save, each of those
 * under a caption. A row shows the clip's frame, its name, where it is, its kept length and its
 * status, and holds no control: it is one `option` of one `listbox`, the list being one keyboard
 * stop with a roving focus (`listKey`). A press selects as a press on a clip's block does, a
 * right-click or Shift+F10 opens the clip's menu (the Timeline's, through `onOpenMenu`), and only
 * an ignored clip's row drags, onto the track, to include it. Moving, rotating, ignoring and
 * cutting are the track's, the Clip tab's and the menu's.
 *
 * Every row is in the page at all times (`content-visibility: auto` lets the browser skip drawing
 * the far ones), so the list's keys, assistive technology and find in page reach them all.
 */

/** What the rows ask of the editor. */
export type BinHandlers = {
  /** A click, or Enter, Ctrl/Cmd+Enter, Shift+Enter or Space on a row: select as the track does. */
  onPress: (identity: string, press: Press) => void
  /** A press on a row's frame: the clip alone, the player shown, focus on its Play. */
  onWatch: (identity: string) => void
  /** A request for the clip's menu; true when one opened (the track draws the clip). */
  onOpenMenu: (open: ClipMenuOpen) => boolean
  /**
   * An ignored clip's row released at a client point: over the track the editor includes it and
   * this returns true; false when the point is not over the track. `group` is true when the row
   * belongs to a selection of several clips: the editor then includes nothing and says so.
   */
  onDropOutside: (identity: string, x: number, y: number, group: boolean) => boolean
  /** Whether a clip is held by the drag now: the editor holds its edits meanwhile. */
  onLift: (lifted: boolean) => void
  onAnnounce: (message: string) => void
}

/** What every row calls: one stable object, so a row re-renders only for its own props. */
type RowApi = {
  register: (identity: string, node: HTMLElement | null) => void
  focused: (identity: string) => void
  press: (event: MouseEvent<HTMLElement>, row: BinRow, frame: boolean) => void
  menu: (event: MouseEvent<HTMLElement>, identity: string) => void
  down: (event: PointerEvent<HTMLElement>, row: BinRow) => void
}

/** Whether two rows say the same, so the list keeps the old object and the row does not redraw. */
function sameRow(a: BinRow, b: BinRow): boolean {
  return (
    a.identity === b.identity &&
    a.name === b.name &&
    a.group === b.group &&
    a.place === b.place &&
    a.moved === b.moved &&
    a.status === b.status &&
    a.keptMs === b.keptMs &&
    a.typed === b.typed &&
    a.onDisk === b.onDisk
  )
}

/** The rows, each the object it was while it says the same: every draft edit makes new rows. */
function useStableRows(rows: readonly BinRow[]): readonly BinRow[] {
  const kept = useRef(new Map<string, BinRow>())
  return useMemo(() => {
    const next = new Map<string, BinRow>()
    const stable = rows.map((row) => {
      const was = kept.current.get(row.identity)
      const use = was !== undefined && sameRow(was, row) ? was : row
      next.set(row.identity, use)
      return use
    })
    kept.current = next
    return stable
  }, [rows])
}

/** Brings `row` into view inside its own scrolling pane, with no move of focus (wide: the bin's). */
function scrollInPane(row: HTMLElement | null): void {
  for (let pane = row?.parentElement ?? null; pane !== null; pane = pane.parentElement) {
    if (pane === document.body || pane === document.documentElement) {
      return
    }
    const { overflowY } = getComputedStyle(pane)
    if ((overflowY === 'auto' || overflowY === 'scroll') && pane.scrollHeight > pane.clientHeight) {
      // Measured inside the pane's scroll padding: the sticky header hides the pane's top rows.
      const box = pane.getBoundingClientRect()
      const style = getComputedStyle(pane)
      const top = box.top + (parseFloat(style.scrollPaddingTop) || 0)
      const bottom = box.bottom - (parseFloat(style.scrollPaddingBottom) || 0)
      const at = row!.getBoundingClientRect()
      if (at.top < top) {
        pane.scrollTop += at.top - top
      } else if (at.bottom > bottom) {
        pane.scrollTop += at.bottom - bottom
      }
      return
    }
  }
}

const BinRowView = memo(function BinRowView({
  eventId,
  row,
  clip,
  turn,
  selected,
  stop,
  api,
}: {
  eventId: string
  row: BinRow
  /** The clip as the draft has it (its status follows an ignore edit). */
  clip: Clip
  turn: Turn
  selected: boolean
  /** The list's one Tab stop. */
  stop: boolean
  api: RowApi
}) {
  const place = rowPlace(row)
  const length = rowLength(row)
  return (
    <div
      ref={(node) => api.register(row.identity, node)}
      className="bin-row"
      role="option"
      aria-selected={selected}
      aria-label={rowWords(row)}
      tabIndex={stop ? 0 : -1}
      data-identity={row.identity}
      data-group={row.group}
      data-status={clip.status}
      data-excluded={clip.excluded || undefined}
      data-moved={row.moved !== null || undefined}
      onFocus={() => api.focused(row.identity)}
      onClick={(event) => api.press(event, row, false)}
      onContextMenu={(event) => api.menu(event, row.identity)}
      onPointerDown={(event) => api.down(event, row)}
    >
      {/* The selected row's ground, a leaf: the row itself carries no selection state. */}
      <span className="bin-sel" aria-hidden="true" data-on={selected || undefined} />
      {/* A press on the frame watches the clip (not a stop of its own: the row is the stop). */}
      <span
        className="bin-frame"
        aria-hidden="true"
        data-watch={row.onDisk || undefined}
        onClick={row.onDisk ? (event) => api.press(event, row, true) : undefined}
      >
        <ClipThumb eventId={eventId} clip={clip} name={row.name} turn={turn} />
      </span>
      <span className="bin-text" aria-hidden="true">
        <span className="bin-name" data-selected={selected || undefined}>
          <ClipName name={row.name} />
        </span>
        {place !== null && <span className="bin-place">{place}</span>}
      </span>
      <span className="bin-facts" aria-hidden="true">
        {row.typed && <span className="bin-typed">typed</span>}
        {length !== null && <span className="bin-length">{length}</span>}
        <span className="bin-status">
          <ClipStatusPills clip={clip} hint />
        </span>
      </span>
    </div>
  )
})

/** The copy that follows the pointer while an ignored clip's row is dragged. */
function DragCopy({ name, x, y }: { name: string; x: number; y: number }) {
  return createPortal(
    <>
      <div className="bin-drag-shield" aria-hidden="true" />
      <div
        className="bin-drag-copy"
        aria-hidden="true"
        style={{ insetInlineStart: x + 12, insetBlockStart: y + 12 }}
      >
        <Icon name="arrow-right" />
        <span className="bin-drag-name">
          <ClipName name={name} />
        </span>
      </div>
    </>,
    document.body,
  )
}

export function ClipBin({
  eventId,
  rows: given,
  clips,
  turns,
  selected,
  lead,
  help,
  helpLines,
  showSlot,
  handlers,
}: {
  eventId: string
  /** `binRows`: every clip of the event, the played ones first. */
  rows: readonly BinRow[]
  /** The clips as the draft has them (`withIgnoreStatus`). */
  clips: ReadonlyMap<string, Clip>
  /** The clips' turns in the draft: what every frame shows. */
  turns: ClipTurns
  /** The clips the selection holds. */
  selected: ReadonlySet<string>
  /** The clip pressed last: the row that scrolls into view. */
  lead: string | null
  help: SectionHelp
  helpLines: readonly string[]
  /** Where the player's Show player button goes while the player is hidden: the header's first row. */
  showSlot: (node: HTMLElement | null) => void
  handlers: BinHandlers
}) {
  const rows = useStableRows(given)
  const order = useMemo(() => binOrder(rows), [rows])
  const groups = useMemo(
    () => ({
      listed: rows.filter((row) => row.group === 'listed'),
      ignored: rows.filter((row) => row.group === 'ignored'),
      removed: rows.filter((row) => row.group === 'removed'),
    }),
    [rows],
  )

  // The one row that holds the Tab stop: the one focus was last on, else the selected clip the
  // list shows, else the first row.
  const [active, setActive] = useState<string | null>(null)
  const known = useMemo(() => new Set(order), [order])
  const stop =
    active !== null && known.has(active)
      ? active
      : lead !== null && known.has(lead)
        ? lead
        : (order[0] ?? null)

  const nodes = useRef(new Map<string, HTMLElement>())
  const latest = useRef({ handlers, order, selected })
  latest.current = { handlers, order, selected }
  const focusedId = useRef<string | null>(null)
  const [drag, setDrag] = useState<{ identity: string; name: string; x: number; y: number } | null>(
    null,
  )
  const suppressClick = useRef(false)
  // The row whose press (not its click) just selected: that click selects nothing more.
  const pressedBy = useRef<string | null>(null)

  const api = useMemo<RowApi>(() => {
    // An ignored clip's row, pressed: a drag once the pointer passes the slop.
    const startDrag = (event: PointerEvent<HTMLElement>, row: BinRow) => {
      const from = { x: event.clientX, y: event.clientY }
      let dragging = false
      const stopListening = () => {
        window.removeEventListener('pointermove', move, true)
        window.removeEventListener('pointerup', up, true)
        window.removeEventListener('pointercancel', cancel, true)
        window.removeEventListener('keydown', key, true)
      }
      const finish = (drop: { x: number; y: number } | null) => {
        stopListening()
        if (!dragging) {
          return
        }
        setDrag(null)
        latest.current.handlers.onLift(false)
        suppressClick.current = true
        window.setTimeout(() => {
          suppressClick.current = false
        }, 0)
        const group = latest.current.selected.size > 1 && latest.current.selected.has(row.identity)
        if (
          drop !== null &&
          !latest.current.handlers.onDropOutside(row.identity, drop.x, drop.y, group)
        ) {
          latest.current.handlers.onAnnounce(`Dropped ${row.name}. It is still ignored.`)
        }
      }
      const move = (moved: globalThis.PointerEvent) => {
        if (!dragging) {
          if (!pastSlop(moved.clientX - from.x, moved.clientY - from.y)) {
            return
          }
          dragging = true
          latest.current.handlers.onLift(true)
          window.getSelection()?.removeAllRanges()
          latest.current.handlers.onAnnounce(
            `Picked up ${row.name}, an ignored clip. Drop it on the video track to include it.`,
          )
        }
        setDrag({ identity: row.identity, name: row.name, x: moved.clientX, y: moved.clientY })
      }
      const up = (released: globalThis.PointerEvent) =>
        finish({ x: released.clientX, y: released.clientY })
      const cancel = () => finish(null)
      const key = (pressed: globalThis.KeyboardEvent) => {
        if (pressed.key === 'Escape' && dragging) {
          pressed.preventDefault()
          finish(null)
          latest.current.handlers.onAnnounce(`Cancelled. ${row.name} is still ignored.`)
        }
      }
      window.addEventListener('pointermove', move, true)
      window.addEventListener('pointerup', up, true)
      window.addEventListener('pointercancel', cancel, true)
      window.addEventListener('keydown', key, true)
    }
    // The press of a mouse or a pen on a row selects at once, as a press in a native list does: a
    // press that moves off the row (onto the track, say) still selects it. The click that follows
    // selects nothing more. An ignored clip's row selects on its click instead, a drag of it being
    // no selection.
    const down = (event: PointerEvent<HTMLElement>, row: BinRow) => {
      if (event.button !== 0 || !pointerDrags(event.pointerType)) {
        return
      }
      if (rowDrags(row)) {
        startDrag(event, row)
        return
      }
      const onFrame = (event.target as HTMLElement).closest('.bin-frame') !== null && row.onDisk
      const press = pressOf(event)
      // A plain press on a frame watches the clip: that is its click's.
      if (onFrame && press === 'alone') {
        return
      }
      if (press === 'range') {
        window.getSelection()?.removeAllRanges()
      }
      latest.current.handlers.onPress(row.identity, press)
      pressedBy.current = row.identity
      const clear = () => {
        window.removeEventListener('pointerup', clear, true)
        window.removeEventListener('pointercancel', clear, true)
        // The click follows the release at once; the mark does not outlive it.
        window.setTimeout(() => {
          pressedBy.current = null
        }, 250)
      }
      window.addEventListener('pointerup', clear, true)
      window.addEventListener('pointercancel', clear, true)
    }
    return {
      register: (identity, node) => {
        if (node === null) {
          nodes.current.delete(identity)
        } else {
          nodes.current.set(identity, node)
        }
      },
      focused: (identity) => {
        focusedId.current = identity
        setActive(identity)
      },
      press: (event, row, frame) => {
        // The release of a drag is followed by a click: it selects nothing. The frame's own press
        // leaves the flag for the row it bubbles to.
        if (suppressClick.current) {
          suppressClick.current = frame ? suppressClick.current : false
          return
        }
        // The press of a mouse or a pen selected this row already.
        if (pressedBy.current === row.identity) {
          pressedBy.current = frame ? pressedBy.current : null
          return
        }
        const press = pressOf(event)
        if (press === 'range') {
          // Shift+click would otherwise leave the browser's text selection behind.
          window.getSelection()?.removeAllRanges()
        }
        if (frame && press === 'alone') {
          // The frame's own press: the row's click must not select again.
          event.stopPropagation()
          latest.current.handlers.onWatch(row.identity)
          return
        }
        if (!frame) {
          latest.current.handlers.onPress(row.identity, press)
        }
      },
      menu: (event, identity) => {
        const row = event.currentTarget
        const opened = latest.current.handlers.onOpenMenu({
          identity,
          at: { x: event.clientX, y: event.clientY },
          invoker: row,
        })
        if (opened) {
          event.preventDefault()
        }
      },
      down,
    } satisfies RowApi
  }, [])

  const onKeyDown = useCallback((event: KeyboardEvent<HTMLElement>) => {
    const option = (event.target as HTMLElement).closest<HTMLElement>('[role="option"]')
    if (option === null || option !== event.target) {
      return
    }
    const identity = option.dataset.identity
    if (identity === undefined) {
      return
    }
    const space = event.key === ' ' || event.key === 'Spacebar'
    // After a pointer press Space is Play (the workspace's listener) when it will take the key.
    const yields =
      space && blockYieldsSpace(lastInput(), shortcutsEnabled(), pointerHeld())
    const command = listKey(event, yields)
    if (command === null) {
      return
    }
    event.preventDefault()
    switch (command.kind) {
      case 'move': {
        const to = stepTo(latest.current.order, identity, command.to)
        if (to !== null) {
          nodes.current.get(to)?.focus()
        }
        return
      }
      case 'select':
        latest.current.handlers.onPress(identity, command.press)
        return
      case 'menu':
        latest.current.handlers.onOpenMenu({
          identity,
          at: { box: option.getBoundingClientRect() },
          invoker: option,
        })
        return
    }
  }, [])

  // The selected clip the list shows scrolls into view when it becomes the one pressed last, with
  // no move of focus. A row that mounts already selected stays put.
  const wasLead = useRef(lead)
  useEffect(() => {
    if (lead !== null && lead !== wasLead.current && selected.has(lead)) {
      scrollInPane(nodes.current.get(lead) ?? null)
    }
    wasLead.current = lead
  }, [lead, selected])

  // A row that took focus and was redrawn as another node (an ignore moves it to its own group)
  // leaves focus on the body: it goes back to the row, never to the page's body.
  useLayoutEffect(() => {
    const id = focusedId.current
    if (id !== null && document.activeElement === document.body) {
      const node = nodes.current.get(id)
      if (node?.isConnected === true) {
        node.focus({ preventScroll: true })
      }
    }
  })

  const total = rows.length
  const renderRow = (row: BinRow) => {
    const clip = clips.get(row.identity)
    if (clip === undefined) {
      // The rows come from the same read as `clips`: a row without its clip is a bug, not a gap.
      throw new Error(`The bin lists the clip ${row.identity}, which the event read does not hold.`)
    }
    return (
      <BinRowView
        key={row.identity}
        eventId={eventId}
        row={row}
        clip={clip}
        turn={turns.get(row.identity) ?? 0}
        selected={selected.has(row.identity)}
        stop={row.identity === stop}
        api={api}
      />
    )
  }

  return (
    <div className="clip-bin">
      <div className="bin-head">
        <span className="bin-head-lead">
          <HelpToggle help={help} section="Clips" />
          <span ref={showSlot} className="bin-head-player" />
        </span>
        <h2 className="bin-title">Clips · {total}</h2>
      </div>
      <HelpPanel help={help}>
        {helpLines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </HelpPanel>
      {total === 0 ? (
        <p className="empty-state">
          <Icon name="film" size={20} />
          No clips.
        </p>
      ) : (
        <div
          role="listbox"
          aria-label="Clips"
          aria-multiselectable="true"
          className="bin-list"
          onKeyDown={onKeyDown}
          onBlur={(event) => {
            // Focus that leaves the list for somewhere else is not a drop to the body.
            const next = event.relatedTarget
            if (next !== null || event.target.isConnected) {
              focusedId.current = null
            }
          }}
        >
          {groups.listed.length > 0 && (
            <div role="group" aria-label="Clips in play order" className="bin-group">
              {groups.listed.map(renderRow)}
            </div>
          )}
          {groups.ignored.length > 0 && (
            <>
              <p className="bin-caption" role="presentation" aria-hidden="true">
                {ignoredCaption(groups.ignored.length)}
              </p>
              <div
                role="group"
                aria-label={ignoredCaption(groups.ignored.length)}
                className="bin-group"
              >
                {groups.ignored.map(renderRow)}
              </div>
            </>
          )}
          {groups.removed.length > 0 && (
            <>
              <p className="bin-caption" role="presentation" aria-hidden="true">
                {removedCaption(groups.removed.length)}
              </p>
              <div
                role="group"
                aria-label={removedCaption(groups.removed.length)}
                className="bin-group"
              >
                {groups.removed.map(renderRow)}
              </div>
            </>
          )}
        </div>
      )}
      {drag !== null && <DragCopy name={drag.name} x={drag.x} y={drag.y} />}
    </div>
  )
}
