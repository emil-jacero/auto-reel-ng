import { encodeEventId } from '../route'
import type { paths, components } from './schema'

/**
 * An event's poster address: the only module that knows its URL. An `<img>` makes the
 * request; every failure looks the same to it (`events/PosterCover.tsx`). The route is checked
 * against the generated `paths`, so renaming it in the service fails `tsc --noEmit`.
 */

const POSTER_PATH = '/api/v1/events/{event_id}/poster.jpg' satisfies keyof paths

export type EventPoster = components['schemas']['PosterOut']

/**
 * The event id encoded per segment. `version` is an opaque value that gives a changed poster a
 * new address (the service ignores `v`): the chosen clip and time, so a saved poster replaces
 * the picture of an element that is already loaded. The service answers `no-cache` with a
 * validator, so a reload costs a 304.
 */
export function posterUrl(eventId: string, version?: string | null): string {
  const path = POSTER_PATH.replace('{event_id}', () => encodeEventId(eventId))
  return version == null || version === '' ? path : `${path}?${new URLSearchParams({ v: version })}`
}

/** The `v` of a detail's poster: where the frame comes from, so a change of frame changes it. */
export function posterVersion(poster: EventPoster | null | undefined): string | null {
  return poster == null ? null : `${poster.source}:${poster.clip}@${poster.at ?? ''}`
}
