import { formatLength, selectedName } from '../cuts/times.ts'
import { chapterHeading } from '../events/labels.ts'
import { extentMs } from './model.ts'
import type { Extent } from './model.ts'

/*
 * What the inspector's Clip tab says of the selected clip (`editor-selection`): its name, where it
 * stands in its chapter and how long it is in the movie, and the words that announce a selection.
 * Pure: no DOM, no React.
 */

/** The parts of a track clip these words need. */
export type ClipLike = {
  identity: string
  name: string
  chapter: number
  kept: Extent
  /** The interior spans the render leaves out, joined, inside the kept extent. */
  drawn: readonly { from: number; to: number }[]
}

export type ClipPlace = {
  name: string
  /** The chapter as the bin names it ("Main" or "Clips" for the unnamed one). */
  chapter: string
  /** 1-based place among the chapter's clips. */
  n: number
  of: number
  /** What the clip takes in the movie: its kept extent less the cuts inside it. */
  lengthMs: number
}

/** Where the clip `identity` stands, or null when the track has no such clip. */
export function clipPlace(
  clips: readonly ClipLike[],
  identity: string,
  chapterNames: readonly string[],
): ClipPlace | null {
  const clip = clips.find((c) => c.identity === identity)
  if (clip === undefined) {
    return null
  }
  const mates = clips.filter((c) => c.chapter === clip.chapter)
  const named = chapterNames.some((name) => name !== '')
  return {
    name: clip.name,
    chapter: chapterHeading(chapterNames[clip.chapter] ?? '', named),
    n: mates.findIndex((c) => c.identity === identity) + 1,
    of: mates.length,
    lengthMs: Math.max(0, extentMs(clip.kept) - clip.drawn.reduce((sum, cut) => sum + (cut.to - cut.from), 0)),
  }
}

/** "Kvällen · clip 1 of 2". */
export function placeWords(place: ClipPlace): string {
  return `${place.chapter} · clip ${place.n} of ${place.of}`
}

/** "12 s in the movie". */
export function lengthWords(place: ClipPlace): string {
  return `${formatLength(place.lengthMs / 1000)} in the movie`
}

/** The polite status when a clip is selected. */
export function clipSelectedWords(place: ClipPlace): string {
  return `${place.name} selected, ${placeWords(place)}`
}

/** The polite status when a cut (the `n`th of the clip's) is selected. */
export function cutSelectedWords(n: number, name: string): string {
  return `${selectedName(n, name)} selected`
}
