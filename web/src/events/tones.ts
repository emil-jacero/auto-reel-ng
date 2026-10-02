import type { ClipStatus } from '../api/event'
import type { EventFailure, JobStatus } from '../api/events'
import type { IconName } from '../ui/Icon'
import type { Tone } from '../ui/Pill'

/*
 * How each status looks: its tone and icon, the same on every screen. The words
 * stay in `labels.ts`, so neither map's readers change when the other does. A
 * `Record` over the generated union fails `tsc --noEmit` when the union gains,
 * loses or renames a member, as the label maps do.
 */

export type StatusLook = { tone: Tone; icon: IconName }

/** The render verdict, keyed by `staleness.stale`. */
export const VERDICT_LOOK: Record<'stale' | 'fresh', StatusLook> = {
  stale: { tone: 'warn', icon: 'refresh' },
  fresh: { tone: 'ok', icon: 'check' },
}

export const JOB_STATUS_LOOK: Record<JobStatus, StatusLook> = {
  queued: { tone: 'idle', icon: 'clock' },
  running: { tone: 'info', icon: 'loader' },
  done: { tone: 'ok', icon: 'check' },
  failed: { tone: 'err', icon: 'alert-triangle' },
  canceled: { tone: 'idle', icon: 'x' },
}

export const CLIP_STATUS_LOOK: Record<ClipStatus, StatusLook> = {
  active: { tone: 'idle', icon: 'check' },
  new: { tone: 'info', icon: 'info' },
  missing: { tone: 'err', icon: 'alert-triangle' },
  ignored: { tone: 'idle', icon: 'x' },
}

/**
 * A clip `reel.yaml` excludes: a flag beside the status (`Clip.excluded`), so it
 * has a look of its own to show next to, or instead of, the status's.
 */
export const EXCLUDED_LOOK: StatusLook = { tone: 'idle', icon: 'eye-off' }

export const FAILURE_LOOK: Record<EventFailure, StatusLook> = {
  unparseable_reel_yaml: { tone: 'err', icon: 'alert-triangle' },
  unusable_metadata: { tone: 'err', icon: 'alert-triangle' },
  unreadable_disk: { tone: 'err', icon: 'alert-triangle' },
}
