import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

/*
 * The docked player's own gap (`.bin-player .clip-preview`) is more specific than the preview's
 * coarse-pointer row gap (`preview/preview.css`), so it wins unless it is restated there: with a
 * coarse pointer a control's tap area reaches 6px past its box, and rows 4px apart would put the
 * picture inside Hide player's area. The rule is CSS, so its contract is read from the stylesheet;
 * the tap areas themselves are measured with Playwright.
 */

const css = readFileSync(new URL('binPlayer.css', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

describe('binPlayer.css', () => {
  it('the player’s column may be narrower than its heading, so Show player is never cut off', () => {
    const root = /\.bin-player\s*\{([^}]*)\}/.exec(css)
    assert.notEqual(root, null, 'a `.bin-player` rule')
    assert.match(root?.[1] ?? '', /grid-template-columns:\s*minmax\(0,\s*1fr\)/)
  })


  it('a coarse pointer keeps the preview rows a tap area apart', () => {
    const coarse = /@media \(pointer: coarse\)\s*\{\s*\.bin-player \.clip-preview\s*\{([^}]*)\}/.exec(css)
    assert.notEqual(coarse, null, 'a coarse-pointer rule for `.bin-player .clip-preview`')
    assert.match(coarse?.[1] ?? '', /row-gap:\s*var\(--s-4\)/)
  })
})

describe('binPlayer.css, the compact player (design D2)', () => {
  const compact = /@media \(width >= 960px\) and \(not \(pointer: coarse\)\)\s*\{([\s\S]*)\n  \}\n\}\s*$/.exec(css)

  it('is for the side pane with a fine pointer only, so a coarse pointer keeps its larger rows', () => {
    assert.notEqual(compact, null, 'a compact media block')
  })

  it('caps the picture box at 136 px and keeps the picture whole in it', () => {
    const stage = /\.bin-player \.preview-stage\s*\{([^}]*)\}/.exec(compact?.[1] ?? '')
    assert.match(stage?.[1] ?? '', /max-block-size:\s*8\.5rem/)
    assert.match(stage?.[1] ?? '', /inline-size:\s*100%/)
  })

  it('keeps the third row inside the least side pane (240 px: 223 px inside the padding)', () => {
    // 3 buttons of 51 to 85 px and three gaps: the column gap is the 4 px token and the compact buttons'
    // sides are 6 px, so the row needs about 212 px. With the 8 px gap and sides it needed 237 px and
    // the player's grid ran 14 px past the pane at 960 to 1160 px wide.
    const block = compact?.[1] ?? ''
    assert.match(/\.bin-player \.clip-preview\s*\{([^}]*)\}/.exec(block)?.[1] ?? '', /gap:\s*var\(--player-gap\) var\(--s-1\)/)
    assert.match(block, /btn-compact:not\(\.preview-original\)\s*\{[^}]*padding-inline:\s*calc\(var\(--s-1\) \* 1\.5\)/)
  })

  it('lays Skip cuts, Set From and Set To in one row and Play original on the picture', () => {
    const block = compact?.[1] ?? ''
    assert.match(block, /\.preview-actions\s*\{\s*display:\s*contents/)
    assert.match(block, /\.preview-original\s*\{[^}]*grid-area:\s*1 \/ 1 \/ 2 \/ -1/)
    assert.match(block, /\.preview-skip\s*\{\s*grid-column:\s*1/)
  })
})

describe('binPlayer.css, the empty player', () => {
  it('its rows below the picture hold their space without showing', () => {
    assert.match(css, /\.preview-ghost\s*\{\s*visibility:\s*hidden/)
  })
})

describe('the bin column (workspace.css)', () => {
  const ws = readFileSync(new URL('workspace/workspace.css', import.meta.url), 'utf8').replace(
    /\/\*[\s\S]*?\*\//g,
    '',
  )

  it('the bin column is a container on its own inline size', () => {
    const binbox = /\.ws-binbox\s*\{([^}]*)\}/.exec(ws)
    assert.match(binbox?.[1] ?? '', /container-type:\s*inline-size/)
  })
})
