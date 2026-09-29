import type { components } from './schema'

/** Response-reading helpers shared by the reads. */

export type Problem = components['schemas']['ProblemOut']

export function isProblem(body: unknown): body is Problem {
  if (typeof body !== 'object' || body === null) {
    return false
  }
  const fields = body as Record<string, unknown>
  return (
    typeof fields.title === 'string' &&
    typeof fields.status === 'number' &&
    typeof fields.detail === 'string'
  )
}

/** The body as JSON, or `undefined` when it is not JSON. Rethrows `AbortError`. */
export async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    return undefined
  }
}
