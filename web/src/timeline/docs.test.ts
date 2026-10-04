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
    const s410 = lines.findIndex((line) => line.startsWith('### 4.10 '))
    const s411 = lines.findIndex((line) => line.startsWith('### 4.11 '))
    assert.ok(s410 > 0 && s411 > s410)
    assert.ok(at.some((i) => i > s410 && i < s411), '§4.10 names it')
    const s6 = lines.findIndex((line) => line.startsWith('## 6. '))
    const s7 = lines.findIndex((line) => line.startsWith('## 7. '))
    assert.ok(s6 > 0 && s7 > s6)
    assert.ok(at.some((i) => i > s6 && i < s7), '§6 names it')
  })
})

/* The design document names the change in D-20, §4.10 and §6 (title-card-duration-drag). */
describe('docs/high-level-design.md and title-card-duration-drag', () => {
  const text = readFileSync(new URL('../../../docs/high-level-design.md', import.meta.url), 'utf8')

  it('names title-card-duration-drag in D-20, §4.10 and §6', () => {
    const lines = text.split('\n')
    const at = lines.flatMap((line, i) => (line.includes('title-card-duration-drag') ? [i] : []))
    const d20 = lines.findIndex((line) => line.startsWith('- **D-20'))
    assert.ok(d20 > 0)
    assert.ok(at.some((i) => i > d20 && i < d20 + 260), 'D-20 names it')
    const s410 = lines.findIndex((line) => line.startsWith('### 4.10 '))
    const s411 = lines.findIndex((line) => line.startsWith('### 4.11 '))
    assert.ok(s410 > 0 && s411 > s410)
    assert.ok(at.some((i) => i > s410 && i < s411), '§4.10 names it')
    const s6 = lines.findIndex((line) => line.startsWith('## 6. '))
    const s7 = lines.findIndex((line) => line.startsWith('## 7. '))
    assert.ok(s6 > 0 && s7 > s6)
    assert.ok(at.some((i) => i > s6 && i < s7), '§6 names it')
  })
})

/* The design document names the change in D-20, D-25, §4.10 and §6 (title-card-toggle). */
describe('docs/high-level-design.md and title-card-toggle', () => {
  const text = readFileSync(new URL('../../../docs/high-level-design.md', import.meta.url), 'utf8')

  it('names title-card-toggle in D-20, D-25, §4.10 and §6', () => {
    const lines = text.split('\n')
    const at = lines.flatMap((line, i) => (line.includes('title-card-toggle') ? [i] : []))
    const start = (prefix: string) => lines.findIndex((line) => line.startsWith(prefix))
    const within = (from: number, to: number) => at.some((i) => i > from && i < to)
    const d20 = start('- **D-20')
    const d21 = start('- **D-21')
    assert.ok(d20 > 0 && d21 > d20)
    assert.ok(within(d20, d21), 'D-20 names it')
    const d25 = start('- **D-25')
    const d24 = start('- **D-24')
    assert.ok(d25 > 0 && d24 > d25)
    assert.ok(within(d25, d24), 'D-25 names it')
    const s410 = start('### 4.10 ')
    const s411 = start('### 4.11 ')
    assert.ok(s410 > 0 && s411 > s410)
    assert.ok(within(s410, s411), '§4.10 names it')
    const s6 = start('## 6. ')
    const s7 = start('## 7. ')
    assert.ok(s6 > 0 && s7 > s6)
    assert.ok(within(s6, s7), '§6 names it')
  })

  it('the README names the switch’s files', () => {
    const readme = readFileSync(new URL('../../README.md', import.meta.url), 'utf8')
    assert.match(readme, /decorators\.ts/)
    assert.match(readme, /EventTab\.tsx/)
  })
})

/* The design document names the change in D-15, D-20, D-26, §4.9, §4.10 and §6 (event-poster-gui). */
describe('docs/high-level-design.md and event-poster-gui', () => {
  const text = readFileSync(new URL('../../../docs/high-level-design.md', import.meta.url), 'utf8')

  it('names event-poster-gui in D-15, D-20, §4.9, §4.10 and §6', () => {
    const lines = text.split('\n')
    const at = lines.flatMap((line, i) => (line.includes('event-poster-gui') ? [i] : []))
    const between = (from: string, to: string) => {
      const a = lines.findIndex((line) => line.startsWith(from))
      const b = lines.findIndex((line) => line.startsWith(to))
      assert.ok(a > 0 && b > a, `${from} .. ${to}`)
      return at.some((i) => i > a && i < b)
    }
    assert.ok(between('### 4.9 ', '### 4.10 '), '§4.9 names it')
    assert.ok(between('### 4.10 ', '### 4.11 '), '§4.10 names it')
    assert.ok(between('## 6. ', '## 7. '), '§6 names it')
    assert.ok(between('- **D-15', '- **D-16'), 'D-15 names it')
    assert.ok(between('- **D-20', '- **D-21'), 'D-20 names it')
  })
})

/* The design document names the change in D-20, D-24, §4.10 and §6 (timeline-plays-cards), and no text says the Timeline plays footage only. */
describe('docs/high-level-design.md and timeline-plays-cards', () => {
  const text = readFileSync(new URL('../../../docs/high-level-design.md', import.meta.url), 'utf8')

  it('names timeline-plays-cards in D-20, D-24, §4.10 and §6', () => {
    const lines = text.split('\n')
    const at = lines.flatMap((line, i) => (line.includes('timeline-plays-cards') ? [i] : []))
    const between = (from: string, to: string) => {
      const a = lines.findIndex((line) => line.startsWith(from))
      const b = lines.findIndex((line) => line.startsWith(to))
      assert.ok(a > 0 && b > a, `${from} .. ${to}`)
      return at.some((i) => i > a && i < b)
    }
    assert.ok(between('### 4.10 ', '### 4.11 '), '§4.10 names it')
    assert.ok(between('## 6. ', '## 7. '), '§6 names it')
    assert.ok(between('- **D-20', '- **D-21'), 'D-20 names it')
    assert.ok(between('- **D-24', '- **D-23'), 'D-24 names it as a second client of the preview')
  })

  it('says nowhere that the Timeline plays footage only, or crosses a card without time', () => {
    assert.doesNotMatch(text, /plays footage only|crosses a black card without time/i)
  })
})

/* The design document names help-text-declutter in §4.10 and no longer describes a permanent movie line. */
describe('docs/high-level-design.md and help-text-declutter', () => {
  const text = readFileSync(new URL('../../../docs/high-level-design.md', import.meta.url), 'utf8')

  it('names help-text-declutter in §4.10, §6 and D-20', () => {
    const lines = text.split('\n')
    const at = lines.flatMap((line, i) => (line.includes('help-text-declutter') ? [i] : []))
    const s410 = lines.findIndex((line) => line.startsWith('### 4.10 '))
    const s411 = lines.findIndex((line) => line.startsWith('### 4.11 '))
    assert.ok(at.some((i) => i > s410 && i < s411), '§4.10 names it')
    const s6 = lines.findIndex((line) => line.startsWith('## 6. '))
    const s7 = lines.findIndex((line) => line.startsWith('## 7. '))
    assert.ok(at.some((i) => i > s6 && i < s7), '§6 names it')
    const d20 = lines.findIndex((line) => line.startsWith('- **D-20'))
    assert.ok(at.some((i) => i > d20 && i < d20 + 220), 'D-20 names it')
  })

  it('no longer describes a permanent "Movie … of … of footage" line', () => {
    assert.ok(!/Movie 3:12\.00 of 3:45\.00 of footage/.test(text))
  })
})
