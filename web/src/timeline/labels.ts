import type { EnqueueProxiesResult } from '../api/proxies.ts'
import type { JobStatus } from '../api/jobs.ts'
import type { ProxyProbe } from '../api/clipMedia.ts'
import { formatTime } from '../cuts/times.ts'
import { plural } from '../events/names.ts'
import type { Tone } from '../ui/Pill.tsx'
import type { Readiness } from './layout.ts'
import type { Ms } from './model.ts'

/*
 * The Timeline's words, pure so that `npm test` checks them: the Prepare state's counts
 * and answers, a proxy job's status, the playhead's names and announcements, and the
 * notes. A `Record` over a closed union (or a `never` check) fails `tsc --noEmit` when
 * the union gains a member without words.
 */

// --- the Prepare state ------------------------------------------------------------------

export const PREPARE_BUTTON = 'Prepare proxies'

/**
 * A proxy job's status in words, in place of a render's ("Rendering", "Rendered"): the
 * job makes a small copy of each clip so the Timeline can lay them out and play them.
 */
export const PROXY_STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'Queued',
  running: 'Preparing proxies',
  done: 'Proxies ready',
  failed: 'Preparing failed',
  canceled: 'Preparing canceled',
}

/** `24 of 25 clips are ready`, `0 of 1 clip is ready`. */
export function readyCountWords(r: Pick<Readiness, 'ready' | 'total'>): string {
  const verb = r.total === 1 ? 'is' : 'are'
  return `${r.ready} of ${plural(r.total, 'clip', 'clips')} ${verb} ready`
}

/** The clips that are not ready, by state: `25 not prepared`, `1 failed`, none for none. */
export function notReadyWords(r: Readiness): string[] {
  const parts: [number, string][] = [
    [r.absent, 'not prepared'],
    [r.stale, 'damaged'],
    [r.failed, 'failed'],
    [r.unusable, 'with no usable length'],
    [r.unknown, 'not known'],
  ]
  return parts.filter(([n]) => n > 0).map(([n, words]) => `${n} ${words}`)
}

/** The line under the counts: what the timeline waits for and what the button makes. */
export const STATE_EXPLAINED =
  'The timeline opens when every clip has a proxy. Prepare proxies makes the missing, damaged and failed ones; a clip that changed on disk counts as not prepared.'

export type Notice = { tone: Tone; title: string; detail: string | null }

/**
 * What the answer to "Prepare proxies" says, apart from the job it shows: null for a
 * created job (the job says it). Exhaustive over the answers.
 */
export function noticeFor(result: EnqueueProxiesResult): Notice | null {
  switch (result.kind) {
    case 'enqueued':
      return null
    case 'ready':
      return { tone: 'ok', title: 'The proxies are ready.', detail: 'Reading the event again.' }
    case 'active':
      return {
        tone: 'info',
        title: 'The proxies are already being prepared.',
        detail: 'Showing the job that is running.',
      }
    case 'problem':
      return result.problem.status === 404
        ? {
            tone: 'err',
            title: 'This event is no longer there, so no proxy job was started.',
            detail: result.problem.detail,
          }
        : {
            tone: 'err',
            title: 'The proxies were not started.',
            detail: result.problem.detail,
          }
    case 'database':
      return {
        tone: 'err',
        title: "The service can't reach its database, so no proxy job was started.",
        detail: result.problem.detail,
      }
    case 'unreachable':
      return {
        tone: 'err',
        title: 'The service did not answer, so no proxy job was started.',
        detail: 'Check that it is running, then try again.',
      }
    case 'unpublished':
      return {
        tone: 'err',
        title: 'The service gave an answer this page does not know.',
        detail: `${result.message}. It cannot tell whether a proxy job started.`,
      }
    default: {
      const unhandled: never = result
      throw new Error(`unhandled proxy enqueue answer ${String(unhandled)}`)
    }
  }
}

/** A proxy job that failed or was canceled, in words, with the error the service recorded. */
export function jobEndWords(status: 'failed' | 'canceled', error: string | null | undefined): Notice {
  if (status === 'canceled') {
    return { tone: 'info', title: 'Preparing the proxies was canceled.', detail: null }
  }
  const text = error?.trim()
  return {
    tone: 'err',
    title: 'Preparing the proxies failed.',
    detail: text === undefined || text === '' ? null : text,
  }
}

/** The words a polite region announces when a proxy job changes state; never its progress. */
export function jobAnnouncement(status: JobStatus, cancelRequested: boolean): string {
  if (cancelRequested && (status === 'queued' || status === 'running')) {
    return 'Cancelling the proxy job'
  }
  switch (status) {
    case 'queued':
      return 'Proxy job queued. Waiting for a worker'
    case 'running':
      return 'Preparing proxies'
    case 'done':
      return 'Proxies ready'
    case 'failed':
      return 'Preparing the proxies failed'
    case 'canceled':
      return 'Preparing the proxies was canceled'
    default: {
      const unhandled: never = status
      throw new Error(`unhandled job status ${String(unhandled)}`)
    }
  }
}

// --- the track --------------------------------------------------------------------------

export const NO_CLIPS = 'This event has no clip to show.'
export const FILM_FAILED = 'A filmstrip could not be loaded.'
export const FILM_FAILED_DETAIL =
  'The clips whose picture is missing keep their names, cuts and place on the track.'
export const CUTS_UNREADABLE = 'The cuts could not be read.'
export const CUTS_UNREADABLE_DETAIL =
  'The track is shown without cuts, and without the movie’s length. Play does not skip cuts.'
/** Shown while the page's read of the cuts is still on its way: Play waits for it. */
export const CUTS_READING = 'Reading the cuts…'

/** `Movie 3:12 of 3:45 of footage`. */
export function movieWords(movie: Ms, footage: Ms): string {
  return `Movie ${formatTime(movie / 1000)} of ${formatTime(footage / 1000)} of footage`
}

/** A clip's length and cuts, for its description. */
export function clipDescription(durationMs: Ms, cutCount: number): string {
  const cuts = cutCount === 0 ? 'no cuts' : plural(cutCount, 'cut', 'cuts')
  return `${formatTime(durationMs / 1000)} long, ${cuts}`
}

/** The slider's value text: `Harbour, 0:12.4 of 0:24.96; 1:12 of 3:12 in all`. */
export function playheadValueText(
  name: string,
  localMs: Ms,
  durationMs: Ms,
  atMs: Ms,
  totalMs: Ms,
): string {
  const here = `${formatTime(localMs / 1000)} of ${formatTime(durationMs / 1000)}`
  const all = `${formatTime(atMs / 1000)} of ${formatTime(totalMs / 1000)} in all`
  return `${name}, ${here}; ${all}`
}

/** Announced once when the playhead is placed: `Playhead at Harbour, 0:12.4`. */
export function playheadAnnouncement(name: string, localMs: Ms): string {
  return `Playhead at ${name}, ${formatTime(localMs / 1000)}`
}

export const PLAY = 'Play'
export const PAUSE = 'Pause'
export const ZOOM_IN = 'Zoom in'
export const ZOOM_OUT = 'Zoom out'
export const FIT = 'Fit'
export const PLAYHEAD = 'Playhead'
export const TRACK_KEYS =
  'Left and Right step a frame, Shift one second, Page Up and Page Down five seconds, Home and End go to the ends, Space plays. + and - zoom, 0 fits.'
export const NOT_STARTED =
  'The browser did not start playing. Press Play again.'

// --- a proxy that does not play ----------------------------------------------------------

export type PlaybackNote = Notice & {
  /** The proxy is gone from the service: Prepare proxies makes it again. */
  gone: boolean
}

/**
 * Why a clip's proxy did not play, from the one byte asked of it after the failure.
 * `mediaWords` is the browser's own account of the failure, used only when the service
 * serves the file and the browser still cannot play it.
 */
export function playbackNote(name: string, probe: ProxyProbe, mediaWords: string): PlaybackNote {
  switch (probe.kind) {
    case 'ok':
      return {
        tone: 'err',
        gone: false,
        title: `This browser cannot play the proxy of ${name}.`,
        detail: mediaWords,
      }
    case 'empty':
      return {
        tone: 'err',
        gone: true,
        title: `The proxy of ${name} is empty.`,
        detail: 'There is nothing to play. Prepare the proxies again.',
      }
    case 'problem':
      return probe.problem.status === 404
        ? {
            tone: 'warn',
            gone: true,
            title: `The proxy of ${name} is no longer there.`,
            detail: `${probe.problem.detail.replace(/\.?$/, '.')} Prepare the proxies again.`,
          }
        : {
            tone: 'err',
            gone: false,
            title: `The proxy of ${name} could not be read.`,
            detail: probe.problem.detail,
          }
    case 'unreachable':
      return {
        tone: 'err',
        gone: false,
        title: `The service did not answer for the proxy of ${name}.`,
        detail: 'Check that it is running, then press Play again.',
      }
    case 'unpublished':
      return {
        tone: 'err',
        gone: false,
        title: `The proxy of ${name} could not be played.`,
        detail: `${probe.message}.`,
      }
    default: {
      const unhandled: never = probe
      throw new Error(`unhandled proxy probe ${String(unhandled)}`)
    }
  }
}

// --- Edit mode (`timeline-trim`) -----------------------------------------------------------

/** Said while the draft's order or chapters differ from the saved ones: the track draws the saved. */
export const ORDER_SAVED =
  'The Timeline shows the order last saved. Reordering and moving clips stay in the lists below; the track follows them once they are saved. Cuts can be trimmed here all the same.'

/** In the Timeline's picture while a clip preview holds the page's one video. */
export const PREVIEW_OPEN =
  'A clip preview is open, so the Timeline’s picture is paused. Move the playhead or press Play to show it here.'
