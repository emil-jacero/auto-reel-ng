import './cuts.css'

import { useEffect, useState } from 'react'

import type { EventDetail } from '../api/event'
import { fetchReel } from '../api/reel'
import type { ReelDocument, ReelReadResult } from '../api/reel'
import { plural } from '../events/common'
import { FAILURE_LABEL, unansweredFailure } from '../events/labels'
import { turnsOf } from '../rotate/turn.ts'
import type { Turn } from '../rotate/turn.ts'
import { Alert } from '../ui/Alert'
import { CHEVRON, CutList, SCISSORS } from './CutsPanel'
import { cutOutSeconds, formatLength } from './times'
import type { Trim } from './times'

/*
 * The event page's view of each clip's cuts: beside a clip with cuts, how many
 * and the time they cut out, which opens their list. The detail carries no
 * cuts, so they come from the same `GET …/reel` Edit mode reads, after each
 * event read; it writes nothing. A failure leaves the clips shown, with a note.
 */

/** Identity → its cuts as `reel.yaml` lists them; only clips with cuts. */
export type ClipCuts = ReadonlyMap<string, readonly Trim[]>

export type ReadFailure = { cause: string; detail: string | null }

/** Identity → its saved turn (`rotate`, as a quarter turn); only clips with a turn. */
export type ClipTurns = ReadonlyMap<string, Turn>

/** No turns: one shared empty map, so a state without them keeps its identity. */
export const NO_TURNS: ClipTurns = new Map()

export type ReadCutsState = {
  cuts: ClipCuts | null
  /** The saved turns, read with the cuts from the same document; null when the read failed. */
  turns?: ClipTurns | null
  failure: ReadFailure | null
}

function cutsOf(document: ReelDocument): ClipCuts {
  return new Map(
    Object.entries(document.clips).flatMap(([identity, entry]): [string, Trim[]][] =>
      entry.trims.length === 0 ? [] : [[identity, entry.trims]],
    ),
  )
}

/**
 * Why a read of the event's `reel.yaml` or its analysis could not be had, in the words
 * the page uses for its own reads.
 */
export function failureOf(result: Exclude<ReelReadResult, { kind: 'ok' }>): ReadFailure {
  if (result.kind !== 'problem') {
    const { cause, detail } = unansweredFailure(result)
    return { cause, detail }
  }
  const problem = result.problem
  if (problem.status === 404) {
    return { cause: 'The event is no longer there; refresh the page.', detail: null }
  }
  if (problem.status === 502 && problem.failure != null) {
    return { cause: FAILURE_LABEL[problem.failure], detail: problem.detail }
  }
  return { cause: problem.title, detail: problem.detail }
}

/**
 * The event's cuts, read after each event read (`event` is a new object for every
 * read, a quiet one too). The cuts read last stay shown until the new read answers;
 * a newer read, or leaving the page, aborts the one in flight, silently.
 */
export function useReadCuts(eventId: string, event: EventDetail): ReadCutsState {
  const [state, setState] = useState<ReadCutsState>({ cuts: null, turns: null, failure: null })
  useEffect(() => {
    const controller = new AbortController()
    fetchReel(eventId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState(
            result.kind === 'ok'
              ? { cuts: cutsOf(result.document), turns: turnsOf(result.document.clips), failure: null }
              : { cuts: null, turns: null, failure: failureOf(result) },
          )
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ cuts: null, turns: null, failure: { cause: String(error), detail: null } })
        }
      })
    return () => controller.abort()
  }, [eventId, event])
  return state
}

/** The note a failed read leaves: part of the page's content, not an alert. */
export function ReadCutsNote({ failure }: { failure: ReadFailure | null }) {
  if (failure === null) {
    return null
  }
  return (
    <Alert
      tone="warn"
      role="note"
      title="Cuts could not be read"
      detail={failure.detail === null ? failure.cause : `${failure.cause} ${failure.detail}`}
    />
  )
}

/**
 * A clip's cuts under its name: "2 cuts · −4.5 s", said as "2 cuts · 4.5 s cut
 * out", opening the list as Edit mode lists it, with no control that changes it.
 * Nothing for a clip without cuts.
 */
export function ReadCuts({ cuts, name }: { cuts: readonly Trim[] | undefined; name: string }) {
  if (cuts === undefined || cuts.length === 0) {
    return null
  }
  return (
    <details className="read-cuts">
      <summary>
        {/* Two parts that never break inside: the count, then the time cut out. */}
        <span className="read-cuts-part">
          {SCISSORS}
          {plural(cuts.length, 'cut', 'cuts')} ·
        </span>{' '}
        <span className="read-cuts-part">
          {/* One item: the part's gap never falls between the minus and its number. */}
          <span>
            <span aria-hidden="true">−</span>
            {formatLength(cutOutSeconds(cuts))}
          </span>
          <span className="visually-hidden"> cut out</span>
          {CHEVRON}
        </span>
      </summary>
      <CutList cuts={cuts} label={`Cuts of ${name}`} keyOf={(_, index) => String(index)} />
    </details>
  )
}
