import { useSyncExternalStore } from 'react'

import { JOB_STATUS_LABEL } from '../events/labels'
import { JOB_STATUS_LOOK } from '../events/tones'
import { formatInstant } from '../format'
import { Pill } from '../ui/Pill'
import { formatEta } from './eta'
import { getState, isActive, subscribe } from './store'
import type { ShownJob } from './useJob'

/*
 * One job, as a screen shows it:
 *
 * | state                       | bar                        | words                  |
 * |-----------------------------|----------------------------|------------------------|
 * | queued                      | indeterminate              | Waiting for a worker   |
 * | running, no progress yet    | indeterminate              | Starting…              |
 * | running                     | determinate, with NN%      | (the pill: Rendering)  |
 * | cancel requested, not ended | kept, muted                | Cancelling…            |
 * | done / failed / canceled    | none                       | (the pill)             |
 *
 * Every state also shows its time (`stateTime`): finished (rendered), ended
 * (failed or canceled), started or queued.
 *
 * A list row (`JobProgress`) says "Starting…" in its meter, where the
 * percentage then appears, not in its words: the row's words and lines are the
 * same before and after the first progress, so the row keeps its height. Its
 * figures sit in a slot as wide as "Starting…" from the first active state, so
 * its bar keeps one length while the job waits, starts and runs.
 *
 * `JobState` is what a status region announces: it changes with the state only.
 * `JobMeter` is outside any live region, so progress is never announced.
 */

function isCancelling(shown: ShownJob): boolean {
  return shown.source !== 'read' && shown.job.cancel_requested && isActive(shown.job.status)
}

const STARTING = 'Starting…'

/** A running job with no progress reported yet, and no cancel requested. */
function isStarting(shown: ShownJob): boolean {
  return shown.job.status === 'running' && shown.job.progress <= 0 && !isCancelling(shown)
}

/**
 * What an active job is doing, beside its pill; null when the pill says it all,
 * or when the meter says "Starting…" (`startingInMeter`, a list row).
 */
function activeWords(shown: ShownJob, startingInMeter: boolean): string | null {
  const { job } = shown
  if (isCancelling(shown)) {
    // A requeue keeps the flag, so a queued job can carry it too.
    return 'Cancelling…'
  }
  if (job.status === 'queued') {
    return 'Waiting for a worker'
  }
  return isStarting(shown) && !startingInMeter ? STARTING : null
}

/**
 * The time that matches the job's state, labelled for what it is: when it
 * finished (rendered), ended (failed or canceled — "finished" would read as a
 * completed render), started (running) or was queued. Every job the service
 * reports, from the connection, a job read or an events read, carries the times
 * it recorded; a time it has not recorded is absent, and then when the job was
 * queued is shown, labelled so — never a time presented as one it is not.
 */
function stateTime({ job }: ShownJob): { label: string; iso: string } {
  if (!isActive(job.status) && job.finished_at != null) {
    return { label: job.status === 'done' ? 'finished' : 'ended', iso: job.finished_at }
  }
  if (job.status === 'running' && job.started_at != null) {
    return { label: 'started', iso: job.started_at }
  }
  return { label: 'queued', iso: job.created_at }
}

/** The job's status in words: its pill, what it is doing, and its state's time. */
export function JobState({
  shown,
  lastJobLabel = false,
  startingInMeter = false,
}: {
  shown: ShownJob
  lastJobLabel?: boolean
  /** The meter beside it says "Starting…" (a list row), so these words do not. */
  startingInMeter?: boolean
}) {
  const { job } = shown
  const look = JOB_STATUS_LOOK[job.status]
  const active = isActive(job.status)
  const words = active ? activeWords(shown, startingInMeter) : null
  const time = stateTime(shown)
  return (
    <span className="job-state" data-status={job.status}>
      {lastJobLabel && !active && <span className="job-label">Last job</span>}
      <Pill tone={look.tone} icon={look.icon}>
        {JOB_STATUS_LABEL[job.status]}
      </Pill>
      {words !== null && <span className="job-words">{words}</span>}
      <span className="job-when">
        {time.label} <time dateTime={time.iso}>{formatInstant(time.iso)}</time>
      </span>
    </span>
  )
}

// The worker reports the full fraction a moment before the done state (finalize
// runs between the two writes): a running job stops at 99%, bar included, and
// only the done state says the render finished.
const RUNNING_MAX = 0.99

/**
 * An active job's bar and figures: the percentage once progress is reported
 * (before it, "Starting…" when `startingInMeter`: a list row), the time-left
 * estimate when one is given (the event page only), and "last known" while the
 * connection that reported it is down. With `startingInMeter` the figures sit in
 * a slot at least as wide as "Starting…", even while there are none, so the bar
 * beside it keeps its length.
 */
export function JobMeter({
  shown,
  eta,
  startingInMeter = false,
}: {
  shown: ShownJob
  eta?: number
  startingInMeter?: boolean
}) {
  const live = useSyncExternalStore(subscribe, () => getState().connection === 'live')
  const { job } = shown
  const determinate = job.status === 'running' && job.progress > 0
  const starting = startingInMeter && isStarting(shown)
  const fraction = Math.min(job.progress, RUNNING_MAX)
  // Floored, and capped above, so a running job never reads 100%.
  const percent = determinate ? Math.floor(fraction * 100) : null
  // A refreshed copy is last known too: it stands in for the store's while the connection is down.
  const lastKnown = shown.source !== 'read' && !live
  const estimate = eta === undefined || isCancelling(shown) ? null : formatEta(eta)
  const figures = (starting || percent !== null || estimate !== null || lastKnown) && (
    <span className="job-figures">
      {starting && <span className="job-starting">{STARTING}</span>}
      {percent !== null && <span className="job-percent">{percent}%</span>}
      {estimate !== null && <span className="job-eta">{estimate}</span>}
      {lastKnown && <span className="job-last-known">last known</span>}
    </span>
  )
  return (
    <span className="job-meter" data-cancelling={isCancelling(shown) || undefined}>
      {/* Keyed by mode: an indeterminate bar is one with no value at all. */}
      <progress
        key={determinate ? 'determinate' : 'indeterminate'}
        className="job-bar"
        max={1}
        value={determinate ? fraction : undefined}
        aria-label="Render progress"
      />
      {startingInMeter ? (
        // The slot's width is reserved by its hidden `data-reserve` text (jobs.css).
        <span className="job-slot" data-reserve={STARTING}>
          {figures}
        </span>
      ) : (
        figures
      )}
    </span>
  )
}

/**
 * A list row's job: its state and, while active, a compact meter (no estimate,
 * no live region) that says "Starting…" where its percentage then appears.
 */
export function JobProgress({ shown }: { shown: ShownJob }) {
  return (
    <span className="job-progress">
      <JobState shown={shown} startingInMeter />
      {isActive(shown.job.status) && <JobMeter shown={shown} startingInMeter />}
    </span>
  )
}
