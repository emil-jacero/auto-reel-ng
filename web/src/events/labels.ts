import type { ClipStatus } from '../api/event'
import type { EventFailure, JobStatus, StalenessReason } from '../api/events'
import type { Unanswered } from '../api/http'

/*
 * Words for the generated vocabularies. A `Record` over the union fails
 * `tsc --noEmit` when the union gains a member (a missing key) or loses or
 * renames one (an excess key), so a slug can never reach the screen verbatim.
 */

export const REASON_LABEL: Record<StalenessReason, string> = {
  no_manifest: 'never rendered',
  output: 'movie file missing',
  output_renamed: 'movie name changed',
  editorial: 'edited since last render',
  defaults: 'project defaults changed',
  clip_set: 'clips changed',
  engine: 'render engine updated',
}

/**
 * What the event page adds, on a line of its own, for a reason whose words alone
 * do not say what the next render does; null for the others. Exhaustive like the
 * labels, so a new reason is a decision here too.
 */
export const REASON_NOTE: Record<StalenessReason, string | null> = {
  no_manifest: null,
  output: null,
  output_renamed:
    'The next render saves the movie under its new name. The movie under its old name stays on disk.',
  editorial: null,
  defaults: null,
  clip_set: null,
  engine: null,
}

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'Queued',
  running: 'Rendering',
  done: 'Rendered',
  failed: 'Failed',
  canceled: 'Canceled',
}

export const FAILURE_LABEL: Record<EventFailure, string> = {
  unparseable_reel_yaml: "reel.yaml can't be read",
  unusable_metadata: 'Missing or invalid date or title',
  unreadable_disk: "Files can't be read",
}

export const CLIP_STATUS_LABEL: Record<ClipStatus, string> = {
  new: 'New, not yet in reel.yaml',
  active: 'Included',
  missing: 'Missing from disk',
  ignored: 'Ignored',
}

/** An excluded clip is listed in reel.yaml but a render leaves it out of the movie. */
export const EXCLUDED_LABEL = 'Excluded'

/*
 * A request with no usable answer, in the words every screen uses. Type-only
 * imports here (no `common.tsx`, which imports this module), so the helpers
 * below run under `node --experimental-strip-types` as they are.
 */

export const UNANSWERED_CAUSE: Record<Unanswered['kind'], string> = {
  unreachable: 'The service is not reachable.',
  unpublished: 'The service sent an unexpected answer.',
}

/** What to do when a read the operator repeats with `control` got no answer at all. */
export function notReachableHint(control: string): string {
  return `Check that auto-reel serve is running, then press ${control}.`
}

/** The same for the list and the page, whose read is repeated by Refresh. */
export const NOT_REACHABLE_HINT = notReachableHint('Refresh')

/** What to do when such a read got an answer its route does not publish. */
export const UNPUBLISHED_HINT = "The service's log may say why; press Refresh to try again."

/**
 * A read's failure for the list and the page: the cause, and what to show under
 * it. No answer gets the way to recover, never the browser's own error text; an
 * unexpected answer gets the request and the status it received, then what to do.
 */
export function unansweredFailure(result: Unanswered): { cause: string; detail: string } {
  return {
    cause: UNANSWERED_CAUSE[result.kind],
    detail:
      result.kind === 'unreachable' ? NOT_REACHABLE_HINT : `${result.message}. ${UNPUBLISHED_HINT}`,
  }
}

/**
 * The service's detail for an event it could not read, as a row or page that
 * already names the event's folder shows it: a leading `<folder name>: ` is
 * dropped and the rest starts with a capital. Anything else, a parse error's
 * `/path/reel.yaml: …` included, is returned as the service wrote it.
 */
export function failureDetail(eventId: string, detail: string): string {
  const prefix = `${eventId.split('/').pop() ?? eventId}: `
  const rest = detail.startsWith(prefix) ? detail.slice(prefix.length) : ''
  if (rest.trim() === '') {
    return detail
  }
  return rest.charAt(0).toUpperCase() + rest.slice(1)
}
