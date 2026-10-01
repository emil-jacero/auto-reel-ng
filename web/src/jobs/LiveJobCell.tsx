import { useCallback, useEffect, useRef, useState } from 'react'
import type { Ref } from 'react'

import type { JobSummary, Staleness } from '../api/events'
import { enqueueJob } from '../api/jobs'
import type { EnqueueResult } from '../api/jobs'
import { markEventsChanged } from '../events/changes'
import { UNREACHABLE_CAUSE, folderName } from '../events/common'
import { eventHref } from '../route'
import { Icon } from '../ui/Icon'
import { toast } from '../ui/toast'
import { JobProgress } from './JobProgress'
import { announce } from './announce'
import { NOT_QUEUED, SCAN_FAILED, eventName } from './labels'
import { isActive, load, merge, track } from './store'
import { useEventJob } from './useJob'

/**
 * A row's enqueue answer. Every answer is told; the row's later states stay quiet.
 * The operator's own Render (queued, or already queued or running) is said to
 * assistive technology only (`announce`): the row shows that job at once, and a
 * toast would cover the Render controls of the rows below it. Every other answer
 * needs the operator's attention and raises a toast: the row has no room for an
 * alert. `name` is the event's title and date (`eventName`); a collision names
 * folders instead, since the events it names share their title and date.
 */
function tellRowAnswer(eventId: string, name: string, result: EnqueueResult): void {
  const open = { action: { label: 'Open', href: eventHref(eventId) } }
  switch (result.kind) {
    case 'enqueued':
      announce(`Render queued: ${name}`)
      track(result.job.id, name)
      merge(result.job)
      break
    case 'active':
      // Someone already started it: the row follows that job.
      announce(`Render already queued or running: ${name}`)
      track(result.jobId, name)
      load(result.jobId)
      break
    case 'fresh':
      // The list never forces a render; the event's page offers Render anyway.
      toast.info(`Already up to date: ${name}`, open)
      markEventsChanged()
      break
    case 'collision': {
      const others = result.claimedBy.map((id) => `“${folderName(id)}”`).join(', ')
      toast.error(`“${folderName(eventId)}” shares its movie file with ${others}`, open)
      break
    }
    case 'problem':
      if (result.problem.status === 404) {
        toast.error(`No longer exists: ${name}`)
        markEventsChanged()
      } else {
        toast.error(`${name}: ${SCAN_FAILED} ${result.problem.detail}`)
      }
      break
    case 'unreachable':
      toast.error(`${name}: ${NOT_QUEUED} ${UNREACHABLE_CAUSE} (${result.message})`)
      break
    case 'unpublished':
      toast.error(`${name}: ${NOT_QUEUED} ${result.message}`)
      break
  }
}

/** The compact Render of one row, named for its event so a list of them is told apart. */
function RowRender({
  eventId,
  name,
  buttonRef,
}: {
  eventId: string
  /** How a toast names the event (`eventName`); the control keeps its folder name. */
  name: string
  buttonRef: Ref<HTMLButtonElement>
}) {
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  return (
    <button
      type="button"
      className="btn btn-secondary btn-compact"
      ref={buttonRef}
      aria-label={`Render ${folderName(eventId)}`}
      aria-disabled={busy || undefined}
      aria-busy={busy || undefined}
      onClick={() => {
        if (inFlight.current) {
          return
        }
        inFlight.current = true
        setBusy(true)
        void enqueueJob(eventId, false).then((result) => {
          inFlight.current = false
          setBusy(false)
          tellRowAnswer(eventId, name, result)
        })
      }}
    >
      <Icon name="play" />
      Render
    </button>
  )
}

/**
 * A list row's job cell: the event's job, live (`useEventJob`), and a compact
 * Render while the event needs one and has no queued or running job — or, when
 * `blockedReason` says why it cannot render, that reason in its place. It
 * renders the `<td>` itself, so the narrow-width "Last job" label follows the
 * job actually shown — including one the connection reported after the read —
 * and a row with no job has none. It never fetches a failed job's error text.
 */
export function LiveJobCell({
  eventId,
  title,
  date,
  staleness,
  latestJob,
  blockedReason,
  role,
  className,
}: {
  eventId: string
  /** The event's title and date, as the row shows them: a toast names the event by them. */
  title: string | null | undefined
  date: string | null | undefined
  staleness: Staleness
  latestJob: JobSummary | null | undefined
  /** Why the event cannot render now; the row then shows it instead of Render. */
  blockedReason?: string
  role: 'cell'
  className: string
}) {
  const shown = useEventJob(eventId, latestJob)
  const active = shown !== null && isActive(shown.job.status)
  const cellRef = useRef<HTMLTableCellElement>(null)

  // Render removed while focused (its job now shows here) hands focus to the
  // row's event link, so a keyboard user keeps their place in the list.
  const handOff = useRef(false)
  const watchRemoval = useCallback((node: HTMLButtonElement | null) => {
    if (node === null) {
      return undefined
    }
    return () => {
      if (document.activeElement === node) {
        handOff.current = true
      }
    }
  }, [])
  useEffect(() => {
    if (!handOff.current) {
      return
    }
    handOff.current = false
    const focused = document.activeElement
    if (focused === null || focused === document.body) {
      cellRef.current
        ?.closest('tr')
        ?.querySelector<HTMLElement>('a[href]')
        ?.focus({ preventScroll: true })
    }
  })

  return (
    <td
      ref={cellRef}
      role={role}
      className={className}
      data-label={shown !== null ? 'Last job' : undefined}
    >
      <span className="live-job">
        {shown !== null && <JobProgress shown={shown} />}
        {staleness.stale &&
          !active &&
          (blockedReason === undefined ? (
            <RowRender
              eventId={eventId}
              name={eventName(eventId, title, date)}
              buttonRef={watchRemoval}
            />
          ) : (
            <span className="row-blocked">
              <Icon name="alert-triangle" />
              {blockedReason}
            </span>
          ))}
      </span>
    </td>
  )
}
