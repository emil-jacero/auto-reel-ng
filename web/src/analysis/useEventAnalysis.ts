import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'

import { enqueueAnalysis, fetchAnalysis } from '../api/analysis'
import type { Problem } from '../api/http'
import { failureOf } from '../cuts/ReadCuts'
import { DATABASE_CAUSE, folderName } from '../events/common'
import { failureDetail, unansweredFailure } from '../events/labels'
import { announce } from '../jobs/announce'
import { getState, isActive, load, merge, subscribe, wasReconciled } from '../jobs/store'
import { useAnalysisJob } from '../jobs/useJob'
import { badgeOf, neverAnalyzed } from './badge'
import type { AnalysisRead, Badge } from './badge'
import { endWords, onJobChange, recheckKey } from './refresh'
import type { Observed } from './refresh'

/*
 * The event page's one analysis read (`analysis-web-controls`, D1, D3, D4): read on opening,
 * on `reload()` (Refresh) and when the event's analysis job ends; the page header, the read
 * view's Re-analyze and Edit mode's Timeline all show this one binding, so they never
 * disagree. Re-analyze lives here too, so the header's and the Timeline's are one action.
 */

/** An alert the action raised: the request was not accepted, in the page's words. */
export type ActionAlert = { title: string; detail: string | null }

export type Reanalyze = {
  /** Send `POST …/analysis {force: true}`; does nothing while busy or analyzing. */
  press(): void
  /** The request is in flight. */
  busy: boolean
  /** "Analyze" while the event was never analysed, else "Re-analyze". */
  label: string
  /** Why it is unavailable (an analysis is queued or running), else null. */
  reason: string | null
  alert: ActionAlert | null
}

export type AnalysisBinding = {
  read: AnalysisRead
  badge: Badge | null
  /** Read the analysis again, keeping the last answer shown meanwhile. */
  reload(): void
  reanalyze: Reanalyze
}

export const ANALYZING_REASON = 'Analysis is already queued or running.'
export const QUEUED_WORDS = 'Analysis queued.'
export const FRESH_WORDS = 'Nothing to analyze.'
/** A Re-analyze that met a running unforced job: that job is not a re-analysis. */
export const NOT_FORCED_WORDS =
  'An analysis is already running, and it is not a re-analysis. Press Re-analyze again once it ends.'
const NOT_QUEUED = 'The analysis could not be queued.'

/** An enqueue the service refused, in the words the page uses for its other reads. */
function problemAlert(problem: Problem, eventId: string): ActionAlert {
  if (problem.status === 404) {
    return { title: `No event “${folderName(eventId)}” under the project root.`, detail: null }
  }
  if (problem.status === 502) {
    return { title: 'This event could not be read.', detail: failureDetail(eventId, problem.detail) }
  }
  return { title: problem.title, detail: problem.detail }
}

/** Read the event's analysis and follow its analysis job; one binding per event page. */
export function useEventAnalysis(eventId: string): AnalysisBinding {
  const [read, setRead] = useState<AnalysisRead>({ status: 'reading' })
  const inFlight = useRef<AbortController | null>(null)
  // A job end seen live, said once the read it caused answers.
  const sayAfterRead = useRef<Parameters<typeof endWords>[0] | null>(null)

  const reload = useCallback(() => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setRead((shown) => (shown.status === 'reading' ? shown : { ...shown, rereading: true }))
    const settle = (next: AnalysisRead) => {
      if (controller.signal.aborted) {
        return
      }
      inFlight.current = null
      setRead(next)
      const ended = sayAfterRead.current
      sayAfterRead.current = null
      if (ended !== null) {
        announce(endWords(ended, next.status === 'ok' ? next.analysis : null))
      }
    }
    fetchAnalysis(eventId, controller.signal)
      .then((result) => {
        settle(
          result.kind === 'ok'
            ? { status: 'ok', analysis: result.analysis, rereading: false }
            : { status: 'failed', failure: failureOf(result), rereading: false },
        )
      })
      .catch((error: unknown) => {
        // An abort is a newer read or leaving the page, not a failure.
        settle({
          status: 'failed',
          failure: { cause: 'The analysis could not be read.', detail: String(error) },
          rereading: false,
        })
      })
  }, [eventId])

  useEffect(() => {
    reload()
    return () => inFlight.current?.abort()
  }, [reload])

  const liveJob = useAnalysisJob(eventId)
  const live = useSyncExternalStore(subscribe, () => getState().connection === 'live')
  const liveActive = liveJob !== null && isActive(liveJob.status)

  // The read shown now, for the effect below, which runs on the job's changes only.
  const shownRead = useRef(read)
  shownRead.current = read
  // The read whose job a re-read was made for (`recheckKey`): never two for one job.
  const checked = useRef<string | null>(null)

  // The end of the event's analysis job, seen in the store: one re-read.
  const seen = useRef<Observed>(null)
  useEffect(() => {
    const next: Observed = liveJob === null ? null : { id: liveJob.id, status: liveJob.status }
    const change = onJobChange(seen.current, next, liveJob !== null && wasReconciled(liveJob.id))
    seen.current = next
    if (change.reload) {
      sayAfterRead.current = change.announce ? change.endedAs : null
      // This re-read also answers the shown read's "analyzing": the check below makes no other.
      const shown = shownRead.current
      if (shown.status === 'ok') {
        checked.current = shown.analysis.job?.id ?? ''
      }
      reload()
    }
  }, [liveJob, reload])

  // The read says analyzing, but the live connection carries no such job: read once more.
  useEffect(() => {
    const key = recheckKey(read, liveActive, live, checked.current)
    if (key !== null) {
      checked.current = key
      reload()
    }
  }, [read, liveActive, live, reload])

  // Re-analyze: one request at a time; the job it queued is shown without waiting for the socket.
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [own, setOwn] = useState<string | null>(null)
  const [alert, setAlert] = useState<ActionAlert | null>(null)
  const trusted = live || (liveJob !== null && liveJob.id === own)
  const badge = useMemo(() => badgeOf(read, liveJob, trusted), [read, liveJob, trusted])
  const analyzing = badge?.state === 'analyzing'

  const press = useCallback(() => {
    if (busyRef.current || analyzing) {
      return
    }
    busyRef.current = true
    setBusy(true)
    setAlert(null)
    enqueueAnalysis(eventId, { force: true })
      .then((result) => {
        switch (result.kind) {
          case 'enqueued':
            setOwn(result.job.id)
            merge(result.job)
            announce(QUEUED_WORDS)
            break
          case 'active':
            // The job is shown as analyzing; nothing failed.
            setOwn(result.jobId)
            load(result.jobId, { force: true })
            announce(result.forced === false ? NOT_FORCED_WORDS : ANALYZING_REASON)
            break
          case 'fresh':
            announce(FRESH_WORDS)
            break
          case 'problem':
            setAlert(problemAlert(result.problem, eventId))
            break
          case 'database':
            setAlert({ title: `${NOT_QUEUED} ${DATABASE_CAUSE}`, detail: result.problem.detail })
            break
          case 'unreachable':
          case 'unpublished': {
            const { cause, detail } = unansweredFailure(result)
            setAlert({ title: `${NOT_QUEUED} ${cause}`, detail })
            break
          }
        }
      })
      .catch((error: unknown) => {
        setAlert({ title: NOT_QUEUED, detail: String(error) })
      })
      .finally(() => {
        busyRef.current = false
        setBusy(false)
      })
  }, [eventId, analyzing])

  const reanalyze = useMemo<Reanalyze>(
    () => ({
      press,
      busy,
      label: neverAnalyzed(read) ? 'Analyze' : 'Re-analyze',
      reason: analyzing ? ANALYZING_REASON : null,
      alert,
    }),
    [press, busy, read, analyzing, alert],
  )

  return useMemo(() => ({ read, badge, reload, reanalyze }), [read, badge, reload, reanalyze])
}
