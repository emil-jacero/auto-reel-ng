import { createContext, useCallback, useContext, useMemo, useState } from 'react'

/*
 * Whether previews are unavailable for the whole page: a count of the thumbnails now
 * shown as failed whose cause is the service's, not a clip's (`api/thumbnail.ts`).
 *
 * The page holds a map of address -> cause, which a failed `ClipThumb` fills once it has
 * read why it failed and empties when it leaves the page or changes address. Counting
 * what is mounted makes the count right without a reset rule: a Refresh drops the rows
 * and so the failures, Edit mode's rows report the same addresses again (keyed by address,
 * never counted twice), and a fixed service plus Refresh clears it.
 */

/** Failures with the same cause that make the page say previews are unavailable. */
export const THUMB_NOTE_AT = 3

export type ThumbHealth = {
  /** The thumbnail at `src` failed because of `key` (the service's `failure`, or `none`). */
  report: (src: string, key: string) => void
  /** The thumbnail at `src` is no longer shown as failed. */
  clear: (src: string) => void
}

/** Whether at least `at` of the failures share one cause. */
export function isUnavailable(failures: Iterable<string>, at = THUMB_NOTE_AT): boolean {
  const counts = new Map<string, number>()
  for (const key of failures) {
    const count = (counts.get(key) ?? 0) + 1
    if (count >= at) {
      return true
    }
    counts.set(key, count)
  }
  return false
}

const NOTHING: ThumbHealth = { report: () => undefined, clear: () => undefined }

/** Where a `ClipThumb` reports; a thumbnail outside a provider reports to nothing. */
export const ThumbHealthContext = createContext<ThumbHealth>(NOTHING)

/** For a thumbnail: where to report that its preview failed for the service's reason. */
export function useThumbReporter(): ThumbHealth {
  return useContext(ThumbHealthContext)
}

/** For the page: the context value to provide, and whether to say previews are unavailable. */
export function useThumbHealth(): { health: ThumbHealth; unavailable: boolean } {
  const [failures, setFailures] = useState<ReadonlyMap<string, string>>(new Map())
  const report = useCallback((src: string, key: string) => {
    setFailures((was) => {
      if (was.get(src) === key) {
        return was
      }
      return new Map(was).set(src, key)
    })
  }, [])
  const clear = useCallback((src: string) => {
    setFailures((was) => {
      if (!was.has(src)) {
        return was
      }
      const next = new Map(was)
      next.delete(src)
      return next
    })
  }, [])
  const health = useMemo(() => ({ report, clear }), [report, clear])
  return { health, unavailable: isUnavailable(failures.values()) }
}
