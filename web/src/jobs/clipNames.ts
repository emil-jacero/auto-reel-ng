/*
 * Kept apart from `labels.ts`, which reaches the screen's components, so that the
 * runner of `npm test` (no JSX) can load it.
 */

/**
 * The clips a refused enqueue names: every one, or with `limit` the first few and how many
 * more there are ("a.mp4, b.mp4, c.mp4 and 2 more"), for a toast that has little room. One
 * clip over the limit is named, since "and 1 more" is no shorter than its name.
 */
export function missingClipNames(missing: readonly string[], limit = missing.length): string {
  if (missing.length <= limit + 1) {
    return missing.join(', ')
  }
  const more = missing.length - limit
  return `${missing.slice(0, limit).join(', ')} and ${more} more`
}
