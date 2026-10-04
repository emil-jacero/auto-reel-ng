import { useId } from 'react'

import type { EventDetail } from '../api/event'
import { posterUrl, posterVersion } from '../api/poster'
import type { ReelDocument } from '../api/reel'
import { thumbnailUrl } from '../api/thumbnail'
import { folderName } from '../events/common'
import { PosterCover } from '../events/PosterCover'
import type { Turn } from '../rotate/turn.ts'
import { HelpPanel, HelpToggle, useSectionHelp } from '../ui/help/HelpToggle'
import { Icon } from '../ui/Icon'
import {
  NOT_PLAYED_WORDS,
  USE_DEFAULT,
  firstPlayed,
  playedInDraft,
  posterNow,
  posterState,
  posterStateWords,
} from './poster.ts'
import type { PosterDraft, PosterPick } from './poster.ts'

/*
 * Edit mode's poster area: the event's cover as the draft has it, and what it is in words.
 * A chosen frame that is not saved shows the frame the Timeline's video showed (a snapshot
 * kept in this session); a saved one shows the service's image; the default shows the first
 * clip's thumbnail, which is the default frame's clip. Use default removes the draft's poster.
 */
export function PosterPanel({
  eventId,
  event,
  read,
  draft,
  orders,
  frame,
  locked,
  onUseDefault,
}: {
  eventId: string
  event: EventDetail
  read: ReelDocument
  draft: PosterDraft
  orders: ReadonlyMap<string, readonly string[]>
  /** The snapshot of the last Use as poster, with the pick it belongs to. */
  frame: { url: string; turn: Turn; pick: PosterPick } | null
  locked: boolean
  onUseDefault: () => void
}) {
  const headingId = useId()
  const help = useSectionHelp('poster')
  const now = posterNow(read, draft)
  const state = posterState(read, draft, event)
  const words = posterStateWords(state)
  const name = event.title ?? folderName(eventId)
  const notPlayed = now !== null && !playedInDraft(now, orders)
  const clip = firstPlayed(event)
  let src: string | null
  let turn: Turn = 0
  if (now === null || notPlayed) {
    src = clip === null ? null : thumbnailUrl(eventId, clip)
  } else if (state === 'unsaved') {
    src = frame !== null && frame.pick.clip === now.clip && frame.pick.at === now.at ? frame.url : null
    turn = src === null ? 0 : frame!.turn
  } else {
    src = event.poster == null ? null : posterUrl(eventId, posterVersion(event.poster))
  }
  const note = state === 'default' && now !== null ? (event.poster_note ?? null) : null
  const disabled = locked || now === null
  return (
    <section className="panel poster-area-panel" aria-labelledby={headingId}>
      <header className="panel-header">
        <h2 id={headingId}>Poster</h2>
        <HelpToggle help={help} section="Poster" />
      </header>
      <HelpPanel help={help}>
        <p>
          Pick the frame on the Timeline, then press Use as poster. The poster is the frame of the
          original clip at that time; a render writes it beside the movie.
        </p>
      </HelpPanel>
      <div className="panel-body poster-area">
        <PosterCover
          src={src}
          alt={`Poster of ${name}, ${words.toLowerCase()}`}
          none={`No poster for ${name}`}
          turn={turn}
        />
        <div>
          <p className="poster-area-state">{words}</p>
          {notPlayed && <p className="poster-area-note">{NOT_PLAYED_WORDS}</p>}
          {note !== null && !notPlayed && <p className="poster-area-note">{note}</p>}
          <div className="poster-area-actions">
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={disabled || undefined}
              onClick={() => {
                if (!disabled) {
                  onUseDefault()
                }
              }}
            >
              <Icon name="rotate-ccw" />
              {USE_DEFAULT}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
