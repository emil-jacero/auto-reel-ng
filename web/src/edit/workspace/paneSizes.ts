/*
 * The workspace's pane sizes (`resizable-panes`, design D1): the limits, the clamping and the
 * shrink to the window, the drag's snap, the keys, what a commit stores and the stored format.
 * Pure, with no DOM access, so `paneSizes.test.ts` checks every rule. `Workspace.tsx` lays the
 * result out, `PaneSeparator.tsx` asks it what a gesture means, `paneSizesPref.ts` keeps it.
 */

export type PaneId = 'bin' | 'insp' | 'tl'

/** What is stored: the chosen sizes in CSS px (a missing entry means "today's rule") and the hidden panes. */
export type PanePrefs = { sizes: Partial<Record<PaneId, number>>; hidden: readonly PaneId[] }

/** The sizes laid out, in whole CSS px; 0 means hidden. */
export type Drawn = Record<PaneId, number>

/** clientWidth/Height, the root font in px, the top bar's drawn height. */
export type Frame = { width: number; height: number; rem: number; top: number }

export const MIN_BIN_PX = 240
export const MIN_INSP_PX = 320
export const MIN_TL_PX = 200
export const MIN_VIEW_REM = 20
export const MIN_MIDDLE_REM = 20
export const MIN_MIDDLE_BARE_REM = 14
export const SNAP_FRACTION = 0.5
export const DRAG_SLOP_PX = 3
export const KEY_STEP_PX = 16
export const KEY_BIG_STEP_PX = 64

export type Limits = { min: number; max: number }
/** `repeat` is `KeyboardEvent.repeat`. */
export type Mods = { shift: boolean; ctrl: boolean; alt: boolean; meta: boolean; repeat: boolean }
export type PaneProperty = '--ws-bin-w' | '--ws-insp-w' | '--ws-tl-h'
/** What a gesture or a key asks of a pane. */
export type PaneAction = { kind: 'size'; px: number } | { kind: 'hide' } | { kind: 'show' } | { kind: 'reset' }

export const PANES: readonly PaneId[] = ['bin', 'insp', 'tl']
const KNOWN_KEYS = new Set<string>([...PANES, 'hidden'])

const MIN_PX: Record<PaneId, number> = { bin: MIN_BIN_PX, insp: MIN_INSP_PX, tl: MIN_TL_PX }

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high)

/** Today's rules as whole px: bin clamp(240, 0.22·width, 320), inspector 340, Timeline max(280, 0.38·height). */
export function defaultSizes(frame: Frame): Drawn {
  return {
    bin: Math.round(clamp(0.22 * frame.width, 240, 320)),
    insp: 340,
    tl: Math.round(Math.max(280, 0.38 * frame.height)),
  }
}

/** The middle row's least height in px: MIN_MIDDLE_REM with the bin shown, MIN_MIDDLE_BARE_REM without. */
export function middleMin(binShown: boolean, frame: Frame): number {
  return (binShown ? MIN_MIDDLE_REM : MIN_MIDDLE_BARE_REM) * frame.rem
}

/** The least and largest shown size of `pane` while the other panes stay as `drawn` (0 = hidden). */
export function limits(pane: PaneId, drawn: Drawn, frame: Frame): Limits {
  const min = MIN_PX[pane]
  let max: number
  if (pane === 'bin') {
    max = frame.width - drawn.insp - MIN_VIEW_REM * frame.rem
  } else if (pane === 'insp') {
    max = frame.width - drawn.bin - MIN_VIEW_REM * frame.rem
  } else {
    max = frame.height - frame.top - middleMin(drawn.bin > 0, frame)
  }
  return { min, max: Math.max(Math.floor(max), min) }
}

/** The layout: shown panes at their preference or default, shrunk to the frame; hidden panes 0. */
export function effectiveSizes(prefs: PanePrefs, frame: Frame): Drawn {
  const def = defaultSizes(frame)
  const hidden = new Set(prefs.hidden)
  const want = (pane: PaneId) => Math.max(Math.round(prefs.sizes[pane] ?? def[pane]), MIN_PX[pane])
  const room = frame.width - MIN_VIEW_REM * frame.rem
  const out: Drawn = { bin: 0, insp: 0, tl: 0 }
  const side = (['bin', 'insp'] as const).filter((pane) => !hidden.has(pane))
  if (side.length === 1) {
    const pane = side[0] as 'bin' | 'insp'
    out[pane] = clamp(want(pane), MIN_PX[pane], Math.max(Math.floor(room), MIN_PX[pane]))
  } else if (side.length === 2) {
    const wanted = want('bin') + want('insp')
    if (wanted <= room) {
      out.bin = want('bin')
      out.insp = want('insp')
    } else {
      const excess = wanted - MIN_BIN_PX - MIN_INSP_PX
      const factor =
        excess <= 0 ? 0 : clamp((room - MIN_BIN_PX - MIN_INSP_PX) / excess, 0, 1)
      out.bin = MIN_BIN_PX + Math.floor((want('bin') - MIN_BIN_PX) * factor)
      out.insp = MIN_INSP_PX + Math.floor((want('insp') - MIN_INSP_PX) * factor)
    }
  }
  if (!hidden.has('tl')) {
    const rows = Math.max(frame.height - frame.top, 0)
    const lower = Math.min(MIN_TL_PX, rows)
    const upper = Math.max(rows - middleMin(out.bin > 0, frame), lower)
    out.tl = Math.floor(clamp(want('tl'), lower, upper))
  }
  return out
}

/** The pane's growth for a pointer movement: the bin +dx, the inspector −dx, the Timeline −dy. */
function growth(pane: PaneId, dx: number, dy: number): number {
  return Math.round(pane === 'bin' ? dx : pane === 'insp' ? -dx : -dy)
}

/**
 * A hidden pane's drag starts at its press's distance from the window edge the pane grows from
 * (its strip sits inside the edge), so the pane's edge follows the pointer from the first pixel.
 */
export function edgeDistance(pane: PaneId, x: number, y: number, width: number, height: number): number {
  const distance = pane === 'bin' ? x : pane === 'insp' ? width - x : height - y
  return Math.max(0, Math.round(distance))
}

/** A drag from `start` (0 when the pane was hidden): hide under SNAP_FRACTION·min, else the size clamped to `lim`. */
export function dragAction(
  pane: PaneId,
  start: number,
  dx: number,
  dy: number,
  lim: Limits,
): PaneAction {
  const raw = start + growth(pane, dx, dy)
  if (raw < SNAP_FRACTION * lim.min) {
    return { kind: 'hide' }
  }
  return { kind: 'size', px: Math.round(clamp(raw, lim.min, lim.max)) }
}

const GROW_KEY: Record<PaneId, string> = { bin: 'ArrowRight', insp: 'ArrowLeft', tl: 'ArrowUp' }
const SHRINK_KEY: Record<PaneId, string> = { bin: 'ArrowLeft', insp: 'ArrowRight', tl: 'ArrowDown' }

/**
 * A key on a focused separator, or null when the key is not the pane's, Ctrl, Alt or Meta is held,
 * or an auto-repeat would hide or show the pane. `current` is the drawn size (0 when hidden).
 */
export function keyAction(
  pane: PaneId,
  key: string,
  mods: Mods,
  current: number,
  lim: Limits,
): PaneAction | null {
  if (mods.ctrl || mods.alt || mods.meta) {
    return null
  }
  const shown = current > 0
  const step = mods.shift ? KEY_BIG_STEP_PX : KEY_STEP_PX
  if (key === 'Enter') {
    if (mods.repeat) {
      return null
    }
    return shown ? { kind: 'hide' } : { kind: 'show' }
  }
  if (key === 'Home') {
    return { kind: 'size', px: lim.min }
  }
  if (key === 'End') {
    return { kind: 'size', px: lim.max }
  }
  if (key === GROW_KEY[pane]) {
    if (!shown) {
      return mods.repeat ? null : { kind: 'size', px: lim.min }
    }
    return { kind: 'size', px: Math.min(current + step, lim.max) }
  }
  if (key === SHRINK_KEY[pane]) {
    if (!shown) {
      return null
    }
    if (current <= lim.min) {
      return mods.repeat ? null : { kind: 'hide' }
    }
    return { kind: 'size', px: Math.max(current - step, lim.min) }
  }
  return null
}

/** Whether a key is one a separator takes for its pane (so a repeat is still kept from scrolling). */
export function isPaneKey(pane: PaneId, key: string): boolean {
  return (
    key === 'Enter' ||
    key === 'Home' ||
    key === 'End' ||
    key === GROW_KEY[pane] ||
    key === SHRINK_KEY[pane]
  )
}

/** What a commit stores: what the operator sees, and no other pane moved (the Timeline after a bin commit aside). */
export function commitPanes(
  pane: PaneId,
  action: PaneAction,
  prefs: PanePrefs,
  drawn: Drawn,
  frame: Frame,
): PanePrefs {
  const sizes: Partial<Record<PaneId, number>> = { ...prefs.sizes }
  const hidden = new Set(prefs.hidden)
  if (action.kind === 'size') {
    sizes[pane] = Math.round(action.px)
    hidden.delete(pane)
  } else if (action.kind === 'hide') {
    // Only hides: no kept size is rewritten (so a hide and a show are exact opposites, however
    // often they alternate), and hiding a pane that is already hidden changes nothing.
    hidden.add(pane)
    return { sizes, hidden: PANES.filter((id) => hidden.has(id)) }
  } else if (action.kind === 'show') {
    // Only unhides: the kept size stays as it was, and `effectiveSizes` fits it to the window, so
    // a window too small for both side panes never rewrites what the operator chose.
    hidden.delete(pane)
    return { sizes, hidden: PANES.filter((id) => hidden.has(id)) }
  } else {
    delete sizes[pane]
    hidden.delete(pane)
    if (pane !== 'tl') {
      // The default does not fit beside the other side pane as drawn: store what does fit, so the
      // other pane stays put (design D1) rather than both shrinking after release.
      const fit = limits(pane, drawn, frame)
      const want = defaultSizes(frame)[pane]
      if (want > fit.max) {
        sizes[pane] = fit.max
      }
    }
  }
  if (pane !== 'tl') {
    const other = pane === 'bin' ? 'insp' : 'bin'
    const next: PanePrefs = { sizes, hidden: PANES.filter((id) => hidden.has(id)) }
    const def = defaultSizes(frame)
    const wanted = Math.max(Math.round(prefs.sizes[other] ?? def[other]), MIN_PX[other])
    // The window is shrinking the other side pane, or the commit would move it: hold it as drawn,
    // so nothing moves on release. Only then is a kept size given up.
    if (
      !hidden.has(other) &&
      drawn[other] > 0 &&
      (drawn[other] < wanted || effectiveSizes(next, frame)[other] !== drawn[other])
    ) {
      sizes[other] = drawn[other]
    }
  }
  return { sizes, hidden: PANES.filter((id) => hidden.has(id)) }
}

/** Whether `pane` is hidden as laid out: never while stacked. */
export function paneHidden(pane: PaneId, prefs: PanePrefs, stacked: boolean): boolean {
  return !stacked && prefs.hidden.includes(pane)
}

/** The custom properties to write on <html>: each drawn size as a px string ("0px" hidden), null for all when `stacked`. */
export function paneProperties(drawn: Drawn, stacked: boolean): Record<PaneProperty, string | null> {
  if (stacked) {
    return { '--ws-bin-w': null, '--ws-insp-w': null, '--ws-tl-h': null }
  }
  return {
    '--ws-bin-w': `${drawn.bin}px`,
    '--ws-insp-w': `${drawn.insp}px`,
    '--ws-tl-h': `${drawn.tl}px`,
  }
}

/** Whether two frames have the same four numbers. */
export function sameFrame(a: Frame, b: Frame): boolean {
  return a.width === b.width && a.height === b.height && a.rem === b.rem && a.top === b.top
}

const isPane = (value: unknown): value is PaneId => PANES.includes(value as PaneId)

/**
 * Stored JSON → prefs; null on anything but an object of finite, positive sizes under known keys
 * and an optional `hidden` array of distinct known panes.
 */
export function parsePanes(raw: string | null): PanePrefs | null {
  if (raw === null) {
    return null
  }
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null
  }
  const record = value as Record<string, unknown>
  const sizes: Partial<Record<PaneId, number>> = {}
  let hidden: PaneId[] = []
  for (const key of Object.keys(record)) {
    if (!KNOWN_KEYS.has(key)) {
      return null
    }
    const entry = record[key]
    if (key === 'hidden') {
      if (!Array.isArray(entry)) {
        return null
      }
      const seen = new Set<PaneId>()
      for (const item of entry) {
        if (!isPane(item) || seen.has(item)) {
          return null
        }
        seen.add(item)
      }
      hidden = PANES.filter((id) => seen.has(id))
    } else if (typeof entry === 'number' && Number.isFinite(entry) && entry > 0) {
      sizes[key as PaneId] = entry
    } else {
      return null
    }
  }
  return { sizes, hidden }
}

/** Prefs → stored JSON, or null (remove the key) when there is no size and no hidden pane. */
export function serializePanes(prefs: PanePrefs): string | null {
  const out: Record<string, unknown> = {}
  for (const pane of PANES) {
    const size = prefs.sizes[pane]
    if (size !== undefined) {
      out[pane] = size
    }
  }
  if (prefs.hidden.length > 0) {
    out.hidden = [...prefs.hidden]
  }
  return Object.keys(out).length === 0 ? null : JSON.stringify(out)
}

const NAMES: Record<PaneId, string> = { bin: 'Clip bin', insp: 'Inspector', tl: 'Timeline' }

/** "Clip bin 282 pixels wide", "Timeline 342 pixels tall"; "Clip bin hidden" at 0. */
export function valueText(pane: PaneId, px: number): string {
  if (px <= 0) {
    return `${NAMES[pane]} hidden`
  }
  return `${NAMES[pane]} ${px} pixels ${pane === 'tl' ? 'tall' : 'wide'}`
}
