import { memo, useSyncExternalStore } from 'react'
import type { KeyboardEvent } from 'react'

import { Icon } from '../ui/Icon'
import { cardSeconds, cardWords, visibleBlocks } from './cards'
import type { DragStore } from './dragStore'
import type { CardBlock, CardSpec } from './cards'
import type { ShiftFrom } from './Track'
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
  drag,
  shifting,
  onOpen,
  onClear,
}: {
  blocks: readonly CardBlock[]
  specs: readonly CardSpec[]
  pps: number
  /** The track's window in px: what meets it is drawn. */
  window: { from: number; to: number }
  /** The selected card's chapter (saved name) or null. */
  selected: string | null
  /** A video card's edge in the air changes its own block only (it adds no time), through this. */
  drag: DragStore | null
  /** A black card's drag in progress: the blocks behind the card move. */
  shifting: ShiftFrom | null
  onOpen: (chapter: string) => void
  onClear: () => void
}) {
  const range = visibleBlocks(blocks, (window.from / pps) * 1000, (window.to / pps) * 1000)
  const nodes = []
  if (range !== null) {
    for (let index = range[0]; index <= range[1]; index += 1) {
      const block = blocks[index]
      const spec = specs[block.chapter]
      nodes.push(
        <CardBlockButton
          key={block.chapter}
          block={block}
          name={spec.chapter}
          title={spec.card?.title ?? null}
          pps={pps}
          selected={selected === spec.chapter}
          drag={drag}
          behind={shifting !== null && block.startMs >= shifting.fromMs - 0.5}
          onOpen={onOpen}
          onClear={onClear}
        />,
      )
    }
  }
  return <div className="tl-cards">{nodes}</div>
}

/** The subscription of a block with no drag store: it never changes. */
const NEVER = () => () => {}

const CardBlockButton = memo(function CardBlockButton({
  block,
  name,
  title: cardTitle,
  pps,
  selected: on,
  drag,
  behind,
  onOpen,
  onClear,
}: {
  block: CardBlock
  name: string
  title: string | null
  pps: number
  selected: boolean
  drag: DragStore | null
  /** Behind a black card being dragged: moved with it. */
  behind: boolean
  onOpen: (chapter: string) => void
  onClear: () => void
}) {
  // The card's edge in the air: only this block follows it (a black card's drag moves the layers
  // behind it with it; the layout is not drawn again until release).
  const live = useSyncExternalStore(drag?.subscribe ?? NEVER, () => {
    const d = drag?.getCard() ?? null
    return d !== null && d.chapter === name ? d : null
  })
  const widthMs =
    live === null
      ? block.widthMs
      : block.background === 'video'
        ? Math.min(live.tenths * 100, block.keptMs)
        : live.tenths * 100
  const durationMs = live === null ? block.durationMs : live.tenths * 100
  const widthPx = Math.max(2, timeToPx(widthMs, pps))
  const words = cardWords(name, {
    durationMs,
    widthMs,
    background: block.background,
    off: block.off,
  })
  const title = cardTitle === '' ? null : cardTitle
  return (
    <button
      type="button"
      className="tl-card"
      data-kind={block.background}
      data-off={block.off || undefined}
      data-selected={on || undefined}
      data-after={behind || undefined}
      aria-pressed={on}
      aria-label={words}
      title={words}
      style={{ insetInlineStart: timeToPx(block.startMs, pps), inlineSize: widthPx }}
      onClick={() => onOpen(name)}
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
              {cardSeconds(widthMs)} · {block.background === 'video' ? 'Video' : 'Black'}
              {block.off ? ' · not enabled' : ''}
            </span>
          )}
        </span>
      )}
    </button>
  )
})
