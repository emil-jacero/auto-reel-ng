import { Fragment, useId } from 'react'

import { Alert } from '../../ui/Alert'
import type { CardsSource } from '../../timeline/cards.ts'
import { changedStyleFields, effective, styleRefusalOf } from '../cardStyle.ts'
import type { StyleDraft, StyleField, StyleRefusal, StyleValue } from '../cardStyle.ts'
import { ColorField } from './ColorField'
import { BACKGROUND_OPTIONS, POSITION_OPTIONS } from './choice.ts'
import { Choice, TextField } from './Fields'
import type { FieldWords } from './Fields'
import { FontField } from './FontField'
import { NO_CARD } from './model.ts'
import { styleWords } from './specs.ts'
import type { EventStyle } from './specs.ts'
import { useFonts } from './useFonts.ts'

/*
 * "All title cards in this event" (`edit-mode-declutter`): the dialog's second tab. It holds the
 * event-wide `look.title_card` that every card inherits from (once the page's "Card style for
 * this event", `title-card-event-style`) and the Title cards On / Off switch (once its own
 * section, `title-card-toggle`, D-25). It edits the editor's one draft, keeps no value of its
 * own, and the dialog's one preview shows the card being edited under it. An unset field says it
 * follows the project default and shows the value in force when the page read it; a field the
 * operator cleared although the saved style set it says "Project default" with no number,
 * because the page does not know it (Principle I). The engine decides what is valid; its
 * refusal is shown at the field. The switch's state is the service's answer (`title_cards`),
 * never a guess from `reel.yaml`; with no answer it is disabled and shows the service's words.
 */

export const PROJECT_DEFAULT = 'Project default'
const WORDS: FieldWords = { clear: 'Use project default', tag: PROJECT_DEFAULT, hint: PROJECT_DEFAULT }

export const SWITCH_NAME = 'Title cards'
export const TURNED_OFF = 'Title cards turned off'
export const TURNED_ON = 'Title cards turned on'

export type CardStyleModel = {
  /** The style as read, and as the draft has it now. */
  read: StyleDraft
  style: StyleDraft
  /** The saved resolved style (the project default under the saved event layer), or null. */
  resolved: EventStyle | null
  /** The detail's `title_card_error`: the engine could not resolve the saved style. */
  error: string | null
  /** The last refused save's naming of a style field. */
  refusal: StyleRefusal | null
  locked: boolean
  onSet: (field: StyleField, value: StyleValue | null) => void
  onReset: () => void
}

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

function text(value: StyleValue | null): string | null {
  return value === null ? null : String(value)
}

/** The style's problems the operator cannot see from the other tab: the refusal and the saved style the engine refuses. */
export function styleProblems(model: Pick<CardStyleModel, 'read' | 'style' | 'error' | 'refusal'>): number {
  const changed = changedStyleFields(model.read, model.style)
  const saved = model.error === null ? null : styleRefusalOf(model.error)
  const savedActive =
    model.error !== null &&
    (saved?.field == null ? changed.length === 0 : !changed.includes(saved.field))
  return (model.refusal !== null ? 1 : 0) + (savedActive ? 1 : 0)
}

export function EventTab({ style: model, cards }: { style: CardStyleModel; cards: TitleCardsModel }) {
  const { read, style, resolved, error, refusal, locked } = model
  const headingId = useId()
  const { state: fonts } = useFonts()
  const list = fonts.status === 'ok' ? fonts.fonts : []
  const changed = changedStyleFields(read, style)

  // The saved style the engine refuses stays told while the field it names is untouched.
  const savedRefusal = error === null ? null : styleRefusalOf(error)
  const savedActive =
    error !== null &&
    (savedRefusal?.field == null ? changed.length === 0 : !changed.includes(savedRefusal.field))

  const at = (field: StyleField): string | null => {
    if (refusal !== null && refusal.field === field) {
      return refusal.message
    }
    return savedActive && savedRefusal?.field === field ? (error as string) : null
  }
  // What an unset field follows, in words: the value, or '' when the page does not know it.
  const follows = (field: StyleField): string => {
    const { value, source } = effective(field, NO_CARD, { ...style, [field]: null }, read, resolved)
    return source === 'default' && value !== null ? styleWords(field, value, list) : ''
  }
  // The option an unset choice inherits (the saved project default), or null when not known.
  const inheritedOf = (field: StyleField): string | null => {
    const { value, source } = effective(field, NO_CARD, { ...style, [field]: null }, read, resolved)
    return source === 'default' && typeof value === 'string' ? value : null
  }
  const placeholder = (field: StyleField): string => follows(field) || PROJECT_DEFAULT
  const clear = (field: string) => model.onSet(field as StyleField, null)
  const shared = { locked, onClear: clear, words: WORDS }

  const number = (field: StyleField, label: string) => (
    <TextField
      label={label}
      field={field}
      multiline={false}
      inputMode="decimal"
      value={text(style[field])}
      placeholder={placeholder(field)}
      follows={follows(field) === '' ? PROJECT_DEFAULT : `${PROJECT_DEFAULT}: ${follows(field)}`}
      error={at(field)}
      onChange={(value) => model.onSet(field, value === '' ? null : value)}
      {...shared}
    />
  )

  return (
    <div className="ci-fields ci-event" data-changed={changed.length > 0 || undefined}>
      <TitleCardsSwitch model={cards} />
      {error !== null && savedActive && (
        <Alert tone="err" title="The service refused this style." detail={error} />
      )}
      {refusal !== null && refusal.field === null && (
        <Alert tone="err" title="The service refused this style." detail={refusal.message} />
      )}
      <p className="ci-lede" id={headingId}>
        Every title card of this event follows these. A card can override any of them. A field left
        empty follows the project default.
      </p>
      <div className="ci-fields" role="group" aria-labelledby={headingId}>
        <FontField
          value={text(style.font_family)}
          inherited={follows('font_family')}
          error={at('font_family')}
          onChange={(value) => model.onSet('font_family', value)}
          {...shared}
        />
        <div className="ci-pair">
          {number('title_font_size', 'Title size')}
          {number('subtitle_font_size', 'Subtitle size')}
        </div>
        <ColorField
          value={text(style.text_color)}
          inherited={follows('text_color')}
          shown={
            text(style.text_color) ?? String(effective('text_color', NO_CARD, style, read, resolved).value ?? '')
          }
          error={at('text_color')}
          onChange={(value) => model.onSet('text_color', value)}
          {...shared}
        />
        <Choice
          label="Position"
          field="position"
          value={text(style.position)}
          options={POSITION_OPTIONS}
          inherited={follows('position')}
          inheritedValue={inheritedOf('position')}
          error={at('position')}
          onChange={(value) => model.onSet('position', value)}
          {...shared}
        />
        {number('duration', 'Default length (seconds)')}
        <Choice
          label="Background"
          field="background"
          value={text(style.background)}
          options={BACKGROUND_OPTIONS}
          inherited={follows('background')}
          inheritedValue={inheritedOf('background')}
          error={at('background')}
          onChange={(value) => model.onSet('background', value)}
          {...shared}
        />
        <div className="ci-actions">
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            aria-disabled={locked || changed.length === 0 || undefined}
            onClick={() => {
              if (!locked && changed.length > 0) {
                model.onReset()
              }
            }}
          >
            Undo changes to the card style
          </button>
        </div>
      </div>
    </div>
  )
}

function TitleCardsSwitch({ model }: { model: TitleCardsModel }) {
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
            {projectOver && ' Saving writes this event’s own list over the project’s.'}
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
