import './movie.css'

import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

import type { EventDetail } from '../api/event'
import { movieUrl, probeMovie } from '../api/movie'
import type { MovieFile, MovieProbe } from '../api/movie'
import { thumbnailUrl } from '../api/thumbnail'
import { formatBytes } from '../events/common'
import { FAILURE_LABEL, failureDetail, unansweredFailure } from '../events/labels'
import { FAILURE_LOOK } from '../events/tones'
import { Alert } from '../ui/Alert'
import { Pill } from '../ui/Pill'
import {
  CHANGED_DETAIL,
  MOVIE_AGE_LABEL,
  MOVIE_AGE_LOOK,
  MOVIE_TROUBLE,
  NO_PICTURE_DETAIL,
  OUTDATED_NOTE,
  mediaErrorWords,
} from './labels'
import type { MovieAge } from './labels'

/**
 * The event's rendered movie, in the browser's own player (D-15).
 *
 * Nothing of the movie loads before Play: `preload="none"`, and the poster is
 * the first played clip's thumbnail. On every read of the event it asks the
 * service for the movie's first byte, which names the file and gives its
 * entity-tag; the player's address carries that tag, so a file replaced on disk
 * (a render) always gets a new address and a new player. Failures are said by
 * cause, never as a silent black box.
 */

type Staleness = EventDetail['staleness']

/**
 * Whether the event has a rendered movie, from the detail alone: the movie
 * route serves one exactly when the verdict cites neither `no_manifest` nor
 * `output` (`media-endpoints`' contract; the route still answers 404 in its
 * three edge cases, which the probe finds).
 */
function hasMovie(staleness: Staleness): boolean {
  return !staleness.reasons.includes('no_manifest') && !staleness.reasons.includes('output')
}

/** The section, or nothing when the event has no movie (and no request is made). */
export function MoviePanel({ eventId, event }: { eventId: string; event: EventDetail }) {
  return hasMovie(event.staleness) ? <MovieSection eventId={eventId} event={event} /> : null
}

/** A probe answer that is not a file: the note shown in the player's place. */
type Gone = Exclude<MovieProbe, { kind: 'ok' }>

type Shown =
  // the first probe of this mount is in flight: the player, with no address yet
  | { kind: 'probing' }
  | { kind: 'file'; file: MovieFile }
  // `announced`: found after Play (an alert), not by a read (a note)
  | { kind: 'gone'; gone: Gone; announced: boolean }

/** Where keyboard focus goes after the next commit, when the focused player is replaced. */
type FocusNext = 'video' | 'note' | null

function MovieSection({ eventId, event }: { eventId: string; event: EventDetail }) {
  const headingId = useId()
  const [shown, setShown] = useState<Shown>({ kind: 'probing' })
  const playerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const noteRef = useRef<HTMLDivElement>(null)
  const focusNext = useRef<FocusNext>(null)
  // The version the committed player shows, for the probe's answer to compare.
  const shownVersion = useRef<string | null>(null)

  /** Whether keyboard focus is in the player (the `<video>` or a note's action). */
  const playerHasFocus = () => playerRef.current?.contains(document.activeElement) === true

  // Each read of the event hands a new `event`: probe again. The same file keeps
  // the player as it is; a new one replaces it.
  useEffect(() => {
    const controller = new AbortController()
    probeMovie(eventId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        if (result.kind === 'ok') {
          // The same version keeps its player (same key): position and play state stay.
          if (shownVersion.current !== result.file.version) {
            focusNext.current = playerHasFocus() ? 'video' : null
          }
          setShown({ kind: 'file', file: result.file })
        } else {
          focusNext.current = playerHasFocus() ? 'note' : null
          setShown({ kind: 'gone', gone: result, announced: false })
        }
      })
      .catch((error: unknown) => {
        // An abort is a newer read or leaving the page, not a failure.
        if (!controller.signal.aborted) {
          focusNext.current = playerHasFocus() ? 'note' : null
          const gone: Gone = { kind: 'unreachable', message: String(error) }
          setShown({ kind: 'gone', gone, announced: false })
        }
      })
    return () => controller.abort()
  }, [eventId, event])

  // After the commit that replaced a focused player: focus is never dropped.
  const version = shown.kind === 'file' ? shown.file.version : null
  useLayoutEffect(() => {
    shownVersion.current = version
    const target = focusNext.current
    focusNext.current = null
    if (target === 'video') {
      videoRef.current?.focus()
    } else if (target === 'note') {
      noteRef.current?.focus()
    }
  }, [shown.kind, version])

  const age: MovieAge = event.staleness.stale ? 'outdated' : 'current'
  const look = MOVIE_AGE_LOOK[age]
  const posterClip = event.chapters
    .flatMap((chapter) => chapter.clips)
    .find((clip) => clip.status === 'active' || clip.status === 'new')
  const poster = posterClip === undefined ? undefined : thumbnailUrl(eventId, posterClip)

  return (
    <section className="panel movie-panel" aria-labelledby={headingId}>
      <header className="panel-header">
        <h2 id={headingId}>Movie</h2>
        <Pill tone={look.tone} icon={look.icon}>
          {MOVIE_AGE_LABEL[age]}
        </Pill>
      </header>
      <div className="movie-body">
        {shown.kind === 'gone' ? (
          <div className="movie-note" tabIndex={-1} ref={noteRef}>
            <GoneNote eventId={eventId} gone={shown.gone} announced={shown.announced} />
          </div>
        ) : (
          <MoviePlayer
            // One player per file version: a new file never plays at an old address.
            key={version ?? ''}
            eventId={eventId}
            file={shown.kind === 'file' ? shown.file : null}
            age={age}
            poster={poster}
            headingId={headingId}
            playerRef={playerRef}
            videoRef={videoRef}
            onGone={(gone) => {
              focusNext.current = playerHasFocus() ? 'note' : null
              setShown({ kind: 'gone', gone, announced: true })
            }}
            onLoadNew={(file) => {
              focusNext.current = 'video'
              setShown({ kind: 'file', file })
            }}
          />
        )}
      </div>
    </section>
  )
}

/** Why the movie cannot be offered: a note when a read found it, an alert after Play. */
function GoneNote({
  eventId,
  gone,
  announced,
}: {
  eventId: string
  gone: Gone
  announced: boolean
}) {
  const role = announced ? 'alert' : 'note'
  switch (gone.kind) {
    case 'empty':
      return <Alert role={role} tone={MOVIE_TROUBLE.empty.tone} title={MOVIE_TROUBLE.empty.title} />
    case 'problem': {
      const { problem } = gone
      if (problem.status === 404) {
        const trouble = MOVIE_TROUBLE.no_file
        return <Alert role={role} tone={trouble.tone} title={trouble.title} detail={problem.detail} />
      }
      const trouble = MOVIE_TROUBLE.unreadable
      const failure = problem.failure ?? undefined
      return (
        <Alert
          role={role}
          tone={trouble.tone}
          title={
            <>
              {trouble.title}{' '}
              {failure !== undefined && (
                <Pill tone={FAILURE_LOOK[failure].tone} icon={FAILURE_LOOK[failure].icon}>
                  {FAILURE_LABEL[failure]}
                </Pill>
              )}
            </>
          }
          detail={failureDetail(eventId, problem.detail)}
        />
      )
    }
    case 'unreachable':
    case 'unpublished': {
      const { cause, detail } = unansweredFailure(gone)
      return <Alert role={role} tone="err" title={cause} detail={detail} />
    }
  }
}

/** What went wrong after Play; it lives with its player, so a new player starts clean. */
type Trouble =
  | { kind: 'no_picture' }
  | { kind: 'cannot_play'; words: string }
  | { kind: 'changed'; next: MovieFile }

/**
 * The player of one file version (keyed by it): the frame, the file's facts and
 * any trouble after Play. With no `file` yet it shows the poster and loads
 * nothing.
 */
function MoviePlayer({
  eventId,
  file,
  age,
  poster,
  headingId,
  playerRef,
  videoRef,
  onGone,
  onLoadNew,
}: {
  eventId: string
  file: MovieFile | null
  age: MovieAge
  poster: string | undefined
  headingId: string
  playerRef: RefObject<HTMLDivElement | null>
  videoRef: RefObject<HTMLVideoElement | null>
  onGone: (gone: Gone) => void
  onLoadNew: (file: MovieFile) => void
}) {
  const [trouble, setTrouble] = useState<Trouble | null>(null)
  const diagnosis = useRef<AbortController | null>(null)
  useEffect(() => () => diagnosis.current?.abort(), [])

  const src = file === null ? undefined : movieUrl(eventId, file.version)

  /**
   * A `MediaError` says too little (a missing file is "format" too): ask for the
   * first byte again, and tell a changed file from a file this browser cannot
   * play from a movie the service no longer serves.
   */
  const diagnose = (video: HTMLVideoElement) => {
    if (file === null || diagnosis.current !== null) {
      return
    }
    const error = video.error
    const controller = new AbortController()
    diagnosis.current = controller
    probeMovie(eventId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) {
          return
        }
        diagnosis.current = null
        if (result.kind !== 'ok') {
          onGone(result)
        } else if (result.file.version !== file.version) {
          setTrouble({ kind: 'changed', next: result.file })
        } else {
          const words = mediaErrorWords(error?.code ?? 0, error?.message ?? '')
          setTrouble({ kind: 'cannot_play', words })
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          diagnosis.current = null
          onGone({ kind: 'unreachable', message: String(reason) })
        }
      })
  }

  // Only what the probe's headers carried; a part it did not get is left out.
  const name = file?.name ?? null
  const size = file?.size == null ? null : formatBytes(file.size)
  const download = src === undefined ? null : (
    <a className="btn btn-secondary" href={src} download>
      Download the movie
    </a>
  )

  return (
    <div className="movie-figure" ref={playerRef}>
      <div className="movie-frame">
        <video
          ref={videoRef}
          controls
          preload="none"
          poster={poster}
          src={src}
          aria-labelledby={headingId}
          onLoadedMetadata={(e) => {
            // A picture this browser cannot decode (MPEG-4 Part 2, HEVC) raises no
            // error: it plays the sound and reports no picture size.
            if (e.currentTarget.videoWidth === 0) {
              setTrouble((was) => was ?? { kind: 'no_picture' })
            }
          }}
          onError={(e) => diagnose(e.currentTarget)}
        />
      </div>
      {(name !== null || size !== null) && (
        <p className="movie-facts">
          {name !== null && <span className="movie-file">{name}</span>}
          {name !== null && size !== null && ' · '}
          {size}
        </p>
      )}
      {age === 'outdated' && <p className="movie-facts">{OUTDATED_NOTE}</p>}
      {trouble?.kind === 'no_picture' && (
        <Alert
          role="status"
          tone={MOVIE_TROUBLE.no_picture.tone}
          title={MOVIE_TROUBLE.no_picture.title}
          detail={NO_PICTURE_DETAIL}
          action={download ?? undefined}
        />
      )}
      {trouble?.kind === 'cannot_play' && (
        <Alert
          role="alert"
          tone={MOVIE_TROUBLE.cannot_play.tone}
          title={MOVIE_TROUBLE.cannot_play.title}
          detail={trouble.words}
          action={download ?? undefined}
        />
      )}
      {trouble?.kind === 'changed' && (
        <Alert
          role="alert"
          tone={MOVIE_TROUBLE.changed.tone}
          title={MOVIE_TROUBLE.changed.title}
          detail={CHANGED_DETAIL}
          action={
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onLoadNew(trouble.next)}
            >
              Load the new movie
            </button>
          }
        />
      )}
    </div>
  )
}
