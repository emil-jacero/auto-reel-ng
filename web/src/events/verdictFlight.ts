/**
 * The bookkeeping of Edit mode's verdict reads: at most one in flight, and a request that
 * comes meanwhile leads to exactly one more after it. Leaving Edit mode (or unmounting)
 * aborts the one on its way and forgets the request, so an answer that comes late is
 * dropped and the next request starts fresh. Pure of React, so `npm test` covers it.
 */
export interface VerdictFlight {
  /** A new controller to read with, or null when a read is in flight (one more will follow it). */
  request: () => AbortController | null
  /** A read ended; true when a request waited and the caller should read again. */
  finish: (controller: AbortController) => boolean
  /** Abort the read on its way and drop any request waiting. */
  abort: () => void
}

export function createVerdictFlight(): VerdictFlight {
  let current: AbortController | null = null
  let pending = false
  return {
    request: () => {
      if (current !== null) {
        pending = true
        return null
      }
      current = new AbortController()
      return current
    },
    finish: (controller) => {
      if (controller.signal.aborted || current !== controller) {
        return false
      }
      current = null
      const again = pending
      pending = false
      return again
    },
    abort: () => {
      current?.abort()
      current = null
      pending = false
    },
  }
}
