import { useEffect, useId, useLayoutEffect, useRef } from 'react'
import type { ReactNode } from 'react'

import { Icon } from './Icon'
import type { IconName } from './Icon'
import { menuKey, placeMenu } from './menu'
import type { Box, Point } from './menu'

/*
 * A menu of menu items (`clip-context-menu`, D3), opened at a point or under a box. One level, no
 * submenus, no check marks. It is a manual popover (the top layer, above the panes and the
 * toasts' region), so it has no light dismiss of its own: it closes itself on a press outside it,
 * a scroll outside it, a resize and a blur. The pure rules, which key does what and where it goes,
 * are `menu.ts`; this lists, listens, measures and applies.
 *
 * Its caller owns what an item does and where focus goes when it closes (`onChoose`, `onClose`).
 * The menu focuses its first item when it opens and gives no other focus away, but for hover.
 */

/** How long after it opens the menu lets scrolls pass (the selection's own scroll into view). */
const SCROLL_GRACE_MS = 250

export type MenuItemView = {
  /** The item's words, also its accessible name. */
  label: string
  icon: IconName
  /** Items of one group sit together; a separator goes between groups. */
  group: number
  /**
   * Why the item cannot act now (shown under it, and described by), or null. A reason equal to the
   * menu's `note` is not repeated under the item: the item is described by the note.
   */
  why: string | null
}

/** Why the menu closed itself or was closed by a key. */
export type MenuClose = 'escape' | 'tab' | 'outside' | 'scroll' | 'resize' | 'blur'

type MenuProps = {
  title: string
  /** A line under the title that holds for every item (the lock), or null. */
  note: string | null
  items: readonly MenuItemView[]
  /** The pointer, or the box (a block's visible part) the menu goes under. */
  at: Point | { box: Box }
  /** Called with the item's index, available or not: the caller says what it does. */
  onChoose: (index: number) => void
  /** `menu` is the closed menu's node: the caller checks where focus is against it. */
  onClose: (why: MenuClose, menu: HTMLElement) => void
}

export function Menu({ title, note, items, at, onChoose, onClose }: MenuProps) {
  const root = useRef<HTMLDivElement>(null)
  const base = useId()
  const titleId = `${base}-title`
  const noteId = `${base}-note`
  // The latest props, so the listeners below are installed once, for the menu's life.
  const now = useRef({ items, onChoose, onClose })
  now.current = { items, onChoose, onClose }

  const nodes = () =>
    Array.from(root.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])

  // Shown, placed and given focus before the first paint: it never flashes at the corner.
  useLayoutEffect(() => {
    const el = root.current
    if (el === null) {
      return undefined
    }
    try {
      if (typeof el.showPopover === 'function') {
        el.showPopover()
      }
    } catch {
      // Left as a fixed box: it still shows.
    }
    const view = { width: document.documentElement.clientWidth, height: document.documentElement.clientHeight }
    const size = el.getBoundingClientRect()
    const place = placeMenu('box' in at ? at.box : at, { width: size.width, height: size.height }, view)
    el.style.left = `${place.left}px`
    el.style.top = `${place.top}px`
    el.style.maxHeight = `${place.maxHeight}px`
    nodes()[0]?.focus({ preventScroll: true })
    return () => {
      try {
        if (typeof el.hidePopover === 'function' && el.matches(':popover-open')) {
          el.hidePopover()
        }
      } catch {
        // Already gone.
      }
    }
    // Placed once: a menu opened again is a new one (the caller keys it).
  }, [])

  // Its own dismissal, since a manual popover has none: the press that closes it goes on to its
  // target (nothing is prevented or stopped).
  useEffect(() => {
    const el = root.current
    if (el === null) {
      return undefined
    }
    const close = (why: MenuClose) => now.current.onClose(why, el)
    const inside = (target: EventTarget | null) => target instanceof Node && el.contains(target)
    const press = (event: PointerEvent) => {
      if (!inside(event.target)) {
        close('outside')
      }
    }
    // Opening a clip's menu selects the clip, which scrolls its bin row (or its block) into view
    // a frame or two later: those scrolls are the opening's own, not the operator's.
    const settled = performance.now() + SCROLL_GRACE_MS
    const scroll = (event: Event) => {
      if (!inside(event.target) && event.timeStamp >= settled) {
        close('scroll')
      }
    }
    const resize = () => close('resize')
    const blur = () => close('blur')
    window.addEventListener('pointerdown', press, true)
    window.addEventListener('scroll', scroll, true)
    window.addEventListener('resize', resize)
    window.addEventListener('blur', blur)
    // Native, on the menu itself: a key never reaches the document's listeners (the workspace's
    // keys, Escape clearing the selection) or the React ancestors the portal would bubble it to.
    const keydown = (event: KeyboardEvent) => {
      const list = nodes()
      const at = list.indexOf(document.activeElement as HTMLElement)
      const result = menuKey(event, list.length, at)
      if (result.kind === 'pass') {
        return
      }
      event.stopPropagation()
      switch (result.kind) {
        case 'focus':
          event.preventDefault()
          list[result.index]?.focus()
          return
        case 'choose':
          event.preventDefault()
          if (at >= 0) {
            now.current.onChoose(at)
          }
          return
        case 'close':
          event.preventDefault()
          close(event.key === 'Tab' ? 'tab' : 'escape')
          return
        case 'keep':
          if (result.preventDefault) {
            event.preventDefault()
          }
          return
      }
    }
    el.addEventListener('keydown', keydown)
    return () => {
      window.removeEventListener('pointerdown', press, true)
      window.removeEventListener('scroll', scroll, true)
      window.removeEventListener('resize', resize)
      window.removeEventListener('blur', blur)
      el.removeEventListener('keydown', keydown)
    }
  }, [])

  const rows: ReactNode[] = []
  items.forEach((item, index) => {
    if (index > 0 && items[index - 1].group !== item.group) {
      rows.push(<div key={`sep-${index}`} role="separator" className="menu-separator" />)
    }
    const whyId = `${base}-why-${index}`
    // An item whose reason is the menu's note (the lock) is described by the note: the line is
    // said once, not again under every item.
    const shared = note !== null && item.why === note
    rows.push(
      <div
        key={index}
        role="menuitem"
        tabIndex={-1}
        className="menu-item"
        aria-label={item.label}
        aria-disabled={item.why !== null || undefined}
        aria-describedby={item.why === null ? undefined : shared ? noteId : whyId}
        onClick={() => now.current.onChoose(index)}
        onPointerMove={(event) => {
          // Hover focuses the item, but not a move the layout made under a still pointer.
          if ((event.movementX !== 0 || event.movementY !== 0) && document.activeElement !== event.currentTarget) {
            event.currentTarget.focus({ preventScroll: true })
          }
        }}
      >
        <Icon name={item.icon} />
        <span className="menu-label">{item.label}</span>
        {item.why !== null && !shared && (
          <span id={whyId} className="menu-why">
            {item.why}
          </span>
        )}
      </div>,
    )
  })

  return (
    <div
      ref={root}
      className="menu"
      popover="manual"
      // The portal would bubble these to the React ancestors; nothing there is the menu's business.
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
      // The browser's own menu has no place on ours, and a release of the right button that opened
      // it (or a Menu key's contextmenu, which targets the focused item) does nothing.
      onContextMenu={(event) => {
        event.preventDefault()
        event.stopPropagation()
      }}
    >
      <p id={titleId} className="menu-title">
        {title}
      </p>
      {note !== null && (
        <p id={noteId} className="menu-note">
          {note}
        </p>
      )}
      <div role="menu" aria-labelledby={titleId} className="menu-items">
        {rows}
      </div>
    </div>
  )
}
