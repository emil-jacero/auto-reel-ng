import './detail.css'

import { useCallback, useEffect, useId, useRef, useState } from 'react'

import { fetchEvent } from '../api/event'
import type { Chapter, Clip, EventDetail as EventDetailData } from '../api/event'
import type { EventFailure, Problem } from '../api/events'
import { LIST_HREF } from '../route'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { LoadStatus, SkeletonRows } from '../ui/Skeleton'
import {
  DATABASE_CAUSE,
  JobCell,
  StalenessCell,
  UNREACHABLE_CAUSE,
  folderName,
  formatBytes,
  plural,
} from './common'
import { CLIP_STATUS_LABEL, FAILURE_LABEL } from './labels'
import { CLIP_STATUS_LOOK, FAILURE_LOOK } from './tones'

/**
 * One event's page: its chapters and clips in play order, and whether it needs
 * a render.
 *
 * It only reads, like the list: read on mount and on refresh, never polled.
 * Loading and failure both replace the content, so an earlier state of the
 * event is never shown as current. Mounted once per event (keyed by id).
 */

type Failure = {
  cause: string
  detail: string | null
  /** The failure kind, shown in the list's "Needs attention" words. */
  failure?: EventFailure
  /** The event does not exist: offer the way back. */
  notFound?: boolean
}

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; event: EventDetailData; fetchedAt: Date }
  | ({ status: 'failed' } & Failure)

function describeProblem(problem: Problem, eventId: string): Failure {
  if (problem.status === 404) {
    return {
      cause: `No event “${folderName(eventId)}” under the project root.`,
      detail: problem.detail,
      notFound: true,
    }
  }
  if (problem.status === 502) {
    return {
      cause: 'This event could not be read.',
      detail: problem.detail,
      failure: problem.failure ?? undefined,
    }
  }
  if (problem.check === 'database') {
    return { cause: DATABASE_CAUSE, detail: problem.detail }
  }
  return { cause: problem.title, detail: problem.detail }
}

export function EventDetail({ eventId }: { eventId: string }) {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const inFlight = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setState({ status: 'loading' })
    fetchEvent(eventId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        switch (result.kind) {
          case 'ok':
            setState({ status: 'ready', event: result.event, fetchedAt: new Date() })
            break
          case 'problem':
            setState({ status: 'failed', ...describeProblem(result.problem, eventId) })
            break
          case 'unreachable':
            setState({ status: 'failed', cause: UNREACHABLE_CAUSE, detail: result.message })
            break
        }
      })
      .catch((error: unknown) => {
        // An abort is a superseding refresh or navigating away, not a failure.
        if (controller.signal.aborted) {
          return
        }
        setState({ status: 'failed', cause: 'The event could not be read.', detail: String(error) })
      })
  }, [eventId])

  useEffect(() => {
    load()
    return () => inFlight.current?.abort()
  }, [load])

  const name =
    state.status === 'ready' ? (state.event.title ?? folderName(eventId)) : folderName(eventId)
  useEffect(() => {
    document.title = `${name} — auto-reel`
  }, [name])

  const loading = state.status === 'loading'
  return (
    <main className="page event-detail">
      <header className="page-header">
        <a className="back-link" href={LIST_HREF}>
          <Icon name="chevron-left" />
          Events
        </a>
        <div className="page-title-row">
          <h1 tabIndex={-1}>{name}</h1>
          <div className="page-actions">
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
        {state.status === 'ready' && <EventFacts event={state.event} />}
        <div className="page-meta">
          {state.status === 'ready' && (
            <Counts clips={state.event.chapters.flatMap((chapter) => chapter.clips)} />
          )}
          {state.status === 'ready' && <span>Read {state.fetchedAt.toLocaleTimeString()}</span>}
          <LoadStatus message={loading ? 'Reading event…' : ''} />
        </div>
      </header>

      {loading && (
        <div className="panel" aria-hidden="true">
          <div className="panel-header">
            <span className="skeleton skeleton-heading" />
          </div>
          <SkeletonRows rows={4} />
        </div>
      )}

      {state.status === 'failed' && (
        <Alert
          tone="err"
          title={
            <>
              {state.cause}{' '}
              {state.failure !== undefined && (
                <Pill tone={FAILURE_LOOK[state.failure].tone} icon={FAILURE_LOOK[state.failure].icon}>
                  {FAILURE_LABEL[state.failure]}
                </Pill>
              )}
            </>
          }
          detail={state.detail}
          action={
            state.notFound === true ? (
              <a className="btn btn-secondary" href={LIST_HREF}>
                <Icon name="chevron-left" />
                Back to the event list
              </a>
            ) : undefined
          }
        />
      )}

      {state.status === 'ready' && <ReadyView event={state.event} />}
    </main>
  )
}

/** The header's facts: date and location, description, verdict and latest job. */
function EventFacts({ event }: { event: EventDetailData }) {
  const facts = [event.date, event.location].filter((fact) => fact != null)
  return (
    <>
      {facts.length > 0 && <p className="event-facts">{facts.join(' · ')}</p>}
      {event.description != null && <p className="description">{event.description}</p>}
      <div className="status-line">
        <StalenessCell staleness={event.staleness} />
        {event.latest_job != null && (
          <span className="status-job">
            <span className="status-label">Last job</span>
            <JobCell job={event.latest_job} />
          </span>
        )}
      </div>
    </>
  )
}

function ReadyView({ event }: { event: EventDetailData }) {
  const clips = event.chapters.flatMap((chapter) => chapter.clips)
  const hasNamedChapter = event.chapters.some((chapter) => chapter.name !== '')
  return (
    <>
      {event.missing.length > 0 && (
        <Alert
          tone="warn"
          title={
            <>
              <code>reel.yaml</code> lists clips that are not on disk
            </>
          }
          detail={event.missing.join(', ')}
        />
      )}

      {clips.length === 0 ? (
        <p className="empty-state">
          <Icon name="film" size={20} />
          No clips.
        </p>
      ) : (
        // A chapter's name is unique within an event, so it is a stable key.
        event.chapters.map((chapter) => (
          <ChapterPanel
            key={chapter.name}
            chapter={chapter}
            heading={chapter.name !== '' ? chapter.name : hasNamedChapter ? 'Main' : 'Clips'}
          />
        ))
      )}
    </>
  )
}

/** `N clips · <total size> · k new · m missing · i ignored`, zero counts omitted. */
function Counts({ clips }: { clips: Clip[] }) {
  const count = (status: Clip['status']) => clips.filter((clip) => clip.status === status).length
  const sizes = clips.flatMap((clip) => (clip.size == null ? [] : [clip.size]))
  // Only known sizes are summed; a missing clip has none, and none is not zero.
  const parts = [plural(clips.length, 'clip', 'clips')]
  if (sizes.length > 0) {
    parts.push(formatBytes(sizes.reduce((sum, size) => sum + size, 0)))
  }
  for (const [status, label] of [
    ['new', 'new'],
    ['missing', 'missing'],
    ['ignored', 'ignored'],
  ] as const) {
    const n = count(status)
    if (n > 0) {
      parts.push(`${n} ${label}`)
    }
  }
  return <strong className="counts">{parts.join(' · ')}</strong>
}

/** The identity's last segment: the file name inside its chapter folder. */
function fileName(identity: string): string {
  return identity.split('/').pop() ?? identity
}

function ChapterPanel({ chapter, heading }: { chapter: Chapter; heading: string }) {
  // Chapter names hold spaces and non-ASCII letters, so the id is generated.
  const headingId = useId()
  return (
    <section className="panel">
      <header className="panel-header">
        <h2 id={headingId}>{heading}</h2>
        <span className="panel-meta">{plural(chapter.clips.length, 'clip', 'clips')}</span>
      </header>
      <table className="data-table clip-table" role="table" aria-labelledby={headingId}>
        <colgroup>
          <col className="col-pos" />
          <col className="col-file" />
          <col className="col-status" />
          <col className="col-size" />
          <col className="col-mtime" />
        </colgroup>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col">
              #
            </th>
            <th role="columnheader" scope="col">
              File
            </th>
            <th role="columnheader" scope="col">
              Status
            </th>
            <th role="columnheader" scope="col">
              Size
            </th>
            <th role="columnheader" scope="col">
              Modified
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {chapter.clips.map((clip, index) => (
            <tr role="row" key={clip.identity} className="clip-row" data-status={clip.status}>
              <td role="cell" className="cell-pos">
                {index + 1}
              </td>
              <td role="cell" className="cell-file">
                {fileName(clip.identity)}
              </td>
              <td role="cell" className="cell-status">
                <Pill
                  tone={CLIP_STATUS_LOOK[clip.status].tone}
                  icon={CLIP_STATUS_LOOK[clip.status].icon}
                >
                  {CLIP_STATUS_LABEL[clip.status]}
                </Pill>
              </td>
              <td role="cell" className="cell-size">
                {clip.size == null ? '—' : formatBytes(clip.size)}
              </td>
              <td role="cell" className="cell-mtime">
                {clip.mtime == null ? (
                  '—'
                ) : (
                  <time dateTime={clip.mtime}>{new Date(clip.mtime).toLocaleString()}</time>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
