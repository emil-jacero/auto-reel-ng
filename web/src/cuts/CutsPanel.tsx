import './cuts.css'

import { memo, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'

import { clipMediaUrl } from '../api/clipMedia'
import type { CutKey, DraftCut } from '../edit/draft'
import { ids } from '../edit/MetadataForm'
import { ClipPreview, useClipLength, usePreviewOpen } from '../preview/ClipPreview'
import { HIDE_PLAYER, WATCH, hideName, setWords, watchName } from '../preview/playback'
import type { ClipPreviews } from '../preview/previews'
import type { ClipProxy } from '../preview/source'
import type { Turn } from '../rotate/turn.ts'
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
 * The panel's first control is Watch: the clip's preview (`preview/`, D-16) opens
 * there, above the cuts, and sets the fields at its playhead. The length it reads
 * from the clip's file then refuses a cut past the clip's end; before any preview, the
 * duration the detail gives the clip (when it has one) does.
 */

/** What one clip's panel holds: whether it is shown, and its two fields as typed. */
export type PanelState = { open: boolean; start: string; end: string }

/** The editor's panel store, stable for its life; reads and writes never re-render anything. */
export type CutPanels = {
  get(identity: string): PanelState | undefined
  set(identity: string, next: PanelState): void
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
const PLAY = <Icon name="play" />
const HIDE = <Icon name="x" />

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
  | { target: 'start' | 'end' | 'preview-toggle' | 'preview-thumb' }
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
  proxy,
  duration,
  name,
  cuts,
  turn = 0,
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
  /** The clip's proxy as the detail gives it: which file the preview plays. */
  proxy: ClipProxy | null
  /**
   * The clip's duration in seconds as the detail gives it (the thumbnail operation's number,
   * never probed by the service), or `null` when unknown: never zero.
   */
  duration: number | null
  /** The clip's name as its row names it. */
  name: string
  cuts: readonly DraftCut[]
  /** The clip's turn in the draft (`rotate`): its preview shows it. */
  turn?: Turn
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
  const previewId = `preview-${fieldId}`
  const rootRef = useRef<HTMLDivElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const { onAdd, onRemove, onRestore, onTyped, onAnnounce } = handlers
  const { previews } = panels
  const previewOpen = usePreviewOpen(previews, identity)
  // The length this browser read from the clip's file in a preview of this Edit mode;
  // keyed by the media address, so a replaced file (a new `mtime`) has none.
  const previewed = useClipLength(previews, clipMediaUrl(eventId, { identity, mtime }))
  // It wins; else the detail's duration (it belongs to the file the detail reported), else unknown.
  const length = clipLength(previewed, duration)
  // The bar's typed span: only one Add cut would accept (the panel's own checks).
  const typed = useMemo(() => {
    const checked = checkCut(cuts, start, end, length)
    return checked.ok ? { in: checked.in, out: checked.out } : null
  }, [cuts, start, end, length])
  const clip = useMemo(() => ({ identity, mtime }), [identity, mtime])

  function setFields(nextStart: string, nextEnd: string): void {
    panels.set(identity, {
      open: panels.get(identity)?.open ?? open,
      start: nextStart,
      end: nextEnd,
    })
    const had = hasText(start, end)
    const has = hasText(nextStart, nextEnd)
    setStart(nextStart)
    setEnd(nextEnd)
    if (had !== has) {
      onTyped(identity, has)
    }
  }

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

  /** Set From / Set To: the playhead's time as typed text, so it counts as typed (G2). */
  function setAt(field: CutField, seconds: number): void {
    if (locked) {
      return
    }
    const text = formatTime(seconds)
    if (field === 'start') {
      setFields(text, end)
    } else {
      setFields(start, text)
    }
    setRefusal(null)
    onAnnounce(setWords(field, seconds))
  }

  /** Close, or Escape in the preview: focus goes back to the control that opened it. */
  function closePlayer(): void {
    const opener = previews.opener(identity)
    previews.hide(identity)
    focusAfter.current = { target: opener === 'thumb' ? 'preview-thumb' : 'preview-toggle' }
  }

  // Hiding the panel closes its preview, before the hidden region could play on.
  useLayoutEffect(() => {
    if (!open) {
      previews.hide(identity)
    }
  }, [open, previews, identity])

  // Focus once the edit is on screen (a dropped cut's node is gone, a refusal's words
  // are in place): a layout effect, so no frame paints with focus on <body>.
  useLayoutEffect(() => {
    const request = focusAfter.current
    if (request === null) {
      return
    }
    focusAfter.current = null
    let target: HTMLElement | null
    if (request.target === 'preview-toggle') {
      target = toggleRef.current
      scrollAfter.current = target
    } else if (request.target === 'preview-thumb') {
      // The row's own thumbnail: a row remounted by a move has its own.
      target =
        rootRef.current
          ?.closest('.clip-item')
          ?.querySelector<HTMLElement>(':scope > .clip-thumb-watch') ?? null
      scrollAfter.current = target
    } else if (!('key' in request)) {
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
      ref={rootRef}
      className="clip-cuts"
      id={id}
      role="group"
      aria-label={`Cuts of ${name}`}
      hidden={!open}
    >
      <button
        ref={toggleRef}
        type="button"
        className="btn btn-secondary btn-compact preview-toggle"
        aria-expanded={previewOpen}
        aria-controls={previewOpen && open ? previewId : undefined}
        aria-label={previewOpen && open ? hideName(name) : watchName(name)}
        onClick={() => {
          if (previewOpen) {
            previews.hide(identity)
          } else {
            previews.show(identity, 'toggle')
          }
        }}
      >
        {/* Open, it says what a press does: Hide player. */}
        {previewOpen && open ? HIDE : PLAY}
        {previewOpen && open ? HIDE_PLAYER : WATCH}
      </button>
      {previewOpen && open && (
        <ClipPreview
          id={previewId}
          eventId={eventId}
          clip={clip}
          proxy={proxy}
          name={name}
          cuts={cuts}
          typed={typed}
          locked={locked}
          turn={turn}
          previews={previews}
          onSet={setAt}
          onClose={closePlayer}
          onAnnounce={onAnnounce}
        />
      )}
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
