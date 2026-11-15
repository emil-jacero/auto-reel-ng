import { checkCut, refusalWords } from '../cuts/times.ts'
import type { ListedCut } from '../cuts/times.ts'

/*
 * "+ Cut at playhead" in the inspector's Clip tab (`editor-selection`): a new cut that starts at
 * the playhead's time in the clip and runs a second, or less where the clip ends or another cut
 * begins. It is checked as a typed cut is (`checkCut`), so what the Cuts panel's Add refuses this
 * refuses, in the same words. Pure: no DOM, no React.
 */

/** How long the new cut runs, at most. */
export const CUT_AT_PLAYHEAD_SECONDS = 1

export function cutAtPlayhead(
  listed: readonly ListedCut[],
  /** The playhead's time in this clip (ms), or null when it is not in this clip. */
  playheadMs: number | null,
  name: string,
  /** The clip's length in seconds. */
  length: number,
): { ok: true; span: { in: number; out: number } } | { ok: false; words: string } {
  if (playheadMs === null) {
    return { ok: false, words: `Move the playhead into ${name} to cut there.` }
  }
  const start = Math.round(playheadMs) / 1000
  const nextStart = listed
    .filter((cut) => cut.removed !== true && cut.in > start)
    .reduce((least, cut) => Math.min(least, cut.in), Infinity)
  const end = Math.round(Math.min(start + CUT_AT_PLAYHEAD_SECONDS, length, nextStart) * 1000) / 1000
  const checked = checkCut(listed, start.toFixed(3), end.toFixed(3), length)
  return checked.ok
    ? { ok: true, span: { in: checked.in, out: checked.out } }
    : { ok: false, words: refusalWords(checked.refusal) }
}
