import { useSyncExternalStore } from 'react'

import { JOB_STATUS_LABEL } from '../events/labels'
import { JOB_STATUS_LOOK } from '../events/tones'
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
 * Every state also shows its time (`stateTime`): finished, started or queued.
 *
 * `JobState` is what a status region announces: it changes with the state only.
 * `JobMeter` is outside any live region, so progress is never announced.
 */

// Short and locale-aware, with the year only when it is not this one; the exact
// instant stays in `dateTime`.
const THIS_YEAR = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const OTHER_YEAR = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

function formatTime(iso: string): string {
  const date = new Date(iso)
  return (date.getFullYear() === new Date().getFullYear() ? THIS_YEAR : OTHER_YEAR).format(date)
}

function isCancelling(shown: ShownJob): boolean {
  return shown.source === 'live' && shown.job.cancel_requested && isActive(shown.job.status)
}

/** What an active job is doing, beside its pill; null when the pill says it all. */
function activeWords(shown: ShownJob): string | null {
  const { job } = shown
  if (isCancelling(shown)) {
    // A requeue keeps the flag, so a queued job can carry it too.
    return 'Cancelling…'
  }
  if (job.status === 'queued') {
    return 'Waiting for a worker'
  }
  return job.progress > 0 ? null : 'Starting…'
}

/**
 * The time that matches the job's state, labelled for what it is: when it
 * finished (ended), started (running) or was queued. Only a full `JobOut` (from
 * the connection or a job read) reports the first two; a read's summary carries
 * only when the job was queued, so that is shown, labelled so, when the matching
 * time is absent — never a time presented as one it is not.
 */
function stateTime(shown: ShownJob): { label: string; iso: string } {
  if (shown.source === 'live') {
    const { job } = shown
    if (!isActive(job.status) && job.finished_at != null) {
      return { label: 'finished', iso: job.finished_at }
    }
    if (job.status === 'running' && job.started_at != null) {
      return { label: 'started', iso: job.started_at }
    }
  }
  return { label: 'queued', iso: shown.job.created_at }
}

/** The job's status in words: its pill, what it is doing, and its state's time. */
export function JobState({
  shown,
  lastJobLabel = false,
}: {
  shown: ShownJob
  lastJobLabel?: boolean
}) {
  const { job } = shown
  const look = JOB_STATUS_LOOK[job.status]
  const active = isActive(job.status)
  const words = active ? activeWords(shown) : null
  const time = stateTime(shown)
  return (
    <span className="job-state" data-status={job.status}>
      {lastJobLabel && !active && <span className="job-label">Last job</span>}
      <Pill tone={look.tone} icon={look.icon}>
        {JOB_STATUS_LABEL[job.status]}
      </Pill>
      {words !== null && <span className="job-words">{words}</span>}
      <span className="job-when">
        {time.label} <time dateTime={time.iso}>{formatTime(time.iso)}</time>
      </span>
    </span>
  )
}

/**
 * An active job's bar and figures: the percentage once progress is reported,
 * the time-left estimate when one is given (the event page only), and "last
 * known" while the connection that reported it is down.
 */
export function JobMeter({ shown, eta }: { shown: ShownJob; eta?: number }) {
  const live = useSyncExternalStore(subscribe, () => getState().connection === 'live')
  const { job } = shown
  const determinate = job.status === 'running' && job.progress > 0
  // Floored, so a running job never reads 100%.
  const percent = determinate ? Math.floor(job.progress * 100) : null
  const lastKnown = shown.source === 'live' && !live
  const estimate = eta === undefined || isCancelling(shown) ? null : formatEta(eta)
  return (
    <span className="job-meter" data-cancelling={isCancelling(shown) || undefined}>
      {/* Keyed by mode: an indeterminate bar is one with no value at all. */}
      <progress
        key={determinate ? 'determinate' : 'indeterminate'}
        className="job-bar"
        max={1}
        value={determinate ? job.progress : undefined}
        aria-label="Render progress"
      />
      {(percent !== null || estimate !== null || lastKnown) && (
        <span className="job-figures">
          {percent !== null && <span className="job-percent">{percent}%</span>}
          {estimate !== null && <span className="job-eta">{estimate}</span>}
          {lastKnown && <span className="job-last-known">last known</span>}
        </span>
      )}
    </span>
  )
}

/** A list row's job: its state and, while active, a compact meter (no estimate, no live region). */
export function JobProgress({ shown }: { shown: ShownJob }) {
  return (
    <span className="job-progress">
      <JobState shown={shown} />
      {isActive(shown.job.status) && <JobMeter shown={shown} />}
    </span>
  )
}
