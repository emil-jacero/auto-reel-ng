import { useSyncExternalStore } from 'react'

/*
 * Toasts: a small module store, shown by `ToastRegion` (rendered once by the
 * shell). Call `toast.success(message)`, `toast.info(message)` or
 * `toast.error(message)`, optionally with a link: `{ action: { label, href } }`.
 *
 * Success and info toasts dismiss themselves after 5 s. While the region is
 * paused (pointer or focus inside it) or a modal dialog is open (`Dialog` calls
 * `enterModal`), their clocks stop, keeping the time left.
 * Errors stay until dismissed. At most three are held: a fourth drops the oldest
 * non-error toast. When all three are errors, only a new error drops the oldest;
 * a success or info toast is not shown then (an unread error is never lost to a
 * lesser one).
 *
 * A page with a bar held at the window's bottom (Edit mode's save bar) registers
 * it with `keepToastsClearOf(bar)`, so no toast ever covers it.
 */

export type ToastTone = 'success' | 'info' | 'error'
export type ToastOptions = { action?: { label: string; href: string } }
export type Toast = { id: number; tone: ToastTone; message: string } & ToastOptions

const AUTO_DISMISS_MS = 5000
const MAX_HELD = 3

let toasts: readonly Toast[] = []
let nextId = 1
let isPaused = false
// Modal dialogs open now (`enterModal`): clocks wait while there is one.
let modalDepth = 0
const listeners = new Set<() => void>()

/** An auto-dismiss clock: the time left, and its timer while it runs. */
type Clock = { remaining: number; startedAt: number; timer: number | undefined }
const clocks = new Map<number, Clock>()

function emit(next: readonly Toast[]): void {
  toasts = next
  for (const listener of listeners) {
    listener()
  }
}

/** Whether the clocks stand still: the pointer or focus is in the region, or a modal dialog is open. */
function isWaiting(): boolean {
  return isPaused || modalDepth > 0
}

function startClock(id: number): void {
  const clock = clocks.get(id)
  if (clock === undefined || clock.timer !== undefined || isWaiting()) {
    return
  }
  clock.startedAt = Date.now()
  clock.timer = window.setTimeout(() => dismissToast(id), clock.remaining)
}

function stopClock(id: number): void {
  const clock = clocks.get(id)
  if (clock === undefined || clock.timer === undefined) {
    return
  }
  window.clearTimeout(clock.timer)
  clock.timer = undefined
  clock.remaining = Math.max(0, clock.remaining - (Date.now() - clock.startedAt))
}

function show(tone: ToastTone, message: string, options: ToastOptions = {}): void {
  let held = toasts
  if (held.length >= MAX_HELD) {
    // An unread error is only ever displaced by a newer error; a lesser toast
    // that cannot make room is not shown at all (no id, no clock, no emit).
    const lesser = held.find((shown) => shown.tone !== 'error')
    const dropped = lesser ?? (tone === 'error' ? held[0] : null)
    if (dropped === null) {
      return
    }
    stopClock(dropped.id)
    clocks.delete(dropped.id)
    held = held.filter((shown) => shown.id !== dropped.id)
  }
  const added: Toast = { id: nextId, tone, message, ...options }
  nextId += 1
  if (tone !== 'error') {
    clocks.set(added.id, { remaining: AUTO_DISMISS_MS, startedAt: 0, timer: undefined })
    startClock(added.id)
  }
  emit([...held, added])
}

export const toast: Record<ToastTone, (message: string, options?: ToastOptions) => void> = {
  success: (message, options) => show('success', message, options),
  info: (message, options) => show('info', message, options),
  error: (message, options) => show('error', message, options),
}

export function dismissToast(id: number): void {
  stopClock(id)
  clocks.delete(id)
  if (toasts.some((shown) => shown.id === id)) {
    emit(toasts.filter((shown) => shown.id !== id))
  }
}

/** Stop or start every clock to match `isWaiting()`. */
function syncClocks(): void {
  const waiting = isWaiting()
  for (const id of clocks.keys()) {
    if (waiting) {
      stopClock(id)
    } else {
      startClock(id)
    }
  }
}

/**
 * Stop (true) or resume (false) every auto-dismiss clock, for the pointer or
 * focus in the region. The clocks run again only once no modal dialog is open.
 */
export function pauseToasts(paused: boolean): void {
  if (paused === isPaused) {
    return
  }
  isPaused = paused
  syncClocks()
}

const modalListeners = new Set<() => void>()
const modalChangeListeners = new Set<() => void>()

function notifyModalChange(): void {
  for (const listener of modalChangeListeners) {
    listener()
  }
}

/** Whether a modal dialog is open now (the region is inert then: nothing in it takes a press). */
export function isModalOpen(): boolean {
  return modalDepth > 0
}

/**
 * A modal dialog opened: success and info clocks stop (an error has none) until
 * the returned function is called, which is safe to call twice. Dialogs may
 * overlap; the clocks continue, with the time they had left, when the last one
 * is released. Listeners (`onModalOpened`) are told at once.
 */
export function enterModal(): () => void {
  modalDepth += 1
  syncClocks()
  for (const listener of modalListeners) {
    listener()
  }
  notifyModalChange()
  let released = false
  return () => {
    if (released) {
      return
    }
    released = true
    modalDepth -= 1
    syncClocks()
    notifyModalChange()
  }
}

/** Call `listener` each time a modal dialog opens (the region lifts itself above it). */
export function onModalOpened(listener: () => void): () => void {
  modalListeners.add(listener)
  return () => {
    modalListeners.delete(listener)
  }
}

export function subscribeModal(listener: () => void): () => void {
  modalChangeListeners.add(listener)
  return () => {
    modalChangeListeners.delete(listener)
  }
}

/** Whether a modal dialog is open; the region marks its controls as unavailable meanwhile. */
export function useModalOpen(): boolean {
  return useSyncExternalStore(subscribeModal, isModalOpen)
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function getToasts(): readonly Toast[] {
  return toasts
}

/** The toasts held now, oldest first. */
export function useToasts(): readonly Toast[] {
  return useSyncExternalStore(subscribe, getToasts)
}

/*
 * The one element toasts keep clear of: a page's bar held at the window's
 * bottom edge. `ToastRegion` places itself above it or below it.
 */
type Clearance = { bar: HTMLElement }

let clearance: Clearance | null = null
const clearanceListeners = new Set<() => void>()

function setClearance(next: Clearance | null): void {
  clearance = next
  for (const listener of clearanceListeners) {
    listener()
  }
}

/**
 * Keep toasts clear of `bar`, an element held at the viewport's bottom edge
 * (position: sticky; inset-block-end: 0) whose box top is where its visible part
 * starts, until the returned function is called. One bar at a time: a later call
 * replaces an earlier one, and a release clears only its own registration (so a
 * StrictMode re-run, which registers the same element again, keeps it).
 */
export function keepToastsClearOf(bar: HTMLElement): () => void {
  const registration: Clearance = { bar }
  setClearance(registration)
  return () => {
    if (clearance === registration) {
      setClearance(null)
    }
  }
}

function subscribeClearance(listener: () => void): () => void {
  clearanceListeners.add(listener)
  return () => {
    clearanceListeners.delete(listener)
  }
}

function getClearance(): HTMLElement | null {
  return clearance?.bar ?? null
}

/** The registered bar, for `ToastRegion`; null when no page registered one. */
export function useToastClearance(): HTMLElement | null {
  return useSyncExternalStore(subscribeClearance, getClearance)
}
