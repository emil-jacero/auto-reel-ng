import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  earlyTimes,
  frameClock,
  FRESH,
  keptEndOf,
  leadOf,
  median,
  preRollOf,
  resetCalibration,
  withAlignmentSample,
  withLeadSample,
} from './lead.ts'
import type { Calibration } from './lead.ts'

const leads = (values: number[]): Calibration => values.reduce(withLeadSample, FRESH)

describe('LEAD', () => {
  it('is 40 ms before any sample', () => {
    assert.equal(leadOf(FRESH), 40)
  })

  it('is the median of the last 9, older ones dropped', () => {
    // ten samples: the first (1000) falls out of the window
    const c = leads([1000, 20, 22, 24, 26, 28, 30, 32, 34, 36])
    assert.equal(c.leads.length, 9)
    assert.equal(leadOf(c), 28)
  })

  it('clamps a huge sample to 250 and a negative one to 0', () => {
    assert.equal(leadOf(leads([900])), 250)
    assert.equal(leadOf(leads([-30])), 0)
  })
})

describe('P', () => {
  const need = (c: Calibration, error: number, used: number, inMs = 1000) =>
    withAlignmentSample(c, error, used, inMs)

  it('is 0 before any sample', () => {
    assert.equal(preRollOf(FRESH, 1000), 0)
  })

  it('a Chrome-like series (errors near 0) keeps P at 0', () => {
    let c = FRESH
    for (const error of [0, 2, -1, 1, 0, -2, 3, 0, 1, -1]) {
      c = need(c, error, preRollOf(c, 1000))
    }
    assert.ok(preRollOf(c, 1000) <= 1)
  })

  it('a Firefox-like series (about +28 ms) raises it', () => {
    const c = need(FRESH, 28, 0)
    assert.equal(preRollOf(c, 1000), 28)
  })

  it('clamps to 40 ms, and to the incoming in-point (0 at IN = 0)', () => {
    const c = need(FRESH, 90, 0)
    assert.equal(preRollOf(c, 1000), 40)
    assert.equal(preRollOf(c, 12), 12)
    assert.equal(preRollOf(c, 0), 0)
  })

  it('IN = 0 gives no sample', () => {
    assert.equal(withAlignmentSample(FRESH, 28, 0, 0), FRESH)
  })

  it('a negative error at P = 0 samples a need of 0, never below', () => {
    const c = need(FRESH, -15, 0)
    assert.deepEqual(c.needs, [0])
  })

  it('closed-loop Firefox: the browser skips 28 - P_applied; P converges to about 28 and holds', () => {
    let c = FRESH
    const ps: number[] = []
    for (let i = 0; i < 24; i += 1) {
      const applied = preRollOf(c, 1000)
      const error = 28 - applied // the browser's skip, T ahead
      c = need(c, error, applied)
      ps.push(preRollOf(c, 1000))
    }
    assert.ok(Math.abs(ps[ps.length - 1] - 28) <= 1000 / 25 / 2)
    // after the first hand-over it is already there and does not fall back toward 0
    for (const p of ps.slice(1)) {
      assert.ok(Math.abs(p - 28) < 1, `P = ${p}`)
    }
  })

  it('overshoot: P starting above the need comes back down', () => {
    // five hand-overs that needed 40 (the window's median is 40) ...
    let c = FRESH
    for (let i = 0; i < 5; i += 1) {
      c = need(c, 40, 0)
    }
    assert.equal(preRollOf(c, 1000), 40)
    // ... then the need is 28: applied 40 gives error -12, needed 28
    for (let i = 0; i < 5; i += 1) {
      const applied = preRollOf(c, 1000)
      c = need(c, 28 - applied, applied)
    }
    assert.equal(preRollOf(c, 1000), 28)
  })
})

describe('reset', () => {
  it('returns LEAD to 40 and P to 0 (devicechange)', () => {
    let c = withAlignmentSample(leads([120, 130]), 28, 0, 1000)
    assert.equal(leadOf(c), 125)
    assert.equal(preRollOf(c, 1000), 28)
    c = resetCalibration()
    assert.equal(leadOf(c), 40)
    assert.equal(preRollOf(c, 1000), 0)
  })
})

describe('median', () => {
  it('takes the middle, or the mean of the middle two', () => {
    assert.equal(median([3, 1, 2]), 2)
    assert.equal(median([4, 1, 2, 3]), 2.5)
  })
})

describe('frameClock', () => {
  it('is the median of callback minus media time over the last second', () => {
    const samples = [
      { atMs: 100, mediaMs: 0 }, // too old at now = 1500
      { atMs: 1000, mediaMs: 40 }, // 960
      { atMs: 1040, mediaMs: 80 }, // 960
      { atMs: 1080, mediaMs: 100 }, // 980
    ]
    assert.equal(frameClock(samples, 1500), 960)
  })

  it('is null with no sample in the last second', () => {
    assert.equal(frameClock([{ atMs: 0, mediaMs: 0 }], 5000), null)
  })
})

describe('earlyTimes', () => {
  // clock: callback time = media time + 1000; S's kept end at 5000 ms of its media
  it('starts one lead before the kept end and decides one frame interval before it', () => {
    const t = earlyTimes(1000, 5000, 40, 40, 2000)
    assert.equal(t.startAt, 5960)
    assert.equal(t.decideAt, 5960)
    assert.equal(t.startNow, false)
    const long = earlyTimes(1000, 5000, 120, 40, 2000)
    assert.equal(long.startAt, 5880)
    assert.equal(long.decideAt, 5960)
  })

  it('a start time already past starts at once', () => {
    const t = earlyTimes(1000, 5000, 40, 40, 5990)
    assert.equal(t.startAt, 5990)
    assert.equal(t.startNow, true)
    assert.ok(t.decideAt >= t.startAt)
  })

  it('a lead longer than the time left starts at once and still decides after it', () => {
    const t = earlyTimes(1000, 5000, 250, 40, 5900)
    assert.equal(t.startNow, true)
    assert.equal(t.startAt, 5900)
    assert.equal(t.decideAt, 5960)
  })

  it('decideAt is one frame interval before the kept end', () => {
    const t = earlyTimes(1000, 5000, 200, 33.3, 0)
    assert.ok(Math.abs(t.decideAt - (6000 - 33.3)) < 1e-9)
  })
})

describe('keptEndOf', () => {
  it('is the length with no cut at the end', () => {
    assert.equal(keptEndOf([], 6000), 6000)
    assert.equal(keptEndOf([{ from: 1000, to: 2000 }], 6000), 6000)
  })
  it('is the start of a cut that runs to the end', () => {
    assert.equal(keptEndOf([{ from: 1000, to: 2000 }, { from: 5000, to: 6000 }], 6000), 5000)
    assert.equal(keptEndOf([{ from: 5000, to: 5950 }], 6000), 5000)
  })
})
