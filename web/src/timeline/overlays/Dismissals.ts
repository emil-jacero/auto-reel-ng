import { useCallback, useMemo, useState } from 'react'

import type { Analysis } from '../../api/analysis'
import { dropGone } from './suggestions'

/*
 * The suggestions dismissed during this page visit. It lives in the event page
 * (`events/EventDetail.tsx`), above Edit mode, because the Timeline section is mounted
 * anew by a Refresh, a Save and every re-entry into Edit mode. It
 * is not an edit: nothing is written, nothing is dirty, and a reload forgets it. The end of
 * the event's analysis job, seen by this page, forgets it too (`useEventAnalysis`'s
 * `onAnalyzed`): Re-analyze brings the dismissed suggestions back, as its help says.
 */

export type Dismissals = {
  held: ReadonlySet<string>
  dismiss(id: string): void
  restore(id: string): void
  /** Forget the dismissals a new read of the analysis no longer lists. */
  keep(segments: Analysis['segments']): void
  /** Forget every dismissal: an analysis this page saw end found the suggestions again. */
  clear(): void
}

export function useDismissals(): Dismissals {
  const [held, setHeld] = useState<ReadonlySet<string>>(new Set())
  const dismiss = useCallback(
    (id: string) => setHeld((was) => (was.has(id) ? was : new Set(was).add(id))),
    [],
  )
  const restore = useCallback(
    (id: string) =>
      setHeld((was) => {
        if (!was.has(id)) {
          return was
        }
        const next = new Set(was)
        next.delete(id)
        return next
      }),
    [],
  )
  const keep = useCallback(
    (segments: Analysis['segments']) => setHeld((was) => dropGone(was, segments)),
    [],
  )
  const clear = useCallback(() => setHeld((was) => (was.size === 0 ? was : new Set())), [])
  return useMemo(
    () => ({ held, dismiss, restore, keep, clear }),
    [held, dismiss, restore, keep, clear],
  )
}
