import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { parseCardLength } from '../../timeline/cardLength.ts'
import type { CardRange } from '../../timeline/cardLength.ts'
import { CARD_WORDS, FieldShell, hintOf } from './Fields'

/*
 * The card dialog's Length field (`edit-mode-declutter`): the card's length in seconds, in whole
 * tenths, with the limits of the Timeline's length drag (`parseCardLength` over `cardLimits`).
 * An accepted value goes into the draft as it is typed, as the drag's release does, so the two
 * are one edit of `duration`; a refused one is explained under the field, the text kept and the
 * draft left as it was. Empty is Use event style.
 */

export function LengthField({
  value,
  inherited,
  range,
  error,
  locked,
  onSet,
  onClear,
  onRefused,
}: {
  /** The card's own `duration` in seconds, or null while it follows the event style. */
  value: number | null
  /** What the event style gives, in words. */
  inherited: ReactNode
  range: CardRange
  /** The service's refusal of the saved length. */
  error: string | null
  locked: boolean
  onSet: (seconds: number) => void
  onClear: () => void
  /** The field holds a refused length (true) or not: the dialog's tab says so. */
  onRefused: (refused: boolean) => void
}) {
  const [text, setText] = useState(value === null ? '' : String(value))
  const [refusal, setRefusal] = useState<string | null>(null)
  // The draft changed by something other than this field (the drag, Undo): the field shows it.
  useEffect(() => {
    const typed = parseCardLength(text, range)
    const same =
      typed.kind === 'set' ? typed.seconds === value : typed.kind === 'unset' && value === null
    if (!same && refusal === null) {
      setText(value === null ? '' : String(value))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])
  useEffect(() => onRefused(refusal !== null), [refusal, onRefused])
  const shown = refusal ?? (range.adjustable ? null : range.reason)
  return (
    <FieldShell
      label="Length of the title card (seconds)"
      field="duration"
      set={value !== null}
      inherited={hintOf(CARD_WORDS, inherited)}
      error={error ?? shown}
      locked={locked}
      onClear={() => {
        setText('')
        setRefusal(null)
        onClear()
      }}
    >
      {(control) => (
        <input
          {...control}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          className="field-input ci-number"
          value={text}
          placeholder={typeof inherited === 'string' && inherited !== '' ? inherited : 'Event style'}
          readOnly={locked || !range.adjustable}
          aria-disabled={locked || !range.adjustable || undefined}
          onChange={(event) => {
            const next = event.currentTarget.value
            setText(next)
            const parsed = parseCardLength(next, range)
            if (parsed.kind === 'refused') {
              setRefusal(parsed.words)
              return
            }
            setRefusal(null)
            if (parsed.kind === 'set') {
              onSet(parsed.seconds)
            } else {
              onClear()
            }
          }}
        />
      )}
    </FieldShell>
  )
}
