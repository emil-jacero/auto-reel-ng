import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchEvents } from '../api/events'
import type { EventSummary, JobSummary, Problem } from '../api/events'
import { groupByYear, needsRender } from './grouping'
import { JOB_STATUS_LABEL, REASON_LABEL } from './labels'

/**
 * The event list: which events need a render, and why.
 *
 * Read-only. The list is scanned from disk per request, so it is read on mount
 * and on refresh, and nowhere else — no polling, no cache. Loading and failure
 * both replace the list: an earlier list is never shown as current.
 */

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; events: EventSummary[]; fetchedAt: Date }
  | { status: 'failed'; cause: string; detail: string | null }

function describeProblem(problem: Problem): { cause: string; detail: string | null } {
  if (problem.check === 'database') {
    return { cause: "The service can't reach its database.", detail: problem.detail }
  }
  if (problem.event_id != null) {
    return { cause: `Event ${problem.event_id} could not be scanned.`, detail: problem.detail }
  }
  return { cause: problem.title, detail: problem.detail }
}

/** The event folder's name: the last segment of its id. */
function folderName(eventId: string): string {
  return eventId.split('/').pop() ?? eventId
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}

function JobCell({ job }: { job: JobSummary | null | undefined }) {
  if (job == null) {
    return null
  }
  const when = new Date(job.created_at).toLocaleString()
  return (
    <>
      <span className={`job job-${job.status}`}>{JOB_STATUS_LABEL[job.status]}</span>
      {job.status === 'running' && <> {Math.round(job.progress * 100)}%</>}
      <div className="muted">{when}</div>
    </>
  )
}

function EventRow({ event }: { event: EventSummary }) {
  const stale = needsRender(event)
  return (
    <tr>
      <td className="date">{event.date ?? ''}</td>
      <td>
        {event.title ?? folderName(event.event_id)}
        {event.location != null && <span className="muted"> · {event.location}</span>}
      </td>
      <td>
        {event.clip_count}
        {event.new_count > 0 && <span className="badge badge-new">{event.new_count} new</span>}
        {event.missing_count > 0 && (
          <span className="badge badge-missing">{event.missing_count} missing</span>
        )}
      </td>
      <td>
        <span className={stale ? 'pill pill-stale' : 'pill pill-fresh'}>
          {stale ? 'Needs render' : 'Up to date'}
        </span>
        {stale && event.staleness.reasons.length > 0 && (
          <span className="reasons">
            {event.staleness.reasons.map((reason) => REASON_LABEL[reason]).join(', ')}
          </span>
        )}
      </td>
      <td>
        <JobCell job={event.latest_job} />
      </td>
    </tr>
  )
}

function EventTables({ events }: { events: EventSummary[] }) {
  return (
    <>
      {groupByYear(events).map((group) => (
        <div className="table-scroll" key={group.year ?? 'undated'}>
          <table>
            <caption>{group.year ?? 'No date'}</caption>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Event</th>
                <th scope="col">Clips</th>
                <th scope="col">Render</th>
                <th scope="col">Last job</th>
              </tr>
            </thead>
            <tbody>
              {group.events.map((event) => (
                <EventRow key={event.event_id} event={event} />
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  )
}

export function EventList() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [onlyStale, setOnlyStale] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setState({ status: 'loading' })
    fetchEvents(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        switch (result.kind) {
          case 'ok':
            setState({ status: 'ready', events: result.events, fetchedAt: new Date() })
            break
          case 'problem':
            setState({ status: 'failed', ...describeProblem(result.problem) })
            break
          case 'unreachable':
            setState({
              status: 'failed',
              cause: 'The service is not reachable.',
              detail: result.message,
            })
            break
        }
      })
      .catch((error: unknown) => {
        // An abort is a superseding refresh or an unmount, not a failure.
        if (controller.signal.aborted) {
          return
        }
        setState({ status: 'failed', cause: 'The events could not be read.', detail: String(error) })
      })
  }, [])

  useEffect(() => {
    load()
    return () => inFlight.current?.abort()
  }, [load])

  return (
    <main>
      <header>
        <h1>Events</h1>
        <button type="button" onClick={load} disabled={state.status === 'loading'}>
          Refresh
        </button>
      </header>

      {state.status === 'loading' && <p className="muted">Scanning events…</p>}

      {state.status === 'failed' && (
        <div className="failure" role="alert">
          <p>
            <strong>{state.cause}</strong>
          </p>
          {state.detail !== null && <p className="muted">{state.detail}</p>}
        </div>
      )}

      {state.status === 'ready' && (
        <ReadyView
          events={state.events}
          fetchedAt={state.fetchedAt}
          onlyStale={onlyStale}
          setOnlyStale={setOnlyStale}
        />
      )}
    </main>
  )
}

function ReadyView({
  events,
  fetchedAt,
  onlyStale,
  setOnlyStale,
}: {
  events: EventSummary[]
  fetchedAt: Date
  onlyStale: boolean
  setOnlyStale: (value: boolean) => void
}) {
  // Counted over the whole list: the filter changes which rows show, not the summary.
  const staleCount = events.filter(needsRender).length
  const shown = onlyStale ? events.filter(needsRender) : events
  return (
    <>
      <div className="summary">
        <p>
          <strong>
            {staleCount} of {plural(events.length, 'event', 'events')}
          </strong>{' '}
          need rendering.
          <span className="muted"> Scanned {fetchedAt.toLocaleTimeString()}.</span>
        </p>
        <label>
          <input
            type="checkbox"
            checked={onlyStale}
            onChange={(change) => setOnlyStale(change.target.checked)}
          />{' '}
          Only events that need rendering
        </label>
      </div>
      {shown.length === 0 ? (
        <p className="muted">
          {events.length === 0 ? 'No events found.' : 'Nothing needs rendering.'}
        </p>
      ) : (
        <EventTables events={shown} />
      )}
    </>
  )
}
