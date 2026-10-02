import {
  Fragment,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'

import type { JobSummary, Staleness } from '../api/events'
import { cancelJob, enqueueJob } from '../api/jobs'
import type { CancelOutcome, EnqueueResult } from '../api/jobs'
import { markEventsChanged } from '../events/changes'
import { DATABASE_CAUSE, UNREACHABLE_CAUSE, folderName } from '../events/common'
import { LIST_HREF, eventHref } from '../route'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { toast } from '../ui/toast'
import { JobMeter, JobState } from './JobProgress'
import { missingClipNames } from './clipNames'
import {
  CANCEL_OUTCOME_LABEL,
  COLLISION_FIX,
  MISSING_CLIPS_FIX,
  NOT_CONFIRMED,
  NOT_QUEUED,
  SCAN_FAILED,
  eventName,
} from './labels'
import { getState, isActive, load, markAnnounced, merge, subscribe, track } from './store'
import { useEventJob } from './useJob'

/*
 * The event page's render region: the event's job, live, and the controls that
 * start or stop one. Every control names what it does, and a pressed one keeps
 * focus and is marked busy (aria-disabled + aria-busy, never `disabled`) until
 * its answer arrives; a ref set in the click handler is the actual guard, so a
 * second press sends nothing.
 */

/** What an answer left to say, below the job. */
type Notice =
  | { kind: 'fresh' }
  | { kind: 'collision'; claimedBy: string[]; detail: string }
  | { kind: 'missingClips'; missing: string[] }
  | { kind: 'eventGone' }
  | { kind: 'scanFailed'; detail: string }
  // `cause`: the service named its database; answered in a way it does not publish; or no answer came
  | { kind: 'notQueued'; cause: Cause; message: string }
  | { kind: 'jobGone' }
  | { kind: 'cancelUnconfirmed'; cause: Cause; message: string }

/** Why a write went unconfirmed: the sentence after its title, if the answer carries a cause. */
type Cause = 'database' | 'unpublished' | 'unreachable'

const CAUSE_SENTENCE: Record<Cause, string | undefined> = {
  database: DATABASE_CAUSE,
  // An answer the service does not publish names no cause: the status is the detail.
  unpublished: undefined,
  unreachable: UNREACHABLE_CAUSE,
}

function withCause(title: string, cause: Cause): string {
  const sentence = CAUSE_SENTENCE[cause]
  return sentence === undefined ? title : `${title} ${sentence}`
}

/** The control whose request is in flight. */
type Pressed = 'render' | 'force' | 'cancel' | 'cancelConfirm'

/**
 * The open question. A cancel names its job, so the confirmation cancels the job
 * it asked about. Whether it may have started unseen is read from the state as it
 * is now, not as it was when the question opened: a reconnect makes it untrue.
 */
type Asking = { kind: 'force' } | { kind: 'cancel'; jobId: string }

const NOTHING_TO_RENDER = 'Nothing to render — the movie is up to date.'

/**
 * Focus is gone: nowhere, on <body>, on a removed node, or inside a closed
 * <dialog> (Chromium moves it to <body> only at the next frame).
 */
function focusIsLost(): boolean {
  const focused = document.activeElement
  return (
    focused === null ||
    focused === document.body ||
    !focused.isConnected ||
    focused.closest('dialog:not([open])') !== null
  )
}

// Whether a cancel's answer also tells how the job ended (so the ending raises
// no second toast): a flagged running job is still to end, at the next segment.
const CANCEL_ENDS_JOB: Record<CancelOutcome, boolean> = {
  'flagged-running': false,
  'canceled-queued': true,
  'no-op-terminal': true,
}

function NoticeAlert({ notice }: { notice: Notice }) {
  switch (notice.kind) {
    case 'fresh':
      // A note: the region's status element says the same words, and announces them.
      return <Alert tone="info" role="note" title={NOTHING_TO_RENDER} />
    case 'collision':
      return (
        <Alert
          tone="err"
          title="Another event renders to the same movie file"
          detail={notice.detail}
          action={
            <div className="render-claimants">
              <p>
                Also claimed by{' '}
                {notice.claimedBy.map((id, index) => (
                  <Fragment key={id}>
                    {index > 0 && ', '}
                    <a href={eventHref(id)}>{folderName(id)}</a>
                  </Fragment>
                ))}
                .
              </p>
              <p>{COLLISION_FIX}</p>
            </div>
          }
        />
      )
    case 'missingClips':
      return (
        <Alert
          tone="err"
          title={`${NOT_QUEUED} Clips are missing from disk.`}
          detail={`${missingClipNames(notice.missing)}. ${MISSING_CLIPS_FIX}`}
        />
      )
    case 'eventGone':
      return (
        <Alert
          tone="err"
          title="This event no longer exists."
          action={
            <a className="btn btn-secondary" href={LIST_HREF}>
              <Icon name="chevron-left" />
              Back to the event list
            </a>
          }
        />
      )
    case 'scanFailed':
      return <Alert tone="err" title={SCAN_FAILED} detail={notice.detail} />
    case 'notQueued':
      return (
        <Alert
          tone="err"
          title={withCause(NOT_QUEUED, notice.cause)}
          detail={notice.message}
        />
      )
    case 'jobGone':
      return <Alert tone="err" title="This job no longer exists." />
    case 'cancelUnconfirmed':
      return (
        <Alert
          tone="err"
          title={withCause(NOT_CONFIRMED, notice.cause)}
          detail={notice.message}
        />
      )
  }
}

export function RenderControl({
  eventId,
  title,
  date,
  staleness,
  latestJob,
  onFinished,
  blockedReason,
}: {
  eventId: string
  /** The event's title and date, as the page read them: a toast names the event by them. */
  title: string | null | undefined
  date: string | null | undefined
  staleness: Staleness
  latestJob: JobSummary | null | undefined
  /** The shown job ended, or an answer showed the page's read is out of date: re-read it. */
  onFinished: () => void
  /** Why the page cannot render now; Render and Render anyway then give way to it. */
  blockedReason?: string
}) {
  const shown = useEventJob(eventId, latestJob)
  const job = shown?.job
  const active = job !== undefined && isActive(job.status)
  const jobId = job?.id
  const eta = useSyncExternalStore(subscribe, () =>
    jobId === undefined ? undefined : getState().eta.get(jobId),
  )
  const connectionLive = useSyncExternalStore(subscribe, () => getState().connection === 'live')
  const [pressed, setPressed] = useState<Pressed | null>(null)
  const [asking, setAsking] = useState<Asking | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const inFlight = useRef(false)
  const statusRef = useRef<HTMLParagraphElement>(null)
  const keepUpToDateRef = useRef<HTMLButtonElement>(null)
  const keepRenderingRef = useRef<HTMLButtonElement>(null)
  // The latest `onFinished`: an answer arrives after re-renders (Edit mode may have
  // opened meanwhile), and must reach the page as it is now, not as it was pressed.
  const onFinishedRef = useRef(onFinished)
  useLayoutEffect(() => {
    onFinishedRef.current = onFinished
  })

  // A control removed while focused (Render once its job shows, Cancel once the
  // cancel is requested, the job ends or another job shows, a dialog closed after
  // its opener went) hands focus to the status element, so a keyboard user keeps
  // their place. A dialog that closed by itself always does, even when its opener
  // is still there: its subject is gone, and the status says what replaced it.
  const handOff = useRef(false)
  const selfClosed = useRef(false)
  const watchRemoval = useCallback((node: HTMLElement | null) => {
    if (node === null) {
      return undefined
    }
    return () => {
      if (document.activeElement === node) {
        handOff.current = true
      }
    }
  }, [])
  // After every commit, and after the dialogs' own cleanups have restored focus.
  useEffect(() => {
    if (!handOff.current) {
      return
    }
    handOff.current = false
    const closedItself = selfClosed.current
    selfClosed.current = false
    if (closedItself || focusIsLost()) {
      statusRef.current?.focus({ preventScroll: true })
    }
  })

  const closeDialog = useCallback(() => {
    handOff.current = true
    setAsking(null)
  }, [])

  // The page re-reads once when its job ends — also when its own read still shows
  // as queued or running a job the store already knows ended (it ended while the
  // read was on its way), which no transition here would report. The refs keep a
  // StrictMode re-run from re-reading twice; the re-read shows the end, so it
  // cannot loop.
  const status = job?.status ?? null
  const readIsBehind =
    latestJob != null &&
    job !== undefined &&
    job.id === latestJob.id &&
    isActive(latestJob.status) &&
    !isActive(job.status)
  const previousStatus = useRef(status)
  const behindFor = useRef<string | null>(null)
  useEffect(() => {
    const was = previousStatus.current
    previousStatus.current = status
    const ended = was !== null && status !== null && isActive(was) && !isActive(status)
    const behind = readIsBehind && behindFor.current !== jobId
    if (readIsBehind) {
      behindFor.current = jobId ?? null
    }
    if (ended || behind) {
      onFinishedRef.current()
    }
  }, [status, readIsBehind, jobId])

  // A failed job's error text is in the full job only: read it once, here on
  // the event's page (list rows never fetch it).
  const failedReadId =
    shown !== null && shown.source === 'read' && shown.job.status === 'failed' ? shown.job.id : null
  useEffect(() => {
    if (failedReadId !== null) {
      load(failedReadId)
    }
  }, [failedReadId])

  const handleEnqueue = (result: EnqueueResult) => {
    switch (result.kind) {
      case 'enqueued':
        track(result.job.id, eventName(eventId, title, date))
        merge(result.job)
        break
      case 'fresh':
        setNotice({ kind: 'fresh' })
        markEventsChanged()
        onFinishedRef.current()
        break
      case 'active':
        // Someone already started it: follow that job.
        track(result.jobId, eventName(eventId, title, date))
        load(result.jobId)
        break
      case 'collision':
        setNotice({ kind: 'collision', claimedBy: result.claimedBy, detail: result.problem.detail })
        break
      case 'missingClips':
        // The page's read is out of date: say why nothing was queued, then re-read so
        // that its own guard (`blockedReason`) takes Render's place.
        setNotice({ kind: 'missingClips', missing: result.missing })
        markEventsChanged()
        onFinishedRef.current()
        break
      case 'problem':
        if (result.problem.status === 404) {
          setNotice({ kind: 'eventGone' })
          markEventsChanged()
          onFinishedRef.current()
        } else {
          setNotice({ kind: 'scanFailed', detail: result.problem.detail })
        }
        break
      case 'database':
        setNotice({ kind: 'notQueued', cause: 'database', message: result.problem.detail })
        break
      case 'unreachable':
      case 'unpublished':
        setNotice({ kind: 'notQueued', cause: result.kind, message: result.message })
        break
      default: {
        // A new answer kind is a `tsc --noEmit` error here until it is handled.
        const unhandled: never = result
        throw new Error(`unhandled enqueue answer ${String(unhandled)}`)
      }
    }
  }

  const enqueue = (force: boolean, control: Pressed) => {
    if (inFlight.current) {
      return
    }
    inFlight.current = true
    setPressed(control)
    setNotice(null)
    void enqueueJob(eventId, force).then((result) => {
      inFlight.current = false
      setPressed(null)
      if (control === 'force') {
        closeDialog()
      }
      handleEnqueue(result)
    })
  }

  const cancel = (target: string, control: Pressed) => {
    if (inFlight.current) {
      return
    }
    inFlight.current = true
    setPressed(control)
    setNotice(null)
    void cancelJob(target).then((answer) => {
      inFlight.current = false
      setPressed(null)
      if (control === 'cancelConfirm') {
        closeDialog()
      }
      switch (answer.kind) {
        case 'ok': {
          const { outcome } = answer.result
          const name = eventName(eventId, title, date)
          track(target, name)
          // An answer that ended the job tells how, naming the event as the store's
          // ending toast would; a toast the store already raised is not repeated.
          if (!CANCEL_ENDS_JOB[outcome] || markAnnounced(target)) {
            toast.info(`${CANCEL_OUTCOME_LABEL[outcome]}: ${name}`)
          }
          // Shows "Cancelling…" or the ending at once, live connection or not.
          load(target, { force: true })
          break
        }
        case 'problem':
          setNotice({ kind: 'jobGone' })
          break
        case 'database':
          setNotice({ kind: 'cancelUnconfirmed', cause: 'database', message: answer.problem.detail })
          break
        case 'unreachable':
        case 'unpublished':
          setNotice({ kind: 'cancelUnconfirmed', cause: answer.kind, message: answer.message })
          break
      }
    })
  }

  const busy = (control: Pressed) => pressed === control || undefined
  // A cancel already requested leaves nothing to press; the job shows Cancelling….
  const cancelRequested = shown !== null && shown.source !== 'read' && shown.job.cancel_requested
  const cancellable = active && !cancelRequested
  // An enqueue answer is newer than the page's read: after "fresh", force it is.
  const upToDate = !staleness.stale || notice?.kind === 'fresh'
  const canRender = !active && blockedReason === undefined

  // A question whose subject is gone closes by itself and sends nothing: Render
  // anyway once the page would not offer it (a job appeared, a block, no longer
  // up to date), a cancel once its job ended, its cancel was requested elsewhere,
  // or another job shows. Never while its own request is in flight: that answer
  // closes it. Focus goes to the status, which says what happened — also when
  // the opener is still there (another job's Cancel), whose next press would act
  // on a subject the operator was never asked about.
  const questionGone =
    asking !== null &&
    pressed === null &&
    (asking.kind === 'force' ? !(canRender && upToDate) : !(cancellable && jobId === asking.jobId))
  useEffect(() => {
    if (questionGone) {
      selfClosed.current = true
      closeDialog()
    }
  }, [questionGone, closeDialog])
  // The cancel question says the render may have started only while that is so:
  // the connection is down and the job is not shown running.
  const mayHaveStarted = !connectionLive && job?.status !== 'running'

  return (
    <div className="render-control">
      <div className="render-card" data-active={active || undefined}>
        <div className="render-row">
          {/* The region's announced words: they change with the job's state only. */}
          <p className="render-status" role="status" tabIndex={-1} ref={statusRef}>
            {shown === null ? (
              <span className="render-none">No render job yet</span>
            ) : (
              <JobState shown={shown} lastJobLabel />
            )}
            {blockedReason !== undefined && <span className="render-blocked">{blockedReason}</span>}
            {/* An answer is said through this element, which exists before its words do. */}
            {notice?.kind === 'fresh' && (
              <span className="visually-hidden">{NOTHING_TO_RENDER}</span>
            )}
          </p>
          {(canRender || cancellable) && (
            <div className="render-actions">
              {canRender &&
                (upToDate ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    ref={watchRemoval}
                    onClick={() => {
                      if (!inFlight.current) {
                        setAsking({ kind: 'force' })
                      }
                    }}
                  >
                    <Icon name="play" />
                    Render anyway
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    ref={watchRemoval}
                    aria-disabled={busy('render')}
                    aria-busy={busy('render')}
                    onClick={() => enqueue(false, 'render')}
                  >
                    <Icon name="play" />
                    Render
                  </button>
                ))}
              {cancellable && job !== undefined && (
                // Keyed by its job: another job's Cancel is another control, so
                // a focused Cancel whose job gave way hands focus to the status.
                <button
                  key={job.id}
                  type="button"
                  className="btn btn-danger"
                  ref={watchRemoval}
                  aria-disabled={busy('cancel')}
                  aria-busy={busy('cancel')}
                  onClick={() => {
                    if (inFlight.current) {
                      return
                    }
                    // A queued job has nothing to lose; a running one asks first, and so
                    // does any job while the connection is down: it may have started.
                    if (job.status === 'running' || !connectionLive) {
                      setAsking({ kind: 'cancel', jobId: job.id })
                    } else {
                      cancel(job.id, 'cancel')
                    }
                  }}
                >
                  <Icon name="square" />
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>
        {/* The estimate is the store's, for the store's progress: never beside a refreshed one. */}
        {shown !== null && active && (
          <JobMeter shown={shown} eta={shown.source === 'live' ? eta : undefined} />
        )}
      </div>

      {shown !== null &&
        shown.source === 'live' &&
        shown.job.status === 'failed' &&
        shown.job.error != null && (
          <Alert tone="err" role="note" title="Why the render failed" detail={shown.job.error} />
        )}
      {notice !== null && <NoticeAlert notice={notice} />}

      <Dialog
        open={asking?.kind === 'force'}
        title="Render anyway?"
        onClose={closeDialog}
        initialFocus={keepUpToDateRef}
      >
        <p>The event is up to date. The existing movie is replaced when the new render finishes.</p>
        <div className="dialog-actions">
          <button
            type="button"
            className="btn btn-secondary"
            ref={keepUpToDateRef}
            disabled={pressed === 'force'}
            onClick={closeDialog}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            aria-disabled={busy('force')}
            aria-busy={busy('force')}
            onClick={() => enqueue(true, 'force')}
          >
            <Icon name="play" />
            Render anyway
          </button>
        </div>
      </Dialog>

      <Dialog
        open={asking?.kind === 'cancel'}
        title="Cancel this render?"
        onClose={closeDialog}
        initialFocus={keepRenderingRef}
      >
        <p>
          {mayHaveStarted ? 'The connection is down, so this render may have started. ' : ''}
          The partial render is discarded. The existing movie, if any, stays as it was.
        </p>
        <div className="dialog-actions">
          <button
            type="button"
            className="btn btn-secondary"
            ref={keepRenderingRef}
            disabled={pressed === 'cancelConfirm'}
            onClick={closeDialog}
          >
            Keep rendering
          </button>
          <button
            type="button"
            className="btn btn-danger"
            aria-disabled={busy('cancelConfirm')}
            aria-busy={busy('cancelConfirm')}
            onClick={() => {
              if (asking?.kind === 'cancel') {
                cancel(asking.jobId, 'cancelConfirm')
              }
            }}
          >
            <Icon name="square" />
            Cancel render
          </button>
        </div>
      </Dialog>
    </div>
  )
}
