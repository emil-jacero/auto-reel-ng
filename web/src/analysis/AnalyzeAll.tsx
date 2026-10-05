import './analysis.css'

import { useCallback, useRef, useState } from 'react'

import { analyzeAll } from '../api/analysis'
import type { AnalyzeAllResult } from '../api/analysis'
import { DATABASE_CAUSE, folderName } from '../events/common'
import { unansweredFailure } from '../events/labels'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { analyzeAllWords } from './analyzeAll'

/*
 * The event list's Analyze all (`analysis-web-controls`): `POST /api/v1/analysis`, no
 * confirmation, one request at a time. Its answer stays as a line on the list's header until
 * the next press or the next Refresh, and is said once by a polite status region; a failure is
 * an alert. It starts no render and changes no row: the header's analysis count shows the jobs.
 */

export type AnalyzeAllState = {
  press(): void
  /** Forget the answer: the list was read again. */
  clear(): void
  busy: boolean
  result: AnalyzeAllResult | null
  failure: { title: string; detail: string | null } | null
}

const NOT_QUEUED = 'Analyze all could not queue the analyses.'

export function useAnalyzeAll(): AnalyzeAllState {
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [result, setResult] = useState<AnalyzeAllResult | null>(null)
  const [failure, setFailure] = useState<AnalyzeAllState['failure']>(null)

  const press = useCallback(() => {
    if (busyRef.current) {
      return
    }
    busyRef.current = true
    setBusy(true)
    setResult(null)
    setFailure(null)
    analyzeAll()
      .then((answer) => {
        switch (answer.kind) {
          case 'counted':
            setResult(answer.result)
            break
          case 'problem':
            setFailure({
              title: `${NOT_QUEUED} The project could not be scanned.`,
              detail: answer.problem.detail,
            })
            break
          case 'database':
            setFailure({ title: `${NOT_QUEUED} ${DATABASE_CAUSE}`, detail: answer.problem.detail })
            break
          case 'unreachable':
          case 'unpublished': {
            const { cause, detail } = unansweredFailure(answer)
            setFailure({ title: `${NOT_QUEUED} ${cause}`, detail })
            break
          }
        }
      })
      .catch((error: unknown) => {
        setFailure({ title: NOT_QUEUED, detail: String(error) })
      })
      .finally(() => {
        busyRef.current = false
        setBusy(false)
      })
  }, [])

  const clear = useCallback(() => {
    setResult(null)
    setFailure(null)
  }, [])

  return { press, clear, busy, result, failure }
}

/** The toolbar's button: busy, not disabled, while its request is in flight (it keeps focus). */
export function AnalyzeAllButton({ state }: { state: AnalyzeAllState }) {
  return (
    <button
      type="button"
      className="btn btn-secondary"
      aria-disabled={state.busy || undefined}
      aria-busy={state.busy || undefined}
      onClick={state.press}
    >
      <Icon name="scan" />
      Analyze all
    </button>
  )
}

/** The answer's line on the list's header, with the unreadable events in a list that expands. */
export function AnalyzeAllLine({ state }: { state: AnalyzeAllState }) {
  const { result } = state
  if (result === null) {
    return null
  }
  return (
    <span className="analyze-all-line">
      <Icon name="scan" />
      <span>{analyzeAllWords(result)}</span>
      {result.unreadable.length > 0 && (
        <details className="analyze-all-unreadable">
          <summary>Which events could not be read</summary>
          <ul>
            {result.unreadable.map((event) => (
              <li key={event.event_id}>
                <strong>{folderName(event.event_id)}</strong>: {event.detail}
              </li>
            ))}
          </ul>
        </details>
      )}
    </span>
  )
}

/** The answer said once (mounted in every state, so the words put into it are announced). */
export function AnalyzeAllStatus({ state }: { state: AnalyzeAllState }) {
  return (
    <p role="status" className="visually-hidden">
      {state.result === null ? '' : analyzeAllWords(state.result)}
    </p>
  )
}

/** A refused Analyze all, in the list's words for its other failures. */
export function AnalyzeAllAlert({ state }: { state: AnalyzeAllState }) {
  const { failure } = state
  return failure === null ? null : <Alert tone="err" title={failure.title} detail={failure.detail} />
}
