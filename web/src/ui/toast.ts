import { useSyncExternalStore } from 'react'

/*
 * Toasts: a small module store, shown by `ToastRegion` (rendered once by the
 * shell). Call `toast.success(message)`, `toast.info(message)` or
 * `toast.error(message)`, optionally with a link: `{ action: { label, href } }`.
 *
 * Success and info toasts dismiss themselves after 5 s. While the region is
 * paused (pointer or focus inside it) their clocks stop, keeping the time left.
 * Errors stay until dismissed. At most three are held: a fourth drops the oldest
 * non-error toast, or the oldest toast when all three are errors.
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

function startClock(id: number): void {
  const clock = clocks.get(id)
  if (clock === undefined || clock.timer !== undefined || isPaused) {
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
  const added: Toast = { id: nextId, tone, message, ...options }
  nextId += 1
  let held = toasts
  if (held.length >= MAX_HELD) {
    const dropped = held.find((shown) => shown.tone !== 'error') ?? held[0]
    stopClock(dropped.id)
    clocks.delete(dropped.id)
    held = held.filter((shown) => shown.id !== dropped.id)
  }
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

/** Stop (true) or resume (false) every auto-dismiss clock. */
export function pauseToasts(paused: boolean): void {
  if (paused === isPaused) {
    return
  }
  isPaused = paused
  for (const id of clocks.keys()) {
    if (paused) {
      stopClock(id)
    } else {
      startClock(id)
    }
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getSnapshot(): readonly Toast[] {
  return toasts
}

/** The toasts held now, oldest first. */
export function useToasts(): readonly Toast[] {
  return useSyncExternalStore(subscribe, getSnapshot)
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
