import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

/* The design document names the change where the card blocks are described (D-20, §4.10, §6). */
describe('docs/high-level-design.md', () => {
  const text = readFileSync(new URL('../../../docs/high-level-design.md', import.meta.url), 'utf8')

  it('names title-card-blocks in D-20, §4.10 and §6', () => {
    const lines = text.split('\n')
    const at = lines.flatMap((line, i) => (line.includes('title-card-blocks') ? [i] : []))
    const d20 = lines.findIndex((line) => line.startsWith('- **D-20'))
    assert.ok(d20 > 0)
    assert.ok(at.some((i) => i > d20 && i < d20 + 220), 'D-20 names it')
    assert.ok(at.some((i) => i > 380 && i < 440), '§4.10 names it')
    assert.ok(at.some((i) => i > 700 && i < 760), '§6 names it')
  })
})
