import type { EventFailure, JobStatus, StalenessReason } from '../api/events'

/*
 * Words for the generated vocabularies. A `Record` over the union fails
 * `tsc --noEmit` when the union gains a member (a missing key) or loses or
 * renames one (an excess key), so a slug can never reach the screen verbatim.
 */

export const REASON_LABEL: Record<StalenessReason, string> = {
  no_manifest: 'never rendered',
  output: 'movie file missing',
  editorial: 'edited since last render',
  defaults: 'project defaults changed',
  clip_set: 'clips changed',
  engine: 'render engine updated',
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
  unusable_metadata: 'missing or invalid date or title',
  unreadable_disk: "files can't be read",
}
