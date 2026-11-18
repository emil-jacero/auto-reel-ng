// Undo/redo history around the draft reducer (editor-undo design D1). Pure: states are immutable
// and shared structurally, so keeping 200 of them is cheap.

export const MAX_STEPS = 200
export const COALESCE_MS = 1000

// `labels[i]` names the edit that left `past[i]`; `futureLabels` is aligned with `future` the same
// way (last entry = the next redo). `key`/`at` identify the open coalescing step, if any.
export type History<S> = {
  past: S[]
  present: S
  future: S[]
  labels: string[]
  futureLabels: string[]
  key?: string
  at?: number
}

export function cleared<S>(present: S): History<S> {
  return { past: [], present, future: [], labels: [], futureLabels: [] }
}

export function record<S>(
  h: History<S>,
  next: S,
  label: string,
  coalesceKey?: string,
  now: number = Date.now(),
): History<S> {
  if (next === h.present) return h
  if (
    coalesceKey !== undefined &&
    h.key === coalesceKey &&
    h.at !== undefined &&
    now - h.at < COALESCE_MS &&
    h.past.length > 0
  ) {
    // Same field, typed in quick succession: fold into the open step.
    return { ...h, present: next, future: [], futureLabels: [], at: now }
  }
  let past = [...h.past, h.present]
  let labels = [...h.labels, label]
  if (past.length > MAX_STEPS) {
    past = past.slice(past.length - MAX_STEPS)
    labels = labels.slice(labels.length - MAX_STEPS)
  }
  return {
    past,
    present: next,
    future: [],
    labels,
    futureLabels: [],
    key: coalesceKey,
    at: coalesceKey === undefined ? undefined : now,
  }
}

export function undo<S>(h: History<S>): History<S> {
  if (h.past.length === 0) return h
  return {
    past: h.past.slice(0, -1),
    present: h.past[h.past.length - 1],
    future: [...h.future, h.present],
    labels: h.labels.slice(0, -1),
    futureLabels: [...h.futureLabels, h.labels[h.labels.length - 1]],
  }
}

export function redo<S>(h: History<S>): History<S> {
  if (h.future.length === 0) return h
  return {
    past: [...h.past, h.present],
    present: h.future[h.future.length - 1],
    future: h.future.slice(0, -1),
    labels: [...h.labels, h.futureLabels[h.futureLabels.length - 1]],
    futureLabels: h.futureLabels.slice(0, -1),
  }
}

export const canUndo = <S>(h: History<S>): boolean => h.past.length > 0
export const canRedo = <S>(h: History<S>): boolean => h.future.length > 0

// Label of the edit Undo would revert / Redo would re-apply, for "Undo <label>" menus.
export const undoLabel = <S>(h: History<S>): string | undefined => h.labels[h.labels.length - 1]
export const redoLabel = <S>(h: History<S>): string | undefined =>
  h.futureLabels[h.futureLabels.length - 1]
