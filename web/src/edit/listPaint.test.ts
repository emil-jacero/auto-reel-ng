import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

/*
 * Edit mode's clip list is cheap to repaint while the Timeline zooms, scrubs and plays
 * (edit-list-paint-cost): off-screen rows skip drawing with a size close to a drawn row's,
 * and the list is one composited layer. These rules are CSS, so their contract is read
 * from the stylesheets; what they do in a browser is measured with Playwright.
 */

const src = new URL('../', import.meta.url)
const editCss = readFileSync(new URL('edit/edit.css', src), 'utf8')

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

describe('the clip rows skip drawing off screen', () => {
  const all = rules(editCss)
  const skipping = all.filter((rule) => declaration(rule.body, 'content-visibility') === 'auto')

  it('each row of a clip list has content-visibility: auto with a remembered size', () => {
    assert.equal(skipping.length, 1, 'one rule')
    const [rule] = skipping
    assert.match(rule.selector, /^\.clip-order > \.clip-item:not\(/)
    assert.equal(declaration(rule.body, 'contain-intrinsic-size'), 'auto var(--clip-row-h)')
  })

  it('rows are drawn as before in a panel too narrow for their tools (under 20.25rem)', () => {
    const [rule] = skipping
    assert.deepEqual(rule.at, ['@layer screens', '@container (width >= 20.25rem)'])
  })

  it('a focused row, a drop target, the lifted row and a row dnd-kit moves are drawn whole', () => {
    const [rule] = skipping
    const excluded = /:not\(([^)]*\([^)]*\)[^)]*|[^)]*)\)/.exec(rule.selector)?.[1] ?? ''
    for (const state of [':focus-within', '[data-drop-before]', '[data-dragging]', "[style*='transform']"]) {
      assert.ok(excluded.includes(state), `excludes ${state}`)
    }
  })

  it('the estimate is the measured collapsed-row height in each container-query layout', () => {
    const estimate = (at: string | null) =>
      all
        .filter(
          (rule) =>
            rule.selector === '.clip-item' &&
            (at === null ? !rule.at.some((p) => p.startsWith('@container')) : rule.at.includes(at)),
        )
        .map((rule) => declaration(rule.body, '--clip-row-h'))
        .filter((value) => value !== null)
    // Rows of 68, 89, 77 and 99 px at a 16 px root (1024, 1280, 768 and 390 px windows), less
    // the 17 px of padding and border the content box leaves out.
    assert.deepEqual(estimate(null), ['3.1875rem'])
    assert.deepEqual(estimate('@container (width >= 64rem)'), ['4.5rem'])
    assert.deepEqual(estimate('@container (width < 58rem)'), ['3.75rem'])
    assert.deepEqual(estimate('@container (width < 30rem)'), ['5.125rem'])
  })

  it('a coarse pointer’s taller two-line row (30-58rem) has its own estimate', () => {
    const coarse = (selector: string, at: string, property: string) =>
      all
        .filter(
          (rule) =>
            rule.selector === selector &&
            rule.at.includes('@media (pointer: coarse)') &&
            rule.at.includes(at),
        )
        .map((rule) => declaration(rule.body, property))
        .filter((value) => value !== null)
    // 91 px rows at 600 and 768 px with a finger: the Cuts control's 14 px gap under the handle
    // comes on top of the fine pointer's 77 px row.
    const estimate = coarse('.clip-item', '@container (30rem <= width < 58rem)', '--clip-row-h')
    assert.deepEqual(estimate, ['4.625rem'])
    const [gap] = coarse('.clip-item > .cuts-toggle', '@container (width < 58rem)', 'margin-block-start')
    assert.equal(parseFloat(estimate[0]!) - 3.75, parseFloat(gap ?? 'NaN'))
  })

  it('the estimate is static CSS: no script writes it', () => {
    for (const file of sourceFiles(src)) {
      assert.doesNotMatch(readFileSync(file, 'utf8'), /--clip-row-h/, file.pathname)
    }
  })

  it('no stylesheet turns scroll anchoring off', () => {
    for (const file of cssFiles(src)) {
      assert.doesNotMatch(readFileSync(file, 'utf8'), /overflow-anchor\s*:\s*none/, file.pathname)
    }
  })
})

describe('the played list is one composited layer', () => {
  it('a chapter’s list of played clips has will-change: transform', () => {
    const list = rules(editCss).filter((rule) => rule.selector === '.edit-chapter > ol.clip-order')
    assert.deepEqual(
      list.map((rule) => declaration(rule.body, 'will-change')),
      ['transform'],
    )
  })
})
