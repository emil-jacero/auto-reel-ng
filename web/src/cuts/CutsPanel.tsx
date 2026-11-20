import './cuts.css'

import { memo, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'

import { clipMediaUrl } from '../api/clipMedia'
import type { CutKey, DraftCut } from '../edit/draft'
import { ids } from '../edit/MetadataForm'
import { useClipLength } from '../preview/ClipPreview'
import type { ClipPreviews } from '../preview/previews'
import { Icon } from '../ui/Icon'
import {
  CUT_HINT,
  NO_CUTS,
  PAST_END,
  addedWords,
  checkCut,
  checkRestore,
  clipLength,
  cutSummary,
  formatLength,
  formatTime,
  keptCuts,
  lengthHint,
  pastEnd,
  reasonWords,
  refusalWords,
  removedAddedWords,
  removedReadWords,
  restoreRefusalWords,
  restoredWords,
  spanWords,
  toggleName,
} from './times'
import type { CutField, CutRefusal, ListedCut } from './times'

/*
 * A clip's cuts in Edit mode: the Cuts control in its row, and the panel it
 * shows and hides under the row, which lists the cuts and adds one from two
 * typed times. The editor owns the cuts (`draft.ts`) and what the panel holds
 * (`CutPanels`): Move marked to…, or a drag into another chapter, mounts a row anew
 * in its new chapter, and a typed cut, or the panel being shown, must survive
 * that. Every announcement goes
 * through the editor's one live region.
 *
 * The clip's preview is not here: it is the bin's player (`edit/BinPlayer.tsx`). The length it
 * reads from the clip's file refuses a cut past the clip's end; before any preview, the
 * duration the detail gives the clip (when it has one) does.
 */

/** What one clip's panel holds: whether it is shown, and its two fields as typed. */
export type PanelState = { open: boolean; start: string; end: string }

/**
 * The editor's panel store, stable for its life. Reads and writes re-render nothing by themselves:
 * what shows a clip's fields (its panel, the bin's player) subscribes to that clip's entry.
 */
export type CutPanels = {
  get(identity: string): PanelState | undefined
  set(identity: string, next: PanelState): void
  /**
   * Write one field's text, as the player's Set From and Set To do: a panel that was never shown
   * gets an entry, hidden, and a shown or hidden one keeps its state.
   */
  setTyped(identity: string, field: CutField, text: string): void
  /** Called after each write to the clip's entry, and after a clear; returns its unsubscribe. */
  subscribe(identity: string, listener: () => void): () => void
  /** The editor's clip previews: one open at a time, and each clip's length once read. */
  previews: ClipPreviews
}

/** The editor's cut operations; one stable object, so rows keep their memoised props. */
export type CutHandlers = {
  onAdd(identity: string, span: { in: number; out: number }, reason?: string): void
  onRemove(identity: string, key: CutKey): void
  onRestore(identity: string, key: CutKey): void
  /** The panel's fields went from empty to holding text, or back. */
  onTyped(identity: string, typed: boolean): void
  onAnnounce(message: string): void
}

// Constant elements: rows re-render without rebuilding them. The event page's
// indicator (`ReadCuts.tsx`) shows the same two.
export const SCISSORS = <Icon name="scissors" />
export const CHEVRON = (
  <span className="cuts-chevron" aria-hidden="true">
    <Icon name="chevron-down" />
  </span>
)
const REMOVE = <Icon name="x" />
const UNDO = <Icon name="rotate-ccw" />
const PLUS = <Icon name="plus" />
const ALERT = <Icon name="alert-triangle" />

/** `0:00 → 0:01.5`, said "0:00 to 0:01.5"; a span may wrap after its arrow, a time never. */
export function CutSpan({ cut }: { cut: { in: number; out: number } }) {
  return (
    <span className="cut-span">
      <span className="cut-at">{formatTime(cut.in)}</span>
      <span aria-hidden="true"> → </span>
      <span className="visually-hidden"> to </span>
      <span className="cut-at">{formatTime(cut.out)}</span>
    </span>
  )
}

/**
 * A clip's cuts in their order, each with its number, span, length and reason in
 * words, then what `controls` adds (Edit mode's Remove or Undo; nothing on the
 * event page).
 */
export function CutList<T extends ListedCut & { reason?: string | null }>({
  cuts,
  label,
  keyOf,
  controls,
}: {
  cuts: readonly T[]
  label: string
  keyOf: (cut: T, index: number) => string
  controls?: (cut: T, number: number) => ReactNode
}) {
  return (
    <ol className="cut-list" aria-label={label}>
      {cuts.map((cut, index) => (
        <li
          key={keyOf(cut, index)}
          className="cut"
          data-key={keyOf(cut, index)}
          data-removed={cut.removed === true || undefined}
        >
          <span className="cut-n">{index + 1}</span>
          {/* The rest wraps beside the number, never under it. */}
          <div className="cut-body">
            <CutSpan cut={cut} />
            <span className="cut-length">{formatLength(cut.out - cut.in)}</span>
            <span className="cut-reason">{reasonWords(cut.reason)}</span>
            {controls?.(cut, index + 1)}
          </div>
        </li>
      ))}
    </ol>
  )
}

/**
 * The Cuts control: the clip's cut count and the time they cut out, or "Cuts"
 * with none; a narrow row shows the count only (`cuts.css`). While its panel holds
 * a time typed but not added, it says "typed" too, in words at every width and in
 * its name, so a hidden panel that holds Save back is found on its row. It shows and
 * hides the panel and stays live while a save is in flight: that changes nothing to
 * save.
 */
export const CutsToggle = memo(function CutsToggle({
  cuts,
  name,
  open,
  typed,
  controls,
  onToggle,
}: {
  cuts: readonly DraftCut[]
  name: string
  open: boolean
  /** Its panel holds a time typed but not added. */
  typed: boolean
  /** The panel's id while it is mounted; never an id that is not in the page. */
  controls: string | null
  onToggle: () => void
}) {
  const kept = keptCuts(cuts).length
  return (
    <button
      type="button"
      className="btn btn-ghost btn-compact cuts-toggle"
      data-cut={kept > 0 || undefined}
      data-typed={typed || undefined}
      aria-expanded={open}
      aria-controls={controls ?? undefined}
      aria-label={toggleName(cuts, name, typed)}
      onClick={onToggle}
    >
      {SCISSORS}
      {kept > 0 && <span className="cuts-toggle-count">{kept}</span>}
      <span className="cuts-toggle-words">{cutSummary(cuts)}</span>
      {typed && <span className="cuts-toggle-typed">typed</span>}
      {CHEVRON}
    </button>
  )
})

/** Where focus goes once a cut edit is on screen. */
type FocusRequest =
  | { target: 'start' | 'end' }
  | { target: 'cut-remove' | 'cut-undo' | 'cut-control'; key: CutKey }

function hasText(start: string, end: string): boolean {
  return start.trim() !== '' || end.trim() !== ''
}

/**
 * The panel under a clip's row. Its fields are local state for rendering,
 * seeded from the editor's store and written back on each change; the editor
 * hears only when "has text" flips (`onTyped`), so typing re-renders no list.
 */
export const CutsPanel = memo(function CutsPanel({
  id,
  eventId,
  identity,
  mtime,
  duration,
  name,
  cuts,
  open,
  locked,
  panels,
  handlers,
}: {
  id: string
  /** The event, for the clip's media address. */
  eventId: string
  identity: string
  /** The clip's modification time as the detail gives it: its media address's `v`. */
  mtime: string | null
  /**
   * The clip's duration in seconds as the detail gives it (the thumbnail operation's number,
   * never probed by the service), or `null` when unknown: never zero.
   */
  duration: number | null
  /** The clip's name as its row names it. */
  name: string
  cuts: readonly DraftCut[]
  open: boolean
  /** A save (or a move of marked clips) is pending: the fields and buttons change nothing. */
  locked: boolean
  panels: CutPanels
  handlers: CutHandlers
}) {
  const [start, setStart] = useState(() => panels.get(identity)?.start ?? '')
  const [end, setEnd] = useState(() => panels.get(identity)?.end ?? '')
  // The refusal of the last Add cut, shown at its field until a field changes.
  const [refusal, setRefusal] = useState<CutRefusal | null>(null)
  // A refused Undo's words, shown in its cut's row until the clip's next cut edit.
  const [undoRefusal, setUndoRefusal] = useState<{ key: CutKey; words: string } | null>(null)
  // What the fields hold now, for the store's listener below (a closure over state would be stale).
  const fields = useRef({ start, end })
  const startRef = useRef<HTMLInputElement>(null)
  const endRef = useRef<HTMLInputElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const focusAfter = useRef<FocusRequest | null>(null)
  const scrollAfter = useRef<HTMLElement | null>(null)
  const fieldId = useId()
  const startId = `${fieldId}-start`
  const endId = `${fieldId}-end`
  const errorId = `${fieldId}-error`
  const hintId = `${fieldId}-hint`
  const undoErrorId = `${fieldId}-undo`
  const { onAdd, onRemove, onRestore, onTyped, onAnnounce } = handlers
  const { previews } = panels
  // The length this browser read from the clip's file in a preview of this Edit mode;
  // keyed by the media address, so a replaced file (a new `mtime`) has none.
  const previewed = useClipLength(previews, clipMediaUrl(eventId, { identity, mtime }))
  // It wins; else the detail's duration (it belongs to the file the detail reported), else unknown.
  const length = clipLength(previewed, duration)

  function setFields(nextStart: string, nextEnd: string): void {
    panels.set(identity, {
      open: panels.get(identity)?.open ?? open,
      start: nextStart,
      end: nextEnd,
    })
    const had = hasText(start, end)
    const has = hasText(nextStart, nextEnd)
    fields.current = { start: nextStart, end: nextEnd }
    setStart(nextStart)
    setEnd(nextEnd)
    if (had !== has) {
      onTyped(identity, has)
    }
  }

  // The fields follow the store when something else writes them (the player's Set From and Set
  // To), and a refusal of the old text goes: it no longer describes the fields. The writer reports
  // whether the clip now holds typed text (`onTyped`), so this changes nothing in the editor.
  useLayoutEffect(
    () =>
      panels.subscribe(identity, () => {
        const held = panels.get(identity)
        const nextStart = held?.start ?? ''
        const nextEnd = held?.end ?? ''
        if (nextStart !== fields.current.start || nextEnd !== fields.current.end) {
          fields.current = { start: nextStart, end: nextEnd }
          setStart(nextStart)
          setEnd(nextEnd)
          setRefusal(null)
        }
      }),
    [panels, identity],
  )

  function add(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (locked) {
      return
    }
    const checked = checkCut(cuts, start, end, length)
    if (!checked.ok) {
      setRefusal(checked.refusal)
      focusAfter.current = { target: checked.refusal.field }
      onAnnounce(refusalWords(checked.refusal))
      return
    }
    const span = { in: checked.in, out: checked.out }
    onAdd(identity, span)
    setFields('', '')
    setRefusal(null)
    setUndoRefusal(null)
    focusAfter.current = { target: 'start' }
    onAnnounce(addedWords(span, name, [...keptCuts(cuts), span]))
  }

  function remove(cut: DraftCut, number: number): void {
    if (locked) {
      return
    }
    setUndoRefusal(null)
    onRemove(identity, cut.key)
    // A cut read from reel.yaml stays listed with its Undo; one added here is gone.
    if (cut.key.startsWith('r')) {
      focusAfter.current = { target: 'cut-undo', key: cut.key }
      onAnnounce(removedReadWords(number, cut, name))
      return
    }
    const after = cuts.filter((listed) => listed.key !== cut.key)
    const next = after[number - 1] ?? after[number - 2]
    focusAfter.current =
      next === undefined ? { target: 'start' } : { target: 'cut-control', key: next.key }
    onAnnounce(removedAddedWords(cut, name, after))
  }

  function restore(cut: DraftCut, number: number): void {
    if (locked) {
      return
    }
    // Refused as adding the cut would be: it stays removed, and focus on its Undo.
    const refused = checkRestore(cuts, cut.key)
    if (refused !== null) {
      const words = restoreRefusalWords(refused)
      setUndoRefusal({ key: cut.key, words })
      onAnnounce(words)
      return
    }
    setUndoRefusal(null)
    onRestore(identity, cut.key)
    focusAfter.current = { target: 'cut-remove', key: cut.key }
    onAnnounce(restoredWords(number, name))
  }

  // Focus once the edit is on screen (a dropped cut's node is gone, a refusal's words
  // are in place): a layout effect, so no frame paints with focus on <body>.
  useLayoutEffect(() => {
    const request = focusAfter.current
    if (request === null) {
      return
    }
    focusAfter.current = null
    let target: HTMLElement | null
    if (!('key' in request)) {
      target = request.target === 'start' ? startRef.current : endRef.current
      scrollAfter.current = formRef.current
    } else {
      const row = listRef.current?.querySelector<HTMLElement>(`.cut[data-key="${request.key}"]`)
      target =
        request.target === 'cut-control'
          ? (row?.querySelector<HTMLElement>('button') ?? null)
          : (row?.querySelector<HTMLElement>(`.${request.target}`) ?? null)
      scrollAfter.current = row ?? null
    }
    target?.focus({ preventScroll: true })
  })

  // Then the focused control's cut row, or the form, comes into view whole, clear of
  // the header, the chapter's heading and the save bar (the page's scroll padding),
  // which the editor has placed in its own layout effect by now.
  useEffect(() => {
    const element = scrollAfter.current
    scrollAfter.current = null
    element?.scrollIntoView({ block: 'nearest' })
  })

  const unavailable = locked || undefined
  return (
    <div
      className="clip-cuts"
      id={id}
      role="group"
      aria-label={`Cuts of ${name}`}
      hidden={!open}
    >
      <div ref={listRef}>
        {cuts.length === 0 ? (
          <p className="cuts-none">{NO_CUTS}</p>
        ) : (
          <CutList
            cuts={cuts}
            label={`Cuts of ${name}`}
            keyOf={(cut) => cut.key}
            controls={(cut, number) => (
              <>
                {length !== undefined && pastEnd(cut, length) && (
                  <span className="badge cut-past-end" data-tone="warn">
                    {ALERT}
                    {PAST_END}
                  </span>
                )}
                {cut.removed ? (
                  <>
                    <span className="badge" data-tone="warn">
                      {REMOVE}
                      Removed when you save
                    </span>
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact cut-undo"
                      aria-label={`Undo removing cut ${number} of ${name}`}
                      aria-describedby={undoRefusal?.key === cut.key ? undoErrorId : undefined}
                      aria-disabled={unavailable}
                      onClick={() => restore(cut, number)}
                    >
                      {UNDO}
                      Undo
                    </button>
                    {undoRefusal?.key === cut.key && (
                      <p className="cut-refusal field-error" id={undoErrorId}>
                        {ALERT}
                        {undoRefusal.words}
                      </p>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    className="btn btn-ghost btn-compact cut-remove"
                    aria-label={`Remove cut ${number} of ${name}, ${spanWords(cut)}`}
                    aria-disabled={unavailable}
                    onClick={() => remove(cut, number)}
                  >
                    {REMOVE}
                    Remove
                  </button>
                )}
              </>
            )}
          />
        )}
      </div>
      <form
        ref={formRef}
        className="cut-form"
        noValidate
        aria-label={`Add a cut to ${name}`}
        onSubmit={add}
      >
        <div className="field cut-field">
          <label className="field-label" htmlFor={startId}>
            From
          </label>
          <input
            ref={startRef}
            id={startId}
            className="field-input cut-time"
            type="text"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="done"
            value={start}
            readOnly={locked}
            aria-disabled={unavailable}
            aria-invalid={refusal?.field === 'start' || undefined}
            aria-describedby={ids(refusal?.field === 'start' && errorId, hintId)}
            onChange={(event) => {
              setRefusal(null)
              setFields(event.currentTarget.value, end)
            }}
          />
        </div>
        <div className="field cut-field">
          <label className="field-label" htmlFor={endId}>
            To
          </label>
          <input
            ref={endRef}
            id={endId}
            className="field-input cut-time"
            type="text"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="done"
            value={end}
            readOnly={locked}
            aria-disabled={unavailable}
            aria-invalid={refusal?.field === 'end' || undefined}
            aria-describedby={ids(refusal?.field === 'end' && errorId, hintId)}
            onChange={(event) => {
              setRefusal(null)
              setFields(start, event.currentTarget.value)
            }}
          />
        </div>
        <button type="submit" className="btn btn-secondary cut-add" aria-disabled={unavailable}>
          {PLUS}
          Add cut
        </button>
        {refusal !== null && (
          <p className="field-error" id={errorId}>
            {ALERT}
            {refusalWords(refusal)}
          </p>
        )}
        <p className="field-hint" id={hintId}>
          {length === undefined ? CUT_HINT : lengthHint(length, previewed !== undefined)}
        </p>
      </form>
    </div>
  )
})
