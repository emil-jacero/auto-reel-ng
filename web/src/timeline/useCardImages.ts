import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'

import { previewCard } from '../api/titleCard.ts'
import type { PreviewRequest } from '../edit/card/model.ts'
import { createCardImages } from './cardImages.ts'
import type { CardImage, CardImages, CardJob } from './cardImages.ts'
import { drawnOf } from './cardRequests.ts'

/*
 * The Timeline's card images as a hook over `createCardImages`: made when the Timeline opens,
 * asked for one at a time, let go (every URL revoked, nothing in flight) when it closes.
 */

export type CardPictures = {
  /** The chapter's image state, or null when it is not listed or not asked for yet. */
  get(chapter: string): CardImage | null
  failures: readonly { chapter: string; message: string }[]
}

const NONE: CardPictures = { get: () => null, failures: [] }
const NEVER = () => () => undefined

export function useCardImages(
  eventId: string,
  jobs: readonly CardJob<PreviewRequest>[],
): CardPictures {
  const [manager, setManager] = useState<CardImages<PreviewRequest> | null>(null)
  useEffect(() => {
    const made = createCardImages<PreviewRequest>({
      draw: async (request, signal) => drawnOf(await previewCard(eventId, request, signal)),
      setTimer: (run, ms) => window.setTimeout(run, ms),
      clearTimer: (handle) => window.clearTimeout(handle as number),
      makeUrl: (png) => URL.createObjectURL(png),
      revokeUrl: (url) => URL.revokeObjectURL(url),
    })
    setManager(made)
    return () => {
      made.dispose()
      setManager(null)
    }
  }, [eventId])
  useEffect(() => {
    manager?.sync(jobs)
  }, [manager, jobs])
  const version = useSyncExternalStore(
    manager === null ? NEVER : manager.subscribe,
    () => manager?.version() ?? 0,
  )
  return useMemo(
    () =>
      manager === null
        ? NONE
        : { get: (chapter) => manager.get(chapter), failures: manager.failures() },
    // `version` changes whenever an image, a state or a failure does.
    [manager, version],
  )
}
