import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchEvent } from '../api/event'
import type { Chapter, Clip, EventDetail as EventDetailData } from '../api/event'
import type { EventFailure, Problem } from '../api/events'
import { LIST_HREF } from '../route'
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

/**
 * One event's page: its chapters and clips in play order, and whether it needs
 * a render.
 *
 * Read-only, like the list: read on mount and on refresh, never polled. Loading
 * and failure both replace the content, so an earlier state of the event is
 * never shown as current. Mounted once per event (keyed by id).
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

  return (
    <main>
      <nav>
        <a href={LIST_HREF}>← Events</a>
      </nav>
      <header>
        <h1>{name}</h1>
        <button type="button" onClick={load} disabled={state.status === 'loading'}>
          Refresh
        </button>
      </header>

      {state.status === 'loading' && <p className="muted">Reading event…</p>}

      {state.status === 'failed' && (
        <div className="failure" role="alert">
          <p>
            <strong>{state.cause}</strong>
            {state.failure !== undefined && (
              <span className="pill pill-attention">{FAILURE_LABEL[state.failure]}</span>
            )}
          </p>
          {state.detail !== null && <p className="muted">{state.detail}</p>}
          {state.notFound === true && (
            <p>
              <a href={LIST_HREF}>Back to the event list</a>
            </p>
          )}
        </div>
      )}

      {state.status === 'ready' && <ReadyView event={state.event} fetchedAt={state.fetchedAt} />}
    </main>
  )
}

function ReadyView({ event, fetchedAt }: { event: EventDetailData; fetchedAt: Date }) {
  const clips = event.chapters.flatMap((chapter) => chapter.clips)
  const hasNamedChapter = event.chapters.some((chapter) => chapter.name !== '')
  const facts = [event.date, event.location].filter((fact) => fact != null)
  return (
    <>
      {facts.length > 0 && <p className="muted event-facts">{facts.join(' · ')}</p>}
      {event.description != null && <p className="description">{event.description}</p>}

      <div className="status-line">
        <span>
          <StalenessCell staleness={event.staleness} />
        </span>
        {event.latest_job != null && (
          <span className="status-job">
            Last job: <JobCell job={event.latest_job} />
          </span>
        )}
      </div>

      <p>
        <Counts clips={clips} />
        <span className="muted"> Read {fetchedAt.toLocaleTimeString()}.</span>
      </p>

      {event.missing.length > 0 && (
        <div className="warning" role="alert">
          <p>
            <strong>reel.yaml lists clips that are not on disk:</strong>{' '}
            {event.missing.join(', ')}
          </p>
        </div>
      )}

      {clips.length === 0 ? (
        <p className="muted">No clips.</p>
      ) : (
        event.chapters.map((chapter, index) => (
          <ChapterTable key={index} chapter={chapter} captioned={hasNamedChapter} />
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
  return <strong>{parts.join(' · ')}</strong>
}

/** The identity's last segment: the file name inside its chapter folder. */
function fileName(identity: string): string {
  return identity.split('/').pop() ?? identity
}

function ChapterTable({ chapter, captioned }: { chapter: Chapter; captioned: boolean }) {
  return (
    <div className="table-scroll">
      <table className="clips">
        {captioned && <caption>{chapter.name === '' ? 'Main' : chapter.name}</caption>}
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">File</th>
            <th scope="col">Status</th>
            <th scope="col">Size</th>
            <th scope="col">Modified</th>
          </tr>
        </thead>
        <tbody>
          {chapter.clips.map((clip, index) => (
            <tr key={clip.identity} className={`clip-${clip.status}`}>
              <td className="num">{index + 1}</td>
              <td className="file">{fileName(clip.identity)}</td>
              <td>
                <span className={`clip-status clip-status-${clip.status}`}>
                  {CLIP_STATUS_LABEL[clip.status]}
                </span>
              </td>
              <td className="num">{clip.size == null ? '—' : formatBytes(clip.size)}</td>
              <td className="date">
                {clip.mtime == null ? '—' : new Date(clip.mtime).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
