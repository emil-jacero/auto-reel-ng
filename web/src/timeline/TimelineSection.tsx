import { useEffect, useId, useMemo, useState } from 'react'

import type { EventDetail } from '../api/event'
import type { ReadCutsState } from '../cuts/ReadCuts'
import { Alert } from '../ui/Alert'
import { CardInspectorPanel } from '../edit/card/Inspector'
import type { CardEditing } from '../edit/card/editing.ts'
import { backdropOf } from '../edit/card/specs.ts'
import type { Backdrop } from '../edit/card/Preview'
import { CardInspector, inspectorWords } from './CardInspector'
import { Prepare, usePrepare } from './Prepare'
import { cardPlacements, cardSpecs, decoratorsRead } from './cards'
import type { CardsBinding } from './useCardSelection'
import { analysisOf } from './overlays/control'
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

export function TimelineSection({
  eventId,
  event,
  read,
  dismissals,
  onFinished,
  editing = null,
  cards,
  cardEditing = null,
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
  /** The page's one card selection (`useCardSelection`), shared with Edit mode's rows. */
  cards: CardsBinding
  /** Edit mode's cards (`title-card-inspector`): the draft's specs and the inspector's edits; null in the read view. */
  cardEditing?: CardEditing | null
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
    () => (editing === null ? read : { cuts: editing.cuts, turns: editing.turns, failure: null }),
    [editing, read],
  )
  const prepare = usePrepare(eventId, onFinished)
  // The analysis lane: in the read view the cuts as read and no decision (reading a screen
  // never changes state), in Edit mode the draft's, as the Cuts panel lists them, and the
  // editor's own add, lock and live region to decide with.
  const analysis = useMemo(
    () => analysisOf(eventId, read, editing, dismissals),
    [eventId, read, editing, dismissals],
  )
  // Each chapter's resolved card, and whether the render draws them (`look.decorators`).
  const savedSpecs = useMemo(() => cardSpecs(event), [event])
  const specs = cardEditing?.specs ?? savedSpecs
  const decorators = decoratorsRead(
    editing === null ? read.look : editing.look,
    editing === null && read.failure !== null,
  )
  const cardBinding = useMemo(
    () => ({ specs, decorators, selection: cards }),
    [specs, decorators, cards],
  )
  // The selection ends with its chapter, whenever the event is read again without it.
  const { retain } = cards
  useEffect(() => retain(specs.map((spec) => spec.chapter)), [retain, specs])
  const selectedSpec =
    cards.selected === null ? undefined : specs.find((spec) => spec.chapter === cards.selected)
  // The selected card's inspector, in Edit mode: the card as the draft has it, and the clip a
  // video card is laid over (the Timeline's own anchor when the clips are ready, else the
  // chapter's first shown clip).
  const selectedView =
    editing !== null && cardEditing !== null && cards.selected !== null
      ? cardEditing.view(cards.selected)
      : null
  const backdrop = useMemo<Backdrop | null>(() => {
    if (cards.selected === null || selectedView === null) {
      return null
    }
    const chapter = specs.findIndex((spec) => spec.chapter === cards.selected)
    const placements =
      clips === null || decorators === 'pending' || decorators === 'unreadable' || chapter === -1
        ? null
        : cardPlacements(
            specs,
            clips.map((clip) => ({
              chapter: clip.chapter,
              durationMs: clip.facts.durationMs,
              spans: clip.spans,
            })),
            decorators,
          )
    const found = chapter === -1 ? null : backdropOf(chapter, shown.clips, placements)
    const clip =
      found === null
        ? undefined
        : event.chapters.flatMap((c) => c.clips).find((c) => c.identity === found.identity)
    return clip === undefined || found === null
      ? null
      : { clip, name: found.name, turn: cutsRead.turns?.get(found.identity) ?? 0 }
  }, [cards.selected, selectedView, specs, clips, decorators, shown, event, cutsRead.turns])
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
      {selectedView !== null && cardEditing !== null && cards.selected !== null ? (
        <CardInspectorPanel
          eventId={eventId}
          saved={cards.selected}
          view={selectedView}
          editing={cardEditing}
          spec={selectedSpec}
          backdrop={backdrop}
          onClose={() => {
            // Focus goes back to the control that selected it, not to <body>.
            document
              .querySelector<HTMLElement>('main:not([hidden]) .card-row-select[data-selected]')
              ?.focus({ preventScroll: true })
            cards.clear()
          }}
        />
      ) : (
        <CardInspector words={inspectorWords(selectedSpec)} />
      )}
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
                cards={cardBinding}
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
