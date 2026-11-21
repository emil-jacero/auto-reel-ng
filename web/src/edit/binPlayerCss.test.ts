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

describe('the bin toolbar with the player hidden (workspace.css)', () => {
  const ws = readFileSync(new URL('workspace/workspace.css', import.meta.url), 'utf8').replace(
    /\/\*[\s\S]*?\*\//g,
    '',
  )

  it('Clear marks gives way to its icon in a pane narrower than 19rem, only while hidden', () => {
    const at = ws.indexOf('@container (width < 19rem)')
    assert.notEqual(at, -1, 'a container query for the narrow pane')
    const query = ws.slice(at, at + 900)
    assert.match(query, /\.mark-line\[data-player='hidden'\] \.mark-clear-icon/)
    assert.match(query, /\.mark-line\[data-player='hidden'\] \.mark-clear-words/)
  })

  it('the bin column is the container the query asks', () => {
    const binbox = /\.ws-binbox\s*\{([^}]*)\}/.exec(ws)
    assert.match(binbox?.[1] ?? '', /container-type:\s*inline-size/)
  })
})
