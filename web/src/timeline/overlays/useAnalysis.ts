import { useEffect, useState } from 'react'

import { fetchAnalysis } from '../../api/analysis'
import type { Analysis } from '../../api/analysis'
import { failureOf } from '../../cuts/ReadCuts'
import type { ReadFailure } from '../../cuts/ReadCuts'

/** How the one read of the analysis stands: a failure is a value, never thrown. */
export type AnalysisState =
  | { status: 'idle' }
  | { status: 'reading' }
  | { status: 'ok'; analysis: Analysis }
  | { status: 'failed'; failure: ReadFailure }

/**
 * Read the event's analysis once, when the track mounts (never while the section is
 * closed or preparing: the hook is called by the Timeline, which only mounts then). A
 * null `eventId` reads nothing. Leaving the page or closing the section abandons a read
 * in flight, silently; the next opening reads again.
 */
export function useAnalysis(eventId: string | null): AnalysisState {
  const [state, setState] = useState<AnalysisState>(
    eventId === null ? { status: 'idle' } : { status: 'reading' },
  )
  useEffect(() => {
    if (eventId === null) {
      return undefined
    }
    const controller = new AbortController()
    setState({ status: 'reading' })
    fetchAnalysis(eventId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState(
            result.kind === 'ok'
              ? { status: 'ok', analysis: result.analysis }
              : { status: 'failed', failure: failureOf(result) },
          )
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ status: 'failed', failure: { cause: String(error), detail: null } })
        }
      })
    return () => controller.abort()
  }, [eventId])
  return eventId === null ? { status: 'idle' } : state
}
