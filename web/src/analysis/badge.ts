import type { Analysis, AnalysisState } from '../api/analysis'
import type { JobOut } from '../api/jobs'
import type { IconName } from '../ui/Icon'
import type { Tone } from '../ui/Pill'

/*
 * The event's analysis badge (`analysis-web-controls`, D2): a pure function of the page's one
 * analysis read and the event's newest `analysis` job the connection carries, so the page
 * header and the Timeline's lane always say the same thing. Run by `npm test`.
 *
 * The state is the service's published `state` (`never | stale | current | analyzing |
 * failed`), never the legacy `analyzed` flag, and never guessed from which clips have
 * segments.
 */

/** How the page's one read of the analysis stands; a failure is a value, never thrown. */
export type ReadFailure = { cause: string; detail: string | null }
export type AnalysisRead =
  | { status: 'reading' }
  // `rereading`: a re-read runs; the answer shown is the last one until it arrives.
  | { status: 'ok'; analysis: Analysis; rereading: boolean }
  | { status: 'failed'; failure: ReadFailure; rereading: boolean }

/** The badge's state: a published one that shows, or `unknown` (a failed read, an unknown value). */
export type BadgeState = Exclude<AnalysisState, 'current'> | 'unknown'

export type Badge = {
  state: BadgeState
  words: string
  icon: IconName
  tone: Tone
  /**
   * While analyzing: null for a bar with no value (queued), else the fraction shown (held
   * below 1 while running) and its whole percent, rounded down.
   */
  progress?: { fraction: number; percent: number } | null
  /** While failed: the failed clips' names, at most `FAILED_NAMES_SHOWN`, and how many more. */
  failed?: { names: readonly string[]; more: number }
  /** A failed read's cause: the badge's description. */
  detail?: string
}

/** A running job's bar stops here: only the read after its end says it finished (the render's rule). */
const RUNNING_MAX = 0.99
export const FAILED_NAMES_SHOWN = 3

export const UNKNOWN_WORDS = 'Analysis state unknown'
export const WAITING_WORDS = 'Waiting to analyze'

type Look = { words: string; icon: IconName; tone: Tone }

/**
 * Every published state's words, glyph and tone, keyed by the generated union: a state the
 * service adds fails `tsc` here until it is given words. `current` shows no badge; its words
 * are what a clip row would say, were it ever asked.
 */
export const ANALYSIS_STATE_WORDS: Record<AnalysisState, Look> = {
  never: { words: 'Not analyzed', icon: 'minus', tone: 'idle' },
  stale: { words: 'Analysis out of date', icon: 'refresh', tone: 'info' },
  analyzing: { words: 'Analyzing…', icon: 'scan', tone: 'info' },
  failed: { words: 'Analysis failed', icon: 'alert-triangle', tone: 'warn' },
  current: { words: 'Analyzed', icon: 'check', tone: 'ok' },
}

const UNKNOWN_LOOK: Look = { words: UNKNOWN_WORDS, icon: 'info', tone: 'idle' }

/** Whether a runtime value is a state this build knows (the service may be newer). */
function isKnown(state: unknown): state is AnalysisState {
  return typeof state === 'string' && Object.hasOwn(ANALYSIS_STATE_WORDS, state)
}

function clips(count: number): string {
  return count === 1 ? '1 clip' : `${count} clips`
}

/** The identities of the clips whose read state is `state`, in the read's order. */
export function clipsIn(analysis: Analysis, state: AnalysisState): string[] {
  return Object.entries(analysis.clips ?? {})
    .filter(([, clip]) => clip.state === state)
    .map(([identity]) => identity)
}

function analyzing(job: Pick<JobOut, 'status' | 'progress'>, analysis: Analysis | null): Badge {
  const look = ANALYSIS_STATE_WORDS.analyzing
  if (job.status === 'queued') {
    return { state: 'analyzing', words: WAITING_WORDS, icon: look.icon, tone: look.tone, progress: null }
  }
  const count = analysis === null ? 0 : clipsIn(analysis, 'analyzing').length
  const fraction = Math.max(0, Math.min(job.progress, RUNNING_MAX))
  return {
    state: 'analyzing',
    words: count === 0 ? look.words : `Analyzing ${clips(count)}…`,
    icon: look.icon,
    tone: look.tone,
    progress: { fraction, percent: Math.floor(fraction * 100) },
  }
}

function isActive(job: Pick<JobOut, 'status'>): boolean {
  return job.status === 'queued' || job.status === 'running'
}

/**
 * The badge, or null when there is none to show (the analysis is current, or the first read
 * has not answered). First rule that holds:
 *
 * 1. the event's newest `analysis` job is queued or running and `trusted` (the connection is
 *    live, or the job is the one this page just queued): analyzing, with the job's progress;
 * 2. the read failed: "Analysis state unknown", its cause as the description;
 * 3. the read's `state`, in `ANALYSIS_STATE_WORDS`; a value this build does not know is
 *    "Analysis state unknown", never its slug; `analyzing` takes the read's own `job`.
 */
export function badgeOf(
  read: AnalysisRead,
  liveJob: Pick<JobOut, 'status' | 'progress'> | null,
  trusted: boolean,
): Badge | null {
  const analysis = read.status === 'ok' ? read.analysis : null
  if (liveJob !== null && trusted && isActive(liveJob)) {
    return analyzing(liveJob, analysis)
  }
  if (read.status === 'reading') {
    return null
  }
  if (read.status === 'failed') {
    const { cause, detail } = read.failure
    return { state: 'unknown', ...UNKNOWN_LOOK, detail: detail === null ? cause : `${cause} ${detail}` }
  }
  const state: unknown = read.analysis.state
  if (!isKnown(state)) {
    return { state: 'unknown', ...UNKNOWN_LOOK }
  }
  switch (state) {
    case 'current':
      return null
    case 'analyzing': {
      const job = read.analysis.job
      // The read's own job, last known; with none, a job the read names but did not carry.
      return analyzing(job ?? { status: 'queued', progress: 0 }, read.analysis)
    }
    case 'failed': {
      const names = clipsIn(read.analysis, 'failed')
      const look = ANALYSIS_STATE_WORDS.failed
      return {
        state,
        words: names.length === 0 ? look.words : `${look.words} for ${clips(names.length)}`,
        icon: look.icon,
        tone: look.tone,
        failed: {
          names: names.slice(0, FAILED_NAMES_SHOWN),
          more: Math.max(0, names.length - FAILED_NAMES_SHOWN),
        },
      }
    }
    case 'never':
    case 'stale':
      return { state, ...ANALYSIS_STATE_WORDS[state] }
    default: {
      const unhandled: never = state
      return { state: 'unknown', ...UNKNOWN_LOOK, detail: String(unhandled) }
    }
  }
}

/** `C0007.MP4, C0008.MP4, C0009.MP4 and 2 more`: the names a failed badge is followed by. */
export function failedNamesWords(failed: NonNullable<Badge['failed']>): string {
  const listed = failed.names.join(', ')
  return failed.more > 0 ? `${listed} and ${failed.more} more` : listed
}

/** What one clip's row says, from its own read state; null when current or not in the read. */
export function clipNoteOf(analysis: Analysis, identity: string): Look | null {
  const clip = Object.hasOwn(analysis.clips ?? {}, identity) ? analysis.clips[identity] : undefined
  if (clip === undefined || clip.state === 'current') {
    return null
  }
  return isKnown(clip.state) ? ANALYSIS_STATE_WORDS[clip.state] : UNKNOWN_LOOK
}

/** The failed clips and the service's failure text, for the Timeline help. */
export function failedClips(analysis: Analysis): { identity: string; detail: string | null }[] {
  return Object.entries(analysis.clips ?? {})
    .filter(([, clip]) => clip.state === 'failed')
    .map(([identity, clip]) => ({ identity, detail: clip.detail ?? null }))
}

/** Whether Re-analyze says "Analyze": the read says the event was never analysed. */
export function neverAnalyzed(read: AnalysisRead): boolean {
  return read.status === 'ok' && read.analysis.state === 'never'
}
