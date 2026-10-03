import { useId, useMemo, useState } from 'react'

import type { EventDetail } from '../api/event'
import type { ReadCutsState } from '../cuts/ReadCuts'
import { Alert } from '../ui/Alert'
import { Prepare, usePrepare } from './Prepare'
import type { AnalysisControl } from './overlays/control'
import type { Dismissals } from './overlays/Dismissals'
import { Timeline } from './Timeline'
import type { EditBinding } from './editing'
import { NO_CLIPS } from './labels'
import { omittedWords, readiness, sectionState, shownClips, trackClips } from './layout'

/*
 * The event page's Timeline section: a heading and one button. Closed, it holds nothing:
 * no video, no request. Open, it shows what the clips' proxies allow: a note when there is
 * no clip to show, the Prepare state while any shown clip has no ready proxy, and the track
 * once every one has. The one thing it can start is the proxy job, by the Prepare button.
 * A Refresh or entering or leaving Edit mode replaces the page's content, so the section is
 * closed again afterwards.
 *
 * In the read view it writes nothing and draws the cuts as saved. In Edit mode (`editing`)
 * it is the same section on the editor's draft: the draft's cuts, with a trim handle at
 * each edge of a cut (`timeline-trim`); the editor owns Save.
 */

const NO_CUTS: readonly never[] = []

export function TimelineSection({
  eventId,
  event,
  read,
  dismissals,
  onFinished,
  editing = null,
}: {
  eventId: string
  event: EventDetail
  /** The page's one read of `reel.yaml`'s cuts (the read view; Edit mode's are the draft's). */
  read: ReadCutsState
  /** The suggestions dismissed during this page visit (kept above the section). */
  dismissals: Dismissals
  /** Read the event again, quietly (a proxy job ended, or every proxy was already ready). */
  onFinished: () => void
  /** Edit mode's binding; null in the read view. */
  editing?: EditBinding | null
}) {
  const [open, setOpen] = useState(false)
  const headingId = useId()
  const bodyId = useId()
  const shown = useMemo(() => shownClips(event), [event])
  const chapterNames = useMemo(() => event.chapters.map((chapter) => chapter.name), [event])
  // In Edit mode the cuts are the draft's: never "being read" and never "unreadable".
  const cuts = editing === null ? read.cuts : editing.cuts
  const clips = useMemo(() => trackClips(shown.clips, cuts), [shown, cuts])
  const cutsRead = useMemo(
    () => (editing === null ? read : { cuts: editing.cuts, failure: null }),
    [editing, read],
  )
  const prepare = usePrepare(eventId, onFinished)
  // The analysis lane shows state and takes no decision here: in the read view the cuts as
  // read, in Edit mode the draft's, as the Cuts panel lists them (a later change decides).
  const analysis = useMemo<AnalysisControl>(
    () => ({
      eventId,
      cutsState:
        editing !== null
          ? 'ok'
          : read.cuts !== null
            ? 'ok'
            : read.failure !== null
              ? 'unreadable'
              : 'reading',
      cutsOf: (identity) =>
        editing !== null ? editing.listed(identity) : (read.cuts?.get(identity) ?? NO_CUTS),
      dismissals,
      decide: null,
    }),
    [eventId, read, editing, dismissals],
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
                cuts={cutsRead}
                prepare={prepare}
                analysis={analysis}
                editing={editing}
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
