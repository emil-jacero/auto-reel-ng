import './titleCardsSwitch.css'

import { Fragment, useId } from 'react'

import type { CardsSource } from '../timeline/cards.ts'

/*
 * "Title cards: On / Off" (`title-card-toggle`): Edit mode's one switch for whether the render
 * draws the event's title cards. It edits the editor's one draft (`look.decorators`,
 * `decorators.ts`), keeps no value of its own and says where the state comes from. The state is
 * the service's answer (`title_cards`), never a guess from `reel.yaml`; with no answer
 * (`look.decorators` is not a list) it is disabled and shows the service's words.
 */

export const SWITCH_NAME = 'Title cards'
export const TURNED_OFF = 'Title cards turned off'
export const TURNED_ON = 'Title cards turned on'

export type TitleCardsModel = {
  /** The service's answer for the document as read; null: none (`error` says why). */
  answer: { enabled: boolean; source: CardsSource } | null
  error: string | null
  /** The switch now: the draft's, else the answer's. */
  on: boolean
  /** Which layer decides it now: the event once the draft differs from the answer. */
  source: CardsSource | null
  changed: boolean
  locked: boolean
  onSet: (on: boolean) => void
  onReset: () => void
}

const WHERE: Record<CardsSource, string> = {
  default: 'Default',
  event: 'Set in this event',
  project: 'Set by the project’s config.yaml',
}

/** Where the state comes from, in words; the draft's own change is "Changed here, not saved". */
export function whereWords(model: Pick<TitleCardsModel, 'source' | 'changed'>): string {
  if (model.changed) {
    return 'Changed here, not saved'
  }
  return model.source === null ? '' : WHERE[model.source]
}

export function TitleCardsSwitch({ model }: { model: TitleCardsModel }) {
  const name = useId()
  const labelId = useId()
  const noteId = useId()
  const { answer, locked } = model
  const disabled = answer === null || locked
  const where = whereWords(model)
  const projectOver = model.answer?.source === 'project' && model.changed
  return (
    <div className="tcs" data-changed={model.changed || undefined}>
      <span className="field-label tcs-label" id={labelId}>
        {SWITCH_NAME}
      </span>
      <div
        className="segmented tcs-choice"
        role="radiogroup"
        aria-labelledby={labelId}
        aria-describedby={noteId}
      >
        {[true, false].map((on) => (
          <Fragment key={String(on)}>
            <input
              className="visually-hidden"
              type="radio"
              id={`${name}-${on ? 'on' : 'off'}`}
              name={name}
              checked={answer !== null && model.on === on}
              aria-disabled={disabled || undefined}
              onChange={() => {
                if (!disabled) {
                  model.onSet(on)
                }
              }}
            />
            <label htmlFor={`${name}-${on ? 'on' : 'off'}`}>{on ? 'On' : 'Off'}</label>
          </Fragment>
        ))}
      </div>
      <p className="tcs-note field-hint" id={noteId}>
        {answer === null ? (
          <span className="tcs-error">
            {model.error ?? 'The service did not say whether the render draws title cards.'}
          </span>
        ) : (
          <>
            {where}.{' '}
            {model.on
              ? 'The render draws a title card at the start and for each chapter.'
              : 'The render draws no title cards. The cards’ edits are kept.'}
            {projectOver &&
              ' Saving writes this event’s own list over the project’s.'}
          </>
        )}
      </p>
      <button
        type="button"
        className="btn btn-secondary btn-compact tcs-undo"
        aria-disabled={locked || !model.changed || undefined}
        onClick={() => {
          if (!locked && model.changed) {
            model.onReset()
          }
        }}
      >
        Undo title cards change
      </button>
    </div>
  )
}
