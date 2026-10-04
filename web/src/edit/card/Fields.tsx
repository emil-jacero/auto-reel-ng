import { Fragment, useId } from 'react'
import type { ReactNode } from 'react'

import { Icon } from '../../ui/Icon'
import type { CardField } from './model.ts'

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

/** What a control needs to be tied to its shell. */
export type Control = {
  id: string
  'aria-describedby': string | undefined
  'aria-invalid': true | undefined
}

type ShellProps = {
  label: string
  field: CardField
  /** The card sets this field (else it inherits). */
  set: boolean
  /** The inherited value, or the words that say what an unset field follows. */
  inherited: ReactNode
  /** The message at the field: the service's refusal, or the preview's bound. */
  error: string | null
  locked: boolean
  onClear: (field: CardField) => void
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
            aria-label={`Use event style for ${label.toLowerCase()}`}
            aria-disabled={locked || undefined}
            onClick={() => {
              if (!locked) {
                onClear(field)
              }
            }}
          >
            Use event style
          </button>
        ) : (
          <span className="ci-style-tag">Event style</span>
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

type Common = Pick<ShellProps, 'label' | 'field' | 'locked' | 'onClear'> & {
  error: string | null
}

/** Title and subtitle: free text; the subtitle keeps its line breaks. */
export function TextField({
  label,
  field,
  locked,
  onClear,
  error,
  multiline,
  value,
  placeholder,
  follows,
  onChange,
}: Common & {
  multiline: boolean
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
    >
      {(control) =>
        multiline ? (
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
            value={value ?? ''}
            placeholder={placeholder}
            readOnly={locked}
            aria-disabled={locked || undefined}
            onChange={(event) => onChange(event.currentTarget.value)}
          />
        )
      }
    </FieldShell>
  )
}

/** Title size and subtitle size: a number, sent as typed. */
export function NumberField({
  label,
  field,
  locked,
  onClear,
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
      inherited={<>Event style: {inherited}</>}
      error={error}
      locked={locked}
      onClear={onClear}
    >
      {(control) => (
        <input
          {...control}
          type="number"
          inputMode="decimal"
          step="any"
          className="field-input ci-number"
          value={value ?? ''}
          placeholder={placeholder}
          readOnly={locked}
          aria-disabled={locked || undefined}
          onChange={(event) => {
            const raw = event.currentTarget.value
            if (raw === '') {
              onChange(null)
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

export type ChoiceOption = { value: string; label: string; words: string | null }

/** Background and position: native radios in a segmented control; none is chosen while unset. */
export function Choice({
  label,
  field,
  locked,
  onClear,
  error,
  value,
  options,
  inherited,
  onChange,
}: Common & {
  value: string | null
  options: readonly ChoiceOption[]
  inherited: ReactNode
  onChange: (value: string) => void
}) {
  const name = useId()
  return (
    <FieldShell
      label={label}
      field={field}
      set={value !== null}
      inherited={<>Event style: {inherited}</>}
      error={error}
      locked={locked}
      onClear={onClear}
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
            {options.map((option) => (
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
                <label htmlFor={`${name}-${option.value}`}>{option.label}</label>
              </Fragment>
            ))}
          </div>
          {options.some((option) => option.words !== null) && (
            <ul className="ci-words">
              {options.map((option) =>
                option.words === null ? null : (
                  <li key={option.value} data-chosen={value === option.value || undefined}>
                    <strong>{option.label}</strong> {option.words}
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
