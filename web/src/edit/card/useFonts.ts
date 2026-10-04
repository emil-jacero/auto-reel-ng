import { useCallback, useEffect, useState } from 'react'

import { fetchFonts } from '../../api/fonts.ts'
import type { Font, FontsResult } from '../../api/fonts.ts'

/*
 * The bundled font list for the inspector: read once per page load, from `GET /api/v1/fonts`,
 * and kept for the next card. A failed read is not kept, so Try again asks again.
 */

let cached: Promise<FontsResult> | null = null

function load(): Promise<FontsResult> {
  if (cached === null) {
    const asked = fetchFonts(new AbortController().signal).catch(
      (error: unknown): FontsResult => ({ kind: 'unreachable', message: String(error) }),
    )
    cached = asked
    void asked.then((result) => {
      if (result.kind !== 'ok' && cached === asked) {
        cached = null
      }
    })
  }
  return cached
}

export type FontsState =
  | { status: 'loading' }
  | { status: 'ok'; fonts: readonly Font[] }
  | { status: 'failed'; message: string }

export function useFonts(): { state: FontsState; retry: () => void } {
  const [state, setState] = useState<FontsState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let live = true
    setState({ status: 'loading' })
    void load().then((result) => {
      if (live) {
        setState(
          result.kind === 'ok'
            ? { status: 'ok', fonts: result.fonts }
            : { status: 'failed', message: result.message },
        )
      }
    })
    return () => {
      live = false
    }
  }, [attempt])
  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, retry }
}
