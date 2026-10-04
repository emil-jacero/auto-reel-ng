import { memo, useSyncExternalStore } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'

import { Icon } from '../ui/Icon'
import { cardBlockPx, cardSeconds, cardWords, visibleBlocks } from './cards'
import type { DragStore } from './dragStore'
import type { CardBlock, CardSpec } from './cards'
import type { CardPictures } from './useCardImages'
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
  pictures,
  onSelect,
  onPlace,
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
  /** Each card's image, when the Timeline has fetched it: the block's miniature. */
  pictures: CardPictures
  onSelect: (chapter: string) => void
  /** A press in a black card's block also puts the playhead there: the track time of the press. */
  onPlace: (chapter: string, trackMs: number) => void
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
          image={pictures.get(spec.chapter)?.url ?? null}
          pps={pps}
          selected={selected === spec.chapter}
          drag={drag}
          behind={shifting !== null && block.startMs >= shifting.fromMs - 0.5}
          onSelect={onSelect}
          onPlace={onPlace}
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
  image,
  pps,
  selected: on,
  drag,
  behind,
  onSelect,
  onPlace,
  onClear,
}: {
  block: CardBlock
  name: string
  title: string | null
  /** The card's image (an object URL), or null while it is missing. */
  image: string | null
  pps: number
  selected: boolean
  drag: DragStore | null
  /** Behind a black card being dragged: moved with it. */
  behind: boolean
  onSelect: (chapter: string) => void
  onPlace: (chapter: string, trackMs: number) => void
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
  const widthPx = cardBlockPx(timeToPx(widthMs, pps))
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
      data-image={image !== null || undefined}
      data-words={widthPx >= TITLE_PX || undefined}
      aria-label={title === null ? words : `${words}: ${title}`}
      title={title === null ? words : `${title}. ${words}`}
      style={{
        insetInlineStart: timeToPx(block.startMs, pps),
        inlineSize: widthPx,
        ...(image === null ? {} : ({ '--tl-card-image': `url("${image}")` } as CSSProperties)),
      }}
      onClick={(event) => {
        onSelect(name)
        if (block.background === 'black' && !block.off) {
          // Where in the block the press was, as a part of its span on the track.
          const box = event.currentTarget.getBoundingClientRect()
          const part = box.width > 0 ? (event.clientX - box.left) / box.width : 0
          onPlace(name, block.startMs + Math.min(0.999, Math.max(0, part)) * widthMs)
        }
      }}
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
