import { readJson } from './http.ts'
import type { Unanswered } from './http.ts'
import type { components, paths } from './schema'

/**
 * The bundled title-card fonts (`GET /api/v1/fonts`): the only module that knows the route. The
 * list is the registry's own, in its order, with exactly one `default`; the page offers these and
 * no other family. Expected failures are values.
 */

export type Font = components['schemas']['FontOut']

const FONTS_PATH = '/api/v1/fonts' satisfies keyof paths

export type FontsResult =
  | { kind: 'ok'; fonts: Font[] }
  // 200 with a body that is not a list of fonts, or any other status
  | Extract<Unanswered, { kind: 'unpublished' }>
  | Extract<Unanswered, { kind: 'unreachable' }>

function isFont(value: unknown): value is Font {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const font = value as Record<string, unknown>
  return (
    typeof font.family === 'string' &&
    typeof font.display_name === 'string' &&
    typeof font.default === 'boolean'
  )
}

/** Read the list. Rethrows `AbortError`. */
export async function fetchFonts(
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<FontsResult> {
  let response: Response
  try {
    response = await fetcher(FONTS_PATH, { signal })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }
  const body = await readJson(response)
  if (response.status === 200 && Array.isArray(body) && body.every(isFont)) {
    return { kind: 'ok', fonts: body }
  }
  return {
    kind: 'unpublished',
    message: `GET ${FONTS_PATH} answered ${`${response.status} ${response.statusText}`.trimEnd()}`,
  }
}
