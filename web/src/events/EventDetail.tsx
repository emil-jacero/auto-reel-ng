import './detail.css'

import { useCallback, useEffect, useId, useRef, useState } from 'react'

import { fetchEvent } from '../api/event'
import type { Chapter, Clip, EventDetail as EventDetailData } from '../api/event'
import type { Problem } from '../api/events'
import { ReadCuts, ReadCutsNote, useReadCuts } from '../cuts/ReadCuts'
import type { ClipCuts } from '../cuts/ReadCuts'
import { EventEditor } from '../edit/EventEditor'
import { requestLeave, useSaving } from '../edit/unsaved'
import { formatInstant } from '../format'
import { missingClipsReason } from '../jobs/labels'
import { RenderControl } from '../jobs/RenderControl'
import { MoviePanel } from '../movie/MoviePanel'
import { LIST_HREF } from '../route'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { LoadStatus } from '../ui/Skeleton'
import { ClipThumb } from './ClipThumb'
import {
  ClipName,
  ClipStatusPills,
  DATABASE_CAUSE,
  StalenessCell,
  clipNames,
  folderName,
  formatBytes,
  plural,
} from './common'
import { FAILURE_LABEL, PREVIEWS_UNAVAILABLE, failureDetail, unansweredFailure } from './labels'
import {
  movieOf,
  readingState,
  verdictOf,
  withVerdict,
  withVerdictUnread,
} from './loadState'
import type { Failure, LoadOptions, LoadState, Verdict, VerdictUnread } from './loadState'
import { ThumbHealthContext, useThumbHealth } from './thumbHealth'
import { FAILURE_LOOK } from './tones'

/**
 * One event's page: its chapters and clips in play order, and whether it needs
 * a render.
 *
 * It reads like the list: on mount and on refresh, never polled. Loading and
 * failure both replace the content, so an earlier state of the event is never
 * shown as current. The exceptions: a Refresh keeps the Movie section's player
 * (its verdict and facts are hidden meanwhile), and a re-read the page starts by
 * itself — its job ended, or an enqueue answer showed its read is out of date — which
 * keeps the content, marked as updating, until the new read answers. In Edit mode
 * that re-read is narrower: the editor's baseline is `state.event`, so only the
 * render region's verdict and latest job are refreshed (`refreshVerdict`), and
 * everything else waits for the read that leaving Edit mode makes. Its Edit
 * mode (`edit/EventEditor.tsx`) writes `reel.yaml` only on an explicit Save, and
 * its render region (`jobs/RenderControl`) enqueues or cancels only through its
 * own controls. Mounted once per event (keyed by id).
 */

function describeProblem(problem: Problem, eventId: string): Failure {
  if (problem.status === 404) {
    return {
      cause: `No event “${folderName(eventId)}” under the project root.`,
      detail: null,
      notFound: true,
    }
  }
  if (problem.status === 502) {
    return {
      cause: 'This event could not be read.',
      detail: failureDetail(eventId, problem.detail),
      failure: problem.failure ?? undefined,
    }
  }
  if (problem.check === 'database') {
    return { cause: DATABASE_CAUSE, detail: problem.detail }
  }
  return { cause: problem.title, detail: problem.detail }
}

export function EventDetail({ eventId }: { eventId: string }) {
  // Whether the previews of the clips shown fail for the service's reason (one note).
  const { health, unavailable } = useThumbHealth()
  return (
    <ThumbHealthContext value={health}>
      <EventDetailBody eventId={eventId} previewsUnavailable={unavailable} />
    </ThumbHealthContext>
  )
}

function EventDetailBody({
  eventId,
  previewsUnavailable,
}: {
  eventId: string
  previewsUnavailable: boolean
}) {
  const [state, setState] = useState<LoadState>({ status: 'loading', editPlace: true })
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
  // The verdict read of Edit mode (`refreshVerdict`): at most one in flight, and a
  // request made meanwhile leads to one more after it.
  const verdictFlight = useRef<AbortController | null>(null)
  const verdictPending = useRef(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const focusHeading = useRef(false)

  /**
   * Read the event. A plain read (first, Refresh) aborts any read and shows
   * placeholders, but a Refresh (`keepMovie`) keeps the Movie section's player. A
   * quiet one keeps the content, marked as updating — unless the page shows a
   * failure, which has no content to keep — and never restarts a read in flight:
   * it runs once after it instead.
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
    setState((shown) => readingState(shown, options))
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
          case 'unpublished':
            setState({ status: 'failed', ...unansweredFailure(result) })
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

  /**
   * The re-read of Edit mode: the same read, but only the event's verdict and latest job
   * reach the render region. `state.event` is the editor's baseline, so it, the time it
   * was read and the updating mark are never written here; the read that leaving Edit mode
   * makes replaces everything. An answer that comes after that, or after an abort, is
   * dropped. A read with no usable answer says so in the region and never replaces the
   * page. Never more than one in flight: a request meanwhile leads to one more after it.
   */
  const refreshVerdict = useCallback(() => {
    if (verdictFlight.current !== null) {
      verdictPending.current = true
      return
    }
    const controller = new AbortController()
    verdictFlight.current = controller
    const settle = (update: (shown: LoadState) => LoadState) => {
      if (!controller.signal.aborted && editingRef.current) {
        setState(update)
      }
    }
    const unread = (failure: VerdictUnread) =>
      settle((shown) => withVerdictUnread(shown, failure))
    fetchEvent(eventId, controller.signal)
      .then((result) => {
        switch (result.kind) {
          case 'ok':
            settle((shown) => withVerdict(shown, result.event))
            break
          case 'problem':
            unread(describeProblem(result.problem, eventId))
            break
          case 'unreachable':
          case 'unpublished':
            unread(unansweredFailure(result))
            break
        }
      })
      .catch((error: unknown) => {
        // An abort is leaving Edit mode or navigating away, not a failure.
        unread({ cause: 'The event could not be read.', detail: String(error) })
      })
      .finally(() => {
        if (controller.signal.aborted || verdictFlight.current !== controller) {
          return
        }
        verdictFlight.current = null
        if (verdictPending.current) {
          verdictPending.current = false
          refreshVerdict()
        }
      })
  }, [eventId])

  // The page's own re-read: its job ended, or an enqueue answer showed its read is
  // out of date. Quiet, so the page keeps its content while it runs.
  // While Edit mode is open only the render region's verdict is read (see
  // `refreshVerdict`): the exit's unconditional `load()` is the deferred re-read of
  // the rest.
  const reread = useCallback(() => {
    if (editingRef.current) {
      refreshVerdict()
    } else {
      load({ quiet: true })
    }
  }, [load, refreshVerdict])

  useEffect(() => {
    load()
    return () => inFlight.current?.abort()
  }, [load])

  useEffect(() => () => verdictFlight.current?.abort(), [])

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
    // A verdict read still on its way is dropped: the read below is newer.
    verdictFlight.current?.abort()
    verdictFlight.current = null
    verdictPending.current = false
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
  // The folder name beside a title that differs from it, which tells look-alike
  // titles apart; while reading, from the address. A failed read's heading is it.
  const folderId = useId()
  const title = state.status === 'ready' ? state.event.title : null
  const folderShown = loading || (title != null && title !== folderName(eventId))
  const facts = state.status === 'ready' && !editing ? factsOf(state.event) : null
  // The Movie section sits between the header and the content, not inside the
  // content that a read replaces, so a Refresh keeps its player (Edit mode shows none).
  const movieEvent = editing ? undefined : movieOf(state)
  return (
    <main className="page event-detail">
      <header className="page-header">
        <div className="page-crumbs">
          <a className="back-link" href={LIST_HREF}>
            <Icon name="chevron-left" />
            Events
          </a>
          {/* The description is the inner span: it leaves out the separator before it. */}
          {folderShown && (
            <span className="crumb-folder">
              <span id={folderId}>
                <span className="visually-hidden">Folder: </span>
                {folderName(eventId)}
              </span>
            </span>
          )}
        </div>
        <div className="page-title-row">
          {/* Focus lands here, so the folder line is read as the heading's description. */}
          <h1
            ref={headingRef}
            tabIndex={-1}
            aria-describedby={!loading && folderShown ? folderId : undefined}
          >
            {loading ? (
              // No name the read may replace: a bar, named by the folder (the address).
              <>
                <span className="visually-hidden">{folderName(eventId)}</span>
                <span className="skeleton skeleton-h1" aria-hidden="true" />
              </>
            ) : (
              name
            )}
          </h1>
          <div className="page-actions">
            {/* Busy, not disabled, while reading: it keeps keyboard focus. */}
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={loading || saving || undefined}
              aria-busy={loading || undefined}
              onClick={() => {
                if (!loading && !saving) {
                  requestLeave(editing ? leaveEditMode : () => load({ keepMovie: true }))
                }
              }}
            >
              <Icon name="refresh" />
              Refresh
            </button>
            {/* Edit's place while the page reads, so Refresh stays under the pointer. */}
            {state.status === 'loading' && state.editPlace && (
              <span className="skeleton skeleton-action" aria-hidden="true" />
            )}
            {/* One element in both modes, so focus stays on it when Edit mode starts. */}
            {state.status === 'ready' && (
              <button
                type="button"
                className="btn btn-secondary"
                aria-disabled={saving || undefined}
                onClick={() => {
                  if (saving) {
                    return
                  }
                  if (editing) {
                    requestLeave(leaveEditMode)
                  } else {
                    // A quiet re-read in flight stops: its answer would replace the
                    // editor's baseline. It was the page's only record of a job that
                    // ended, so the verdict read takes its place; the exit's read
                    // replaces everything else.
                    const wasReading = inFlight.current !== null || pending.current
                    inFlight.current?.abort()
                    inFlight.current = null
                    pending.current = false
                    editingRef.current = true
                    setEditing(true)
                    if (wasReading) {
                      refreshVerdict()
                    }
                  }
                }}
              >
                <Icon name={editing ? 'x' : 'pencil'} />
                {editing ? 'Stop editing' : 'Edit'}
              </button>
            )}
          </div>
        </div>
        {/* The event's facts (Edit mode's fields take the date and location's place). */}
        <div className="page-meta">
          {loading && (
            <span className="event-facts">
              <span className="skeleton skeleton-facts" aria-hidden="true" />
            </span>
          )}
          {facts !== null && <span className="event-facts">{facts}</span>}
          {state.status === 'ready' && (
            <Counts clips={state.event.chapters.flatMap((chapter) => chapter.clips)} />
          )}
          {state.status === 'ready' && (
            <span>
              Read{' '}
              <time dateTime={state.fetchedAt.toISOString()}>
                {formatInstant(state.fetchedAt)}
              </time>
            </span>
          )}
          <LoadStatus message={loading ? 'Reading event…' : updating ? 'Updating…' : ''} />
        </div>
        {state.status === 'ready' && !editing && state.event.description != null && (
          <p className="description">{state.event.description}</p>
        )}
        {state.status === 'ready' && (
          <RenderPanel
            eventId={eventId}
            event={state.event}
            verdict={verdictOf(state)}
            unread={state.verdictUnread}
            editing={editing}
            onFinished={reread}
          />
        )}
        {loading && <RenderPanelPlaceholder />}
      </header>

      {movieEvent !== undefined && (
        <MoviePanel eventId={eventId} event={movieEvent} reading={loading} />
      )}

      {previewsUnavailable && state.status === 'ready' && (
        <Alert
          tone="warn"
          role="note"
          title={PREVIEWS_UNAVAILABLE.map((part, index) =>
            typeof part === 'string' ? part : <code key={index}>{part.code}</code>,
          )}
        />
      )}

      {loading && <ChapterPlaceholder />}

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
            <ReadyView eventId={eventId} event={state.event} />
          </div>
        ))}
    </main>
  )
}

/** `date · location`, from the facts the event has; null when it has neither. */
function factsOf(event: EventDetailData): string | null {
  const facts = [event.date, event.location].filter((fact) => fact != null)
  return facts.length > 0 ? facts.join(' · ') : null
}

/**
 * The render region, one frame for the whole render story: the verdict and its
 * reasons, then the latest job and Render or Cancel. `RenderControl` keeps its
 * own card; the page's frame replaces that card's (`detail.css`).
 */
function RenderPanel({
  eventId,
  event,
  verdict,
  unread,
  editing,
  onFinished,
}: {
  eventId: string
  event: EventDetailData
  /** The verdict and latest job shown: the event's, or a newer read's in Edit mode. */
  verdict: Verdict
  /** Edit mode's verdict read got no usable answer: the verdict may be out of date. */
  unread: VerdictUnread | undefined
  editing: boolean
  onFinished: () => void
}) {
  return (
    <div className="render-panel">
      <StalenessCell staleness={verdict.staleness} explain />
      <RenderControl
        eventId={eventId}
        title={event.title}
        date={event.date}
        staleness={verdict.staleness}
        latestJob={verdict.latest_job}
        onFinished={onFinished}
        blockedReason={
          editing
            ? 'Save or leave Edit mode to render'
            : missingClipsReason(event.blocking_missing)
        }
      />
      {editing && unread !== undefined && (
        <Alert
          tone="warn"
          role="status"
          title="The render verdict may be out of date. Stop editing to read the event again."
          detail={unread.detail === null ? unread.cause : `${unread.cause} ${unread.detail}`}
        />
      )}
    </div>
  )
}

function ReadyView({ eventId, event }: { eventId: string; event: EventDetailData }) {
  const clips = event.chapters.flatMap((chapter) => chapter.clips)
  const hasNamedChapter = event.chapters.some((chapter) => chapter.name !== '')
  const read = useReadCuts(eventId, event)
  return (
    <>
      {event.missing.length > 0 && (
        <Alert
          tone="warn"
          role="note"
          title={
            <>
              <code>reel.yaml</code> lists clips that are not on disk
            </>
          }
          detail={event.missing
            .map((identity) =>
              event.blocking_missing.includes(identity) ? identity : `${identity} (excluded)`,
            )
            .join(', ')}
        />
      )}
      <ReadCutsNote failure={read.failure} />

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
            eventId={eventId}
            chapter={chapter}
            heading={chapter.name !== '' ? chapter.name : hasNamedChapter ? 'Main' : 'Clips'}
            cuts={read.cuts}
          />
        ))
      )}
    </>
  )
}

/**
 * `N clips · <their size> · k new · m missing · e excluded · i ignored`, zero
 * counts omitted. The N clips are the ones the event lists and does not ignore,
 * the new, missing and excluded among them, as each chapter's heading and Edit
 * mode count them; its ignored clips come after.
 */
function Counts({ clips }: { clips: Clip[] }) {
  const count = (status: Clip['status']) => clips.filter((clip) => clip.status === status).length
  const played = clips.filter((clip) => clip.status !== 'ignored')
  const sizes = played.flatMap((clip) => (clip.size == null ? [] : [clip.size]))
  // Only known sizes are summed; a missing clip has none, and none is not zero.
  const parts = [plural(played.length, 'clip', 'clips')]
  if (sizes.length > 0) {
    parts.push(formatBytes(sizes.reduce((sum, size) => sum + size, 0)))
  }
  const excluded = clips.filter((clip) => clip.excluded).length
  for (const [n, label] of [
    [count('new'), 'new'],
    [count('missing'), 'missing'],
    [excluded, 'excluded'],
    [count('ignored'), 'ignored'],
  ] as const) {
    if (n > 0) {
      parts.push(`${n} ${label}`)
    }
  }
  return <span className="counts">{parts.join(' · ')}</span>
}

/** The clip tables' columns and headers: each chapter's, and the placeholder's. */
function ClipTableHead() {
  return (
    <>
      <colgroup>
        <col className="col-pos" />
        <col className="col-thumb" />
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
            <span className="visually-hidden">Preview</span>
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
    </>
  )
}

function ChapterPanel({
  eventId,
  chapter,
  heading,
  cuts,
}: {
  eventId: string
  chapter: Chapter
  heading: string
  cuts: ClipCuts | null
}) {
  // Chapter names hold spaces and non-ASCII letters, so the id is generated.
  const headingId = useId()
  // The clips it plays, numbered; then the ones the event ignores, which have no
  // place in the play order (Edit mode's order: `editableChapters`).
  const played = chapter.clips.filter((clip) => clip.status !== 'ignored')
  const ignored = chapter.clips.filter((clip) => clip.status === 'ignored')
  const nameOf = clipNames(chapter.name, chapter.clips.map((clip) => clip.identity))
  const count = plural(played.length, 'clip', 'clips')
  if (chapter.clips.length === 0) {
    // Added and saved without clips: its heading and count, and no table.
    return (
      <section className="panel">
        <header className="panel-header">
          <h2 id={headingId}>{heading}</h2>
          <span className="panel-meta">{count}</span>
        </header>
        <p className="chapter-empty">No clips. This chapter is left out of the movie.</p>
      </section>
    )
  }
  return (
    <section className="panel">
      <header className="panel-header">
        <h2 id={headingId}>{heading}</h2>
        <span className="panel-meta">
          {ignored.length > 0 ? `${count} · ${ignored.length} ignored` : count}
        </span>
      </header>
      <table className="data-table clip-table" role="table" aria-labelledby={headingId}>
        <ClipTableHead />
        <tbody role="rowgroup">
          {[...played, ...ignored].map((clip, index) => (
            <tr
              role="row"
              key={clip.identity}
              className="clip-row"
              data-status={clip.status}
              data-excluded={clip.excluded || undefined}
            >
              <td role="cell" className="cell-pos">
                {index < played.length ? index + 1 : null}
              </td>
              <td role="cell" className="cell-thumb">
                <ClipThumb eventId={eventId} clip={clip} name={nameOf(clip.identity)} />
              </td>
              <td role="cell" className="cell-file">
                <ClipName name={nameOf(clip.identity)} />
                {/* An excluded clip is not in the movie, so its cuts do not apply. */}
                <ReadCuts
                  cuts={clip.excluded ? undefined : cuts?.get(clip.identity)}
                  name={nameOf(clip.identity)}
                />
              </td>
              <td role="cell" className="cell-status">
                <ClipStatusPills clip={clip} />
              </td>
              <td role="cell" className="cell-size">
                {clip.size == null ? '—' : formatBytes(clip.size)}
              </td>
              <td role="cell" className="cell-mtime">
                {clip.mtime == null ? (
                  '—'
                ) : (
                  <time dateTime={clip.mtime}>{formatInstant(clip.mtime)}</time>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

/*
 * What the page shows while it reads: placeholders in the loaded page's shape,
 * carrying no event data and hidden from assistive technology (`LoadStatus` says
 * what is happening). The bars are `.skeleton`, whose shimmer rests under reduced
 * motion; their sizes are in `detail.css`.
 */

/** A placeholder bar for a line of text, `width` wide at most. */
function Bar({ width }: { width: string }) {
  return <span className="skeleton" style={{ inlineSize: width }} />
}

/** The render region's shape: the verdict line, then the job line with its button. */
function RenderPanelPlaceholder() {
  return (
    <div className="render-panel" aria-hidden="true">
      <div className="skeleton-line">
        <span className="skeleton skeleton-verdict" />
        <span className="skeleton skeleton-title" style={{ inlineSize: '16rem' }} />
      </div>
      <div className="skeleton-line">
        <span className="skeleton skeleton-title" style={{ inlineSize: '12rem' }} />
        <span className="skeleton skeleton-button" />
      </div>
    </div>
  )
}

// Varied name widths, so the placeholder reads as rows of file names.
const FILE_WIDTHS = ['7.5rem', '6rem', '8.5rem', '6.75rem']

/** One chapter's shape: the real table, so its rows lay out as loaded rows at every width. */
function ChapterPlaceholder() {
  return (
    <section className="panel" aria-hidden="true">
      <header className="panel-header">
        <span className="skeleton skeleton-heading" />
      </header>
      <table className="data-table clip-table">
        <ClipTableHead />
        <tbody>
          {FILE_WIDTHS.map((width, index) => (
            <tr className="clip-row" key={index}>
              <td className="cell-pos">
                <Bar width="0.75rem" />
              </td>
              <td className="cell-thumb">
                <span className="clip-thumb" data-state="loading" />
              </td>
              <td className="cell-file">
                <Bar width={width} />
              </td>
              <td className="cell-status">
                <Bar width="4.25rem" />
              </td>
              <td className="cell-size">
                <Bar width="4rem" />
              </td>
              <td className="cell-mtime">
                <Bar width="8.5rem" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
