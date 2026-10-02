import type { JobStatus } from '../api/jobs'

/*
 * Which job statuses are still going. Kept apart from `store.ts` (the socket, the
 * toasts), so the pure rules in `shownJob.ts` can run under `npm test`.
 */

// Whether a status is active (queued or running); the other statuses are final.
// A `Record` over the generated union, so a new status fails `tsc --noEmit` here.
export const ACTIVE: Record<JobStatus, boolean> = {
  queued: true,
  running: true,
  done: false,
  failed: false,
  canceled: false,
}

/** Queued or running: not yet ended. */
export function isActive(status: JobStatus): boolean {
  return ACTIVE[status]
}
