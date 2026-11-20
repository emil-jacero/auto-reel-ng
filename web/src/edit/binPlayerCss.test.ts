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
  it('a coarse pointer keeps the preview rows a tap area apart', () => {
    const coarse = /@media \(pointer: coarse\)\s*\{\s*\.bin-player \.clip-preview\s*\{([^}]*)\}/.exec(css)
    assert.notEqual(coarse, null, 'a coarse-pointer rule for `.bin-player .clip-preview`')
    assert.match(coarse?.[1] ?? '', /row-gap:\s*var\(--s-4\)/)
  })
})
