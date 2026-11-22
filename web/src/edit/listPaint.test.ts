import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

/*
 * The bin's list is cheap to repaint while the Timeline zooms, scrubs and plays
 * (edit-list-paint-cost, `plain-clip-bin` D2): off-screen rows skip drawing, each keeping the block
 * size of a drawn row. These rules are CSS, so their contract is read from the stylesheets; what
 * they do in a browser is measured with Playwright.
 */

const src = new URL('../', import.meta.url)
const binCss = readFileSync(new URL('edit/clipBin.css', src), 'utf8')

type Rule = { at: string[]; selector: string; body: string }

/** The style rules of a stylesheet, each with the at-rule and nesting preludes around it. */
function rules(css: string): Rule[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const out: Rule[] = []
  const stack: { prelude: string; body: string }[] = []
  let token = ''
  for (const char of text) {
    if (char === '{') {
      stack.push({ prelude: token.trim(), body: '' })
      token = ''
    } else if (char === '}') {
      const block = stack.pop()
      if (block === undefined) {
        throw new Error('unbalanced braces')
      }
      block.body += token
      token = ''
      if (!block.prelude.startsWith('@')) {
        out.push({ at: stack.map((outer) => outer.prelude), selector: block.prelude, body: block.body })
      }
    } else if (char === ';' && stack.length > 0) {
      stack[stack.length - 1].body += token + ';'
      token = ''
    } else {
      token += char
    }
  }
  return out
}

function declaration(body: string, property: string): string | null {
  const match = new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+);`).exec(body)
  return match === null ? null : match[1].trim()
}

function cssFiles(dir: URL): URL[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? cssFiles(new URL(`${entry.name}/`, dir))
      : entry.name.endsWith('.css')
        ? [new URL(entry.name, dir)]
        : [],
  )
}

function sourceFiles(dir: URL): URL[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? sourceFiles(new URL(`${entry.name}/`, dir))
      : /\.tsx?$/.test(entry.name) && !entry.name.endsWith('.test.ts')
        ? [new URL(entry.name, dir)]
        : [],
  )
}

describe('the bin rows skip drawing off screen', () => {
  const all = rules(binCss)
  const rows = all.filter((rule) => rule.selector === '.bin-row')
  const skipping = all.filter((rule) => declaration(rule.body, 'content-visibility') === 'auto')

  it('each row has a fixed block size, and skips drawing off screen with that size remembered', () => {
    assert.equal(rows.length, 1, 'one `.bin-row` rule')
    assert.equal(declaration(rows[0].body, 'block-size'), 'var(--bin-row-h)')
    assert.equal(skipping.length, 1, 'one skipping rule')
    assert.equal(skipping[0].selector, '&:not(:focus-within)')
    assert.equal(declaration(skipping[0].body, 'contain-intrinsic-block-size'), 'auto var(--bin-row-h)')
  })

  it('a focused row is drawn whole, so its ring and what it scrolls to are never skipped', () => {
    assert.match(skipping[0].selector, /:not\(:focus-within\)/)
  })

  it('the row height is a token: 40 px with a fine pointer, 48 px with a coarse one', () => {
    const tokens = all.filter((rule) => declaration(rule.body, '--bin-row-h') !== null)
    assert.deepEqual(
      tokens.map((rule) => [rule.at.join(' / '), declaration(rule.body, '--bin-row-h')]),
      [
        ['@layer screens', '2.5rem'],
        ['@layer screens / @media (pointer: coarse)', '3rem'],
      ],
    )
  })

  it('the row height is static CSS: no script writes it', () => {
    for (const file of sourceFiles(src)) {
      assert.doesNotMatch(readFileSync(file, 'utf8'), /--bin-row-h/, file.pathname)
    }
  })

  it('no stylesheet turns scroll anchoring off', () => {
    for (const file of cssFiles(src)) {
      assert.doesNotMatch(readFileSync(file, 'utf8'), /overflow-anchor\s*:\s*none/, file.pathname)
    }
  })
})
