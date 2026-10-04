import './card.css'

import { useId, useRef, useState } from 'react'
import type { KeyboardEvent, RefObject } from 'react'

import type { Font } from '../../api/fonts.ts'
import type { CardRange } from '../../timeline/cardLength.ts'
import type { CardSpec } from '../../timeline/cards.ts'
import { Alert } from '../../ui/Alert'
import { Icon } from '../../ui/Icon'
import type { CardEditing, CardView } from './editing.ts'
import { ColorField } from './ColorField'
import { FontField } from './FontField'
import { BACKGROUND_OPTIONS, POSITION_OPTIONS } from './choice.ts'
import { EventTab, styleProblems } from './EventTab'
import { Choice, NumberField, TextField } from './Fields'
import { LengthField } from './LengthField'
import { NameField } from './NameField'
import type { NameGate } from './NameField'
import { TAB_LIST_NAME, TAB_ORDER, openingTab, tabAfterKey, tabLabel } from './tabs.ts'
import type { Problems, TabId } from './tabs.ts'
import { cardTitleShown } from './nameField.ts'
import type { FieldWords } from './Fields'
import { CardPreview } from './Preview'
import type { Backdrop } from './Preview'
import { useFonts } from './useFonts.ts'
import {
  NO_SUBTITLE_WORDS,
  changedFields,
  openingSubtitleFollows,
  openingSubtitlePlaceholder,
  overBounds,
  previewRequest,
  titlePlaceholder,
  tooLongWords,
} from './model.ts'
import type { CardField } from './model.ts'
import { effectiveBackground, styleWords } from './specs.ts'
import { overrideWords } from '../cardStyle.ts'

/*
 * The title-card inspector (`title-card-inspector`), Edit mode's one card editor. It is the
 * body of the modal dialog (`card-editor-dialog`) that a chapter's Edit Titlecard button or a
 * Timeline block opens; the dialog (`ui/Dialog`) carries the title, Escape and the Done button.
 * Two tabs (`edit-mode-declutter`): "This title card" (the Name first, then the card's own
 * fields and Length) and "All title cards in this event" (the event style and the Title cards
 * switch). Every card field is a per-card override: unset, it shows what the event style gives;
 * set, it offers Use event style. The preview is the service's own drawing of the draft
 * (`Preview.tsx`), outside the panels so that it stays in view on either tab. All edits go into
 * the editor's one draft; the inspector keeps no value of its own.
 */

export const NO_SUBTITLE_PLACEHOLDER = 'No subtitle'
export const FOLLOW_SUBTITLE = 'Event style: no subtitle'
/** The opening card's subtitle follows the engine's default, not the event style. */
export const OPENING_SUBTITLE_WORDS: FieldWords = {
  clear: 'Use default',
  tag: 'Default',
  hint: 'Default',
}

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
  lengthRange,
  gate,
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
  /** The limits of the card's length: the Timeline's drag has the same. */
  lengthRange: CardRange
  /** The Name field's gate: Done is held while it holds a refused name. */
  gate: RefObject<NameGate | null>
  onClose: () => void
}) {
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
  // The opening card alone has a default subtitle (the engine's date and place); the page shows
  // the detail's value and composes none.
  const defaultSubtitle = spec?.card?.defaultSubtitle ?? ''
  const effectiveSubtitle = card.subtitle ?? defaultSubtitle
  const nameBinding = editing.name(saved)
  const off = editing.switchModel.answer !== null && !editing.switchModel.on

  // The tabs. The service's last answer decides which opens; a hidden tab says if it holds a problem.
  const tabsId = useId()
  const named: Problems = {
    card: view.refusal !== null ? 1 : 0,
    event: styleProblems(editing.styleModel),
  }
  const [tab, setTab] = useState<TabId>(() => openingTab(named))
  const [local, setLocal] = useState({ name: false, length: false })
  const problems: Problems = {
    card: named.card + (local.name ? 1 : 0) + (local.length ? 1 : 0),
    event: named.event,
  }
  const tabButtons = useRef(new Map<TabId, HTMLButtonElement>())
  const onTabKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const next = tabAfterKey(tab, event.key)
    if (next !== null) {
      event.preventDefault()
      setTab(next)
      tabButtons.current.get(next)?.focus()
    }
  }
  // The card title's field leaves with its last character: focus goes to the Name, not the page.
  const nameInput = useRef<HTMLDivElement>(null)
  const keepFocus = () =>
    nameInput.current?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true })
  const lengthNow = card.duration

  return (
    <div className="ci">
      <header className="ci-head">
        <p className="ci-overrides" hidden={tab !== 'card'}>{overrideWords(card)}</p>
        <div className="ci-head-actions">
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            hidden={tab !== 'card'}
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
      {view.added && (
        <Alert tone="info" role="note" title="Its title card is drawn after Save." />
      )}
      {off && (
        <Alert
          tone="info"
          role="note"
          title="Title cards are off for this event."
          detail="This card is kept, and not drawn, until they are turned on."
        />
      )}

      <div className="ci-tabs" role="tablist" aria-label={TAB_LIST_NAME}>
        {TAB_ORDER.map((id) => (
          <button
            key={id}
            ref={(node) => {
              if (node === null) {
                tabButtons.current.delete(id)
              } else {
                tabButtons.current.set(id, node)
              }
            }}
            type="button"
            role="tab"
            id={`${tabsId}-tab-${id}`}
            className="ci-tab"
            aria-selected={tab === id}
            aria-controls={`${tabsId}-panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            data-problem={problems[id] > 0 || undefined}
            onClick={() => setTab(id)}
            onKeyDown={onTabKey}
          >
            {tabLabel(id, problems)}
          </button>
        ))}
      </div>

      <div className="ci-body">
        <div className="ci-panels">
          <div
            role="tabpanel"
            id={`${tabsId}-panel-card`}
            aria-labelledby={`${tabsId}-tab-card`}
            className="ci-fields"
            hidden={tab !== 'card'}
          >
            <div ref={nameInput} className="ci-name-host">
              {nameBinding !== null && (
                <NameField
                  binding={nameBinding}
                  locked={locked}
                  gate={gate}
                  announce={editing.announce}
                  onRefused={(on) => setLocal((was) => (was.name === on ? was : { ...was, name: on }))}
                />
              )}
            </div>
            {cardTitleShown(card) && (
              <TextField
                label="Card title (overrides the name)"
                field="title"
                multiline={false}
                value={card.title}
                placeholder={follow.placeholder}
                follows={follow.follows}
                error={refused('title') ?? bound('title')}
                onChange={(value) => {
                  set('title', value === '' ? null : value)
                  if (value === '') {
                    keepFocus()
                  }
                }}
                words={{ clear: 'Use the name', tag: 'Name', hint: 'Name' }}
                locked={locked}
                onClear={() => {
                  set('title', null)
                  keepFocus()
                }}
              />
            )}
            <TextField
              label="Subtitle"
              field="subtitle"
              multiline
              value={card.subtitle}
              placeholder={
                opening
                  ? openingSubtitlePlaceholder(card.subtitle, defaultSubtitle)
                  : NO_SUBTITLE_PLACEHOLDER
              }
              follows={opening ? openingSubtitleFollows(defaultSubtitle) : FOLLOW_SUBTITLE}
              words={opening ? OPENING_SUBTITLE_WORDS : undefined}
              action={
                opening && card.subtitle !== ''
                  ? { label: NO_SUBTITLE_WORDS, onPress: () => set('subtitle', '') }
                  : null
              }
              error={refused('subtitle') ?? bound('subtitle')}
              onChange={(value) => set('subtitle', value === '' ? null : value)}
              {...shared}
            />
            <Choice
              label="Background"
              field="background"
              value={card.background}
              options={BACKGROUND_OPTIONS}
              inherited={inherited('background', style?.background)}
              inheritedValue={style?.background ?? null}
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
              options={POSITION_OPTIONS}
              inherited={inherited('position', style?.position)}
              inheritedValue={style?.position ?? null}
              error={refused('position')}
              onChange={(value) => set('position', value)}
              {...shared}
            />
            <LengthField
              value={lengthNow}
              inherited={
                style?.duration === undefined ? '' : `${style.duration.toFixed(1)} s`
              }
              range={lengthRange}
              error={refused('duration')}
              locked={locked}
              onSet={(seconds) => editing.setLength(saved, seconds)}
              onClear={() => clear('duration')}
              onRefused={(on) => setLocal((was) => (was.length === on ? was : { ...was, length: on }))}
            />
          </div>
          <div
            role="tabpanel"
            id={`${tabsId}-panel-event`}
            aria-labelledby={`${tabsId}-tab-event`}
            hidden={tab !== 'event'}
          >
            <EventTab style={editing.styleModel} cards={editing.switchModel} />
          </div>
        </div>

        <CardPreview
          key={saved}
          eventId={eventId}
          request={request}
          title={card.title ?? follow.placeholder}
          subtitle={effectiveSubtitle}
          video={effectiveBackground(card, style, spec) === 'video'}
          backdrop={backdrop}
          tooLong={over.length > 0}
        />
      </div>
    </div>
  )
}
