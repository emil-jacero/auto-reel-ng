import { useCallback, useEffect, useRef, useState } from 'react'

import { enqueueProxies } from '../api/proxies'
import type { JobStatus } from '../api/jobs'
import { JobMeter, JobState } from '../jobs/JobProgress'
import { isActive, load, merge } from '../jobs/store'
import type { ShownJob } from '../jobs/shownJob'
import { useProxyJob } from '../jobs/useJob'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import {
  PREPARE_BUTTON,
  PROXY_STATUS_LABEL,
  STATE_EXPLAINED,
  jobAnnouncement,
  jobEndWords,
  noticeFor,
  notReadyWords,
  readyCountWords,
} from './labels'
import type { Notice } from './labels'
import type { Readiness } from './layout'

/*
 * Asking for the proxies. The Timeline lays clips out from their proxies, so while any is
 * missing the section shows this instead of the track: the counts, "Prepare proxies" (the
 * only way the page starts that job), and the proxy job once there is one, from the jobs
 * connection the page already holds. Opening the Timeline never starts it. No toast and
 * no `track()`: a proxy job's end is told here, in the section.
 */

export type PrepareControl = {
  /** Ask for the proxies (one request per press). */
  press: () => void
  /** A request is waiting for its answer, or a proxy job is queued or running. */
  busy: boolean
  /** What the last answer says, apart from the job. */
  notice: Notice | null
  /** The proxy job to show: one that is active, or that failed or was canceled while this page watched. */
  job: ShownJob | null
  /** The words a polite region announces: a job's state changes, never its progress. */
  announcement: string
}

/**
 * The Prepare state's behaviour, held by the section so that the track's "proxy is gone"
 * note can press the same button. `onFinished` reads the event again (quietly) when the
 * job ends, whichever way, and after the answer "all ready".
 */
export function usePrepare(eventId: string, onFinished: () => void): PrepareControl {
  const proxyJob = useProxyJob(eventId)
  const [waiting, setWaiting] = useState(false)
  const pressing = useRef(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [watched, setWatched] = useState<ReadonlySet<string>>(new Set())
  const seen = useRef(new Map<string, { status: JobStatus; cancel: boolean }>())
  const onFinishedRef = useRef(onFinished)
  useEffect(() => {
    onFinishedRef.current = onFinished
  })

  const jobId = proxyJob?.job.id
  const status = proxyJob?.job.status
  const cancel = proxyJob?.job.cancel_requested
  useEffect(() => {
    if (jobId === undefined || status === undefined || cancel === undefined) {
      return
    }
    const was = seen.current.get(jobId)
    seen.current.set(jobId, { status, cancel })
    if (isActive(status)) {
      setWatched((held) => (held.has(jobId) ? held : new Set(held).add(jobId)))
      if (was === undefined || was.status !== status || was.cancel !== cancel) {
        setAnnouncement(jobAnnouncement(status, cancel))
      }
    } else if (was !== undefined && isActive(was.status)) {
      // Ended while this page watched: say so once, and read the event again.
      setAnnouncement(jobAnnouncement(status, cancel))
      onFinishedRef.current()
    }
  }, [jobId, status, cancel])

  const press = useCallback(() => {
    if (pressing.current) {
      return
    }
    pressing.current = true
    setWaiting(true)
    setNotice(null)
    enqueueProxies(eventId)
      .then((result) => {
        switch (result.kind) {
          case 'enqueued':
            merge(result.job)
            break
          case 'ready':
            setNotice(noticeFor(result))
            onFinishedRef.current()
            break
          case 'active':
            // Someone else started it: follow that job.
            load(result.jobId)
            setNotice(noticeFor(result))
            break
          default:
            setNotice(noticeFor(result))
        }
      })
      .finally(() => {
        pressing.current = false
        setWaiting(false)
      })
  }, [eventId])

  const active = proxyJob !== null && isActive(proxyJob.job.status)
  const job =
    proxyJob !== null &&
    (active ||
      ((proxyJob.job.status === 'failed' || proxyJob.job.status === 'canceled') &&
        watched.has(proxyJob.job.id)))
      ? proxyJob
      : null
  return { press, busy: waiting || active, notice, job, announcement }
}

/** The button: busy is `aria-disabled` + `aria-busy`, never `disabled`, so focus stays. */
export function PrepareButton({ control, primary = true }: { control: PrepareControl; primary?: boolean }) {
  return (
    <button
      type="button"
      className={`btn ${primary ? 'btn-primary' : 'btn-secondary'}`}
      aria-disabled={control.busy || undefined}
      aria-busy={control.busy || undefined}
      onClick={() => {
        if (!control.busy) {
          control.press()
        }
      }}
    >
      <Icon name="film" />
      {PREPARE_BUTTON}
    </button>
  )
}

/** The answer's note and the job's state, as the Prepare state and the gone-proxy note show them. */
export function PrepareJob({ control }: { control: PrepareControl }) {
  const { job, notice } = control
  const end =
    job !== null && (job.job.status === 'failed' || job.job.status === 'canceled')
      ? jobEndWords(job.job.status, 'error' in job.job ? job.job.error : null)
      : null
  return (
    <>
      {job !== null && (
        <div className="tl-job">
          <JobState shown={job} statusLabel={PROXY_STATUS_LABEL} />
          {isActive(job.job.status) && <JobMeter shown={job} label="Proxy progress" />}
        </div>
      )}
      {end !== null && (
        <Alert tone={end.tone} role="note" title={end.title} detail={end.detail} />
      )}
      {notice !== null && (
        <Alert
          tone={notice.tone}
          role={notice.tone === 'err' ? 'alert' : 'note'}
          title={notice.title}
          detail={notice.detail}
        />
      )}
    </>
  )
}

/** The state that stands in the track's place while a shown clip has no ready proxy. */
export function Prepare({ readiness, control }: { readiness: Readiness; control: PrepareControl }) {
  const notReady = notReadyWords(readiness)
  return (
    <div className="tl-prepare">
      <p className="tl-counts">
        <strong>{readyCountWords(readiness)}</strong>
        {notReady.length > 0 && <> · {notReady.join(' · ')}</>}
      </p>
      <p className="tl-hint">
        The timeline lays the clips out from small copies of them, called proxies. {STATE_EXPLAINED}
      </p>
      <div className="tl-prepare-actions">
        <PrepareButton control={control} />
      </div>
      <PrepareJob control={control} />
    </div>
  )
}
