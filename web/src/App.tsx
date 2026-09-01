import { useEffect, useState } from 'react'

import type { paths } from './api/schema'

/**
 * The wiring check, not a screen.
 *
 * It exists to exercise four things at once: the dev server's `/api` proxy, a
 * same-origin fetch addressed by path alone, a response type generated from the
 * service's own OpenAPI schema, and the static mount that serves this bundle in
 * production. The event-list slice replaces this file outright.
 */

// Derived from the committed schema — never hand-written. Removing a field the
// client reads becomes a `tsc --noEmit` error at the line that reads it.
type EventsListResponse =
  paths['/api/v1/events']['get']['responses'][200]['content']['application/json']

type State =
  | { status: 'loading' }
  | { status: 'ready'; events: EventsListResponse }
  | { status: 'failed'; message: string }

async function fetchEvents(signal: AbortSignal): Promise<EventsListResponse> {
  const response = await fetch('/api/v1/events', { signal })
  if (!response.ok) {
    throw new Error(`GET /api/v1/events returned ${response.status}`)
  }
  return (await response.json()) as EventsListResponse
}

export function App() {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchEvents(controller.signal)
      .then((events) => setState({ status: 'ready', events }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setState({ status: 'failed', message: String(error) })
      })
    return () => controller.abort()
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem' }}>
      <h1>auto-reel-ng</h1>
      {state.status === 'loading' && <p>Loading events…</p>}
      {state.status === 'failed' && <p>Could not reach the API: {state.message}</p>}
      {state.status === 'ready' && (
        <p>
          The API reports <strong>{state.events.length}</strong>{' '}
          {state.events.length === 1 ? 'event' : 'events'}.
        </p>
      )}
    </main>
  )
}
