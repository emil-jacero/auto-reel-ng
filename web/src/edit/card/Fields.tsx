import { Fragment, useId } from 'react'
import type { ReactNode } from 'react'

import { Icon } from '../../ui/Icon'
import { inheritedTag, optionState } from './choice.ts'
import type { ChoiceOption } from './choice.ts'

/*
 * The inspector's field shells: a label, the control, the muted "Event style" value while the
 * field is unset, Use event style while it is set, and the message at the field. The controls
 * are native (input, textarea, select, radio) so the keyboard and assistive technology get
 * their own behaviour; a locked editor makes them read-only and keeps them focusable.
 */

/** Space-separated ids, empty ones dropped; undefined when none is left. */
export function ids(...parts: (string | false | null | undefined)[]): string | undefined {
  const kept = parts.filter((part): part is string => typeof part === 'string' && part !== '')
  return kept.length > 0 ? kept.join(' ') : undefined
}

/** What the clear button and the unset tag say: a card's field follows the event style. */
export type FieldWords = { clear: string; tag: string; hint: string }
export const CARD_WORDS: FieldWords = { clear: 'Use event style', tag: 'Event style', hint: 'Event style' }

/** The hint of an unset field: what it follows and the value, or the words alone while the value is not known. */
export function hintOf(words: FieldWords, inherited: ReactNode): ReactNode {
  return inherited === '' ? words.hint : <>{words.hint}: {inherited}</>
}

/** What a control needs to be tied to its shell. */
export type Control = {
  id: string
  'aria-describedby': string | undefined
  'aria-invalid': true | undefined
}

type ShellProps = {
  label: string
  /** The field's name, for tests and styling (`data-field`). */
  field: string
  /** The card sets this field (else it inherits). */
  set: boolean
  /** The inherited value, or the words that say what an unset field follows. */
  inherited: ReactNode
  /** The message at the field: the service's refusal, or the preview's bound. */
  error: string | null
  locked: boolean
  onClear: (field: string) => void
  /** The clear button's words and the tag of an unset field: the card's, or the event style's. */
  words?: FieldWords
  /** A native radio group labels itself with a span, not a <label for>. */
  group?: boolean
}

export function FieldShell({
  label,
  field,
  set,
  inherited,
  error,
  locked,
  onClear,
  words = CARD_WORDS,
  group = false,
  children,
}: ShellProps & { children: (control: Control) => ReactNode }) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const control: Control = {
    id,
    'aria-describedby': ids(!set && hintId, error !== null && errorId),
    'aria-invalid': error !== null ? true : undefined,
  }
  return (
    <div className="ci-field" data-field={field} data-set={set || undefined}>
      <div className="ci-field-head">
        {group ? (
          <span className="field-label" id={`${id}-label`}>
            {label}
          </span>
        ) : (
          <label className="field-label" htmlFor={id}>
            {label}
          </label>
        )}
        {set ? (
          <button
            type="button"
            className="btn btn-ghost btn-compact ci-clear"
            aria-label={`${words.clear} for ${label.toLowerCase()}`}
            aria-disabled={locked || undefined}
            onClick={() => {
              if (!locked) {
                onClear(field)
              }
            }}
          >
            {words.clear}
          </button>
        ) : (
          <span className="ci-style-tag">{words.tag}</span>
        )}
      </div>
      {children(control)}
      {!set && (
        <p className="field-hint ci-inherited" id={hintId}>
          {inherited}
        </p>
      )}
      {error !== null && (
        <p className="field-error" id={errorId}>
          <Icon name="alert-triangle" />
          {error}
        </p>
      )}
    </div>
  )
}

type Common = Pick<ShellProps, 'label' | 'field' | 'locked' | 'onClear' | 'words'> & {
  error: string | null
}

/** Title and subtitle: free text; the subtitle keeps its line breaks. */
export function TextField({
  label,
  field,
  locked,
  onClear,
  words,
  error,
  multiline,
  inputMode,
  value,
  placeholder,
  follows,
  onChange,
  action,
}: Common & {
  /** A button beside the control that sets the field to a value of its own (No subtitle). */
  action?: { label: string; onPress: () => void } | null
  multiline: boolean
  /** The on-screen keyboard to ask for (numbers typed as text, to be refused by the service). */
  inputMode?: 'text' | 'numeric' | 'decimal'
  value: string | null
  placeholder: string
  /** What the field follows while empty, in words. */
  follows: string
  onChange: (value: string) => void
}) {
  return (
    <FieldShell
      label={label}
      field={field}
      set={value !== null}
      inherited={follows}
      error={error}
      locked={locked}
      onClear={onClear}
      words={words}
    >
      {(control) => (
        <>
        {multiline ? (
          <textarea
            {...control}
            className="field-input ci-text ci-multiline"
            rows={3}
            value={value ?? ''}
            placeholder={placeholder}
            readOnly={locked}
            aria-disabled={locked || undefined}
            onChange={(event) => onChange(event.currentTarget.value)}
          />
        ) : (
          <input
            {...control}
            type="text"
            className="field-input ci-text"
            autoComplete="off"
            inputMode={inputMode}
            value={value ?? ''}
            placeholder={placeholder}
            readOnly={locked}
            aria-disabled={locked || undefined}
            onChange={(event) => onChange(event.currentTarget.value)}
          />
        )}
        {action != null && (
          <button
            type="button"
            className="btn btn-ghost btn-compact ci-action"
            data-action={field}
            aria-disabled={locked || undefined}
            onClick={() => {
              if (!locked) {
                action.onPress()
              }
            }}
          >
            {action.label}
          </button>
        )}
        </>
      )}
    </FieldShell>
  )
}

/** Title size and subtitle size: a number, sent as typed. */
export function NumberField({
  label,
  field,
  locked,
  onClear,
  words,
  error,
  value,
  placeholder,
  inherited,
  onChange,
}: Common & {
  value: number | null
  placeholder: string
  inherited: ReactNode
  onChange: (value: number | null) => void
}) {
  return (
    <FieldShell
      label={label}
      field={field}
      set={value !== null}
      inherited={hintOf(words ?? CARD_WORDS, inherited)}
      error={error}
      locked={locked}
      onClear={onClear}
      words={words}
    >
      {(control) => (
        <input
          {...control}
          type="number"
          inputMode="numeric"
          step={1}
          className="field-input ci-number"
          value={value ?? ''}
          placeholder={placeholder}
          readOnly={locked}
          aria-disabled={locked || undefined}
          onChange={(event) => {
            const raw = event.currentTarget.value
            if (raw === '') {
              // A partial entry such as "-" or "1e" reads as '' but is not a cleared field.
              if (!event.currentTarget.validity.badInput) {
                onChange(null)
              }
              return
            }
            const parsed = Number(raw)
            if (Number.isFinite(parsed)) {
              onChange(parsed)
            }
          }}
        />
      )}
    </FieldShell>
  )
}

export type { ChoiceOption }

/**
 * Background and position: native radios in a segmented control. A set field has its option
 * chosen; an unset one has none chosen and shows the value it inherits as pressed in a muted
 * style (`data-inherited`, a dashed outline and the layer's words), which pressing sets as an
 * override. An inherited value the page does not know shows none.
 */
export function Choice({
  label,
  field,
  locked,
  onClear,
  words,
  error,
  value,
  options,
  inherited,
  inheritedValue,
  onChange,
}: Common & {
  value: string | null
  options: readonly ChoiceOption[]
  inherited: ReactNode
  /** The option the field inherits, or null when the page does not know it. */
  inheritedValue: string | null
  onChange: (value: string) => void
}) {
  const name = useId()
  // A value written by hand that is none of the options (`middle`) stays shown, and chosen.
  const shown =
    value !== null && !options.some((option) => option.value === value)
      ? [...options, { value, label: value, words: null }]
      : options
  return (
    <FieldShell
      label={label}
      field={field}
      set={value !== null}
      inherited={hintOf(words ?? CARD_WORDS, inherited)}
      error={error}
      locked={locked}
      onClear={onClear}
      words={words}
      group
    >
      {(control) => (
        <>
          <div
            className="segmented ci-choice"
            role="radiogroup"
            aria-labelledby={`${control.id}-label`}
            aria-describedby={control['aria-describedby']}
          >
            {shown.map((option) => {
              const state = optionState(option.value, value, inheritedValue)
              return (
              <Fragment key={option.value}>
                <input
                  className="visually-hidden"
                  type="radio"
                  id={`${name}-${option.value}`}
                  name={name}
                  checked={value === option.value}
                  aria-disabled={locked || undefined}
                  onChange={() => {
                    if (!locked) {
                      onChange(option.value)
                    }
                  }}
                />
                <label
                  htmlFor={`${name}-${option.value}`}
                  data-inherited={state === 'inherited' || undefined}
                >
                  {option.label}
                  {state === 'inherited' && (
                    <span className="ci-inherited-tag"> {inheritedTag((words ?? CARD_WORDS).tag)}</span>
                  )}
                </label>
              </Fragment>
              )
            })}
          </div>
          {options.some((option) => option.words !== null) && (
            <ul className="ci-words">
              {options.map((option) =>
                option.words === null ? null : (
                  <li key={option.value} data-chosen={value === option.value || undefined}>
                    <strong>{option.label}:</strong> {option.words}
                  </li>
                ),
              )}
            </ul>
          )}
        </>
      )}
    </FieldShell>
  )
}
