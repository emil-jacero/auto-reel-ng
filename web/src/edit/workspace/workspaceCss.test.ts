import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { MIN_BIN_PX, MIN_INSP_PX, MIN_TL_PX } from './paneSizes.ts'

/*
 * The workspace's pane rules are CSS, so their contract is read from the stylesheet (as
 * `binPlayerCss.test.ts` does); the drawn result is measured in a browser.
 */

const css = readFileSync(new URL('workspace.css', import.meta.url), 'utf8').replace(
  /\/\*[\s\S]*?\*\//g,
  '',
)

/** Every balanced `{ … }` body that follows `header`, in order. */
function blocks(source: string, header: string): string[] {
  const found: string[] = []
  let from = 0
  for (;;) {
    const at = source.indexOf(header, from)
    if (at === -1) {
      return found
    }
    const open = source.indexOf('{', at)
    let depth = 0
    let end = open
    for (; end < source.length; end += 1) {
      if (source[end] === '{') {
        depth += 1
      } else if (source[end] === '}') {
        depth -= 1
        if (depth === 0) {
          break
        }
      }
    }
    found.push(source.slice(open + 1, end))
    from = end
  }
}

const wide = blocks(css, '@media (width >= 960px) {').join('\n')
const stacked = blocks(css, '@media (width < 960px) {').join('\n')
const outsideWide = (() => {
  let rest = css
  for (const body of blocks(css, '@media (width >= 960px) {')) {
    rest = rest.replace(body, '')
  }
  return rest
})()

describe('workspace.css, resizable panes', () => {
  it('the Timeline row follows --ws-tl-h and falls back to today’s rule', () => {
    assert.match(css, /'tl tl tl' var\(--ws-tl-h, minmax\(280px, 38vh\)\)/)
  })

  it('--ws-bin-w and --ws-insp-w keep their defaults on <html>', () => {
    const root = blocks(css, 'html[data-workspace] {')[0] ?? ''
    assert.match(root, /--ws-bin-w:\s*clamp\(240px, 22vw, 320px\)/)
    assert.match(root, /--ws-insp-w:\s*340px/)
  })

  it('the borders are not shown stacked', () => {
    assert.match(stacked, /\.ws-sep\s*\{\s*display:\s*none;\s*\}/)
  })

  it('the hidden-pane rules and overflow: clip are only in the wide frame', () => {
    assert.match(wide, /\.ws-binbox\[data-hidden\]/)
    assert.match(wide, /\.ws-insp\[data-hidden\]/)
    assert.match(wide, /\.ws-tl\[data-hidden\]/)
    assert.match(wide, /\.ws\s*\{\s*overflow:\s*clip/)
    assert.match(wide, /\.ws-binbox\s*\{[^}]*overflow-x:\s*clip/)
    assert.doesNotMatch(outsideWide, /\[data-hidden\]\s*\{[^}]*visibility/)
    assert.doesNotMatch(outsideWide, /\.ws(-binbox)?\s*\{[^}]*overflow(-x)?:\s*clip;/)
  })

  it('the bin never clips a reachable control: the list shrinks first, then the box scrolls', () => {
    const box = /\.ws-binbox\s*\{([^}]*)\}/.exec(wide)?.[1] ?? ''
    assert.match(box, /overflow-y:\s*auto/)
    assert.match(box, /overflow-x:\s*clip/)
    assert.doesNotMatch(box, /overflow:\s*clip/)
    assert.match(wide, /pointer: coarse\)\s*\{\s*\.ws-binbox\s*\{[^}]*padding-block-end:\s*12px/)
    const list = /\.ws-bin\s*\{([^}]*flex:[^}]*)\}/.exec(wide)?.[1] ?? ''
    assert.match(list, /flex:\s*1 1 0/)
    assert.match(list, /min-block-size:\s*calc\(var\(--bin-head-h, 2\.5rem\) \+ var\(--bin-row-h, 2\.5rem\)\)/)
    assert.doesNotMatch(outsideWide, /\.ws-bin\s*\{[^}]*flex:\s*1 1 0/)
    assert.match(outsideWide, /\.ws-bin\s*\{\s*flex:\s*1 1 auto;/) // today's rule, kept for the stacked layout
    assert.doesNotMatch(outsideWide, /\.ws-bin\s*\{[^}]*min-block-size/)
    assert.doesNotMatch(stacked, /\.ws-bin\s*\{[^}]*flex:/)
    assert.doesNotMatch(css, /\.ws-bin(box)?:focus-visible/) // Firefox's Tab stop on the scroll box is accepted as is
    const info = readFileSync(new URL('../clipInfo.css', import.meta.url), 'utf8').replace(
      /\/\*[\s\S]*?\*\//g,
      '',
    )
    // Stacked (outside the wide media block) the info keeps today's fixed parts; wide it shrinks.
    const infoWide = blocks(info, '@media (width >= 960px) {').join('\n')
    const infoOutside = info.replace(infoWide, '')
    assert.match(infoOutside, /\.bin-info\s*\{[^}]*flex:\s*none/)
    assert.doesNotMatch(infoOutside, /\.bin-info\s*\{[^}]*flex:\s*0 1 auto/)
    assert.match(infoWide, /\.bin-info\s*\{[^}]*flex:\s*0 1 auto/)
    // Least height: the real heading (34 px) and the border; the body's padding never spills past it.
    assert.match(infoWide, /\.bin-info\s*\{[^}]*min-block-size:\s*35px/)
    assert.match(infoWide, /\.bin-info\s*\{[^}]*overflow-y:\s*clip/)
    assert.doesNotMatch(info, /2\.25rem/)
    assert.doesNotMatch(infoOutside, /overflow-y/)
    assert.match(infoWide, /\.bin-info\s*\{[^}]*max-block-size:\s*30%/)
    assert.match(infoWide, /\.bin-info-body:focus-visible\s*\{[^}]*outline-offset:\s*-2px/)
    assert.doesNotMatch(infoOutside, /focus-visible/)
  })

  it('a live-collapsing pane is laid out like a hidden one but never visibility: hidden', () => {
    for (const pane of ['binbox', 'insp', 'tl']) {
      assert.match(wide, new RegExp(`\\.ws-${pane}\\[data-collapsing\\],\\s*\\.ws-${pane}\\[data-hidden\\]\\s*\\{`))
    }
    assert.doesNotMatch(css, /\[data-collapsing\][^{]*\{[^}]*visibility/)
    assert.doesNotMatch(wide, /\[data-collapsing\]\s*\{[^}]*visibility/)
    assert.doesNotMatch(wide, /\[data-collapsing\],\s*\.ws-\w+\[data-hidden\]\s*\{[^}]*visibility/)
  })

  it('a hidden pane keeps its least size, as paneSizes.ts has it', () => {
    assert.match(wide, new RegExp(`\\.ws-binbox\\[data-hidden\\]\\s*\\{[^}]*inline-size:\\s*${MIN_BIN_PX}px`))
    assert.match(wide, new RegExp(`\\.ws-insp\\[data-hidden\\]\\s*\\{[^}]*inline-size:\\s*${MIN_INSP_PX}px`))
    assert.match(wide, new RegExp(`\\.ws-tl\\[data-hidden\\]\\s*\\{[^}]*block-size:\\s*${MIN_TL_PX}px`))
    assert.match(wide, /\.ws-binbox\[data-hidden\]\s*\{[^}]*translate:\s*-100% 0/)
  })

  it('a hidden pane’s border is drawn in --fg-subtle, and the Timeline’s spans only the viewer', () => {
    const hidden = blocks(css, '&[data-hidden] {')[0] ?? ''
    assert.match(hidden, /&::before\s*\{\s*background:\s*var\(--fg-subtle\)/)
    assert.match(hidden, /&\[data-pane='tl'\]\s*\{[^}]*grid-column:\s*2/)
  })

  it('the toast region still reads both pane widths', () => {
    assert.match(
      wide,
      /inset-inline:\s*calc\(var\(--ws-bin-w\) \+ var\(--s-3\)\) calc\(var\(--ws-insp-w\) \+ var\(--s-3\)\)/,
    )
  })

  it('a border is a resize cursor, above the sticky tabs and below the top bar', () => {
    assert.match(css, /cursor:\s*col-resize/)
    assert.match(css, /cursor:\s*row-resize/)
    const sep = blocks(css, '.ws-sep {')[0] ?? ''
    assert.match(sep, /z-index:\s*5/)
    assert.match(sep, /touch-action:\s*none/)
  })

  it('a drag sets the cursor and stops text selection on the page', () => {
    assert.match(css, /html\[data-ws-resizing='col'\] \*[^}]*cursor:\s*col-resize/)
    assert.match(css, /html\[data-ws-resizing='row'\] \*[^}]*cursor:\s*row-resize/)
    assert.match(css, /user-select:\s*none/)
  })
})
