import type { Ms } from './model.ts'
import { nextClip } from './follow.ts'
import type { Skip } from '../preview/playback.ts'

/*
 * The Timeline's standby slot (change `seamless-playback`, design D2): where play goes on
 * after a clip at a plain boundary, the standby's state while it loads, seeks, starts early
 * (the lead) and is cancelled, and what the boundary does with it. Pure: the hook turns
 * media events into `StandbyEvent`s and acts on the answers.
 */

export type Target = { clip: number; ms: Ms }

type Playable = { durationMs: Ms; spans: readonly Skip[] }

/**
 * Where play goes on after `clip` at a plain boundary: `nextClip`'s answer (the first clip
 * with kept footage, at its first kept frame, so the end of a leading cut). Null at the end
 * of the timeline, and when a black card opens the next clip's chapter (the card bridge
 * loads it, as today).
 */
export function standbyTarget(
  clips: readonly Playable[],
  gaps: readonly { clip: number }[],
  clip: number,
): Target | null {
  const next = nextClip(clips, clip)
  if (next === null || gaps.some((gap) => gap.clip === next.clip)) {
    return null
  }
  return { clip: next.clip, ms: next.ms }
}

export type Standby =
  | { kind: 'idle' }
  | { kind: 'loading' | 'seeking' | 'ready'; target: Target; address: string }
  // the early start has run: `play()` was called at `playAt` (performance.now)
  | { kind: 'started'; target: Target; address: string; playAt: number }

export type StandbyEvent =
  | 'loadedmetadata'
  // the sought position landed (the hook sends it with `readyState >= 2` and not `seeking`)
  | 'seeked'
  | 'error'
  | 'released'
  // the lead was cancelled: the hook paused the standby and sought it back
  | 'cancelled'
  | { type: 'started'; playAt: number }

export const IDLE: Standby = { kind: 'idle' }

function sameTarget(a: Target, b: Target): boolean {
  return a.clip === b.clip && a.ms === b.ms
}

/**
 * Points the standby at `target` (null: nothing to hold). The same target at the same
 * address leaves it as it is; any other re-points the slot, which loads again (also while
 * it was loading, seeking or started). `loading` always means the hook REASSIGNS the
 * slot's src (and calls `load()`), even for the same address with a new in-point: leaving
 * `loading` needs a fresh `loadedmetadata`, which a bare seek of an element that already
 * holds the address would never fire.
 */
export function standbyAim(s: Standby, target: Target | null, address: string): Standby {
  if (target === null) {
    return IDLE
  }
  if (s.kind !== 'idle' && s.address === address && sameTarget(s.target, target)) {
    return s
  }
  return { kind: 'loading', target, address }
}

export function standbyStep(s: Standby, e: StandbyEvent): Standby {
  if (e === 'error' || e === 'released') {
    return IDLE
  }
  if (typeof e === 'object') {
    // a start is valid from `ready` only: never on a standby that is still seeking
    return s.kind === 'ready' ? { kind: 'started', target: s.target, address: s.address, playAt: e.playAt } : s
  }
  switch (e) {
    case 'loadedmetadata':
      return s.kind === 'loading' ? { kind: 'seeking', target: s.target, address: s.address } : s
    case 'seeked':
      return s.kind === 'seeking' ? { kind: 'ready', target: s.target, address: s.address } : s
    case 'cancelled':
      // never straight to `ready`: only the seek back that lands leads there
      return s.kind === 'started' ? { kind: 'seeking', target: s.target, address: s.address } : s
    default:
      return s
  }
}

/**
 * At the early start's timer and at the decision on the shown slot's last kept frame (and
 * again if it is missed): hand over, wait for the standby (it holds `want` and is on its
 * way), or load as today.
 */
export function atBoundary(s: Standby, want: Target, address: string): 'hand-over' | 'wait' | 'load' {
  if (s.kind === 'idle' || s.address !== address || !sameTarget(s.target, want)) {
    return 'load'
  }
  return s.kind === 'loading' || s.kind === 'seeking' ? 'wait' : 'hand-over'
}

/**
 * Play from inside the end slack of a clip goes on at the next clip (`startFrom`): when the
 * standby already holds that very target, Play hands over to it (or waits for it) as the
 * boundary does, and the shown slot is never loaded with the next clip. Any other start loads.
 */
export function atPlay(
  s: Standby,
  at: { clip: number },
  start: Target,
  address: string,
): 'hand-over' | 'wait' | 'load' {
  return start.clip === at.clip ? 'load' : atBoundary(s, start, address)
}
