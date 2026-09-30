import './detail.css'

import { useCallback, useEffect, useId, useRef, useState } from 'react'

import { fetchEvent } from '../api/event'
import type { Chapter, Clip, EventDetail as EventDetailData } from '../api/event'
import type { EventFailure, Problem } from '../api/events'
import { EventEditor } from '../edit/EventEditor'
import { requestLeave, useSaving } from '../edit/unsaved'
import { missingClipsReason } from '../jobs/labels'
import { RenderControl } from '../jobs/RenderControl'
import { LIST_HREF } from '../route'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { LoadStatus, SkeletonRows } from '../ui/Skeleton'
import {
  DATABASE_CAUSE,
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
 * It reads like the list: on mount and on refresh, never polled. Loading and
 * failure both replace the content, so an earlier state of the event is never
 * shown as current. The one exception is a re-read the page starts by itself —
 * its job ended, or an enqueue answer showed its read is out of date — which
 * keeps the content, marked as updating, until the new read answers. Its Edit
 * mode (`edit/EventEditor.tsx`) writes `reel.yaml` only on an explicit Save, and
 * its render region (`jobs/RenderControl`) enqueues or cancels only through its
 * own controls. Mounted once per event (keyed by id).
 */

type Failure = {
  cause: string
  detail: string | null
  /** The failure kind, shown in the list's "Needs attention" words. */
  failure?: EventFailure
  /** The event does not exist: offer the way back. */
  notFound?: boolean
}

/** `quiet`: a re-read the page starts by itself, which keeps the content shown. */
type LoadOptions = { quiet?: boolean }

type LoadState =
  | { status: 'loading' }
  // `updating`: a quiet re-read runs, and the content shown is the last read's.
  | { status: 'ready'; event: EventDetailData; fetchedAt: Date; updating?: boolean }
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
  const [editing, setEditing] = useState(false)
  // While a save is in flight, Refresh and Stop editing wait for its answer.
  const saving = useSaving()
  const shown = useRef(false)
  const inFlight = useRef<AbortController | null>(null)
  // A quiet re-read asked for while a read runs: one more runs after it.
  const pending = useRef(false)
  // Whether Edit mode is open, for the page's own re-reads however late they run:
  // set together with `editing` at its two changes, never during render.
  const editingRef = useRef(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const focusHeading = useRef(false)

  /**
   * Read the event. A plain read (first, Refresh) aborts any read and shows
   * placeholders. A quiet one keeps the content, marked as updating — unless the
   * page shows a failure, which has no content to keep — and never restarts a
   * read in flight: it runs once after it instead.
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
    setState((shown) =>
      quiet && shown.status === 'ready' ? { ...shown, updating: true } : { status: 'loading' },
    )
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
      .finally(() => {
        if (controller.signal.aborted || inFlight.current !== controller) {
          return
        }
        inFlight.current = null
        if (pending.current) {
          load({ quiet: true })
        }
      })
  }, [eventId])

  // The page's own re-read: its job ended, or an enqueue answer showed its read is
  // out of date. Quiet, so the page keeps its content while it runs.
  // While Edit mode is open it reads nothing: the exit's unconditional `load()` is
  // the deferred re-read.
  const reread = useCallback(() => {
    if (!editingRef.current) {
      load({ quiet: true })
    }
  }, [load])

  useEffect(() => {
    load()
    return () => inFlight.current?.abort()
  }, [load])

  useEffect(() => {
    shown.current = true
    return () => {
      shown.current = false
    }
  }, [])

  // Every way out of Edit mode, so none skips a step: `load()` never touches
  // `editing`, and leaving always reads the event again.
  const leaveEditMode = useCallback(() => {
    // A save answered after the page left needs no re-read.
    if (!shown.current) {
      return
    }
    editingRef.current = false
    setEditing(false)
    load()
    focusHeading.current = true
  }, [load])

  // After the commit, and after a closing dialog has returned focus to its opener.
  useEffect(() => {
    if (focusHeading.current) {
      focusHeading.current = false
      headingRef.current?.focus()
    }
  }, [editing, state])

  const name =
    state.status === 'ready' ? (state.event.title ?? folderName(eventId)) : folderName(eventId)
  useEffect(() => {
    document.title = `${name} — auto-reel`
  }, [name])

  const loading = state.status === 'loading'
  const updating = state.status === 'ready' && state.updating === true && !editing
  return (
    <main className="page event-detail">
      <header className="page-header">
        <a className="back-link" href={LIST_HREF}>
          <Icon name="chevron-left" />
          Events
        </a>
        <div className="page-title-row">
          <h1 ref={headingRef} tabIndex={-1}>{name}</h1>
          <div className="page-actions">
            {/* Busy, not disabled, while reading: it keeps keyboard focus. */}
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={loading || saving || undefined}
              aria-busy={loading || undefined}
              onClick={() => {
                if (!loading && !saving) {
                  requestLeave(editing ? leaveEditMode : load)
                }
              }}
            >
              <Icon name="refresh" />
              Refresh
            </button>
            {/* One element in both modes, so focus stays on it when Edit mode starts. */}
            {state.status === 'ready' && (
              <button
                type="button"
                className={editing ? 'btn btn-ghost' : 'btn btn-secondary'}
                aria-disabled={saving || undefined}
                onClick={() => {
                  if (saving) {
                    return
                  }
                  if (editing) {
                    requestLeave(leaveEditMode)
                  } else {
                    // A quiet re-read in flight stops; the exit's read replaces it.
                    inFlight.current?.abort()
                    editingRef.current = true
                    setEditing(true)
                  }
                }}
              >
                <Icon name={editing ? 'x' : 'pencil'} />
                {editing ? 'Stop editing' : 'Edit'}
              </button>
            )}
          </div>
        </div>
        {state.status === 'ready' && (
          <EventFacts
            eventId={eventId}
            event={state.event}
            editing={editing}
            onFinished={reread}
          />
        )}
        <div className="page-meta">
          {state.status === 'ready' && (
            <Counts clips={state.event.chapters.flatMap((chapter) => chapter.clips)} />
          )}
          {state.status === 'ready' && <span>Read {state.fetchedAt.toLocaleTimeString()}</span>}
          <LoadStatus message={loading ? 'Reading event…' : updating ? 'Updating…' : ''} />
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

      {state.status === 'failed' && state.failure === 'unusable_metadata' && (
        <EventEditor
          eventId={eventId}
          event={null}
          heading="Fix the date or title"
          onSaved={leaveEditMode}
          onReload={leaveEditMode}
        />
      )}

      {state.status === 'ready' &&
        (editing ? (
          <EventEditor
            eventId={eventId}
            event={state.event}
            onSaved={leaveEditMode}
            onReload={leaveEditMode}
          />
        ) : (
          <div className="page-content" aria-busy={updating || undefined}>
            <ReadyView event={state.event} />
          </div>
        ))}
    </main>
  )
}

/**
 * The header's facts: date and location, description, verdict, and the render
 * region. In Edit mode the editor's fields take the place of the first two.
 */
function EventFacts({
  eventId,
  event,
  editing,
  onFinished,
}: {
  eventId: string
  event: EventDetailData
  editing: boolean
  onFinished: () => void
}) {
  const facts = [event.date, event.location].filter((fact) => fact != null)
  return (
    <>
      {!editing && facts.length > 0 && <p className="event-facts">{facts.join(' · ')}</p>}
      {!editing && event.description != null && (
        <p className="description">{event.description}</p>
      )}
      <div className="status-line">
        <StalenessCell staleness={event.staleness} />
        <RenderControl
          eventId={eventId}
          staleness={event.staleness}
          latestJob={event.latest_job}
          onFinished={onFinished}
          blockedReason={
            editing ? 'Save or leave Edit mode to render' : missingClipsReason(event.missing)
          }
        />
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
