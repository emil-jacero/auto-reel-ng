/*
 * Pure parsers for the two media headers the client reads. No imports, so an ad
 * hoc check runs them under `node --experimental-strip-types` as they are.
 *
 * They accept exactly the forms the service's media routes write (Starlette's
 * `FileResponse`) and nothing else: an unknown form is an absent fact, never a
 * guessed one.
 */

const CONTENT_RANGE = /^bytes (?:\d+-\d+|\*)\/(\d+)$/

/** `bytes 0-0/1234` or `bytes *\/1234` → 1234; null for anything else. */
export function contentRangeSize(value: string | null): number | null {
  const match = value === null ? null : CONTENT_RANGE.exec(value)
  return match === null ? null : Number(match[1])
}

const DISPOSITION_ENCODED = /^inline; filename\*=utf-8''(.+)$/
const DISPOSITION_PLAIN = /^inline; filename="(.+)"$/

/**
 * `inline; filename*=utf-8''<pct>` → the decoded name, `inline; filename="<name>"`
 * → the name; null otherwise, a malformed percent-escape included.
 */
export function dispositionName(value: string | null): string | null {
  if (value === null) {
    return null
  }
  const encoded = DISPOSITION_ENCODED.exec(value)
  if (encoded !== null) {
    try {
      return decodeURIComponent(encoded[1])
    } catch {
      return null
    }
  }
  return DISPOSITION_PLAIN.exec(value)?.[1] ?? null
}
