import { useId } from 'react'
import type { ReactNode, RefObject } from 'react'

import type { ReelDocument } from '../api/reel'
import { Icon } from '../ui/Icon'
import type { MetadataDraft, MetadataField } from './draft'

/*
 * The event's title, date, location and description, as `reel.yaml` itself
 * says them. An empty field inherits: where the page resolved a value from
 * the folder name, the field shows it as inherited, and a field the operator
 * empties says it will inherit once saved.
 *
 * The fields are not in a submitting <form>, so Enter never saves: Save is the
 * save bar's. The one client-side rule is the date input's own: a date typed
 * only in part reads as '' and must not be taken for "inherit".
 */

/** The values the page resolved (reel.yaml over the folder name), for the hints. */
export type Resolved = { title: string | null; date: string | null; location: string | null }

export const FIELD_LABEL: Record<MetadataField, string> = {
  title: 'Title',
  date: 'Date',
  location: 'Location',
  description: 'Description',
}

function isSet(value: string | null | undefined): boolean {
  return value != null && value.trim() !== ''
}

/**
 * The inherited-value hint, or null. The page resolves a field to the folder
 * name's value only when `reel.yaml` leaves it unset, so the resolved value is
 * named only then; a field the operator empties says it will inherit, but not
 * what, since the resolved value it shows is the authored one being removed.
 */
export function inheritHint(
  field: 'title' | 'date' | 'location',
  read: ReelDocument,
  draft: MetadataDraft,
  resolved: Resolved | null,
): ReactNode {
  if (draft[field].trim() !== '') {
    return null
  }
  if (isSet(read.metadata[field])) {
    return 'Left empty: inherits from the folder name when saved'
  }
  const inherited = resolved?.[field]
  if (inherited == null) {
    return null
  }
  return (
    <>
      From the folder name: <span className="field-hint-value">{inherited}</span>
    </>
  )
}

function Field({
  id,
  label,
  changed,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  /** Marked beside the label, as a moved clip is in its row; the save bar says it in words. */
  changed: boolean
  hint: ReactNode
  error?: string | null
  children: ReactNode
}) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
        {changed && <span className="field-changed" aria-hidden="true" />}
      </label>
      {children}
      {error != null && (
        <p className="field-error" id={`${id}-error`}>
          <Icon name="alert-triangle" />
          {error}
        </p>
      )}
      {hint != null && (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
    </div>
  )
}

/** Space-separated ids, empty ones dropped; undefined when none is left. */
export function ids(...parts: (string | false | null)[]): string | undefined {
  const kept = parts.filter((part): part is string => typeof part === 'string' && part !== '')
  return kept.length > 0 ? kept.join(' ') : undefined
}

export function MetadataForm({
  read,
  draft,
  resolved,
  changed,
  locked,
  dateIncomplete,
  refusal,
  refusalRef,
  onChange,
  onDateValidity,
}: {
  read: ReelDocument
  draft: MetadataDraft
  /** The page's resolved values; null without a detail (the needs-attention form). */
  resolved: Resolved | null
  /** The fields whose draft differs from what was read. */
  changed: readonly MetadataField[]
  locked: boolean
  dateIncomplete: boolean
  /** The service's explanation of an unusable date or title, shown at those fields. */
  refusal: string | null
  refusalRef: RefObject<HTMLDivElement | null>
  onChange: (field: MetadataField, value: string) => void
  onDateValidity: (incomplete: boolean) => void
}) {
  const id = useId()
  const fieldId = (field: MetadataField) => `${id}-${field}`
  const refusalId = `${id}-refusal`
  const hints = {
    title: inheritHint('title', read, draft, resolved),
    // A date typed in part reads as '' but is not left empty: no inherit hint then.
    date: dateIncomplete ? null : inheritHint('date', read, draft, resolved),
    location: inheritHint('location', read, draft, resolved),
  }
  const hintId = (field: 'title' | 'date' | 'location') =>
    hints[field] != null && `${fieldId(field)}-hint`
  // A partly typed date reads as ''. Its validity says so, and the input fires no
  // change while its value stays '', so every edit and the blur read it again.
  const readDateValidity = (input: HTMLInputElement) => onDateValidity(input.validity.badInput)

  return (
    <div className="metadata-form">
      <div className="field-group" role="group" aria-label="Date and title">
        {refusal !== null && (
          <div
            className="alert field-refusal"
            data-tone="err"
            id={refusalId}
            ref={refusalRef}
            tabIndex={-1}
          >
            <Icon name="alert-triangle" size={20} />
            <div className="alert-body">
              <p className="alert-title">This date or title can't be used</p>
              <p className="alert-detail">{refusal}</p>
            </div>
          </div>
        )}
        <Field
          id={fieldId('title')}
          label={FIELD_LABEL.title}
          changed={changed.includes('title')}
          hint={hints.title}
        >
          <input
            id={fieldId('title')}
            className="field-input"
            type="text"
            autoComplete="off"
            value={draft.title}
            readOnly={locked}
            aria-disabled={locked || undefined}
            aria-invalid={refusal !== null || undefined}
            aria-describedby={ids(refusal !== null && refusalId, hintId('title'))}
            onChange={(event) => onChange('title', event.currentTarget.value)}
          />
        </Field>
        <Field
          id={fieldId('date')}
          label={FIELD_LABEL.date}
          changed={changed.includes('date')}
          hint={hints.date}
          error={dateIncomplete ? 'Enter a complete date, or clear the field' : null}
        >
          <input
            id={fieldId('date')}
            className="field-input field-date"
            type="date"
            value={draft.date}
            readOnly={locked}
            aria-disabled={locked || undefined}
            aria-invalid={refusal !== null || dateIncomplete || undefined}
            aria-describedby={ids(
              refusal !== null && refusalId,
              dateIncomplete && `${fieldId('date')}-error`,
              hintId('date'),
            )}
            onChange={(event) => {
              onChange('date', event.currentTarget.value)
              readDateValidity(event.currentTarget)
            }}
            onKeyUp={(event) => readDateValidity(event.currentTarget)}
            onBlur={(event) => readDateValidity(event.currentTarget)}
          />
        </Field>
      </div>
      <Field
        id={fieldId('location')}
        label={FIELD_LABEL.location}
        changed={changed.includes('location')}
        hint={hints.location}
      >
        <input
          id={fieldId('location')}
          className="field-input"
          type="text"
          autoComplete="off"
          value={draft.location}
          readOnly={locked}
          aria-disabled={locked || undefined}
          aria-describedby={ids(hintId('location'))}
          onChange={(event) => onChange('location', event.currentTarget.value)}
        />
      </Field>
      <Field
        id={fieldId('description')}
        label={FIELD_LABEL.description}
        changed={changed.includes('description')}
        hint={null}
      >
        <textarea
          id={fieldId('description')}
          className="field-input field-description"
          rows={3}
          value={draft.description}
          readOnly={locked}
          aria-disabled={locked || undefined}
          onChange={(event) => onChange('description', event.currentTarget.value)}
        />
      </Field>
    </div>
  )
}
