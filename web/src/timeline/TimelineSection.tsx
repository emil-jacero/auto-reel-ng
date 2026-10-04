import { useId, useMemo, useRef } from 'react'
import type { RefObject } from 'react'

import type { EventDetail } from '../api/event'
import { Alert } from '../ui/Alert'
import { Dialog } from '../ui/Dialog'
import { HelpPanel, HelpToggle, useSectionHelp } from '../ui/help/HelpToggle'
import { CUT_FIELDS_HINT, SELECT_CUT_HINT } from '../cuts/times'
import { CardInspectorPanel, inspectorName } from '../edit/card/Inspector'
import type { CardEditing } from '../edit/card/editing.ts'
import { backdropOf, effectiveBackground } from '../edit/card/specs.ts'
import type { NameGate } from '../edit/card/NameField'
import { doneHeld } from '../edit/card/nameField.ts'
import { cardLimits, secondsToTenths } from './cardLength.ts'
import type { CardRange } from './cardLength.ts'
import type { Backdrop } from '../edit/card/Preview'
import { CardInspector, inspectorWords } from './CardInspector'
import { Prepare, usePrepare } from './Prepare'
import { cardPlacements, cardSpecs, cardsEnabled, cardsSource } from './cards'
import type { CardsBinding } from './useCardSelection'
import { analysisOf } from './overlays/control'
import type { Dismissals } from './overlays/Dismissals'
import { ANALYZE_COMMAND, DISMISSAL_NOTE } from './overlays/suggestions'
import { Timeline } from './Timeline'
import type { EditBinding } from './editing'
import { CARDS_FADES, NO_CLIPS } from './labels'
import { omittedWords, readiness, sectionState, shownClips, trackClips } from './layout'

/*
 * Edit mode's Timeline section (`edit-mode-declutter`, `timeline-zoom-slider`): a heading and,
 * from the start, what the clips' proxies allow: a note when there is no clip to show, the
 * Prepare state while any shown clip has no ready proxy, and the track once every one has. The
 * one thing it can start is the proxy job, by the Prepare button. The read view has no Timeline.
 *
 * It is the editor's draft: the draft's cuts, with a trim handle at each edge of a cut
 * (`timeline-trim`); the editor owns Save.
 */

/** The Length field's range while no card is open (unused: the dialog is closed). */
const NO_RANGE: CardRange = { adjustable: false, reason: '' }

export function TimelineSection({
  eventId,
  event,
  dismissals,
  onFinished,
  editing,
  cards,
  cardEditing,
}: {
  eventId: string
  event: EventDetail
  /** The suggestions dismissed during this page visit (kept above the section). */
  dismissals: Dismissals
  /** Read the event again, quietly (a proxy job ended, or every proxy was already ready). */
  onFinished: () => void
  /** Edit mode's binding: the draft's cuts and the editor's edits. */
  editing: EditBinding
  /** The page's one card selection (`useCardSelection`), shared with Edit mode's rows. */
  cards: CardsBinding
  /** Edit mode's cards (`title-card-inspector`): the draft's specs and the inspector's edits. */
  cardEditing: CardEditing
}) {
  const headingId = useId()
  const cutHintId = useId()
  const help = useSectionHelp('timeline')
  const shown = useMemo(() => shownClips(event), [event])
  const chapterNames = useMemo(() => event.chapters.map((chapter) => chapter.name), [event])
  // The cuts are the draft's: never "being read" and never "unreadable".
  const cuts = editing.cuts
  const clips = useMemo(() => trackClips(shown.clips, cuts), [shown, cuts])
  const prepare = usePrepare(eventId, onFinished)
  // The analysis lane: the draft's cuts, as the Cuts panel lists them, and the editor's own
  // add, lock and live region to decide with.
  const analysis = useMemo(
    () => analysisOf(eventId, editing, dismissals),
    [eventId, editing, dismissals],
  )
  // Each chapter's resolved card, and whether the render draws them: the service's answer
  // (`title_cards`), under Edit mode's Title cards switch while that differs (`title-card-toggle`).
  const savedSpecs = useMemo(() => cardSpecs(event), [event])
  const specs = cardEditing.specs
  const switched = cardEditing.titleCardsDraft ?? null
  const decorators = cardsEnabled(event.title_cards, switched)
  const source = cardsSource(event.title_cards, switched)
  const cardsError = event.title_cards_error ?? null
  const cardBinding = useMemo(
    () => ({
      specs,
      decorators,
      source,
      error: cardsError,
      selection: cards,
      previewStyle: cardEditing.previewStyle,
    }),
    [specs, decorators, source, cardsError, cards, cardEditing.previewStyle],
  )
  // The card whose dialog is open, in Edit mode: the card as the draft has it, and the clip a
  // video card is laid over (the Timeline's own anchor when the clips are ready, else the
  // chapter's first shown clip).
  const selectedView = cards.editing !== null ? cardEditing.view(cards.editing) : null
  // The dialog's first field, for the focus it opens on.
  const dialogBody = useRef<HTMLDivElement>(null)
  const firstField = useMemo<RefObject<HTMLElement | null>>(
    () => ({
      get current() {
        return dialogBody.current?.querySelector<HTMLElement>('input, textarea, select') ?? null
      },
    }),
    [],
  )
  // Where the dialog's card sits among the clips, when the Timeline knows them (not in Prepare).
  const placements = useMemo(
    () =>
      clips === null
        ? null
        : cardPlacements(
            specs,
            clips.map((clip) => ({
              chapter: clip.chapter,
              // The full length and every span: the placement derives the kept extent itself.
              durationMs: clip.facts.durationMs,
              spans: clip.spans,
            })),
            decorators,
          ),
    [specs, clips, decorators],
  )
  const backdrop = useMemo<Backdrop | null>(() => {
    if (cards.editing === null || selectedView === null) {
      return null
    }
    const chapter = specs.findIndex((spec) => spec.chapter === cards.editing)
    const found = chapter === -1 ? null : backdropOf(chapter, shown.clips, placements)
    const clip =
      found === null
        ? undefined
        : event.chapters.flatMap((c) => c.clips).find((c) => c.identity === found.identity)
    return clip === undefined || found === null
      ? null
      : { clip, name: found.name, turn: editing.turns.get(found.identity) ?? 0 }
  }, [cards.editing, selectedView, specs, placements, shown, event, editing.turns])
  // The limits of the dialog's Length field: the drag's own, from the card's placement.
  const lengthRange = useMemo<CardRange>(() => {
    if (cards.editing === null || selectedView === null) {
      return NO_RANGE
    }
    const chapter = specs.findIndex((spec) => spec.chapter === cards.editing)
    const spec = chapter === -1 ? undefined : specs[chapter]
    const seconds = selectedView.card.duration ?? spec?.card?.duration ?? cardEditing.style?.duration ?? 4
    const currentTenths = secondsToTenths(seconds)
    const place = placements?.find(
      (candidate) =>
        candidate.chapter === chapter && (candidate.kind === 'anchored' || candidate.kind === 'off'),
    )
    const background = effectiveBackground(selectedView.card, cardEditing.style ?? null, spec)
    if (place !== undefined && 'keptMs' in place) {
      return cardLimits({ background: place.background, currentTenths, keptMs: place.keptMs })
    }
    if (background === 'video') {
      return {
        adjustable: false,
        reason:
          placements === null
            ? 'Prepare the Timeline to see how much footage is under a video card.'
            : 'The chapter has no footage to put the card over.',
      }
    }
    return cardLimits({ background: 'black', currentTenths, keptMs: null })
  }, [cards.editing, selectedView, specs, placements, cardEditing.style])
  // The Name field's gate: Done is held while it holds a refused name.
  const nameGate = useRef<NameGate | null>(null)
  const onDone = () => {
    if (doneHeld(nameGate.current?.refusal() ?? null)) {
      nameGate.current?.focus()
      return
    }
    cards.dismiss()
  }
  const state = sectionState(shown.clips)
  const omitted = omittedWords(shown.omitted)
  return (
    <section className="panel timeline-panel" aria-labelledby={headingId}>
      <header className="panel-header">
        <h2 id={headingId}>Timeline</h2>
        <HelpToggle help={help} section="Timeline" />
      </header>
      <HelpPanel help={help}>
        <p>{CARDS_FADES}</p>
        <p>{ANALYZE_COMMAND}</p>
        <p>{DISMISSAL_NOTE}</p>
        <p>{SELECT_CUT_HINT}</p>
        <p id={cutHintId}>{CUT_FIELDS_HINT}</p>
      </HelpPanel>
      <div className="timeline-body">
        {omitted.map((words) => (
          <Alert key={words} tone="info" role="note" title={words} />
        ))}
        {state === 'none' && <Alert tone="info" role="note" title={NO_CLIPS} />}
        {state === 'prepare' && <Prepare readiness={readiness(shown.clips)} control={prepare} />}
        {state === 'track' && clips !== null && (
          <Timeline
            eventId={eventId}
            clips={clips}
            chapterNames={chapterNames}
            prepare={prepare}
            analysis={analysis}
            editing={editing}
            cards={cardBinding}
            cutHintId={cutHintId}
          />
        )}
        {/* Always there, so the words put into it are announced. */}
        <p className="visually-hidden" role="status">
          {prepare.announcement}
        </p>
      </div>
      {/* Edit mode's one card editor: a modal over the page, so the operator never scrolls back to it. */}
      {selectedView !== null && cards.editing !== null && (
        <Dialog
          open
          className="ci-dialog"
          title={inspectorName(selectedView.opening, selectedView.name)}
          onClose={cards.dismiss}
          initialFocus={firstField}
        >
          <div className="dialog-fields" ref={dialogBody}>
            <CardInspectorPanel
              eventId={eventId}
              saved={cards.editing}
              view={selectedView}
              editing={cardEditing}
              spec={specs.find((spec) => spec.chapter === cards.editing)}
              backdrop={backdrop}
              lengthRange={lengthRange}
              gate={nameGate}
              onClose={cards.dismiss}
            />
          </div>
          <div className="dialog-actions">
            <button type="button" className="btn btn-primary" onClick={onDone}>
              Done
            </button>
          </div>
        </Dialog>
      )}
      {/* No visible read-out: the dialog is the card's editor; the status region announces a selection once. */}
      <CardInspector
        announced={inspectorWords(
          cards.selected === null
            ? undefined
            : savedSpecs.find((spec) => spec.chapter === cards.selected),
        )}
      />
    </section>
  )
}
