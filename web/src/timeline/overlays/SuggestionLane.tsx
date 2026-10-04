import './overlays.css'

import type { KeyboardEvent } from 'react'

import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import { timeToPx } from '../model'
import type { LaneView, MarkModel } from './control'
import { CLIP_NOT_ANALYZED, STATE_GLYPH, kindWords, laneName, markName } from './suggestions'

/*
 * The analysis lane: for each clip in the window a group of marks, one button per
 * suggestion, placed on the track at the timeline's scale. One tab stop per clip
 * (roving); the mark carries its kind as an icon and a word and its state as a glyph and
 * a word, never colour alone. Only the marks of the windowed clips are drawn, and the one
 * with focus wherever its clip is.
 */

/** A mark shows its kind in words when its box is at least this wide. */
const LABEL_PX = 120

const KIND_ICON: Record<string, IconName> = {
  black: 'moon',
  white: 'sun',
  freeze: 'pause',
}

/** A kind's icon; one neutral icon for a kind the page does not know. */
export function kindIcon(kind: string): IconName {
  return Object.hasOwn(KIND_ICON, kind) ? KIND_ICON[kind] : 'info'
}

export type ClipMarks = {
  clipIndex: number
  marks: readonly MarkModel[]
  /** The event was analysed but this clip has no entry. */
  notAnalyzed: boolean
}

export function SuggestionLane({
  view,
  groups,
  selectedId,
  keepId,
  tabStop,
  decidable,
  detailId,
  register,
  onSelect,
  onKeyDown,
  onFocus,
  onBlur,
}: {
  view: LaneView
  /** By clip index. */
  groups: readonly ClipMarks[]
  selectedId: string | null
  /** A mark drawn wherever its clip is: the one with focus, or about to have it. */
  keepId: string | null
  /** The mark that is the clip's one tab stop. */
  tabStop: (clipIndex: number) => string | null
  /** Whether a decision is available on a mark in this state (the keys are declared). */
  decidable: (mark: MarkModel) => boolean
  detailId: string
  register: (id: string, element: HTMLButtonElement | null) => void
  onSelect: (mark: MarkModel) => void
  onKeyDown: (mark: MarkModel, event: KeyboardEvent<HTMLButtonElement>) => void
  onFocus: (id: string) => void
  onBlur: (id: string) => void
}) {
  const { clips, lay, shown, shifted } = view
  const drawn = new Set<number>()
  if (shown !== null) {
    for (let index = shown[0]; index <= shown[1]; index += 1) {
      drawn.add(index)
    }
  }
  const kept = keepId === null ? undefined : groups.find((g) => g.marks.some((m) => m.id === keepId))
  if (kept !== undefined) {
    drawn.add(kept.clipIndex)
  }

  const nodes = [...drawn]
    .sort((a, b) => a - b)
    .map((index) => {
      const group = groups[index]
      const clip = clips[index]
      if (group === undefined || clip === undefined || (group.marks.length === 0 && !group.notAnalyzed)) {
        return null
      }
      const inWindow = shown !== null && index >= shown[0] && index <= shown[1]
      const marks = inWindow ? group.marks : group.marks.filter((mark) => mark.id === keepId)
      const stop = tabStop(index)
      return (
        <div key={clip.identity} className="sg-group" role="group" aria-label={laneName(clip.name)}>
          {group.notAnalyzed && inWindow && (
            <span
              className="sg-clip-note"
              data-after={shifted?.(index) || undefined}
              title={CLIP_NOT_ANALYZED}
              style={{
                insetInlineStart: timeToPx(lay.startsMs[index], view.pps),
                inlineSize: Math.max(1, timeToPx(clip.facts.durationMs, view.pps)),
              }}
            >
              <span className="sg-clip-note-text">{CLIP_NOT_ANALYZED}</span>
            </span>
          )}
          {marks.map((mark) => {
            const wide = mark.width >= LABEL_PX
            const selected = mark.id === selectedId
            return (
              <button
                key={mark.id}
                type="button"
                ref={(element) => register(mark.id, element)}
                className="sg-mark"
                data-kind={mark.segment.kind}
                data-state={mark.state}
                data-selected={selected || undefined}
                data-after={shifted?.(index) || undefined}
                aria-label={markName(mark.segment, mark.state)}
                aria-current={selected || undefined}
                aria-controls={selected ? detailId : undefined}
                aria-keyshortcuts={decidable(mark) ? 'A R' : undefined}
                tabIndex={stop === mark.id ? 0 : -1}
                style={{
                  insetInlineStart: mark.left,
                  inlineSize: mark.width,
                  insetBlockStart: `calc(${mark.row} * var(--sg-row))`,
                }}
                onClick={() => onSelect(mark)}
                onKeyDown={(event) => onKeyDown(mark, event)}
                onFocus={() => onFocus(mark.id)}
                onBlur={() => onBlur(mark.id)}
              >
                <span
                  className="sg-bar"
                  aria-hidden="true"
                  style={{ insetInlineStart: mark.barLeft, inlineSize: mark.barWidth }}
                />
                <span className="sg-face" aria-hidden="true">
                  <Icon name={kindIcon(mark.segment.kind)} size={16} />
                  <span className="sg-glyph">{STATE_GLYPH[mark.state]}</span>
                  {wide && <span className="sg-label">{kindWords(mark.segment.kind)}</span>}
                </span>
              </button>
            )
          })}
        </div>
      )
    })
  return <>{nodes}</>
}
