import { Fragment, useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'

import type { JobSummary, Staleness } from '../api/events'
import { cancelJob, enqueueJob } from '../api/jobs'
import type { CancelOutcome, EnqueueResult } from '../api/jobs'
import { markEventsChanged } from '../events/changes'
import { folderName } from '../events/common'
import { LIST_HREF, eventHref } from '../route'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { toast } from '../ui/toast'
import { JobMeter, JobState } from './JobProgress'
import { CANCEL_OUTCOME_LABEL, COLLISION_FIX, NOT_QUEUED, SCAN_FAILED } from './labels'
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
  | { kind: 'eventGone' }
  | { kind: 'scanFailed'; detail: string }
  | { kind: 'notQueued'; message: string }
  | { kind: 'jobGone' }
  | { kind: 'cancelUnconfirmed'; message: string }

/** The control whose request is in flight. */
type Pressed = 'render' | 'force' | 'cancel' | 'cancelConfirm'

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
      return (
        <Alert tone="info" role="status" title="Nothing to render — the movie is up to date." />
      )
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
      return <Alert tone="err" title={NOT_QUEUED} detail={notice.message} />
    case 'jobGone':
      return <Alert tone="err" title="This job no longer exists." />
    case 'cancelUnconfirmed':
      return <Alert tone="err" title="The cancel was not confirmed." detail={notice.message} />
  }
}

export function RenderControl({
  eventId,
  staleness,
  latestJob,
  onFinished,
  blockedReason,
}: {
  eventId: string
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
  const [pressed, setPressed] = useState<Pressed | null>(null)
  const [asking, setAsking] = useState<'force' | 'cancel' | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const inFlight = useRef(false)
  const statusRef = useRef<HTMLParagraphElement>(null)
  const keepUpToDateRef = useRef<HTMLButtonElement>(null)
  const keepRenderingRef = useRef<HTMLButtonElement>(null)

  // A control removed while focused (Render once its job shows, Cancel once the
  // cancel is requested or the job ends, a dialog closed after its opener went)
  // hands focus to the status element, so a keyboard user keeps their place.
  const handOff = useRef(false)
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
    const focused = document.activeElement
    if (focused === null || focused === document.body) {
      statusRef.current?.focus({ preventScroll: true })
    }
  })

  const closeDialog = useCallback(() => {
    handOff.current = true
    setAsking(null)
  }, [])

  // The page re-reads once when its job ends; the ref keeps a StrictMode re-run
  // from seeing a transition twice.
  const status = job?.status ?? null
  const previousStatus = useRef(status)
  useEffect(() => {
    const was = previousStatus.current
    previousStatus.current = status
    if (was !== null && status !== null && isActive(was) && !isActive(status)) {
      onFinished()
    }
  }, [status, onFinished])

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
        track(result.job.id)
        merge(result.job)
        break
      case 'fresh':
        setNotice({ kind: 'fresh' })
        markEventsChanged()
        onFinished()
        break
      case 'active':
        // Someone already started it: follow that job.
        track(result.jobId)
        load(result.jobId)
        break
      case 'collision':
        setNotice({ kind: 'collision', claimedBy: result.claimedBy, detail: result.problem.detail })
        break
      case 'problem':
        if (result.problem.status === 404) {
          setNotice({ kind: 'eventGone' })
          markEventsChanged()
          onFinished()
        } else {
          setNotice({ kind: 'scanFailed', detail: result.problem.detail })
        }
        break
      case 'unreachable':
        setNotice({ kind: 'notQueued', message: result.message })
        break
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
          track(target)
          // An answer that ended the job tells how; a toast the store already
          // raised for that ending is not repeated.
          if (!CANCEL_ENDS_JOB[outcome] || markAnnounced(target)) {
            toast.info(CANCEL_OUTCOME_LABEL[outcome])
          }
          // Shows "Cancelling…" or the ending at once, live connection or not.
          load(target, { force: true })
          break
        }
        case 'problem':
          setNotice({ kind: 'jobGone' })
          break
        case 'unreachable':
          setNotice({ kind: 'cancelUnconfirmed', message: answer.message })
          break
      }
    })
  }

  const busy = (control: Pressed) => pressed === control || undefined
  // A cancel already requested leaves nothing to press; the job shows Cancelling….
  const cancellable = active && !(shown?.source === 'live' && shown.job.cancel_requested)
  // An enqueue answer is newer than the page's read: after "fresh", force it is.
  const upToDate = !staleness.stale || notice?.kind === 'fresh'
  const canRender = !active && blockedReason === undefined

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
                        setAsking('force')
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
                <button
                  type="button"
                  className="btn btn-danger"
                  ref={watchRemoval}
                  aria-disabled={busy('cancel')}
                  aria-busy={busy('cancel')}
                  onClick={() => {
                    if (inFlight.current) {
                      return
                    }
                    // A queued job has nothing to lose; a running one asks first.
                    if (job.status === 'running') {
                      setAsking('cancel')
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
        {shown !== null && active && <JobMeter shown={shown} eta={eta} />}
      </div>

      {shown !== null &&
        shown.source === 'live' &&
        shown.job.status === 'failed' &&
        shown.job.error != null && (
          <Alert tone="err" role="note" title="Why the render failed" detail={shown.job.error} />
        )}
      {notice !== null && <NoticeAlert notice={notice} />}

      <Dialog
        open={asking === 'force'}
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
        open={asking === 'cancel'}
        title="Cancel this render?"
        onClose={closeDialog}
        initialFocus={keepRenderingRef}
      >
        <p>The partial render is discarded. The existing movie, if any, stays as it was.</p>
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
              if (job !== undefined) {
                cancel(job.id, 'cancelConfirm')
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
