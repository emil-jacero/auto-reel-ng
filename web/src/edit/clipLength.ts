import { formatTime, keptCuts } from '../cuts/times.ts'
import type { ListedCut } from '../cuts/times.ts'
import { playedMs } from '../timeline/edgeTrim.ts'

/*
 * The length a clip plays, as the workspace's clip bin shows it in a compact row
 * (`ClipOrderList` `compact`, editor-workspace-layout D3).
 */

/**
 * How long a clip plays: its duration (seconds) less what its kept cuts cover, once, written as
 * the Timeline writes a length (`0:06.02`); an em dash when the duration is unknown or not a
 * length (a missing clip).
 */
export function lengthWords(duration: number | null | undefined, cuts: readonly ListedCut[]): string {
  if (duration == null || !Number.isFinite(duration) || duration <= 0) {
    return '—'
  }
  return formatTime(playedMs(keptCuts(cuts), Math.round(duration * 1000)) / 1000)
}
