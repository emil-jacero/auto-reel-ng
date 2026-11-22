import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createTrackCuts, trackCutsOf } from './trackCuts.ts'
import type { TrackCutsView } from './trackCuts.ts'

function view(over: Partial<TrackCutsView> = {}): TrackCutsView {
  return {
    drawn: new Set(['a.mp4']),
    selected: null,
    select: () => undefined,
    selectClip: () => undefined,
    add: () => null,
    ...over,
  }
}

describe('the track-cuts bridge', () => {
  it('tells its readers of each new view, once, and not of the same one again', () => {
    const bridge = createTrackCuts()
    let calls = 0
    const off = bridge.subscribe(() => {
      calls += 1
    })
    const first = view()
    bridge.set(first)
    bridge.set(first)
    assert.equal(calls, 1)
    assert.equal(bridge.get(), first)
    bridge.set(null)
    assert.equal(calls, 2)
    off()
    bridge.set(view())
    assert.equal(calls, 2)
  })

  it('offers nothing for a clip the track does not draw, or while there is no track', () => {
    assert.equal(trackCutsOf(null, 'a.mp4'), null)
    assert.equal(trackCutsOf(view(), 'b.mp4'), null)
  })

  it('carries the clip into each call and names the selected cut only for its own clip', () => {
    const calls: string[] = []
    const v = view({
      drawn: new Set(['a.mp4', 'b.mp4']),
      selected: { identity: 'b.mp4', key: 'r1' },
      select: (identity, key) => calls.push(`select ${identity} ${key}`),
      selectClip: (identity) => calls.push(`clip ${identity}`),
      add: (identity) => (calls.push(`add ${identity}`), 'No.'),
    })
    const a = trackCutsOf(v, 'a.mp4')
    const b = trackCutsOf(v, 'b.mp4')
    assert.equal(a?.selectedKey, null)
    assert.equal(b?.selectedKey, 'r1')
    a?.select('r0')
    b?.selectClip()
    assert.equal(b?.add(), 'No.')
    assert.deepEqual(calls, ['select a.mp4 r0', 'clip b.mp4', 'add b.mp4'])
  })
})
