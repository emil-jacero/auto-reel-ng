import type { EventDetail } from '../api/event.ts'
import { cardLimits } from './cardLength.ts'
import type { CardRange, Tenths } from './cardLength.ts'
import { ModelError } from './model.ts'
import type { Layout, Ms } from './model.ts'

/*
 * The title cards on the Timeline, as pure rules (D-20, `title-card-blocks`): which chapter
 * draws a card and where it anchors (the render's rule, cuts included), the track map that
 * the black cards cause, the card's words and the one card selection. No DOM, no React, no
 * network, no media read and no frame rate. Clip time stays the one time the playhead, the
 * cuts, the handles and the marks use; only drawing goes through `trackX`.
 *
 * Nothing is guessed (Principle I): a duration that is not a finite number above zero is
 * refused, a background the render does not know is refused, and a card the service could
 * not resolve is not drawn.
 */

/** A card as the event detail resolved it. */
export type CardSpec = {
  /** The chapter's saved name (`""` is the default chapter, the opening). */
  chapter: string
  /** The resolved card, or null with `error` saying why. */
  card: {
    duration: number
    background: string
    title: string
    subtitle: string
    fontFamily: string
  } | null
  error: string | null
}

/** The clips a chapter's cards anchor on: the shown clips in play order. */
export type CardClip = {
  /** Index into the event's chapters. */
  chapter: number
  durationMs: Ms
  /** The cuts as the render joins them, clamped to the clip, in order. */
  spans: readonly { from: Ms; to: Ms }[]
}

export type Background = 'black' | 'video'

/** Whether the render draws title cards, as the service reports it; `invalid` is no answer (`title_cards: null`). */
export type Decorators = 'on' | 'off' | 'invalid'

/** Which layer decided it (`TitleCardsOut.source`). */
export type CardsSource = 'event' | 'project' | 'default'

/** The event detail's `title_cards`: the engine's answer from the event and the project's look. */
export type TitleCardsAnswer = { enabled: boolean; source: CardsSource } | null | undefined

/**
 * Whether the render draws title cards: the service's answer (`title_cards`), which resolves
 * the event's `look.decorators` over the project's the way the render does, so the page cannot
 * disagree with a render. `draft` is Edit mode's Title cards switch while it differs from the
 * answer (true: on). No answer (`title_cards: null`, `look.decorators` not a list) is `invalid`:
 * nothing is guessed from `reel.yaml` (Principle I).
 */
export function cardsEnabled(answer: TitleCardsAnswer, draft: boolean | null = null): Decorators {
  if (answer === null || answer === undefined) {
    return 'invalid'
  }
  return (draft ?? answer.enabled) ? 'on' : 'off'
}

/** Which layer decided: the event's own list once the draft's switch differs, else the answer's. */
export function cardsSource(answer: TitleCardsAnswer, draft: boolean | null = null): CardsSource | null {
  if (answer === null || answer === undefined) {
    return null
  }
  return draft === null || draft === answer.enabled ? answer.source : 'event'
}

/**
 * Each chapter's resolved card from the event detail, in chapter order. A chapter's
 * own `card_error`, else the event-wide `title_card_error`, says why a card is missing.
 */
export function cardSpecs(
  event: Pick<EventDetail, 'chapters' | 'title_card_error'>,
): CardSpec[] {
  return event.chapters.map((chapter) => {
    const { card } = chapter
    return {
      chapter: chapter.name,
      card:
        card == null
          ? null
          : {
              duration: card.duration,
              background: card.background,
              title: card.title,
              subtitle: card.subtitle,
              fontFamily: card.font_family,
            },
      error: card == null ? (chapter.card_error ?? event.title_card_error ?? null) : null,
    }
  })
}

/**
 * `specs` with the draft's card lengths laid over the resolved ones: `seconds` is by the
 * chapter's saved name. The same array back when nothing changes, so memos hold. This is the
 * one path of the drag and the release: the layout is always derived from the specs.
 */
export function withDurations(
  specs: readonly CardSpec[],
  seconds: ReadonlyMap<string, number> | null | undefined,
): readonly CardSpec[] {
  if (seconds === null || seconds === undefined || seconds.size === 0) {
    return specs
  }
  let changed = false
  const next = specs.map((spec) => {
    const value = seconds.get(spec.chapter)
    if (value === undefined || spec.card === null || spec.card.duration === value) {
      return spec
    }
    changed = true
    return { ...spec, card: { ...spec.card, duration: value } }
  })
  return changed ? next : specs
}

/** A card's length in whole milliseconds, or a `ModelError` naming it. */
export function cardDurationMs(seconds: number): Ms {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) {
    throw new ModelError(`card duration must be a finite number above zero, got ${String(seconds)}`)
  }
  const ms = Math.round(seconds * 1000)
  if (ms < 1) {
    throw new ModelError(`card duration must be at least a millisecond, got ${seconds} s`)
  }
  return ms
}

function backgroundOf(value: string): Background {
  if (value === 'black' || value === 'video') {
    return value
  }
  throw new ModelError(`card background must be "black" or "video", got ${JSON.stringify(value)}`)
}

/** One chapter's place in the movie. */
export type Placement =
  | {
      kind: 'anchored' | 'off'
      chapter: number
      /** Index of the anchor clip in the shown clips. */
      clip: number
      /** Where the card starts in the anchor clip: 0, or the end of a cut that starts at zero. */
      atMs: Ms
      background: Background
      durationMs: Ms
      /** The first kept span of the anchor: the footage a video card sits on. */
      keptMs: Ms
      /** The width drawn: a black card's length; a video (or off) card's, held to the footage. */
      widthMs: Ms
      clamped: boolean
    }
  | { kind: 'no-footage'; chapter: number }
  | { kind: 'unresolved'; chapter: number; error: string }
  | { kind: 'unreadable'; chapter: number; error: string }

/** The first kept span of a clip: where it starts and how long it runs, or null when all is cut. */
function firstKept(clip: CardClip): { start: Ms; length: Ms } | null {
  const first = clip.spans[0]
  const start = first !== undefined && first.from <= 0 ? first.to : 0
  if (start >= clip.durationMs) {
    return null
  }
  const next = clip.spans.find((span) => span.from > start)
  return { start, length: (next?.from ?? clip.durationMs) - start }
}

/**
 * Per chapter, whether and where its title card is drawn. A chapter anchors at its first
 * shown clip, or at the next shown clip with footage when every part of the first is cut
 * (as the render moves it); with no footage it has no card. A video card is held to the
 * first kept span, a black card adds its length. `decorators` `off` makes the
 * anchored chapters `off`; `invalid` places nothing.
 */
export function cardPlacements(
  cards: readonly CardSpec[],
  clips: readonly CardClip[],
  decorators: Decorators,
): Placement[] {
  const out: Placement[] = []
  cards.forEach((spec, chapter) => {
    if (spec.card === null) {
      out.push({ kind: 'unresolved', chapter, error: spec.error ?? 'The card was not resolved.' })
      return
    }
    let durationMs: Ms
    let background: Background
    try {
      durationMs = cardDurationMs(spec.card.duration)
      background = backgroundOf(spec.card.background)
    } catch (error) {
      out.push({ kind: 'unreadable', chapter, error: (error as Error).message })
      return
    }
    for (let index = 0; index < clips.length; index += 1) {
      const clip = clips[index]
      if (clip.chapter !== chapter) {
        continue
      }
      const kept = firstKept(clip)
      if (kept === null) {
        continue
      }
      if (decorators === 'invalid') {
        return
      }
      const widthMs = background === 'black' ? durationMs : Math.min(durationMs, kept.length)
      out.push({
        kind: decorators === 'on' ? 'anchored' : 'off',
        chapter,
        clip: index,
        atMs: kept.start,
        background,
        durationMs,
        keptMs: kept.length,
        widthMs,
        clamped: background === 'video' && widthMs < durationMs,
      })
      return
    }
    out.push({ kind: 'no-footage', chapter })
  })
  return out
}

// --- the track map ---------------------------------------------------------------------

export type Gap = {
  chapter: number
  /** The anchor clip's index. */
  clip: number
  /** The clip time the card sits before: the anchor clip's start. */
  atMs: Ms
  lengthMs: Ms
  /** The black cards' lengths before this one. */
  beforeMs: Ms
}

/** Where the black cards are, in clip time, in order. */
export type CardMap = { gaps: readonly Gap[]; totalMs: Ms }

/** The map of the black cards among `placements` (video and off cards add nothing). */
export function cardMap(placements: readonly Placement[], lay: Layout): CardMap {
  const gaps: Gap[] = []
  let totalMs = 0
  for (const place of placements) {
    if (place.kind === 'anchored' && place.background === 'black') {
      gaps.push({
        chapter: place.chapter,
        clip: place.clip,
        atMs: lay.startsMs[place.clip],
        lengthMs: place.widthMs,
        beforeMs: totalMs,
      })
      totalMs += place.widthMs
    }
  }
  return { gaps, totalMs }
}

/** The index of the first gap for which `past(gap)` is true, in a sorted list (log n). */
function firstWhere(gaps: readonly Gap[], past: (gap: Gap) => boolean): number {
  let low = 0
  let high = gaps.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (past(gaps[mid])) {
      high = mid
    } else {
      low = mid + 1
    }
  }
  return low
}

/** The black cards' length at or before clip time `ms` (a card at `ms` comes before it). */
function offsetAt(map: CardMap, ms: Ms): Ms {
  const next = firstWhere(map.gaps, (gap) => gap.atMs > ms)
  return next === 0 ? 0 : map.gaps[next - 1].beforeMs + map.gaps[next - 1].lengthMs
}

/** The track time of a clip time: the lengths of every black card anchored at or before it added. */
export function trackX(map: CardMap, clipMs: Ms): Ms {
  return clipMs + offsetAt(map, clipMs)
}

export type TrackTime =
  | { kind: 'clip'; ms: Ms }
  /** In black card `index` of `chapter`; `afterMs` is the clip time of the footage that follows it. */
  | { kind: 'card'; index: number; chapter: number; afterMs: Ms }

/** The inverse of `trackX`: a clip time, or the black card whose span holds the track time. */
export function clipTimeAt(map: CardMap, trackMs: Ms): TrackTime {
  // The last gap that starts at or before `trackMs` on the track.
  const next = firstWhere(map.gaps, (gap) => gap.atMs + gap.beforeMs > trackMs)
  if (next === 0) {
    return { kind: 'clip', ms: trackMs }
  }
  const gap = map.gaps[next - 1]
  const startsAt = gap.atMs + gap.beforeMs
  if (trackMs < startsAt + gap.lengthMs) {
    return { kind: 'card', index: next - 1, chapter: gap.chapter, afterMs: gap.atMs }
  }
  return { kind: 'clip', ms: trackMs - (gap.beforeMs + gap.lengthMs) }
}

/** The clips end to end with the black cards between them: where each clip starts on the track. */
export function trackLayout(lay: Layout, map: CardMap): Layout {
  return {
    startsMs: lay.startsMs.map((start) => trackX(map, start)),
    totalMs: lay.totalMs + map.totalMs,
  }
}

/** The movie's length: the footage less the cuts (`movie`), plus each black card once. */
export function movieWithCards(movieMs: Ms, map: CardMap): Ms {
  return movieMs + map.totalMs
}

// --- blocks ----------------------------------------------------------------------------

/** A card as the lane draws it: a span of the track, with its look and words. */
export type CardBlock = {
  chapter: number
  /** Where it starts on the track and how wide it is. */
  startMs: Ms
  widthMs: Ms
  background: Background
  off: boolean
  clamped: boolean
  durationMs: Ms
  /** The anchor clip's index. */
  clip: number
  /** The footage a video card is held to (`Placement.keptMs`). */
  keptMs: Ms
}

/**
 * The blocks to draw, in track order. A black card starts at its clip's track start less its
 * own length; a video (or off) card starts where the first kept span starts.
 */
export function cardBlocks(placements: readonly Placement[], track: Layout): CardBlock[] {
  const blocks: CardBlock[] = []
  for (const place of placements) {
    if (place.kind !== 'anchored' && place.kind !== 'off') {
      continue
    }
    const black = place.kind === 'anchored' && place.background === 'black'
    blocks.push({
      chapter: place.chapter,
      startMs: black ? track.startsMs[place.clip] - place.widthMs : track.startsMs[place.clip] + place.atMs,
      widthMs: place.widthMs,
      background: place.background,
      off: place.kind === 'off',
      clamped: place.clamped,
      durationMs: place.durationMs,
      clip: place.clip,
      keptMs: place.keptMs,
    })
  }
  return blocks
}

/** The blocks that meet `[fromMs, toMs)` of the track, as `[first, last]` or null (log n). */
export function visibleBlocks(
  blocks: readonly CardBlock[],
  fromMs: Ms,
  toMs: Ms,
): [number, number] | null {
  // Blocks do not overlap, so ends are in order as well as starts.
  let low = 0
  let high = blocks.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (blocks[mid].startMs + blocks[mid].widthMs > fromMs) {
      high = mid
    } else {
      low = mid + 1
    }
  }
  const first = low
  low = first
  high = blocks.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (blocks[mid].startMs >= toMs) {
      high = mid
    } else {
      low = mid + 1
    }
  }
  return low > first ? [first, low - 1] : null
}

// --- handles ---------------------------------------------------------------------------

/** What a card's end-edge handle needs (`title-card-duration-drag`), in track order. */
export type CardHandle = {
  /** The block's index in `cardBlocks`' list. */
  index: number
  /** The chapter's saved name. */
  chapter: string
  background: Background
  /** The card's length now. */
  tenths: Tenths
  range: CardRange
  /** Where the block starts on the track. */
  startMs: Ms
  /** The footage a video card is held to (null: none for a black card). */
  keptMs: Ms
  /** A video card longer than its footage. */
  clamped: boolean
  /** The block's width now. */
  widthMs: Ms
}

/** The width a block takes for a length: a black card's own, a video card's held to the footage. */
export function cardWidthMs(handle: Pick<CardHandle, 'background' | 'keptMs'>, tenths: Tenths): Ms {
  return handle.background === 'black' ? tenths * 100 : Math.min(tenths * 100, handle.keptMs)
}

/** One handle per drawn block (`cardBlocks`), with the limits its card has. */
export function cardHandles(
  placements: readonly Placement[],
  blocks: readonly CardBlock[],
  specs: readonly CardSpec[],
): CardHandle[] {
  const handles: CardHandle[] = []
  let at = 0
  for (const place of placements) {
    if (place.kind !== 'anchored' && place.kind !== 'off') {
      continue
    }
    const block = blocks[at]
    const tenths = Math.round(place.durationMs / 100)
    handles.push({
      index: at,
      chapter: specs[place.chapter].chapter,
      background: place.background,
      tenths,
      range: cardLimits({ background: place.background, currentTenths: tenths, keptMs: place.keptMs }),
      startMs: block.startMs,
      keptMs: place.keptMs,
      clamped: place.clamped,
      widthMs: block.widthMs,
    })
    at += 1
  }
  return handles
}

/** The handles whose end edge meets `[fromMs, toMs]` of the track, as `[first, last]` or null. */
export function visibleHandles(
  handles: readonly CardHandle[],
  fromMs: Ms,
  toMs: Ms,
): [number, number] | null {
  let first = -1
  let last = -1
  handles.forEach((handle, index) => {
    const edge = handle.startMs + handle.widthMs
    if (edge >= fromMs && edge <= toMs) {
      first = first === -1 ? index : first
      last = index
    }
  })
  return first === -1 ? null : [first, last]
}

// --- words -----------------------------------------------------------------------------

/** Seconds to one decimal: `4.0 s`. */
export function cardSeconds(ms: Ms): string {
  return `${(ms / 1000).toFixed(1)} s`
}

/** What a chapter's card is called: the default chapter is the opening. */
export function cardSubject(chapterName: string): string {
  return chapterName === '' ? 'the opening' : chapterName
}

/**
 * `Title card for Dag 2, 4.0 s, over video` / `…, on black`; a clamped video card
 * `3.0 s of 7.0 s`; the off look adds `, not enabled`.
 */
export function cardWords(
  chapterName: string,
  card: { durationMs: Ms; widthMs?: Ms; background: Background; off?: boolean },
): string {
  const width = card.widthMs ?? card.durationMs
  const length =
    width < card.durationMs
      ? `${cardSeconds(width)} of ${cardSeconds(card.durationMs)}`
      : cardSeconds(card.durationMs)
  const look = card.background === 'video' ? 'over video' : 'on black'
  return `Title card for ${cardSubject(chapterName)}, ${length}, ${look}${card.off === true ? ', not enabled' : ''}`
}

/** `with 8 s of title cards` for the movie's length; empty when no black card adds time. */
export function cardTimeWords(map: CardMap): string {
  if (map.totalMs <= 0) {
    return ''
  }
  const seconds = map.totalMs / 1000
  return `with ${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)} s of title cards`
}

// --- the selection ---------------------------------------------------------------------

/** The selected card, by its chapter's saved name; none is null. */
export type CardSelection = { chapter: string } | null

export const cardSelection = {
  select(state: CardSelection, chapter: string): CardSelection {
    return state?.chapter === chapter ? state : { chapter }
  },
  clear(state: CardSelection): CardSelection {
    return state === null ? state : null
  },
  /** Ends a selection whose chapter is not among `names`. */
  chapters(state: CardSelection, names: readonly string[]): CardSelection {
    return state === null || names.includes(state.chapter) ? state : null
  },
  /** A cut is selected: the card is not. */
  selectCut(state: CardSelection): CardSelection {
    return state === null ? state : null
  },
}
