import type { AnalyzeAllResult } from '../api/analysis'

/*
 * Analyze all's answer in words (`analysis-web-controls`): the event list's result line and
 * what its status region says once. Pure, so `npm test` holds the wording.
 */

export const NOTHING_TO_ANALYZE = 'Nothing to analyze: every event is analyzed or already queued.'

function events(count: number): string {
  return count === 1 ? '1 event' : `${count} events`
}

/**
 * `Queued 12 events. 1 already queued. 2 could not be read.`: the counts the service reported,
 * zero ones left out; nothing queued and every event read is `NOTHING_TO_ANALYZE`.
 */
export function analyzeAllWords(result: AnalyzeAllResult): string {
  const unreadable = result.unreadable.length
  if (result.queued === 0 && unreadable === 0) {
    return NOTHING_TO_ANALYZE
  }
  const parts = [result.queued === 0 ? 'Queued no events.' : `Queued ${events(result.queued)}.`]
  if (result.active > 0) {
    parts.push(`${result.active} already queued.`)
  }
  if (unreadable > 0) {
    parts.push(`${unreadable} could not be read.`)
  }
  return parts.join(' ')
}
