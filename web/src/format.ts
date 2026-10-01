/*
 * How the client writes an instant: one format on every screen, for when a list
 * or an event was read, when a clip was last modified and when a job was queued,
 * started or ended. Event dates are calendar dates, not instants: they stay
 * `YYYY-MM-DD`, as the folders write them, and never come through here.
 *
 * No imports, so it runs under `node --experimental-strip-types` as it is.
 */

const THIS_YEAR = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const OTHER_YEAR = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

/**
 * An instant, written the one way the client writes times: short month and day,
 * hour and minute, the year only when it is not the current one, never seconds,
 * locale-aware. A value that does not parse is returned as given, never as a
 * made-up time. Callers keep the exact instant in `<time dateTime>`.
 */
export function formatInstant(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }
  return (date.getFullYear() === new Date().getFullYear() ? THIS_YEAR : OTHER_YEAR).format(date)
}
