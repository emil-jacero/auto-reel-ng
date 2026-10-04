import { CARD_WORDS, FieldShell } from './Fields'
import type { FieldWords } from './Fields'

/*
 * The text colour control shared by the card inspector and the event's card style: a native colour
 * picker beside a text field, so a hand-written value stays editable as text. Whatever is typed
 * is sent; the service decides whether it is a colour.
 */

export function ColorField({
  value,
  inherited,
  shown,
  error,
  locked,
  onChange,
  onClear,
  words = CARD_WORDS,
}: {
  /** The colour set, or null while the field follows the layer below. */
  value: string | null
  /** The value in force below, in words (empty: unknown). */
  inherited: string
  /** The colour the picker rests on: the set one, else the one in force, else none. */
  shown: string
  error: string | null
  locked: boolean
  onChange: (value: string | null) => void
  onClear: (field: string) => void
  words?: FieldWords
}) {
  return (
    <FieldShell
      label="Text colour"
      field="text_color"
      set={value !== null}
      inherited={inherited === '' ? words.hint : `${words.hint}: ${inherited}`}
      error={error}
      locked={locked}
      onClear={onClear}
      words={words}
    >
      {(control) => (
        <div className="ci-color">
          <input
            type="color"
            className="ci-swatch"
            aria-label="Text colour picker"
            value={/^#[0-9a-fA-F]{6}$/.test(shown) ? shown.toLowerCase() : '#000000'}
            data-unset={value === null || undefined}
            aria-disabled={locked || undefined}
            onChange={(event) => {
              if (!locked) {
                onChange(event.currentTarget.value)
              }
            }}
          />
          <input
            {...control}
            type="text"
            className="field-input ci-hex"
            autoComplete="off"
            spellCheck={false}
            value={value ?? ''}
            placeholder={inherited === '' ? words.hint : inherited}
            readOnly={locked}
            aria-disabled={locked || undefined}
            onChange={(event) =>
              onChange(event.currentTarget.value === '' ? null : event.currentTarget.value)
            }
          />
        </div>
      )}
    </FieldShell>
  )
}
