import type { components } from '../api/schema'
import type { Clip } from '../api/event.ts'
import { formatTime, keptCuts, reasonWords, spanWords } from '../cuts/times.ts'
import { CLIP_STATUS_LABEL, EXCLUDED_LABEL } from '../events/labels.ts'
import { formatBytes, formatInstant } from '../format.ts'
import { normalizeTurn, turnWords } from '../rotate/turn.ts'
import type { Turn } from '../rotate/turn.ts'
import { playedMs } from '../timeline/edgeTrim.ts'
import type { DraftCut } from './draft.ts'

/*
 * What the clip bin's information panel says of the shown clip (`plain-clip-bin`, design D3),
 * from what the page already holds: the event read's `ClipOut`, the ready proxy's facts and the
 * draft's cuts. Pure: no DOM, no React, no request, and type-only imports besides the page's
 * own formats, so `npm test` runs it as it is.
 *
 * Only facts the client has. The proxy's width and height are the proxy's (540 on the short
 * side), so the picture is said as an orientation and a ratio, never as a pixel size; there is
 * no source resolution, video codec, bitrate or capture time to show (Principle I). An unknown
 * value is "unknown", never a zero.
 */

/** A ready proxy's facts (the generated schema's `ProxyFactsOut`). */
export type ProxyFacts = components['schemas']['ProxyFactsOut']

/** Where a line belongs in the panel: the event read, the proxy's facts, or the clip's cuts. */
export type InfoSection = 'read' | 'proxy' | 'cuts'

/** One line of the panel: a label and its value, both plain words. */
export type InfoLine = { section: InfoSection; label: string; value: string }

/** A value the page does not have. */
export const UNKNOWN = 'unknown'

/** What the proxy-fact lines are replaced by while no ready proxy has given facts. */
export const AWAITING_PROXY = 'Frame rate, picture and sound are known once its proxy is prepared.'

/** A positive finite number, or null: a length or a rate the page can use. */
function usable(value: number | null | undefined): number | null {
  return value != null && Number.isFinite(value) && value > 0 ? value : null
}

/**
 * The clip's length in seconds: the event read's duration, else the facts' (the source's, as
 * probed). Null when neither is a length: unknown, never 0.
 */
export function clipSeconds(clip: Pick<Clip, 'duration'>, facts: ProxyFacts | null): number | null {
  return usable(clip.duration) ?? usable(facts?.duration)
}

/**
 * The length the clip plays: its length less what its kept cuts cover, once (the union rule the
 * movie's length uses, `playedMs`), in seconds. Null when the length is unknown.
 */
export function keptSeconds(seconds: number | null, cuts: readonly DraftCut[]): number | null {
  return seconds === null ? null : playedMs(keptCuts(cuts), Math.round(seconds * 1000)) / 1000
}

/** A rounded number without trailing zeros: 25 → "25", 29.9700299 → "29.97". */
function plain(value: number, places: number): string {
  return String(Number(value.toFixed(places)))
}

/**
 * The frame rate: "25 fps", "29.97 fps", and for a variable one "variable, about 29.97 fps".
 * A rate the facts cannot give (a zero or missing denominator) is "unknown".
 */
export function frameRateWords(facts: Pick<ProxyFacts, 'fps_num' | 'fps_den' | 'vfr'>): string {
  const rate = facts.fps_den > 0 ? usable(facts.fps_num / facts.fps_den) : null
  if (rate === null) {
    return UNKNOWN
  }
  const fps = `${plain(rate, 2)} fps`
  return facts.vfr === true ? `variable, about ${fps}` : fps
}

// Ratios the picture is named by (long side : short side), matched within 1 %.
const RATIOS: readonly (readonly [number, number])[] = [
  [16, 9],
  [4, 3],
  [3, 2],
  [21, 9],
]
const RATIO_TOLERANCE = 0.01

/**
 * The picture's orientation and ratio from the proxy's displayed width and height: "Landscape,
 * 16:9", "Portrait, 9:16", "Square, 1:1", else "Landscape, about 1.85:1". No pixel size: those
 * are the proxy's, not the source's. Null when the size is not usable.
 */
export function pictureWords(width: number, height: number): string | null {
  if (usable(width) === null || usable(height) === null) {
    return null
  }
  const long = Math.max(width, height)
  const short = Math.min(width, height)
  const ratio = long / short
  if (Math.abs(ratio - 1) <= RATIO_TOLERANCE) {
    return 'Square, 1:1'
  }
  const landscape = width > height
  const orientation = landscape ? 'Landscape' : 'Portrait'
  const named = RATIOS.find(([a, b]) => Math.abs(ratio - a / b) / (a / b) <= RATIO_TOLERANCE)
  if (named !== undefined) {
    return `${orientation}, ${landscape ? `${named[0]}:${named[1]}` : `${named[1]}:${named[0]}`}`
  }
  const about = plain(ratio, 2)
  return `${orientation}, about ${landscape ? `${about}:1` : `1:${about}`}`
}

/**
 * The container's rotation: "Turned 90° by its container" for a quarter-turn, 180° or 270°
 * (a negative one as its clockwise equal); null for none. A value that is not a quarter-turn is
 * shown as given, never rounded.
 */
export function containerRotationWords(rotation: number | null | undefined): string | null {
  if (rotation == null || rotation === 0) {
    return null
  }
  const turn = normalizeTurn(rotation)
  if (turn === 0) {
    return null
  }
  return `Turned ${turn ?? rotation}° by its container`
}

/** The sound's codec in capitals ("AAC"), any `pcm_*` as "PCM"; none is "No sound". */
export function soundWords(codec: string | null | undefined): string {
  if (codec == null) {
    return 'No sound'
  }
  const name = codec.trim()
  if (name === '') {
    return UNKNOWN
  }
  return name.toLowerCase().startsWith('pcm_') ? 'PCM' : name.toUpperCase()
}

/** The status in the page's words; an excluded clip says Excluded in place of the quiet Included. */
function statusWords(clip: Pick<Clip, 'status' | 'excluded'>): string {
  if (!clip.excluded) {
    return CLIP_STATUS_LABEL[clip.status]
  }
  return clip.status === 'active'
    ? EXCLUDED_LABEL
    : `${CLIP_STATUS_LABEL[clip.status]} · ${EXCLUDED_LABEL}`
}

/** A length as the Cuts panel writes a time (`0:06.02`), "unknown" when it is not known. */
function lengthWords(seconds: number | null): string {
  return seconds === null ? UNKNOWN : formatTime(seconds)
}

/**
 * The panel's lines for one clip, in the order shown:
 * - `read`: status, chapter and position (`place`, when the clip has one), size, modified, length,
 *   and the kept length when kept cuts shorten it, and the draft's turn when it is set;
 * - `proxy`: frame rate, picture, container rotation and sound from the ready proxy's `facts`, or
 *   one line saying they wait for the proxy;
 * - `cuts`: each cut the save keeps (removed ones left out), numbered as the Cuts panel
 *   numbers them, in its time format, or "None".
 */
export function clipInfo(
  clip: Clip,
  facts: ProxyFacts | null,
  cuts: readonly DraftCut[],
  place: string | null,
  turn: Turn = 0,
): InfoLine[] {
  const lines: InfoLine[] = []
  const read = (label: string, value: string) => lines.push({ section: 'read', label, value })

  read('Status', statusWords(clip))
  if (place !== null) {
    read('Chapter', place)
  }
  read('Size', clip.size == null ? UNKNOWN : formatBytes(clip.size))
  read('Modified', clip.mtime == null ? UNKNOWN : formatInstant(clip.mtime))
  const seconds = clipSeconds(clip, facts)
  read('Length', lengthWords(seconds))
  if (keptCuts(cuts).length > 0) {
    read('Kept length', lengthWords(keptSeconds(seconds, cuts)))
  }
  if (turn !== 0) {
    read('Turn', turnWords(turn))
  }

  if (facts === null) {
    lines.push({ section: 'proxy', label: 'Proxy', value: AWAITING_PROXY })
  } else {
    const proxy = (label: string, value: string) => lines.push({ section: 'proxy', label, value })
    proxy('Frame rate', frameRateWords(facts))
    proxy('Picture', pictureWords(facts.width, facts.height) ?? UNKNOWN)
    const rotation = containerRotationWords(facts.rotation)
    if (rotation !== null) {
      proxy('Rotation', rotation)
    }
    proxy('Sound', soundWords(facts.audio_codec))
  }

  cuts.forEach((cut, index) => {
    if (cut.removed) {
      return
    }
    const reason = cut.reason == null || cut.reason.trim() === '' ? '' : ` · ${reasonWords(cut.reason)}`
    lines.push({ section: 'cuts', label: `Cut ${index + 1}`, value: `${spanWords(cut)}${reason}` })
  })
  if (keptCuts(cuts).length === 0) {
    lines.push({ section: 'cuts', label: 'Cuts', value: 'None' })
  }
  return lines
}
