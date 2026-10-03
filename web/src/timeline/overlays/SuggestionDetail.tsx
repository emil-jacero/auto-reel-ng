import { Icon } from '../../ui/Icon'
import type { MarkModel } from './control'
import { kindIcon } from './SuggestionLane'
import { STATE_GLYPH, STATE_WORD, kindWords, segmentLength, segmentSpan } from './suggestions'

/*
 * The selected mark's detail: the clip, the kind in words, the span and length, the
 * state as a glyph and a word, and the decision as real, labelled buttons (the route for
 * touch and assistive technology; A and R on the mark are only an accelerator). In the
 * read view it carries no decision.
 */

export function SuggestionDetail({
  id,
  mark,
  clipName,
  decide,
  refusal,
  onApprove,
  onDismiss,
  onRestore,
}: {
  id: string
  mark: MarkModel
  clipName: string
  /** Null outside Edit mode. */
  decide: { locked: boolean } | null
  /** Why the last approval of this suggestion was refused. */
  refusal: string | null
  onApprove: () => void
  onDismiss: () => void
  onRestore: () => void
}) {
  const { segment, state } = mark
  const locked = decide?.locked === true
  return (
    <section id={id} className="sg-detail" data-state={state} aria-label="Selected suggestion">
      <p className="sg-detail-head">
        <Icon name={kindIcon(segment.kind)} size={16} />
        <strong>{kindWords(segment.kind)}</strong>
        <span className="sg-detail-where">
          {clipName} · {segmentSpan(segment)} ({segmentLength(segment)})
        </span>
        <span className="sg-detail-state">
          <span aria-hidden="true">{STATE_GLYPH[state]}</span> {STATE_WORD[state]}
        </span>
      </p>
      {decide !== null && (
        <div className="sg-actions">
          {(state === 'pending' || state === 'partly-cut') && (
            <button
              type="button"
              className="btn btn-primary"
              aria-disabled={locked || undefined}
              onClick={onApprove}
            >
              <Icon name="scissors" />
              Approve as cut
            </button>
          )}
          {state === 'pending' && (
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={locked || undefined}
              onClick={onDismiss}
            >
              <Icon name="x" />
              Dismiss
            </button>
          )}
          {state === 'dismissed' && (
            <button
              type="button"
              className="btn btn-secondary"
              aria-disabled={locked || undefined}
              onClick={onRestore}
            >
              <Icon name="rotate-ccw" />
              Restore
            </button>
          )}
          {state === 'cut' && <span className="sg-already">Already cut.</span>}
        </div>
      )}
      {refusal !== null && <p className="sg-refusal">{refusal}</p>}
    </section>
  )
}
