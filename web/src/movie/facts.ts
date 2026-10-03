import type { EventDetail } from '../api/event'
import { formatInstant } from '../format.ts'
import { listedChapters } from './chapters.ts'
import type { ChapterMark } from './chapters.ts'

/*
 * What the event detail says about the rendered movie (`movie`), the one place that
 * reads those generated fields. A rename in the API is one `tsc` error here.
 */

/** When the render record was written, and the short identity of the inputs it was made from. */
export type MovieVersion = { recordedAt: string; fingerprint: string }

/** What the detail says of the movie: the chapters the list shows and the version. */
export type MovieFacts = { chapters: ChapterMark[] | null; version: MovieVersion | null }

/**
 * The movie's facts from the detail: the chapters the list shows (`null` when the
 * detail gives none it can rely on, never `[]`) and the version (`null` when the
 * detail has no `movie`). Read only; nothing is derived.
 */
export function movieFacts(event: Pick<EventDetail, 'movie'>): MovieFacts {
  const movie = event.movie ?? null
  if (movie === null) {
    return { chapters: null, version: null }
  }
  return {
    chapters: listedChapters(movie.chapters),
    version: { recordedAt: movie.recorded_at, fingerprint: movie.fingerprint },
  }
}

/** The version as the facts line writes it; each part is left out when it cannot be told. */
export type VersionWords = {
  /** The exact instant (for `<time dateTime>`) and how the client writes it. */
  time: { dateTime: string; text: string } | null
  fingerprint: string | null
}

/**
 * "Recorded {time} · version {fingerprint}": "Recorded", not "Rendered", because the
 * time is when the record was written, which for an adopted movie is the adoption.
 * A time that does not parse is left out rather than shown as a made-up one.
 */
export function movieVersionWords(version: MovieVersion | null): VersionWords | null {
  if (version === null) {
    return null
  }
  const parses = !Number.isNaN(new Date(version.recordedAt).getTime())
  const time = parses ? { dateTime: version.recordedAt, text: formatInstant(version.recordedAt) } : null
  const fingerprint = version.fingerprint.trim() === '' ? null : version.fingerprint
  return time === null && fingerprint === null ? null : { time, fingerprint }
}
