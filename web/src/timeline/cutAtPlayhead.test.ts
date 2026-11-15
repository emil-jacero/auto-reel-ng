import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { cutAtPlayhead } from './cutAtPlayhead.ts'

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
