import './cardStyle.css'

import { useEffect, useId, useState } from 'react'

import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { ColorField } from './card/ColorField'
import { BACKGROUND_OPTIONS, POSITION_OPTIONS } from './card/choice.ts'
import { Choice, TextField } from './card/Fields'
import type { FieldWords } from './card/Fields'
import { FontField } from './card/FontField'
import { NO_CARD, previewRequest } from './card/model.ts'
import { CardPreview } from './card/Preview'
import { styleWords } from './card/specs.ts'
import type { EventStyle } from './card/specs.ts'
import { useFonts } from './card/useFonts.ts'
import { changedStyleFields, effective, styleRefusalOf } from './cardStyle.ts'
import type { StyleDraft, StyleField, StyleRefusal, StyleValue } from './cardStyle.ts'

/*
 * "Card style for this event" (`title-card-event-style`): Edit mode's one place for the
 * event-wide `look.title_card`, the layer every title card inherits from. Closed until opened.
 * It edits the editor's one draft (`style`), keeps no value of its own, and shows the service's
 * own drawing of the event's opening card from the draft. An unset field says it follows the
 * project default and shows the value in force when the page read it; a field the operator
 * cleared although the saved style set it says "Project default" with no number, because the
 * page does not know it (Principle I). The engine decides what is valid; its refusal is shown
 * at the field.
 */

export const PANEL_NAME = 'Card style for this event'
export const PROJECT_DEFAULT = 'Project default'
const WORDS: FieldWords = { clear: 'Use project default', tag: PROJECT_DEFAULT, hint: PROJECT_DEFAULT }

export type CardStyleModel = {
  eventId: string
  /** The style as read, and as the draft has it now. */
  read: StyleDraft
  style: StyleDraft
  /** The saved resolved style (the project default under the saved event layer), or null. */
  resolved: EventStyle | null
  /** The detail's `title_card_error`: the engine could not resolve the saved style. */
  error: string | null
  /** The last refused save's naming of a style field. */
  refusal: StyleRefusal | null
  /** The draft style as a save would write it, while it is not the saved one. */
  previewStyle: { [key: string]: unknown } | undefined
  /** The draft event title and the one the folder name gives: what the opening card says. */
  eventTitle: string
  folderTitle: string | null
  locked: boolean
  onSet: (field: StyleField, value: StyleValue | null) => void
  onReset: () => void
}

function text(value: StyleValue | null): string | null {
  return value === null ? null : String(value)
}

export function CardStylePanel({ model }: { model: CardStyleModel }) {
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
  const open0 = savedActive || refusal !== null
  const [open, setOpen] = useState(open0)
  useEffect(() => {
    if (open0) {
      setOpen(true)
    }
  }, [open0])

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

  const request = previewRequest({
    opening: true,
    chapterName: '',
    card: NO_CARD,
    eventTitle: model.eventTitle,
    style: model.previewStyle,
  })
  const background = effective('background', NO_CARD, style, read, resolved).value

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
    <details
      className="cs"
      open={open}
      data-changed={changed.length > 0 || undefined}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cs-summary">
        <Icon name="chevron-down" size={16} />
        <span id={headingId} className="cs-name">
          {PANEL_NAME}
        </span>
        {changed.length > 0 && <span className="cs-changed">Changed</span>}
      </summary>
      <div className="cs-body">
        {error !== null && savedActive && (
          <Alert tone="err" title="The service refused this style." detail={error} />
        )}
        {refusal !== null && refusal.field === null && (
          <Alert tone="err" title="The service refused this style." detail={refusal.message} />
        )}
        <p className="cs-lede">
          Every title card of this event follows these. A card can override any of them. A field left
          empty follows the project default.
        </p>
        <div className="cs-grid">
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
              shown={text(style.text_color) ?? String(effective('text_color', NO_CARD, style, read, resolved).value ?? '')}
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
            <div className="cs-actions">
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
          <CardPreview
            key="style"
            eventId={model.eventId}
            request={request}
            title={model.eventTitle || model.folderTitle || ''}
            subtitle=""
            video={background === 'video'}
            backdrop={null}
            backdropNote="Text over the start of each chapter’s first clip, shown here on a pattern, without the opening card’s own overrides."
            tooLong={false}
          />
        </div>
      </div>
    </details>
  )
}
