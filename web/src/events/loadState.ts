import type { EventDetail as EventDetailData } from '../api/event'
import type { EventFailure } from '../api/events'

/*
 * What the event page shows while it reads, and how a read changes it. Pure, so
 * `loadState.test.ts` (run by `npm test`) holds what the page's Refresh promises.
 */

export type Failure = {
  cause: string
  detail: string | null
  /** The failure kind, shown in the list's "Needs attention" words. */
  failure?: EventFailure
  /** The event does not exist: offer the way back. */
  notFound?: boolean
}

/**
 * `quiet`: a re-read the page starts by itself, which keeps the content shown.
 * `keepMovie`: an operator's Refresh, which keeps the Movie section's player.
 */
export type LoadOptions = { quiet?: boolean; keepMovie?: boolean }

/** The two fields of an event read that the render region shows. */
export type Verdict = Pick<EventDetailData, 'staleness' | 'latest_job'>

/** Why a verdict read in Edit mode got no usable answer: the words the region shows. */
export type VerdictUnread = { cause: string; detail: string | null }

export type LoadState =
  // `editPlace`: the header keeps Edit's place, so Refresh stays where it was
  // pressed. Set when the page showed Edit before this read, or reads for the first
  // time; not after a failure, which has no Edit.
  // `movie`: the event whose Movie section stays through a Refresh, so its player
  // is the same element when the read answers.
  | { status: 'loading'; editPlace: boolean; movie?: EventDetailData }
  // `updating`: a quiet re-read runs, and the content shown is the last read's.
  // `verdict`, `verdictUnread`: only while Edit mode is open, where `event` is the editor's
  // baseline and a newer read must not replace it. `verdict` is the render region's newer
  // verdict and latest job; `verdictUnread` says that a read of them got no answer. A read
  // that answers builds a new state without either.
  | {
      status: 'ready'
      event: EventDetailData
      fetchedAt: Date
      updating?: boolean
      verdict?: Verdict
      verdictUnread?: VerdictUnread
    }
  | ({ status: 'failed' } & Failure)

/** The event whose Movie section a page in this state shows, if any. */
export function movieOf(state: LoadState): EventDetailData | undefined {
  if (state.status === 'ready') {
    return state.event
  }
  return state.status === 'loading' ? state.movie : undefined
}

/**
 * The state a read starts in, given the one shown. A quiet read keeps the content
 * of a page that has some. Any other shows placeholders, keeping the Movie
 * section's event only for a Refresh: the first read, leaving Edit mode and a
 * failure's retry carry none, so their players are new.
 */
export function readingState(shown: LoadState, options: LoadOptions): LoadState {
  if (options.quiet === true && shown.status === 'ready') {
    return { ...shown, updating: true }
  }
  return {
    status: 'loading',
    editPlace: shown.status === 'loading' ? shown.editPlace : shown.status === 'ready',
    movie: options.keepMovie === true ? movieOf(shown) : undefined,
  }
}

/** What the render region shows: a newer verdict if Edit mode got one, else the last read's. */
export function verdictOf(state: Extract<LoadState, { status: 'ready' }>): Verdict {
  return state.verdict ?? state.event
}

/**
 * The state after a verdict read in Edit mode answered: the event's verdict and latest job,
 * and nothing else (`event`, `fetchedAt` and `updating` are the shown state's own), and no
 * note that a read got no answer. A page that is not ready has no region to refresh.
 */
export function withVerdict(shown: LoadState, read: EventDetailData): LoadState {
  if (shown.status !== 'ready') {
    return shown
  }
  const { verdictUnread: _unread, ...kept } = shown
  return { ...kept, verdict: { staleness: read.staleness, latest_job: read.latest_job } }
}

/** The state after a verdict read got no usable answer: the region keeps its words and says so. */
export function withVerdictUnread(shown: LoadState, unread: VerdictUnread): LoadState {
  return shown.status === 'ready' ? { ...shown, verdictUnread: unread } : shown
}
