import './card.css'

import { useId } from 'react'
import type { KeyboardEvent } from 'react'

import type { Font } from '../../api/fonts.ts'
import type { CardSpec } from '../../timeline/cards.ts'
import { Alert } from '../../ui/Alert'
import { Icon } from '../../ui/Icon'
import type { CardEditing, CardView } from './editing.ts'
import { ColorField } from './ColorField'
import { FontField } from './FontField'
import { Choice, NumberField, TextField } from './Fields'
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
import { effectiveBackground, styleWords } from './specs.ts'
import { overrideWords } from '../cardStyle.ts'

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
  const { state: fonts } = useFonts()
  const list: readonly Font[] = fonts.status === 'ok' ? fonts.fonts : []
  const { card, opening } = view
  const { style, locked } = editing
  const set = <F extends CardField>(field: F, value: Parameters<CardEditing['set']>[2]) =>
    editing.set(saved, field, value as never)
  const clear = (field: string) => editing.set(saved, field as CardField, null as never)
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
    style: editing.previewStyle,
  })
  const cardError = spec?.card == null && spec?.error != null ? spec.error : null
  const inherited = (field: CardField, value: string | number | undefined) => {
    const words = style === null ? '' : styleWords(field, value, list)
    return words === '' ? 'unknown' : words
  }
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
        <div className="ci-heading">
          <h3 id={headingId} className="ci-title">
            {name}
          </h3>
          <p className="ci-overrides">{overrideWords(card)}</p>
        </div>
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
          <FontField
            value={card.font_family}
            inherited={inherited('font_family', style?.font_family)}
            error={refused('font_family')}
            onChange={(value) => set('font_family', value)}
            {...shared}
          />
          <div className="ci-pair">
            <NumberField
              label="Title size"
              field="title_font_size"
              value={card.title_font_size}
              placeholder={inherited('title_font_size', style?.title_font_size)}
              inherited={inherited('title_font_size', style?.title_font_size)}
              error={refused('title_font_size')}
              onChange={(value) => set('title_font_size', value)}
              {...shared}
            />
            <NumberField
              label="Subtitle size"
              field="subtitle_font_size"
              value={card.subtitle_font_size}
              placeholder={inherited('subtitle_font_size', style?.subtitle_font_size)}
              inherited={inherited('subtitle_font_size', style?.subtitle_font_size)}
              error={refused('subtitle_font_size')}
              onChange={(value) => set('subtitle_font_size', value)}
              {...shared}
            />
          </div>
          <ColorField
            value={card.text_color}
            inherited={inherited('text_color', style?.text_color)}
            shown={card.text_color ?? style?.text_color ?? ''}
            error={refused('text_color')}
            onChange={(value) => set('text_color', value)}
            {...shared}
          />
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
