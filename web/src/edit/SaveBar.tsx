import { useId } from 'react'
import type { RefObject } from 'react'

import type { EventFailure } from '../api/events'
import { FAILURE_LABEL, UNANSWERED_CAUSE } from '../events/labels'
import { FAILURE_LOOK } from '../events/tones'
import { LIST_HREF } from '../route'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'

/*
 * The save bar: sticky at the bottom of the viewport while Edit mode holds
 * unsaved changes. It says what changed, offers Reset and Save, and shows the
 * last save's failure above them with that failure's own choices (Retry,
 * Reload latest, Overwrite with mine).
 *
 * Every control here follows the busy-control rule: one that cannot act now is
 * aria-disabled and ignores presses, never `disabled`, which would drop focus
 * to <body>; the one that started the save in flight is also aria-busy. So
 * focus stays where the operator left it, through the save and its answer.
 */

/** The control that started the save in flight. */
export type Pressed = 'save' | 'retry' | 'overwrite'
/** What a Retry repeats: a plain save, or the overwrite (re-read the tag, then save). */
export type Operation = 'save' | 'overwrite'

export type SaveProblem =
  | { kind: 'conflict' }
  | { kind: 'refused'; detail: string }
  | { kind: 'gone'; detail: string }
  | { kind: 'disk'; title: string; failure: EventFailure | null; detail: string; retry: Operation }
  | { kind: 'unreachable' | 'unpublished'; detail: string; retry: Operation }
  // An error in this page itself, not an answer of the service (EventEditor's catch).
  | { kind: 'page'; detail: string; retry: Operation }

const PAGE_ERROR_TITLE = 'The save stopped on an error in this page.'

/** A control's state: busy if it started the save in flight, else unavailable while one runs. */
function controlState(pressed: Pressed | null, self: Pressed | null, blocked = false) {
  if (pressed !== null && pressed === self) {
    return { 'aria-disabled': true, 'aria-busy': true } as const
  }
  return pressed !== null || blocked ? ({ 'aria-disabled': true } as const) : {}
}

export function SaveBar({
  barRef,
  alertRef,
  edited,
  problem,
  pressed,
  summary,
  dateIncomplete,
  onReset,
  onSave,
  onRetry,
  onReload,
  onOverwrite,
}: {
  barRef: RefObject<HTMLDivElement | null>
  /** The alert, focused by the editor when the control pressed went with the last one. */
  alertRef: RefObject<HTMLDivElement | null>
  /** Whether there is anything to save. */
  edited: boolean
  problem: SaveProblem | null
  pressed: Pressed | null
  summary: string
  dateIncomplete: boolean
  onReset: () => void
  onSave: () => void
  onRetry: (operation: Operation) => void
  onReload: () => void
  onOverwrite: () => void
}) {
  const alertId = useId()
  const summaryId = useId()
  const locked = pressed !== null
  // Nothing to send: no edits, or a date typed in part (it would be sent as unset).
  const unsendable = !edited || dateIncomplete
  // Save also waits while the failure's own choices are the way on.
  const saveBlocked = unsendable || problem?.kind === 'conflict' || problem?.kind === 'gone'
  // One primary action at a time: the failure's way on while it holds Save back, else Save.
  const savePrimary = problem?.kind !== 'conflict' && problem?.kind !== 'gone'
  const describedBy = dateIncomplete ? summaryId : problem !== null ? alertId : undefined
  // With no edits the bar stays only for a vanished event's alert: it says so, not "unsaved".
  const unsaved = edited || dateIncomplete
  const title = locked ? 'Saving…' : unsaved ? 'Unsaved changes' : 'This event no longer exists'
  return (
    <div
      ref={barRef}
      className="save-bar"
      role="region"
      aria-label={unsaved ? 'Unsaved changes' : title}
    >
      <div className="save-bar-card">
        {/* Keyed by kind: another kind of failure is a new alert, never reused buttons. */}
        {problem !== null && (
          <div
            key={problem.kind}
            ref={alertRef}
            id={alertId}
            className="save-bar-alert"
            tabIndex={-1}
          >
            <SaveProblemAlert
              problem={problem}
              pressed={pressed}
              blocked={unsendable}
              describedBy={describedBy}
              onReload={onReload}
              onOverwrite={onOverwrite}
              onRetry={onRetry}
            />
          </div>
        )}
        <div className="save-bar-row">
          <div className="save-bar-text">
            <p className="save-bar-title">
              {unsaved && <span className="save-bar-dot" aria-hidden="true" />}
              {title}
            </p>
            {summary !== '' && (
              <p id={summaryId} className="save-bar-summary">
                {summary}
              </p>
            )}
          </div>
          <div className="save-bar-actions">
            <button
              type="button"
              className="btn btn-secondary"
              {...controlState(pressed, null)}
              onClick={() => {
                if (!locked) {
                  onReset()
                }
              }}
            >
              <Icon name="rotate-ccw" />
              Reset
            </button>
            <button
              type="button"
              className={savePrimary ? 'btn btn-primary' : 'btn btn-secondary'}
              {...controlState(pressed, 'save', saveBlocked)}
              aria-describedby={describedBy}
              onClick={() => {
                if (!locked && !saveBlocked) {
                  onSave()
                }
              }}
            >
              <Icon name="check" />
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SaveProblemAlert({
  problem,
  pressed,
  blocked,
  describedBy,
  onReload,
  onOverwrite,
  onRetry,
}: {
  problem: SaveProblem
  pressed: Pressed | null
  /** Nothing to send (no edits, or a date typed in part): Retry and Overwrite wait too. */
  blocked: boolean
  describedBy: string | undefined
  onReload: () => void
  onOverwrite: () => void
  onRetry: (operation: Operation) => void
}) {
  const locked = pressed !== null
  switch (problem.kind) {
    case 'conflict':
      return (
        <Alert
          tone="warn"
          title="This event was changed elsewhere since you started editing."
          action={
            <>
              <button
                type="button"
                className="btn btn-primary"
                {...controlState(pressed, null)}
                onClick={() => {
                  if (!locked) {
                    onReload()
                  }
                }}
              >
                Reload latest (discard my changes)
              </button>
              <button
                type="button"
                className="btn btn-danger"
                {...controlState(pressed, 'overwrite', blocked)}
                aria-describedby={blocked ? describedBy : undefined}
                onClick={() => {
                  if (!locked && !blocked) {
                    onOverwrite()
                  }
                }}
              >
                Overwrite with mine
              </button>
              <span className="alert-note">Your edits are kept.</span>
            </>
          }
        />
      )
    case 'refused':
      return <Alert tone="err" title="The change was refused." detail={problem.detail} />
    case 'gone':
      return (
        <Alert
          tone="err"
          title="This event no longer exists."
          detail={problem.detail}
          action={
            <a className="btn btn-primary" href={LIST_HREF}>
              <Icon name="chevron-left" />
              Back to the event list
            </a>
          }
        />
      )
    case 'disk':
    case 'unreachable':
    case 'unpublished':
    case 'page':
      return (
        <Alert
          tone="err"
          title={
            problem.kind === 'page' ? (
              PAGE_ERROR_TITLE
            ) : problem.kind !== 'disk' ? (
              UNANSWERED_CAUSE[problem.kind]
            ) : (
              <>
                {problem.title}{' '}
                {problem.failure !== null && (
                  <Pill
                    tone={FAILURE_LOOK[problem.failure].tone}
                    icon={FAILURE_LOOK[problem.failure].icon}
                  >
                    {FAILURE_LABEL[problem.failure]}
                  </Pill>
                )}
              </>
            )
          }
          // No answer: the title says it all, and the browser's error text ("TypeError: Failed
          // to fetch") would add nothing but a line.
          detail={problem.kind === 'unreachable' ? null : problem.detail}
          action={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                {...controlState(pressed, 'retry', blocked)}
                aria-describedby={blocked ? describedBy : undefined}
                onClick={() => {
                  if (!locked && !blocked) {
                    onRetry(problem.retry)
                  }
                }}
              >
                <Icon name="refresh" />
                Retry
              </button>
              <span className="alert-note">Your edits are kept.</span>
            </>
          }
        />
      )
  }
}
