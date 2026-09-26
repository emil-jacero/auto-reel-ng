import type { EventSummary } from '../api/events'

export interface YearGroup {
  /** The year of the events' dates, or `null` for the undated group. */
  year: string | null
  events: EventSummary[]
}

/** Freshness comes from the verdict alone — a finished job is not freshness. */
export function needsRender(event: EventSummary): boolean {
  return event.staleness.stale
}

function byEventId(a: EventSummary, b: EventSummary): number {
  return a.event_id < b.event_id ? -1 : a.event_id > b.event_id ? 1 : 0
}

/**
 * Group by the year of `date` (the year D-9 files the movie under), newest year
 * first; within a year, newest date first, then `event_id`. Undated events form
 * a trailing group ordered by `event_id`. `date` is ISO `YYYY-MM-DD`, so string
 * order is date order and no timezone is involved.
 */
export function groupByYear(events: readonly EventSummary[]): YearGroup[] {
  const dated = new Map<string, EventSummary[]>()
  const undated: EventSummary[] = []
  for (const event of events) {
    if (event.date == null) {
      undated.push(event)
      continue
    }
    const year = event.date.slice(0, 4)
    const group = dated.get(year)
    if (group === undefined) {
      dated.set(year, [event])
    } else {
      group.push(event)
    }
  }

  const groups: YearGroup[] = [...dated.keys()]
    .sort()
    .reverse()
    .map((year) => ({
      year,
      events: (dated.get(year) ?? []).sort((a, b) => {
        const byDate = (b.date ?? '').localeCompare(a.date ?? '')
        return byDate !== 0 ? byDate : byEventId(a, b)
      }),
    }))
  if (undated.length > 0) {
    groups.push({ year: null, events: undated.sort(byEventId) })
  }
  return groups
}
