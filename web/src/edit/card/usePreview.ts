import { useEffect, useRef, useState } from 'react'

import { previewCard } from '../../api/titleCard.ts'
import { answerOf } from './answer.ts'
import type { PreviewRequest } from './model.ts'
import { PreviewController } from './preview.ts'
import type { PreviewView } from './preview.ts'

/*
 * The preview of one card as a hook over `PreviewController`: it owns one controller for the
 * event, shows the request it is given (a new one after the quiet time) and gives the view back.
 * Mount it per card (key it by the card), so one card's image is never shown for another.
 */

const IDLE: PreviewView = { state: 'idle', url: null, message: null, field: null }

export function useCardPreview(eventId: string, request: PreviewRequest | null): PreviewView {
  const [view, setView] = useState<PreviewView>(IDLE)
  const controller = useRef<PreviewController | null>(null)
  const latest = useRef(request)
  latest.current = request
  useEffect(() => {
    const made = new PreviewController({
      draw: async (body, signal) => answerOf(await previewCard(eventId, body, signal)),
      setTimer: (run, ms) => window.setTimeout(run, ms),
      clearTimer: (handle) => window.clearTimeout(handle as number),
      makeUrl: (png) => URL.createObjectURL(png),
      revokeUrl: (url) => URL.revokeObjectURL(url),
    })
    controller.current = made
    const unsubscribe = made.subscribe(() => setView(made.snapshot()))
    made.show(latest.current)
    return () => {
      unsubscribe()
      made.dispose()
      controller.current = null
    }
  }, [eventId])
  const key = request === null ? null : JSON.stringify(request)
  useEffect(() => {
    controller.current?.show(latest.current)
  }, [key])
  return view
}
