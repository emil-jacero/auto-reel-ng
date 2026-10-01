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

/**
 * The ids of every event that would read the same as another in the list: the
 * same date, the same title (or, untitled, the same folder name in its place)
 * and the same location, compared without regard to letter case and after NFC
 * normalization, so two spellings of "å" that look alike compare alike. Such
 * rows also show their folder's path, the one fact no two events share.
 */
export function lookAlikes(events: readonly EventSummary[]): ReadonlySet<string> {
  const byKey = new Map<string, string[]>()
  for (const event of events) {
    // The folder name is the id's last segment (`common.tsx` is not imported here).
    const shownTitle = event.title ?? event.event_id.split('/').pop() ?? event.event_id
    const key = [
      event.date ?? '',
      shownTitle.normalize('NFC').toLowerCase(),
      (event.location ?? '').normalize('NFC').toLowerCase(),
    ].join('\u0000')
    const ids = byKey.get(key)
    if (ids === undefined) {
      byKey.set(key, [event.event_id])
    } else {
      ids.push(event.event_id)
    }
  }
  const alike = new Set<string>()
  for (const ids of byKey.values()) {
    if (ids.length > 1) {
      for (const id of ids) {
        alike.add(id)
      }
    }
  }
  return alike
}
