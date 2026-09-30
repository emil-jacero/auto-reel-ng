import './list.css'

import { useCallback, useEffect, useId, useRef, useState } from 'react'

import { fetchEvents } from '../api/events'
import type { EventError, EventRow, EventSummary, Problem } from '../api/events'
import { eventHref } from '../route'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { LoadStatus, SkeletonRows } from '../ui/Skeleton'
import { currentEventsVersion, useEventsVersion } from './changes'
import {
  DATABASE_CAUSE,
  JobCell,
  StalenessCell,
  UNREACHABLE_CAUSE,
  folderName,
  plural,
} from './common'
import { groupByYear, needsRender } from './grouping'
import type { YearGroup } from './grouping'
import { FAILURE_LABEL } from './labels'
import { FAILURE_LOOK } from './tones'

/**
 * The event list: which events need a render, and why.
 *
 * It only reads. The list is scanned from disk per request, so it is read on
 * mount, on refresh, and when it is shown after the client recorded that an
 * event changed (`changes.ts`) — nowhere else: no polling, no cache. Loading and
 * failure both replace the list: an earlier list is never shown as current.
 * Events the service could not read arrive as error rows and are shown first,
 * under "Needs attention", with nothing the row does not carry.
 */

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; events: EventRow[]; fetchedAt: Date }
  | { status: 'failed'; cause: string; detail: string | null }

function describeProblem(problem: Problem): { cause: string; detail: string | null } {
  if (problem.check === 'database') {
    return { cause: DATABASE_CAUSE, detail: problem.detail }
  }
  if (problem.status === 502) {
    return { cause: 'The project could not be scanned.', detail: problem.detail }
  }
  return { cause: problem.title, detail: problem.detail }
}

function EventRow({ event }: { event: EventSummary }) {
  return (
    <tr role="row">
      <td role="cell" className="cell-date">
        {event.date != null && <time dateTime={event.date}>{event.date}</time>}
      </td>
      <td role="cell" className="cell-event">
        <a href={eventHref(event.event_id)}>{event.title ?? folderName(event.event_id)}</a>
        {event.location != null && <span className="event-location"> · {event.location}</span>}
      </td>
      <td role="cell" className="cell-clips">
        <span className="clip-count">{plural(event.clip_count, 'clip', 'clips')}</span>
        {event.new_count > 0 && (
          <span className="badge" data-tone="info">
            {event.new_count} new
          </span>
        )}
        {event.missing_count > 0 && (
          <span className="badge" data-tone="err">
            {event.missing_count} missing
          </span>
        )}
      </td>
      <td role="cell" className="cell-render">
        <StalenessCell staleness={event.staleness} />
      </td>
      {/* Labelled only when it holds a job: at narrow width the label shows beside it. */}
      <td
        role="cell"
        className="cell-job"
        data-label={event.latest_job != null ? 'Last job' : undefined}
      >
        <JobCell job={event.latest_job} />
      </td>
    </tr>
  )
}

function AttentionPanel({ errors }: { errors: EventError[] }) {
  const headingId = useId()
  return (
    <section className="panel attention-panel">
      <header className="panel-header">
        <Icon name="alert-triangle" />
        <h2 id={headingId}>Needs attention</h2>
        <span className="panel-meta">{plural(errors.length, 'event', 'events')}</span>
      </header>
      <table className="data-table attention-table" role="table" aria-labelledby={headingId}>
        <colgroup>
          <col className="col-folder" />
          <col className="col-problem" />
          <col className="col-fix" />
        </colgroup>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col">
              Folder
            </th>
            <th role="columnheader" scope="col">
              Problem
            </th>
            <th role="columnheader" scope="col">
              How to fix
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {errors.map((error) => (
            <tr role="row" key={error.event_id}>
              <td role="cell" className="cell-folder">
                {folderName(error.event_id)}
              </td>
              <td role="cell" className="cell-problem">
                <Pill tone={FAILURE_LOOK[error.failure].tone} icon={FAILURE_LOOK[error.failure].icon}>
                  {FAILURE_LABEL[error.failure]}
                </Pill>
              </td>
              <td role="cell" className="cell-fix">
                {error.detail}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function YearPanel({ group }: { group: YearGroup }) {
  const headingId = useId()
  return (
    <section className="panel">
      <header className="panel-header">
        <h2 id={headingId}>{group.year ?? 'No date'}</h2>
        <span className="panel-meta">{plural(group.events.length, 'event', 'events')}</span>
      </header>
      <table className="data-table event-table" role="table" aria-labelledby={headingId}>
        <colgroup>
          <col className="col-date" />
          <col className="col-event" />
          <col className="col-clips" />
          <col className="col-render" />
          <col className="col-job" />
        </colgroup>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col">
              Date
            </th>
            <th role="columnheader" scope="col">
              Event
            </th>
            <th role="columnheader" scope="col">
              Clips
            </th>
            <th role="columnheader" scope="col">
              Render
            </th>
            <th role="columnheader" scope="col">
              Last job
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {group.events.map((event) => (
            <EventRow key={event.event_id} event={event} />
          ))}
        </tbody>
      </table>
    </section>
  )
}

/** `hidden` keeps the list mounted, and its state, while an event page is shown. */
export function EventList({ hidden }: { hidden: boolean }) {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [onlyStale, setOnlyStale] = useState(false)
  const inFlight = useRef<AbortController | null>(null)
  const version = useEventsVersion()
  // The events version the list was last read at (recorded when the read starts).
  const readVersion = useRef(currentEventsVersion())

  const load = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    readVersion.current = currentEventsVersion()
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
              cause: UNREACHABLE_CAUSE,
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

  // Read again when shown after the client recorded that an event changed.
  // Declared after the mount effect, so on mount the versions already match and
  // no second read starts; a mark during a read starts one more, aborting it.
  useEffect(() => {
    if (!hidden && version !== readVersion.current) {
      load()
    }
  }, [hidden, version, load])

  const loading = state.status === 'loading'
  const rows = state.status === 'ready' ? partition(state.events) : null
  return (
    <main hidden={hidden} className="page event-list">
      <header className="page-header">
        <div className="page-title-row">
          <h1 tabIndex={-1}>Events</h1>
          <div className="toolbar">
            {rows !== null && <FilterControl onlyStale={onlyStale} setOnlyStale={setOnlyStale} />}
            {/* Busy, not disabled, while reading: it keeps keyboard focus. */}
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={loading || undefined}
              aria-busy={loading || undefined}
              onClick={() => {
                if (!loading) {
                  load()
                }
              }}
            >
              <Icon name="refresh" />
              Refresh
            </button>
          </div>
        </div>
        <div className="page-meta">
          {rows !== null && <Summary events={rows.events} errors={rows.errors} />}
          {state.status === 'ready' && (
            <span>Scanned {state.fetchedAt.toLocaleTimeString()}</span>
          )}
          <LoadStatus message={loading ? 'Scanning events…' : ''} />
        </div>
      </header>

      {loading && (
        <div className="panel" aria-hidden="true">
          <div className="panel-header">
            <span className="skeleton skeleton-heading" />
          </div>
          <SkeletonRows rows={8} />
        </div>
      )}

      {state.status === 'failed' && <Alert tone="err" title={state.cause} detail={state.detail} />}

      {rows !== null && <ReadyView events={rows.events} errors={rows.errors} onlyStale={onlyStale} />}
    </main>
  )
}

/** Split the rows by `kind`, keeping each side in the service's order. */
function partition(rows: readonly EventRow[]): { events: EventSummary[]; errors: EventError[] } {
  const events: EventSummary[] = []
  const errors: EventError[] = []
  for (const row of rows) {
    if (row.kind === 'error') {
      errors.push(row)
    } else {
      events.push(row)
    }
  }
  return { events, errors }
}

/** The summary's words as stat chips, counted over the whole list whatever the filter shows. */
function Summary({ events, errors }: { events: EventSummary[]; errors: EventError[] }) {
  const staleCount = events.filter(needsRender).length
  return (
    <ul className="stats">
      <li className="stat">
        <Icon name="film" />
        <span>
          <strong>{staleCount}</strong> of {plural(events.length, 'event', 'events')} need rendering
        </span>
      </li>
      {errors.length > 0 && (
        <li className="stat" data-tone="warn">
          <Icon name="alert-triangle" />
          <span>
            <strong>{errors.length}</strong> {errors.length === 1 ? 'needs' : 'need'} attention
          </span>
        </li>
      )}
    </ul>
  )
}

/** All events, or only those that need a render: two native radios. */
function FilterControl({
  onlyStale,
  setOnlyStale,
}: {
  onlyStale: boolean
  setOnlyStale: (value: boolean) => void
}) {
  const name = useId()
  return (
    <fieldset className="segmented">
      <legend className="visually-hidden">Show</legend>
      <input
        className="visually-hidden"
        type="radio"
        id={`${name}-all`}
        name={name}
        checked={!onlyStale}
        onChange={() => setOnlyStale(false)}
      />
      <label htmlFor={`${name}-all`}>All</label>
      <input
        className="visually-hidden"
        type="radio"
        id={`${name}-stale`}
        name={name}
        checked={onlyStale}
        onChange={() => setOnlyStale(true)}
      />
      <label htmlFor={`${name}-stale`}>Needs render</label>
    </fieldset>
  )
}

function ReadyView({
  events,
  errors,
  onlyStale,
}: {
  events: EventSummary[]
  errors: EventError[]
  onlyStale: boolean
}) {
  const shown = onlyStale ? events.filter(needsRender) : events
  return (
    <>
      {/* Error rows need action too, so the filter never hides them. */}
      {errors.length > 0 && <AttentionPanel errors={errors} />}
      {shown.length === 0 ? (
        <p className="empty-state">
          <Icon name="film" size={20} />
          {events.length > 0
            ? 'Nothing needs rendering.'
            : errors.length === 0
              ? 'No events found.'
              : 'No other events.'}
        </p>
      ) : (
        groupByYear(shown).map((group) => <YearPanel key={group.year ?? 'undated'} group={group} />)
      )}
    </>
  )
}
