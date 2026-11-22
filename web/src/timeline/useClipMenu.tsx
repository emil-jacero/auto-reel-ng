import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import type { ClipState } from '../edit/clipInspector'
import type { SelectionBinding } from '../edit/workspace/useSelection.ts'
import type { IconName } from '../ui/Icon'
import { Menu } from '../ui/Menu'
import type { MenuClose } from '../ui/Menu'
import { mayReturnFocus } from '../ui/returnFocus'
import { clipMenu, focusAfter, focusAfterMany, menuSelects, targets } from './clipMenu'
import type { ClipAction } from './clipMenu'
import type { ClipMenuOpen, EditBinding } from './editing'
import type { TrackClip } from './layout'
import type { DrawnChapter } from './reorder'

/*
 * The clip's menu (`clip-context-menu`, D1; `plain-clip-bin` D5): one, opened by the track's blocks
 * and by the bin's rows. It is a hook so that it lives wherever the bin can be used: the Timeline
 * gives it the track's facts (`track`), and while no track is drawn (a clip without a ready proxy,
 * or no clip at all) the section mounts it with `track` null, and every clip is one the track does
 * not draw: Cut at playhead and Use frame as poster say "The Timeline does not show <name>.".
 */

/** The icon of a menu item. */
function menuIcon(action: ClipAction): IconName {
  switch (action.kind) {
    case 'rotate':
      return action.way === 'left' ? 'rotate-ccw' : 'rotate-cw'
    case 'cut':
      return 'scissors'
    case 'poster':
      return 'film'
    case 'move':
      return 'arrow-right'
    case 'ignore':
      return 'eye-off'
    case 'include':
      return 'plus'
    case 'remove':
      return 'x'
    case 'restore':
      return 'rotate-ccw'
  }
}

/** What the Timeline lends the menu while it draws the track. */
export type MenuTrack = {
  clips: readonly TrackClip[]
  /** The drawn chapters, in order, with the clips each plays. */
  chapters: readonly DrawnChapter[]
  /** Why Cut at playhead cannot act on this clip now, or null. */
  cutWhyFor(clip: TrackClip): string | null
  /** Why Use frame as poster cannot act on this clip now, or null. */
  posterWhyFor(clip: TrackClip): string | null
  /** Cut at playhead: null once the cut is made, else why not. */
  addCut(clip: TrackClip): string | null
  /** Use frame as poster: whether it went ahead (false: it said why). */
  takePoster(clip: TrackClip): boolean
  /** The clip at the end of the chapter, the edit a drop on that chapter's band makes. */
  moveToEnd(identity: string, chapter: string): void
  /** The clip's block, else the track (null: the track). */
  focusBlock(identity: string | null): void
}

export function useClipMenu({
  editing,
  selection,
  announce,
  track,
}: {
  editing: EditBinding
  selection: SelectionBinding
  announce: (words: string) => void
  track: MenuTrack | null
}) {
  const clips = track?.clips ?? []
  /** The bin's row of a clip, in the list that shows now. */
  const rowOf = (identity: string): HTMLElement | null =>
    Array.from(document.querySelectorAll<HTMLElement>('[role="option"][data-identity]')).find(
      (row) => row.dataset.identity === identity && row.closest('[hidden]') === null,
    ) ?? null
  /** The clip's block, else the track; with no track, the clip's bin row. */
  const focusBlock = (identity: string | null) => {
    if (track !== null) {
      track.focusBlock(identity)
    } else if (identity !== null) {
      rowOf(identity)?.focus({ preventScroll: true })
    }
  }
  // The clip's menu (`clip-context-menu`, D1): one, opened by the track and
  // the bin's rows. Its playhead reasons are taken when it opens; the lock follows `editing.locked`.
  const [menu, setMenu] = useState<{
    id: number
    open: ClipMenuOpen
    cutWhy: string | null
    posterWhy: string | null
    /** The clip's state when the menu opened: a change (an Undo, a Reset) closes it. */
    state: ClipState | null
  } | null>(null)
  const menuCount = useRef(0)
  // Where focus goes once the menu is gone (a layout effect: never onto a node about to unmount).
  const menuFocus = useRef<(() => void) | null>(null)
  useLayoutEffect(() => {
    const run = menuFocus.current
    menuFocus.current = null
    run?.()
  }, [menu])
  // A clip the track does not draw (ignored, missing, removed, or any clip while it prepares) has its
  // menu too (`plain-clip-bin` D5): its facts come from the editor's draft, its track reasons are words.
  const openClipMenu = (open: ClipMenuOpen): boolean => {
    const clip = clips.find((c) => c.identity === open.identity)
    const known = editing.menuFacts().clip(open.identity)
    if (known === null) {
      return false
    }
    if (menuSelects(selection.selection, open.identity)) {
      selection.set({ kind: 'clip', identity: open.identity })
    }
    menuCount.current += 1
    setMenu({
      id: menuCount.current,
      open,
      cutWhy: clip === undefined || track === null ? null : track.cutWhyFor(clip),
      posterWhy: clip === undefined || track === null ? null : track.posterWhyFor(clip),
      state: known.state,
    })
    return true
  }
  // The bin's rows open the same menu: the latest closure, while this is mounted.
  const menuAt = editing.menuAt
  useLayoutEffect(() => {
    menuAt.current = openClipMenu
    return () => {
      menuAt.current = null
    }
  })
  // `focusOn`: where a choice sends focus (D5): the clip's block by default, another clip's block,
  // or (null) the track.
  const closeMenu = (
    why: MenuClose | 'choice' | 'gone',
    el: HTMLElement | null,
    focusOn?: string | null,
  ) => {
    if (menu === null) {
      return
    }
    const identity = menu.open.identity
    const invoker = menu.open.invoker
    // Where focus goes back to once the press, scroll or resize closed it: the invoker, else the block.
    const focusInvoker = () => {
      if (invoker.isConnected) {
        invoker.focus({ preventScroll: true })
      } else {
        focusBlock(identity)
      }
    }
    setMenu(null)
    switch (why) {
      case 'escape':
      case 'tab':
      case 'choice':
        menuFocus.current = () => {
          // A menu opened from a bin row gives focus back to the row, which may have moved to
          // another group of the list (a removal, an inclusion): found again by its clip.
          if (focusOn === undefined && invoker.getAttribute('role') === 'option') {
            const row = invoker.isConnected ? invoker : rowOf(identity)
            if (row !== null) {
              row.focus({ preventScroll: true })
              return
            }
          }
          focusBlock(focusOn === undefined ? identity : focusOn)
        }
        return
      case 'outside':
        // The press goes on to its target first; focus comes back only if it was left nowhere.
        window.setTimeout(() => {
          if (el === null || mayReturnFocus<Node>(document.activeElement, el, document.body)) {
            focusInvoker()
          }
        }, 0)
        return
      case 'scroll':
      case 'resize':
      case 'gone':
        menuFocus.current = () => {
          if (el === null || mayReturnFocus<Node>(document.activeElement, el, document.body)) {
            focusInvoker()
          }
        }
        return
      case 'blur':
        return
    }
  }
  // Its clip leaving the event, or changing state (an Undo, a Reset), closes it.
  const menuFactsNow = menu === null ? null : editing.menuFacts()
  const menuInfo = menu === null ? null : (menuFactsNow?.clip(menu.open.identity) ?? null)
  const menuClipGone = menu !== null && (menuInfo === null || menuInfo.state !== menu.state)
  useEffect(() => {
    if (menuClipGone) {
      closeMenu('gone', null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuClipGone])
  const menuClip = menu === null ? undefined : clips.find((c) => c.identity === menu.open.identity)
  // The clips the menu acts on: the selected clips when it was opened on one of two or more, else
  // the clip alone (`clip-multi-select` D7). Taken in the bin's order, which holds ignored clips too.
  const menuTargets =
    menu === null || menuInfo === null || menuFactsNow === null
      ? []
      : targets(selection.selection, menu.open.identity, menuFactsNow.order)
  const menuView =
    menu === null || menuInfo === null || menuFactsNow === null
      ? null
      : clipMenu({
          locked: editing.locked,
          cutWhy: menu.cutWhy,
          posterWhy: menu.posterWhy,
          // Several clips may be gathered at the end of any chapter, their own included. A clip the
          // track draws lists the chapters the track draws; any other the chapters the draft lists.
          others:
            menuClip === undefined || track === null
              ? menuInfo.chapters.filter((chapter) => menuTargets.length > 1 || chapter.key !== menuInfo.own)
              : track.chapters
                  .filter((chapter) => menuTargets.length > 1 || !chapter.identities.includes(menuClip.identity))
                  .map((chapter) => ({ key: chapter.key, name: chapter.name ?? '' })),
          targets: menuTargets,
          name: menuInfo.name,
          state: menuInfo.state,
          drawn: menuClip !== undefined,
          played: menuTargets.filter((id) => menuFactsNow.clip(id)?.state !== 'ignored').length,
          ignored: menuTargets.filter((id) => menuFactsNow.clip(id)?.state === 'ignored').length,
        })
  // Choosing an item: one that cannot act says why and keeps the menu; otherwise it makes the
  // edit the Clip tab's control makes (D2) and the menu closes, focus going where D5 says.
  const chooseMenuItem = (index: number) => {
    const item = menuView?.items[index]
    if (item === undefined || menu === null || menuInfo === null) {
      return
    }
    if (item.why !== null) {
      announce(item.why)
      return
    }
    const clip = menuClip
    const identity = menu.open.identity
    // The playhead's reasons are taken again now: Play may have moved it since the menu opened.
    const refused = (cutWhy: string | null, posterWhy: string | null) =>
      setMenu((was) => (was === null ? was : { ...was, cutWhy, posterWhy }))
    const action = item.action
    // Two or more selected clips: each item makes the edit the group tab makes (D7).
    if (menuTargets.length > 1) {
      switch (action.kind) {
        case 'rotate':
          editing.onRotateMany(menuTargets, action.way)
          break
        case 'move':
          editing.onMoveSelection(menuTargets, action.chapter)
          break
        case 'ignore': {
          const next = focusAfterMany(
            clips.map((c) => c.identity),
            menuTargets,
          )
          editing.onIgnoreMany(menuTargets)
          selection.clear()
          closeMenu('choice', null, next)
          return
        }
        // The clips stay selected, and the row the menu opened on takes focus back (it is played now).
        case 'include':
          editing.onIncludeMany(menuTargets)
          break
        // Not reached: Cut and Poster are unavailable for several clips, so `item.why` stopped them;
        // Remove and Undo remove are listed for one clip only.
        case 'cut':
        case 'poster':
        case 'remove':
        case 'restore':
          return
      }
      closeMenu('choice', null)
      return
    }
    switch (action.kind) {
      case 'rotate':
        editing.onRotate(identity, action.way)
        break
      case 'cut':
        // Not reached for a clip the track does not draw: `item.why` stopped it.
        if (clip === undefined || track === null || track.addCut(clip) !== null) {
          if (clip !== undefined && track !== null) {
            refused(track.cutWhyFor(clip), track.posterWhyFor(clip))
          }
          return
        }
        break
      case 'poster':
        if (clip === undefined || track === null || !track.takePoster(clip)) {
          if (clip !== undefined && track !== null) {
            refused(track.cutWhyFor(clip), track.posterWhyFor(clip))
          }
          return
        }
        break
      case 'move':
        if (clip === undefined || track === null) {
          editing.onMoveToEnd(identity, action.chapter)
        } else {
          track.moveToEnd(identity, action.chapter)
        }
        break
      case 'ignore': {
        const next = focusAfter(
          clips.map((c) => c.identity),
          identity,
        )
        editing.onIgnore(identity)
        closeMenu('choice', null, next)
        return
      }
      // The three status items make the edit the Clip tab's end button makes; focus goes back to
      // the clip's row, which has moved to another group of the list.
      case 'include':
        editing.onInclude(identity)
        break
      case 'remove':
        editing.onRemoveClip(identity)
        break
      case 'restore':
        editing.onRestoreClip(identity)
        break
    }
    closeMenu('choice', null)
  }
  const element =
      menu !== null &&
      menuView !== null &&
      menuInfo !== null &&
      createPortal(
        <Menu
          key={menu.id}
          title={menuView.title ?? menuInfo.name}
          note={menuView.note}
          items={menuView.items.map((item) => ({
            label: item.label,
            icon: menuIcon(item.action),
            group: item.group,
            why: item.why,
          }))}
          at={'box' in menu.open.at ? { box: menu.open.at.box } : menu.open.at}
          onChoose={chooseMenuItem}
          onClose={closeMenu}
        />,
        document.body,
      )
  return { element, open: openClipMenu }
}
