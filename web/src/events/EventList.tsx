import './list.css'

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import type { MouseEvent, RefObject } from 'react'

import { fetchEvents } from '../api/events'
import type { EventError, EventRow, EventSummary, Problem } from '../api/events'
import { formatInstant } from '../format'
import { MISSING_BLOCKS_ROW } from '../jobs/labels'
import { LiveJobCell } from '../jobs/LiveJobCell'
import { eventHref } from '../route'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { LoadStatus, SkeletonRows } from '../ui/Skeleton'
import { currentEventsVersion, useEventsVersion } from './changes'
import { DATABASE_CAUSE, StalenessCell, folderName, plural } from './common'
import { groupByYear, lookAlikes, needsRender } from './grouping'
import type { YearGroup } from './grouping'
import { FAILURE_LABEL, failureDetail, unansweredFailure } from './labels'
import { CLIP_STATUS_LOOK, FAILURE_LOOK } from './tones'

/**
 * The event list: which events need a render, and why.
 *
 * The list is scanned from disk per request, so it is read on mount, on
 * refresh, and when it is shown after the client recorded that an event changed
 * (`changes.ts`) — nowhere else: no polling, no cache. Loading and failure both
 * replace the list: an earlier list is never shown as current. The one exception
 * is the re-read after an event changed, which keeps the rows, marked as
 * updating, until the new read answers (a failure still replaces them). Events
 * the service could not read arrive as error rows and are shown first, under
 * "Needs attention", with nothing the row does not carry. Each row's job is live
 * (`jobs/LiveJobCell`), with a Render for a row that needs one. A click anywhere
 * on an event row opens its event, as its title does; rows that would read the
 * same (`lookAlikes`) also show their folder's path.
 */

/** `quiet`: a re-read because events changed, which keeps the rows shown. */
type LoadOptions = { quiet?: boolean }

type LoadState =
  | { status: 'loading' }
  // `updating`: a quiet re-read runs, and the rows shown are the last read's.
  | { status: 'ready'; events: EventRow[]; fetchedAt: Date; updating?: boolean }
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

/**
 * A plain click on a row, not on a control and not ending a text selection, opens
 * its title's link. The row gets no role, tab stop or key handler of its own: the
 * title link stays its one keyboard stop.
 */
function openRow(event: MouseEvent<HTMLTableRowElement>): void {
  if (event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
    return
  }
  // Ahead of the click below: the link's own click bubbles back here and stops here.
  if (
    event.target instanceof Element &&
    event.target.closest('a, button, input, label, select, textarea')
  ) {
    return
  }
  if (window.getSelection()?.isCollapsed === false) {
    return
  }
  event.currentTarget.querySelector<HTMLAnchorElement>('.cell-event a[href]')?.click()
}

function EventRow({ event, lookAlike }: { event: EventSummary; lookAlike: boolean }) {
  // Called on every render, whether or not the row shows its path (rules of hooks).
  const pathId = useId()
  return (
    <tr role="row" onClick={openRow}>
      <td role="cell" className="cell-date">
        {event.date != null && <time dateTime={event.date}>{event.date}</time>}
      </td>
      <td role="cell" className="cell-event">
        <a href={eventHref(event.event_id)} aria-describedby={lookAlike ? pathId : undefined}>
          {event.title ?? folderName(event.event_id)}
        </a>
        {event.location != null && <span className="event-location"> · {event.location}</span>}
        {lookAlike && (
          <span id={pathId} className="event-folder">
            {event.event_id}
          </span>
        )}
      </td>
      <td role="cell" className="cell-clips">
        <span className="clip-counts">
          <span className="clip-count">{plural(event.clip_count, 'clip', 'clips')}</span>
          {/* The same tone and icon as the clip statuses on the event page. */}
          {event.new_count > 0 && (
            <span className="badge" data-tone={CLIP_STATUS_LOOK.new.tone}>
              <Icon name={CLIP_STATUS_LOOK.new.icon} />
              {event.new_count} new
            </span>
          )}
          {event.missing_count > 0 && (
            <span className="badge" data-tone={CLIP_STATUS_LOOK.missing.tone}>
              <Icon name={CLIP_STATUS_LOOK.missing.icon} />
              {event.missing_count} missing
            </span>
          )}
        </span>
      </td>
      <td role="cell" className="cell-render">
        <StalenessCell staleness={event.staleness} />
      </td>
      <LiveJobCell
        role="cell"
        className="cell-job"
        eventId={event.event_id}
        staleness={event.staleness}
        latestJob={event.latest_job}
        blockedReason={event.missing_count > 0 ? MISSING_BLOCKS_ROW : undefined}
      />
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
                <a href={eventHref(error.event_id)}>{folderName(error.event_id)}</a>
              </td>
              <td role="cell" className="cell-problem">
                <Pill tone={FAILURE_LOOK[error.failure].tone} icon={FAILURE_LOOK[error.failure].icon}>
                  {FAILURE_LABEL[error.failure]}
                </Pill>
              </td>
              <td role="cell" className="cell-fix">
                {failureDetail(error.event_id, error.detail)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function YearPanel({ group, alike }: { group: YearGroup; alike: ReadonlySet<string> }) {
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
            <EventRow key={event.event_id} event={event} lookAlike={alike.has(event.event_id)} />
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
  // The "All" choice, which Show all events hands focus to.
  const allRef = useRef<HTMLInputElement>(null)
  const inFlight = useRef<AbortController | null>(null)
  // A quiet re-read asked for while a read runs: one more runs after it.
  const pending = useRef(false)
  const version = useEventsVersion()
  // The events version the list was last read at (recorded when the read starts).
  const readVersion = useRef(currentEventsVersion())

  /**
   * Read the list. A plain read (first, Refresh) aborts any read and shows
   * placeholders. A quiet one keeps the rows, marked as updating — unless the list
   * shows a failure, which has no rows to keep — and never restarts a read in
   * flight: it runs once after it instead, so a burst of finished renders cannot
   * restart a whole-library scan forever.
   */
  const load: (options?: LoadOptions) => void = useCallback((options = {}) => {
    const quiet = options.quiet === true
    if (quiet && inFlight.current !== null) {
      pending.current = true
      return
    }
    inFlight.current?.abort()
    pending.current = false
    const controller = new AbortController()
    inFlight.current = controller
    readVersion.current = currentEventsVersion()
    setState((shown) =>
      quiet && shown.status === 'ready' ? { ...shown, updating: true } : { status: 'loading' },
    )
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
          case 'unpublished':
            setState({ status: 'failed', ...unansweredFailure(result) })
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
      .finally(() => {
        if (controller.signal.aborted || inFlight.current !== controller) {
          return
        }
        inFlight.current = null
        if (pending.current) {
          load({ quiet: true })
        }
      })
  }, [])

  useEffect(() => {
    load()
    return () => inFlight.current?.abort()
  }, [load])

  // Read again, in place, when shown after the client recorded that an event
  // changed: while shown, or on return, when the hidden list's rows are still
  // there for App's scroll restore. Declared after the mount effect, so on mount
  // the versions already match and no second read starts; a mark during a read
  // queues one more after it.
  useEffect(() => {
    if (!hidden && version !== readVersion.current) {
      load({ quiet: true })
    }
  }, [hidden, version, load])

  const loading = state.status === 'loading'
  const updating = state.status === 'ready' && state.updating === true
  const rows = state.status === 'ready' ? partition(state.events) : null
  // Show all events hands focus to "All", which exists before the button unmounts.
  const showAll = () => {
    setOnlyStale(false)
    allRef.current?.focus()
  }
  return (
    <main hidden={hidden} className="page event-list">
      <header className="page-header">
        <div className="page-title-row">
          <h1 tabIndex={-1}>Events</h1>
          <div className="toolbar">
            {/* Mounted in every state: it only holds the choice, so a read never moves Refresh. */}
            <FilterControl onlyStale={onlyStale} setOnlyStale={setOnlyStale} allRef={allRef} />
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
          {rows !== null && (rows.events.length > 0 || rows.errors.length > 0) && (
            <Summary events={rows.events} errors={rows.errors} />
          )}
          {state.status === 'ready' && (
            <span>
              Scanned{' '}
              <time dateTime={state.fetchedAt.toISOString()}>
                {formatInstant(state.fetchedAt)}
              </time>
            </span>
          )}
          <LoadStatus message={loading ? 'Scanning events…' : updating ? 'Updating…' : ''} />
          {/*
           * The read's result, mounted in every state and filled only while ready: an
           * operator's read empties it on the way (it passes through loading), so its
           * end is announced even with unchanged counts; a quiet re-read changes it
           * only when the counts change; a filter change, at once. Hidden, because
           * the stat chips show the same counts.
           */}
          <p role="status" className="visually-hidden">
            {rows !== null ? resultText(rows.events, rows.errors, onlyStale) : ''}
          </p>
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

      {rows !== null && (
        <div className="page-content" aria-busy={updating || undefined}>
          <ReadyView
            events={rows.events}
            errors={rows.errors}
            onlyStale={onlyStale}
            onShowAll={showAll}
          />
        </div>
      )}
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
      {events.length > 0 && (
        <li className="stat">
          <Icon name="film" />
          <span>
            <strong>{staleCount}</strong> of {plural(events.length, 'event', 'events')} need
            rendering
          </span>
        </li>
      )}
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

/**
 * What the status message says once a read is shown: how many events are shown,
 * how many of them need rendering, and how many need attention when any do.
 */
function resultText(events: EventSummary[], errors: EventError[], onlyStale: boolean): string {
  if (events.length === 0 && errors.length === 0) {
    return 'No events found.'
  }
  const stale = events.filter(needsRender).length
  const total = plural(events.length, 'event', 'events')
  let text: string
  if (events.length === 0) {
    text = 'No other events.'
  } else if (!onlyStale) {
    text = `Showing ${total}; ${stale} ${stale === 1 ? 'needs' : 'need'} rendering.`
  } else if (stale === 0) {
    text =
      events.length === 1
        ? 'The one event does not need rendering.'
        : `None of the ${total} needs rendering.`
  } else {
    text = `Showing the ${stale} of ${total} that ${stale === 1 ? 'needs' : 'need'} rendering.`
  }
  if (errors.length > 0) {
    text += ` ${errors.length} ${errors.length === 1 ? 'needs' : 'need'} attention.`
  }
  return text
}

/** All events, or only those that need a render: two native radios. */
function FilterControl({
  onlyStale,
  setOnlyStale,
  allRef,
}: {
  onlyStale: boolean
  setOnlyStale: (value: boolean) => void
  allRef: RefObject<HTMLInputElement | null>
}) {
  const name = useId()
  return (
    <fieldset className="segmented">
      <legend className="visually-hidden">Show</legend>
      <input
        ref={allRef}
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
  onShowAll,
}: {
  events: EventSummary[]
  errors: EventError[]
  onlyStale: boolean
  onShowAll: () => void
}) {
  const shown = onlyStale ? events.filter(needsRender) : events
  // Over every readable event, not the filtered ones: a path line never comes and
  // goes with the filter.
  const alike = lookAlikes(events)
  return (
    <>
      {/* Error rows need action too, so the filter never hides them. */}
      {errors.length > 0 && <AttentionPanel errors={errors} />}
      {shown.length === 0 ? (
        <EmptyState events={events} errors={errors} onShowAll={onShowAll} />
      ) : (
        groupByYear(shown).map((group) => (
          <YearPanel key={group.year ?? 'undated'} group={group} alike={alike} />
        ))
      )}
    </>
  )
}

/** No event shown: none found, the filter hides every one, or only error rows. */
function EmptyState({
  events,
  errors,
  onShowAll,
}: {
  events: EventSummary[]
  errors: EventError[]
  onShowAll: () => void
}) {
  if (events.length > 0) {
    return (
      <div className="empty-state">
        <Icon name="check" size={20} />
        <p className="empty-title">Nothing needs rendering</p>
        <p>
          {events.length === 1
            ? 'The one event is up to date.'
            : `All ${events.length} events are up to date.`}
        </p>
        <button type="button" className="btn btn-secondary" onClick={onShowAll}>
          Show all events
        </button>
      </div>
    )
  }
  if (errors.length > 0) {
    return (
      <div className="empty-state">
        <Icon name="film" size={20} />
        <p>No other events.</p>
      </div>
    )
  }
  return (
    <div className="empty-state">
      <Icon name="film" size={20} />
      <p className="empty-title">No events yet</p>
      <p>
        The service found no event folders in its project. Add a folder of clips for an event,
        then press Refresh.
      </p>
    </div>
  )
}
