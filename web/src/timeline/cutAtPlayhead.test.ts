import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { addCutAtPlayhead, cutAtPlayhead } from './cutAtPlayhead.ts'
import type { CutAtPlayheadDeps } from './cutAtPlayhead.ts'

const none: { in: number; out: number }[] = []

describe('cutAtPlayhead', () => {
  it('runs a second from the playhead', () => {
    assert.deepEqual(cutAtPlayhead(none, 2000, 'a.mp4', 6), { ok: true, span: { in: 2, out: 3 } })
  })
  it('stops at the clip’s end and at the next cut', () => {
    assert.deepEqual(cutAtPlayhead(none, 5500, 'a.mp4', 6), { ok: true, span: { in: 5.5, out: 6 } })
    assert.deepEqual(cutAtPlayhead([{ in: 2.4, out: 3 }], 2000, 'a.mp4', 6), {
      ok: true,
      span: { in: 2, out: 2.4 },
    })
  })
  it('is refused inside a cut, at the end, and outside the clip', () => {
    for (const [cuts, at] of [
      [[{ in: 1, out: 3 }], 2000],
      [none, 6000],
      [none, null],
    ] as const) {
      assert.equal(cutAtPlayhead(cuts, at, 'a.mp4', 6).ok, false)
    }
  })
})

describe('addCutAtPlayhead', () => {
  // Two clips: the playhead is in the first (index 0) or the second.
  const clip = (name: string, durationMs: number) =>
    ({ identity: `Kvällen/${name}`, name, facts: { durationMs } }) as unknown as CutAtPlayheadDeps['clip']
  const clips = [clip('a.mp4', 6000), clip('b.mp4', 6000)]
  const setup = (at: { clip: number; ms: number; card?: number }, listed: { in: number; out: number }[] = []) => {
    const calls: string[] = []
    const editing = {
      listed: () => listed,
      onAdd: (identity: string, span: { in: number; out: number }) => calls.push(`add ${identity} ${span.in}-${span.out}`),
      announce: (words: string) => calls.push(`say ${words}`),
    }
    return {
      calls,
      deps: { clip: clips[1], clips, editing, playhead: { get: () => at } } as unknown as CutAtPlayheadDeps,
    }
  }

  it('adds the cut and announces it, as the Clip tab says it', () => {
    const { calls, deps } = setup({ clip: 1, ms: 2000 })
    assert.equal(addCutAtPlayhead(deps), null)
    assert.deepEqual(calls, [
      'add Kvällen/b.mp4 2-3',
      'say Cut 0:02 to 0:03 added to b.mp4. 1 cut, 1 second cut out.',
    ])
  })
  it('refuses with the words, announces them and adds nothing', () => {
    const { calls, deps } = setup({ clip: 0, ms: 2000 })
    const words = 'Move the playhead into b.mp4 to cut there.'
    assert.equal(addCutAtPlayhead(deps), words)
    assert.deepEqual(calls, [`say ${words}`])
  })
  it('refuses a playhead on a card', () => {
    const { calls, deps } = setup({ clip: 1, ms: 0, card: 0 })
    assert.notEqual(addCutAtPlayhead(deps), null)
    assert.equal(calls.length, 1)
  })
})
