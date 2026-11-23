import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { atBoundary, IDLE, standbyAim, standbyStep, standbyTarget } from './standby.ts'
import type { Standby, Target } from './standby.ts'

const plain = { durationMs: 10_000, spans: [] }
const T1: Target = { clip: 1, ms: 0 }
const A = '/api/proxy/1?v=1'

const loading: Standby = { kind: 'loading', target: T1, address: A }
const seeking: Standby = { kind: 'seeking', target: T1, address: A }
const ready: Standby = { kind: 'ready', target: T1, address: A }
const started: Standby = { kind: 'started', target: T1, address: A, playAt: 1234 }

describe('standbyTarget', () => {
  it('is the next clip at its start after a plain clip', () => {
    assert.deepEqual(standbyTarget([plain, plain, plain], [], 0), { clip: 1, ms: 0 })
  })

  it('is the end of the cut after a clip with a leading cut', () => {
    const lead = { durationMs: 10_000, spans: [{ from: 0, to: 1_500 }] }
    assert.deepEqual(standbyTarget([plain, lead], [], 0), { clip: 1, ms: 1_500 })
  })

  it('skips a clip cut whole', () => {
    const whole = { durationMs: 10_000, spans: [{ from: 0, to: 10_000 }] }
    assert.deepEqual(standbyTarget([plain, whole, plain], [], 0), { clip: 2, ms: 0 })
  })

  it('is null before a black-card gap', () => {
    assert.equal(standbyTarget([plain, plain], [{ clip: 1 }], 0), null)
  })

  it('is null at the last clip', () => {
    assert.equal(standbyTarget([plain, plain], [], 1), null)
  })

  it('is null when only clips cut whole follow', () => {
    const whole = { durationMs: 10_000, spans: [{ from: 0, to: 10_000 }] }
    assert.equal(standbyTarget([plain, whole], [], 0), null)
  })

  it('ignores a gap before a clip that is not the target', () => {
    const whole = { durationMs: 10_000, spans: [{ from: 0, to: 10_000 }] }
    assert.deepEqual(standbyTarget([plain, whole, plain], [{ clip: 1 }], 0), { clip: 2, ms: 0 })
  })
})

describe('standbyAim', () => {
  it('loads a new target from idle', () => {
    assert.deepEqual(standbyAim(IDLE, T1, A), loading)
  })

  it('leaves the same target at the same address as it is, whatever its state', () => {
    for (const s of [loading, seeking, ready, started]) {
      assert.equal(standbyAim(s, { ...T1 }, A), s)
    }
  })

  it('re-points to a changed target while loading', () => {
    assert.deepEqual(standbyAim(loading, { clip: 2, ms: 0 }, A), {
      kind: 'loading',
      target: { clip: 2, ms: 0 },
      address: A,
    })
  })

  it('re-points to a changed in-point or address', () => {
    assert.equal(standbyAim(ready, { clip: 1, ms: 40 }, A).kind, 'loading')
    assert.equal(standbyAim(ready, T1, '/other').kind, 'loading')
  })

  it('goes idle with no target', () => {
    assert.deepEqual(standbyAim(ready, null, A), IDLE)
  })
})

describe('standbyStep', () => {
  it('loading -> seeking on loadedmetadata -> ready on seeked', () => {
    const s1 = standbyStep(loading, 'loadedmetadata')
    assert.deepEqual(s1, seeking)
    assert.deepEqual(standbyStep(s1, 'seeked'), ready)
  })

  it('ignores seeked while loading, and loadedmetadata anywhere else', () => {
    assert.equal(standbyStep(loading, 'seeked'), loading)
    for (const s of [IDLE, seeking, ready, started]) {
      assert.equal(standbyStep(s, 'loadedmetadata'), s)
    }
  })

  it('ignores seeked when not seeking', () => {
    for (const s of [IDLE, ready, started]) {
      assert.equal(standbyStep(s, 'seeked'), s)
    }
  })

  it('started comes from ready only and keeps playAt', () => {
    assert.deepEqual(standbyStep(ready, { type: 'started', playAt: 1234 }), started)
    for (const s of [IDLE, loading, seeking, started]) {
      assert.equal(standbyStep(s, { type: 'started', playAt: 9 }), s)
    }
  })

  it('cancelled goes from started to seeking, never ready', () => {
    const s = standbyStep(started, 'cancelled')
    assert.deepEqual(s, seeking)
    assert.deepEqual(standbyStep(s, 'seeked'), ready)
  })

  it('ignores cancelled in every other state', () => {
    for (const s of [IDLE, loading, seeking, ready]) {
      assert.equal(standbyStep(s, 'cancelled'), s)
    }
  })

  it('goes idle on an error or a release, from every state', () => {
    for (const s of [IDLE, loading, seeking, ready, started]) {
      assert.deepEqual(standbyStep(s, 'error'), IDLE)
      assert.deepEqual(standbyStep(s, 'released'), IDLE)
    }
  })

  it('re-targets while loading, then follows only the new load', () => {
    const next = standbyAim(loading, { clip: 2, ms: 0 }, A)
    assert.equal(next.kind, 'loading')
    const seek = standbyStep(next, 'loadedmetadata')
    assert.equal(seek.kind === 'seeking' && seek.target.clip, 2)
  })

  it('a cancelled start that errors while seeking goes idle', () => {
    assert.deepEqual(standbyStep(standbyStep(started, 'cancelled'), 'error'), IDLE)
  })
})

describe('the wait path', () => {
  it('sends started from ready too, after seeked', () => {
    const afterSeek = standbyStep(seeking, 'seeked')
    assert.equal(afterSeek.kind, 'ready')
    assert.equal(standbyStep(afterSeek, { type: 'started', playAt: 5 }).kind, 'started')
  })

  it('cancelled during it, then atBoundary waits until seeked', () => {
    const wait = standbyStep(standbyStep(seeking, 'seeked'), { type: 'started', playAt: 5 })
    const cancelled = standbyStep(wait, 'cancelled')
    assert.equal(atBoundary(cancelled, T1, A), 'wait')
    assert.equal(atBoundary(standbyStep(cancelled, 'seeked'), T1, A), 'hand-over')
  })
})

describe('the lead', () => {
  it('started only from ready, and playAt kept', () => {
    const s = standbyStep(ready, { type: 'started', playAt: 77 })
    assert.equal(s.kind === 'started' && s.playAt, 77)
    assert.equal(standbyStep(seeking, { type: 'started', playAt: 77 }).kind, 'seeking')
  })

  it('a cancelled standby that is still seeking waits', () => {
    assert.equal(atBoundary(standbyStep(started, 'cancelled'), T1, A), 'wait')
  })
})

describe('atBoundary', () => {
  it('hands over from a ready or started standby holding the want', () => {
    assert.equal(atBoundary(ready, T1, A), 'hand-over')
    assert.equal(atBoundary(started, T1, A), 'hand-over')
  })

  it('waits for a loading or seeking standby holding the want', () => {
    assert.equal(atBoundary(loading, T1, A), 'wait')
    assert.equal(atBoundary(seeking, T1, A), 'wait')
  })

  it('loads when idle, or for another clip, in-point or address', () => {
    assert.equal(atBoundary(IDLE, T1, A), 'load')
    for (const s of [loading, seeking, ready, started]) {
      assert.equal(atBoundary(s, { clip: 2, ms: 0 }, A), 'load')
      assert.equal(atBoundary(s, { clip: 1, ms: 40 }, A), 'load')
      assert.equal(atBoundary(s, T1, '/other'), 'load')
    }
  })
})
