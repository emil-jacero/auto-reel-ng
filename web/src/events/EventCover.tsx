import type { EventDetail } from '../api/event'
import { posterUrl, posterVersion } from '../api/poster'
import { pageCoverWords } from './cover.ts'
import { PosterCover } from './PosterCover'

/*
 * The event page's cover: the event's poster larger, with the words that say whether the frame
 * is the default or a chosen one. An event that plays no clip has no poster and asks for none.
 */
export function EventCover({ eventId, event, name }: { eventId: string; event: EventDetail; name: string }) {
  const poster = event.poster ?? null
  const words = pageCoverWords(name, poster)
  return (
    <figure className="event-cover">
      <PosterCover
        src={poster === null ? null : posterUrl(eventId, posterVersion(poster))}
        alt={words.alt}
        none={words.none}
        eager
      />
      <figcaption>{words.caption}</figcaption>
      {event.poster_note != null && <p className="poster-area-note">{event.poster_note}</p>}
    </figure>
  )
}
