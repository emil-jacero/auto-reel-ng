import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { createCoalescer } from './scrub.ts'

/*
 * The seek coalescer (`scrub.ts`), run by `npm test` with fake `load` and `seek`: at most
 * one in flight, always ending at the last target.
 */

function rig() {
  const calls: string[] = []
  const c = createCoalescer({
    load: (clip) => calls.push(`load ${clip}`),
    seek: (ms) => calls.push(`seek ${ms}`),
  })
  return { c, calls }
}

describe('createCoalescer', () => {
  it('loads a clip once and then seeks it', () => {
    const { c, calls } = rig()
    c.request({ clip: 2, ms: 500 })
    assert.deepEqual(calls, ['load 2'])
    c.settled()
    assert.deepEqual(calls, ['load 2', 'seek 500'])
    c.settled()
    assert.equal(c.busy(), false)
  })

  it('answers 100 requests made while a seek is in flight with one more seek, to the last', () => {
    const { c, calls } = rig()
    c.request({ clip: 0, ms: 0 })
    c.settled() // loaded
    c.settled() // seeked to 0
    calls.length = 0
    c.request({ clip: 0, ms: 40 })
    for (let ms = 80; ms <= 4000; ms += 40) {
      c.request({ clip: 0, ms })
    }
    assert.deepEqual(calls, ['seek 40'])
    c.settled()
    assert.deepEqual(calls, ['seek 40', 'seek 4000'])
    c.settled()
    assert.deepEqual(calls, ['seek 40', 'seek 4000'])
  })

  it('takes the last clip of a scrub across three, loading only what it lands on', () => {
    const { c, calls } = rig()
    c.request({ clip: 0, ms: 100 })
    c.request({ clip: 1, ms: 200 })
    c.request({ clip: 2, ms: 300 })
    assert.deepEqual(calls, ['load 0'])
    c.settled()
    // the clip 0 load settled: the target is in clip 2 now, so clip 1 is never loaded
    assert.deepEqual(calls, ['load 0', 'load 2'])
    c.settled()
    assert.deepEqual(calls, ['load 0', 'load 2', 'seek 300'])
    assert.equal(c.busy(), true)
  })

  it('seeks nothing for a request equal to where the video is', () => {
    const { c, calls } = rig()
    c.request({ clip: 0, ms: 120 })
    c.settled()
    c.settled()
    calls.length = 0
    c.request({ clip: 0, ms: 120 })
    assert.deepEqual(calls, [])
    assert.equal(c.busy(), false)
  })

  it('measures from where the video played to, after sync', () => {
    const { c, calls } = rig()
    c.request({ clip: 0, ms: 0 })
    c.settled()
    c.settled()
    calls.length = 0
    c.sync({ clip: 0, ms: 5000 })
    c.request({ clip: 0, ms: 5000 })
    assert.deepEqual(calls, [])
    c.request({ clip: 0, ms: 0 })
    assert.deepEqual(calls, ['seek 0'])
  })

  it('does not take the video back to an older request after it played on, then settled a seek of its own', () => {
    const { c, calls } = rig()
    c.request({ clip: 0, ms: 5000 })
    c.settled()
    c.settled()
    calls.length = 0
    // it played to 8000, and a cut skip there seeked by itself
    c.sync({ clip: 0, ms: 8000 })
    c.settled()
    assert.deepEqual(calls, [])
    assert.equal(c.busy(), false)
  })

  it('ignores a sync while a load or seek is in flight', () => {
    const { c, calls } = rig()
    c.request({ clip: 0, ms: 100 })
    c.sync({ clip: 0, ms: 9000 })
    c.settled()
    assert.deepEqual(calls, ['load 0', 'seek 100'])
  })

  it('loads the clip again after a failed load, on the next request only', () => {
    const { c, calls } = rig()
    c.request({ clip: 1, ms: 0 })
    c.failed()
    assert.deepEqual(calls, ['load 1'])
    assert.equal(c.busy(), false)
    c.request({ clip: 1, ms: 0 })
    assert.deepEqual(calls, ['load 1', 'load 1'])
  })

  it('loads again after a reset, to the wanted target', () => {
    const { c, calls } = rig()
    c.request({ clip: 1, ms: 700 })
    c.settled()
    c.settled()
    calls.length = 0
    c.reset()
    assert.deepEqual(calls, ['load 1'])
    c.settled()
    assert.deepEqual(calls, ['load 1', 'seek 700'])
  })
})
