import type { KeyboardEvent } from 'react'

import { Icon } from '../ui/Icon'
import { cardSeconds, cardWords, visibleBlocks } from './cards'
import type { CardBlock, CardSpec } from './cards'
import { timeToPx } from './model'

/*
 * The card lane (`title-card-blocks`): one block per chapter whose card the render draws, in
 * a lane of its own directly above the clips. Every block is a real button with a name in
 * words, and its look is told by shape and word as well as colour: a black card is a solid
 * block of its own span; a video card is an outlined block over the footage it sits on, with
 * an edge marker down to the clip; the off look is dashed with the words "not enabled". Only the
 * blocks in the track's window are drawn.
 */

/** A block narrower than this is drawn without its words. */
const TITLE_PX = 56
const META_PX = 120

export function CardLane({
  blocks,
  specs,
  pps,
  window,
  selected,
  onSelect,
  onClear,
}: {
  blocks: readonly CardBlock[]
  specs: readonly CardSpec[]
  pps: number
  /** The track's window in px: what meets it is drawn. */
  window: { from: number; to: number }
  /** The selected card's chapter (saved name) or null. */
  selected: string | null
  onSelect: (chapter: string) => void
  onClear: () => void
}) {
  const range = visibleBlocks(blocks, (window.from / pps) * 1000, (window.to / pps) * 1000)
  const nodes = []
  if (range !== null) {
    for (let index = range[0]; index <= range[1]; index += 1) {
      const block = blocks[index]
      const spec = specs[block.chapter]
      const name = spec.chapter
      const widthPx = Math.max(2, timeToPx(block.widthMs, pps))
      const words = cardWords(name, {
        durationMs: block.durationMs,
        widthMs: block.widthMs,
        background: block.background,
        off: block.off,
      })
      const on = selected === name
      const title = spec.card?.title === '' ? null : (spec.card?.title ?? null)
      nodes.push(
        <button
          key={block.chapter}
          type="button"
          className="tl-card"
          data-kind={block.background}
          data-off={block.off || undefined}
          data-selected={on || undefined}
          aria-pressed={on}
          aria-label={words}
          title={words}
          style={{ insetInlineStart: timeToPx(block.startMs, pps), inlineSize: widthPx }}
          onClick={() => onSelect(name)}
          onKeyDown={(event: KeyboardEvent<HTMLButtonElement>) => {
            if (event.key === 'Escape' && on) {
              event.preventDefault()
              onClear()
            }
          }}
        >
          {block.background === 'video' && <span className="tl-card-edge" aria-hidden="true" />}
          {widthPx >= TITLE_PX && (
            <span className="tl-card-text" aria-hidden="true">
              {on && <Icon name="check" size={16} />}
              <span className="tl-card-title">{title ?? (name === '' ? 'Opening' : name)}</span>
              {widthPx >= META_PX && (
                <span className="tl-card-meta">
                  {cardSeconds(block.widthMs)} · {block.background === 'video' ? 'Video' : 'Black'}
                  {block.off ? ' · not enabled' : ''}
                </span>
              )}
            </span>
          )}
        </button>,
      )
    }
  }
  return <div className="tl-cards">{nodes}</div>
}
