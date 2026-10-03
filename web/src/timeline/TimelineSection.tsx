import { useId, useMemo, useState } from 'react'

import type { EventDetail } from '../api/event'
import type { ReadCutsState } from '../cuts/ReadCuts'
import { Alert } from '../ui/Alert'
import { Prepare, usePrepare } from './Prepare'
import type { AnalysisControl } from './overlays/control'
import type { Dismissals } from './overlays/Dismissals'
import { Timeline } from './Timeline'
import { NO_CLIPS } from './labels'
import { omittedWords, readiness, sectionState, shownClips, trackClips } from './layout'

/*
 * The event page's Timeline section (read view only): a heading and one button. Closed,
 * it holds nothing: no video, no request. Open, it shows what the clips' proxies allow:
 * a note when there is no clip to show, the Prepare state while any shown clip has no
 * ready proxy, and the track once every one has. It writes nothing; the one thing it can
 * start is the proxy job, by the Prepare button. A Refresh or Edit mode replaces the
 * page's content, so the section is closed again afterwards.
 */

const NO_CUTS: readonly never[] = []

export function TimelineSection({
  eventId,
  event,
  read,
  dismissals,
  onFinished,
}: {
  eventId: string
  event: EventDetail
  /** The page's one read of `reel.yaml`'s cuts. */
  read: ReadCutsState
  /** The suggestions dismissed during this page visit (kept above the section). */
  dismissals: Dismissals
  /** Read the event again, quietly (a proxy job ended, or every proxy was already ready). */
  onFinished: () => void
}) {
  const [open, setOpen] = useState(false)
  const headingId = useId()
  const bodyId = useId()
  const shown = useMemo(() => shownClips(event), [event])
  const chapterNames = useMemo(() => event.chapters.map((chapter) => chapter.name), [event])
  const clips = useMemo(() => trackClips(shown.clips, read.cuts), [shown, read.cuts])
  const prepare = usePrepare(eventId, onFinished)
  // The analysis lane in the read view: the cuts as read, and no decision (Edit mode decides).
  const analysis = useMemo<AnalysisControl>(
    () => ({
      eventId,
      cutsState: read.cuts !== null ? 'ok' : read.failure !== null ? 'unreadable' : 'reading',
      cutsOf: (identity) => read.cuts?.get(identity) ?? NO_CUTS,
      dismissals,
      decide: null,
    }),
    [eventId, read, dismissals],
  )
  const state = sectionState(open, shown.clips)
  const omitted = omittedWords(shown.omitted)
  return (
    <section className="panel timeline-panel" aria-labelledby={headingId}>
      <header className="panel-header">
        <h2 id={headingId}>Timeline</h2>
        <button
          type="button"
          className="btn btn-secondary tl-toggle"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((was) => !was)}
        >
          {open ? 'Close timeline' : 'Open timeline'}
        </button>
      </header>
      <div id={bodyId} className="timeline-body" hidden={!open}>
        {state !== 'closed' && (
          <>
            {omitted.map((words) => (
              <Alert key={words} tone="info" role="note" title={words} />
            ))}
            {state === 'none' && <Alert tone="info" role="note" title={NO_CLIPS} />}
            {state === 'prepare' && (
              <Prepare readiness={readiness(shown.clips)} control={prepare} />
            )}
            {state === 'track' && clips !== null && (
              <Timeline
                eventId={eventId}
                clips={clips}
                chapterNames={chapterNames}
                cuts={read}
                prepare={prepare}
                analysis={analysis}
              />
            )}
            {/* Always there while open, so the words put into it are announced. */}
            <p className="visually-hidden" role="status">
              {prepare.announcement}
            </p>
          </>
        )}
      </div>
    </section>
  )
}
