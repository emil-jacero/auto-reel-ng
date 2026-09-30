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
import { NOT_QUEUED, SCAN_FAILED } from './labels'
import { isActive, load, merge, track } from './store'
import { useEventJob } from './useJob'

/** A row's enqueue answer, told by toast: the row has no room for an alert. */
function tellRowAnswer(eventId: string, result: EnqueueResult): void {
  const name = `“${folderName(eventId)}”`
  const open = { action: { label: 'Open', href: eventHref(eventId) } }
  switch (result.kind) {
    case 'enqueued':
      track(result.job.id)
      merge(result.job)
      break
    case 'active':
      // Someone already started it: the row follows that job.
      track(result.jobId)
      load(result.jobId)
      break
    case 'fresh':
      // The list never forces a render; the event's page offers Render anyway.
      toast.info(`${name} is already up to date`, open)
      markEventsChanged()
      break
    case 'collision': {
      const others = result.claimedBy.map((id) => `“${folderName(id)}”`).join(', ')
      toast.error(`${name} shares its movie file with ${others}`, open)
      break
    }
    case 'problem':
      if (result.problem.status === 404) {
        toast.error(`${name} no longer exists.`)
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
function RowRender({ eventId, buttonRef }: { eventId: string; buttonRef: Ref<HTMLButtonElement> }) {
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
          tellRowAnswer(eventId, result)
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
 * Render while the event needs one and has no queued or running job. It renders
 * the `<td>` itself, so the narrow-width "Last job" label follows the job
 * actually shown — including one the connection reported after the read — and
 * a row with no job has none. It never fetches a failed job's error text.
 */
export function LiveJobCell({
  eventId,
  staleness,
  latestJob,
  role,
  className,
}: {
  eventId: string
  staleness: Staleness
  latestJob: JobSummary | null | undefined
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
        {staleness.stale && !active && <RowRender eventId={eventId} buttonRef={watchRemoval} />}
      </span>
    </td>
  )
}
