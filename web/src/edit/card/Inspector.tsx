import './card.css'

import { useId } from 'react'
import type { KeyboardEvent } from 'react'

import type { Font } from '../../api/fonts.ts'
import type { CardSpec } from '../../timeline/cards.ts'
import { Alert } from '../../ui/Alert'
import { Icon } from '../../ui/Icon'
import type { CardEditing, CardView } from './editing.ts'
import { Choice, FieldShell, NumberField, TextField } from './Fields'
import { CardPreview } from './Preview'
import type { Backdrop } from './Preview'
import { useFonts } from './useFonts.ts'
import {
  changedFields,
  overBounds,
  previewRequest,
  titlePlaceholder,
  tooLongWords,
} from './model.ts'
import type { CardField } from './model.ts'
import { effectiveBackground } from './specs.ts'

/*
 * The title-card inspector (`title-card-inspector`), Edit mode's one card editor. It renders in
 * the Timeline section's slot for the card selected on the Timeline or in a chapter's row.
 * Every field is a per-card override: unset, it shows what the event style gives; set, it
 * offers Use event style. Typing a title never renames the chapter. The preview is the service's
 * own drawing of the draft (`Preview.tsx`). All edits go into the editor's one draft; the
 * inspector keeps no value of its own. It is not a modal, and Escape closes it.
 */

export const NO_SUBTITLE_PLACEHOLDER = 'No subtitle'
export const FOLLOW_SUBTITLE = 'Event style: no subtitle'

/** The inspector's name: the opening card is not a chapter's. */
export function inspectorName(opening: boolean, name: string): string {
  return opening ? 'Opening title card' : `Title card for ${name}`
}

/** A style value as words (`Black`, a font's display name, the number), or `unknown`. */
function styleWords(
  field: CardField,
  value: string | number | undefined,
  fonts: readonly Font[],
): string {
  if (value === undefined || value === '') {
    return 'unknown'
  }
  if (field === 'font_family') {
    return fonts.find((font) => font.family === value)?.display_name ?? String(value)
  }
  if (field === 'background' || field === 'position') {
    const text = String(value)
    return text.charAt(0).toUpperCase() + text.slice(1)
  }
  return String(value)
}

export function CardInspectorPanel({
  eventId,
  saved,
  view,
  editing,
  spec,
  backdrop,
  onClose,
}: {
  eventId: string
  /** The card's chapter as saved: what the selection is keyed by. */
  saved: string
  view: CardView
  editing: CardEditing
  /** The card as the draft would have it drawn, for the error it may carry. */
  spec: CardSpec | undefined
  /** The clip a video card sits over, or null when there is none to show. */
  backdrop: Backdrop | null
  onClose: () => void
}) {
  const headingId = useId()
  const { state: fonts, retry } = useFonts()
  const list: readonly Font[] = fonts.status === 'ok' ? fonts.fonts : []
  const { card, opening } = view
  const { style, locked } = editing
  const set = <F extends CardField>(field: F, value: Parameters<CardEditing['set']>[2]) =>
    editing.set(saved, field, value as never)
  const clear = (field: CardField) => editing.set(saved, field, null as never)
  const changed = changedFields(view.read, card)
  const name = inspectorName(opening, view.name)
  const follow = titlePlaceholder({
    opening,
    chapterName: view.name,
    eventTitle: view.eventTitle,
    folderTitle: view.folderTitle,
  })
  const over = overBounds(card)
  const bound = (field: 'title' | 'subtitle') => {
    const item = over.find((candidate) => candidate.field === field)
    return item === undefined ? null : tooLongWords(item.limit)
  }
  const refused = (field: CardField) =>
    view.refusal !== null && view.refusal.field === field ? view.refusal.message : null
  const request = previewRequest({
    opening,
    chapterName: opening ? '' : view.name,
    card,
    eventTitle: view.eventTitle,
  })
  const cardError = spec?.card == null && spec?.error != null ? spec.error : null
  const inherited = (field: CardField, value: string | number | undefined) =>
    style === null ? 'unknown' : styleWords(field, value, list)
  const shared = { locked, onClear: clear }

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape' && !event.defaultPrevented) {
      event.preventDefault()
      onClose()
    }
  }

  return (
    <section className="ci" aria-labelledby={headingId} onKeyDown={onKeyDown}>
      <header className="ci-head">
        <h3 id={headingId} className="ci-title">
          {name}
        </h3>
        <div className="ci-head-actions">
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            aria-disabled={locked || changed.length === 0 || undefined}
            onClick={() => {
              if (!locked && changed.length > 0) {
                editing.reset(saved)
                editing.announce(`Changes to the ${name.toLowerCase()} undone.`)
              }
            }}
          >
            Undo changes to this card
          </button>
          <button type="button" className="btn btn-ghost btn-compact" onClick={onClose}>
            <Icon name="x" />
            Close
          </button>
        </div>
      </header>

      {cardError !== null && (
        <Alert tone="warn" title="This card could not be resolved." detail={cardError} />
      )}
      {style === null && editing.styleError !== null && (
        <Alert tone="warn" title="The event style could not be resolved." detail={editing.styleError} />
      )}
      {view.refusal !== null && view.refusal.field === null && (
        <Alert tone="err" title="The service refused this card." detail={view.refusal.message} />
      )}

      <div className="ci-body">
        <div className="ci-fields">
          <TextField
            label="Title"
            field="title"
            multiline={false}
            value={card.title}
            placeholder={follow.placeholder}
            follows={follow.follows}
            error={refused('title') ?? bound('title')}
            onChange={(value) => set('title', value === '' ? null : value)}
            {...shared}
          />
          <TextField
            label="Subtitle"
            field="subtitle"
            multiline
            value={card.subtitle}
            placeholder={NO_SUBTITLE_PLACEHOLDER}
            follows={FOLLOW_SUBTITLE}
            error={refused('subtitle') ?? bound('subtitle')}
            onChange={(value) => set('subtitle', value === '' ? null : value)}
            {...shared}
          />
          <Choice
            label="Background"
            field="background"
            value={card.background}
            options={[
              { value: 'black', label: 'Black', words: 'Text on black, before the chapter' },
              {
                value: 'video',
                label: 'Video',
                words: 'Text over the start of the chapter’s first clip',
              },
            ]}
            inherited={inherited('background', style?.background)}
            error={refused('background')}
            onChange={(value) => set('background', value)}
            {...shared}
          />
          <FieldShell
            label="Font"
            field="font_family"
            set={card.font_family !== null}
            inherited={`Event style: ${inherited('font_family', style?.font_family)}`}
            error={refused('font_family')}
            {...shared}
          >
            {(control) => (
              <>
                <select
                  {...control}
                  className="field-input ci-select"
                  value={card.font_family ?? ''}
                  aria-disabled={locked || fonts.status !== 'ok' || undefined}
                  onChange={(event) => {
                    const value = event.currentTarget.value
                    if (!locked && fonts.status === 'ok') {
                      set('font_family', value === '' ? null : value)
                    }
                  }}
                >
                  <option value="">Event style: {inherited('font_family', style?.font_family)}</option>
                  {list.map((font) => (
                    <option key={font.family} value={font.family}>
                      {font.display_name}
                      {font.default ? ' (default)' : ''}
                    </option>
                  ))}
                  {/* A family the list does not hold stays shown as it is, never silently dropped. */}
                  {fonts.status === 'ok' &&
                    card.font_family !== null &&
                    !list.some((font) => font.family === card.font_family) && (
                      <option value={card.font_family}>{card.font_family} (not in the list)</option>
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
          <div className="ci-pair">
            <NumberField
              label="Title size"
              field="title_font_size"
              value={card.title_font_size}
              placeholder={style === null ? 'unknown' : String(style.title_font_size)}
              inherited={inherited('title_font_size', style?.title_font_size)}
              error={refused('title_font_size')}
              onChange={(value) => set('title_font_size', value)}
              {...shared}
            />
            <NumberField
              label="Subtitle size"
              field="subtitle_font_size"
              value={card.subtitle_font_size}
              placeholder={style === null ? 'unknown' : String(style.subtitle_font_size)}
              inherited={inherited('subtitle_font_size', style?.subtitle_font_size)}
              error={refused('subtitle_font_size')}
              onChange={(value) => set('subtitle_font_size', value)}
              {...shared}
            />
          </div>
          <FieldShell
            label="Text colour"
            field="text_color"
            set={card.text_color !== null}
            inherited={`Event style: ${inherited('text_color', style?.text_color)}`}
            error={refused('text_color')}
            {...shared}
          >
            {(control) => {
              const shown = card.text_color ?? style?.text_color ?? ''
              return (
                <div className="ci-color">
                  <input
                    type="color"
                    className="ci-swatch"
                    aria-label="Text colour picker"
                    value={/^#[0-9a-fA-F]{6}$/.test(shown) ? shown.toLowerCase() : '#000000'}
                    data-unset={card.text_color === null || undefined}
                    aria-disabled={locked || undefined}
                    onChange={(event) => {
                      if (!locked) {
                        set('text_color', event.currentTarget.value)
                      }
                    }}
                  />
                  <input
                    {...control}
                    type="text"
                    className="field-input ci-hex"
                    autoComplete="off"
                    spellCheck={false}
                    value={card.text_color ?? ''}
                    placeholder={style === null ? 'unknown' : style.text_color}
                    readOnly={locked}
                    aria-disabled={locked || undefined}
                    onChange={(event) =>
                      set('text_color', event.currentTarget.value === '' ? null : event.currentTarget.value)
                    }
                  />
                </div>
              )
            }}
          </FieldShell>
          <Choice
            label="Position"
            field="position"
            value={card.position}
            options={[
              { value: 'top', label: 'Top', words: null },
              { value: 'center', label: 'Center', words: null },
              { value: 'bottom', label: 'Bottom', words: null },
            ]}
            inherited={inherited('position', style?.position)}
            error={refused('position')}
            onChange={(value) => set('position', value)}
            {...shared}
          />
        </div>

        <CardPreview
          key={saved}
          eventId={eventId}
          request={request}
          title={card.title ?? follow.placeholder}
          subtitle={card.subtitle ?? ''}
          video={effectiveBackground(card, style, spec) === 'video'}
          backdrop={backdrop}
          tooLong={over.length > 0}
        />
      </div>
    </section>
  )
}
