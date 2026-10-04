import { CARD_WORDS, FieldShell, hintOf } from './Fields'
import type { FieldWords } from './Fields'
import { useFonts } from './useFonts.ts'

/*
 * The font control shared by the card inspector and the event's card style
 * (`title-card-event-style`): a native select over the families `GET /api/v1/fonts` lists, with
 * the empty choice saying what an unset field follows. A family the list does not hold stays
 * shown as it is, never silently dropped. The face itself is shown by the service's preview.
 */

export function FontField({
  value,
  inherited,
  error,
  locked,
  onChange,
  onClear,
  words = CARD_WORDS,
}: {
  /** The family set, or null while the field follows the layer below. */
  value: string | null
  /** The value in force below, in words. */
  inherited: string
  error: string | null
  locked: boolean
  onChange: (family: string | null) => void
  onClear: (field: string) => void
  words?: FieldWords
}) {
  const { state: fonts, retry } = useFonts()
  const list = fonts.status === 'ok' ? fonts.fonts : []
  return (
    <FieldShell
      label="Font"
      field="font_family"
      set={value !== null}
      inherited={hintOf(words, inherited)}
      error={error}
      locked={locked}
      onClear={onClear}
      words={words}
    >
      {(control) => (
        <>
          <select
            {...control}
            className="field-input ci-select"
            value={value ?? ''}
            aria-disabled={locked || fonts.status !== 'ok' || undefined}
            onChange={(event) => {
              const next = event.currentTarget.value
              if (!locked && fonts.status === 'ok') {
                onChange(next === '' ? null : next)
              }
            }}
          >
            <option value="">{inherited === '' ? words.hint : `${words.hint}: ${inherited}`}</option>
            {list.map((font) => (
              <option key={font.family} value={font.family}>
                {font.display_name}
                {font.default ? ' (default)' : ''}
              </option>
            ))}
            {fonts.status === 'ok' && value !== null && !list.some((font) => font.family === value) && (
              <option value={value}>{value} (not in the list)</option>
            )}
          </select>
          {fonts.status === 'loading' && <p className="ci-note">Reading the font list…</p>}
          {fonts.status === 'failed' && (
            <p className="ci-note" data-tone="err">
              The font list could not be read: {fonts.message}{' '}
              <button type="button" className="btn btn-ghost btn-compact" onClick={retry}>
                Try again
              </button>
            </p>
          )}
        </>
      )}
    </FieldShell>
  )
}
