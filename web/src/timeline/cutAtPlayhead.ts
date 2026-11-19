import { addedWords, checkCut, keptCuts, refusalWords } from '../cuts/times.ts'
import type { ListedCut } from '../cuts/times.ts'
import type { EditBinding } from './editing.ts'
import type { TrackClip } from './layout.ts'
import type { Playhead } from './playhead.ts'

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

/** What `addCutAtPlayhead` reads: the clip, the track's clips, the editor and the playhead's store. */
export type CutAtPlayheadDeps = {
  clip: TrackClip
  clips: readonly TrackClip[]
  editing: Pick<EditBinding, 'listed' | 'onAdd' | 'announce'>
  playhead: Pick<Playhead, 'get'>
}

/** The cut "+ Cut at playhead" would make in `clip` now, or why it cannot. */
export function cutAtClipPlayhead({ clip, clips, editing, playhead }: CutAtPlayheadDeps) {
  const at = playhead.get()
  const inClip = at.card == null && clips[at.clip]?.identity === clip.identity
  return cutAtPlayhead(
    editing.listed(clip.identity),
    inClip ? at.ms : null,
    clip.name,
    clip.facts.durationMs / 1000,
  )
}

/**
 * The one edit behind the Clip tab's "+ Cut at playhead" and the clip menu's Cut at playhead
 * (`clip-context-menu`, D2): the cut is added to the draft and announced, or refused in words
 * (announced as well) and nothing changes. Returns the refusal, or null when the cut was made.
 */
export function addCutAtPlayhead(deps: CutAtPlayheadDeps): string | null {
  const { clip, editing } = deps
  const made = cutAtClipPlayhead(deps)
  if (!made.ok) {
    editing.announce(made.words)
    return made.words
  }
  const listed = editing.listed(clip.identity)
  editing.onAdd(clip.identity, made.span)
  editing.announce(addedWords(made.span, clip.name, [...keptCuts(listed), made.span]))
  return null
}
