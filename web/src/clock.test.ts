import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { formatTime } from './cuts/times.ts'
import { clockChars, clockScale, formatClock, tenthsCell } from './clock.ts'
import type { ClockScale } from './clock.ts'

const at = (ms: number | null, scale: ClockScale) => formatClock(ms, scale)

describe('the clock writes a running time to a fixed number of digits', () => {
  it('keeps the trailing zero that formatTime drops', () => {
    const scale = clockScale(150_000)
    assert.equal(at(0, scale), '0:00.00')
    assert.equal(at(960, scale), '0:00.96')
    assert.equal(at(62_400, scale), '1:02.40')
    assert.equal(formatTime(62.4), '1:02.4') // the cut's form is untouched
  })

  it('cuts down, never rounds up, so a position never reads past its total', () => {
    const scale = clockScale(39_996)
    assert.equal(at(39_996, scale), '0:39.99')
    assert.equal(at(39_999, scale), '0:39.99')
    assert.equal(at(1_999, scale), '0:01.99')
  })

  it('has the same length for every millisecond of the clip, for five scales', () => {
    for (const longest of [6_020, 39_840, 599_990, 750_000, 3_723_450]) {
      const scale = clockScale(longest)
      const lengths = new Set<number>()
      for (let ms = 0; ms <= longest; ms += longest > 700_000 ? 37 : 1) {
        lengths.add(at(ms, scale).length)
      }
      lengths.add(at(longest, scale).length)
      assert.deepEqual([...lengths], [clockChars(scale)], `scale of ${longest} ms`)
    }
  })

  it('does not change length from 9.99 to 10.00 s, nor from 9:59 to 10:00', () => {
    const short = clockScale(12_000)
    assert.equal(at(9_999, short), '0:09.99')
    assert.equal(at(10_000, short), '0:10.00')
    const long = clockScale(750_000)
    assert.equal(at(599_990, long), '09:59.99')
    assert.equal(at(600_000, long), '10:00.00')
    assert.equal(at(0, long), '00:00.00')
    const tenMinutesLess = clockScale(599_990)
    assert.equal(at(599_990, tenMinutesLess), '9:59.99')
  })

  it('writes hours in every value of a readout or in none', () => {
    const hours = clockScale(3_723_450)
    assert.equal(at(3_600_000, hours), '1:00:00.00')
    assert.equal(at(0, hours), '0:00:00.00')
    assert.equal(at(3_723_450, hours), '1:02:03.45')
    const ten = clockScale(10 * 3_600_000 + 1)
    assert.equal(at(5_000, ten), '00:00:05.00')
    assert.equal(clockChars(ten), 11)
    assert.equal(clockChars(clockScale(3_599_999)), 8) // 59:59.99, no hours
  })

  it('writes three decimals for a trim', () => {
    const scale = clockScale(6_020, 3)
    assert.equal(at(1_250, scale), '0:01.250')
    assert.equal(at(1_300, scale), '0:01.300')
    assert.equal(at(1_250, scale).length, at(1_300, scale).length)
    assert.equal(clockChars(scale), 8)
  })

  it('writes an unknown time as dashes in the same places', () => {
    const short = clockScale(20_640)
    assert.equal(at(null, short), '-:--.--')
    assert.equal(at(null, short).length, clockChars(short))
    const long = clockScale(750_000)
    assert.equal(at(null, long), '--:--.--')
    assert.equal(at(null, long).length, clockChars(long))
    assert.equal(at(null, clockScale(3_723_450)), '-:--:--.--')
    assert.equal(at(null, clockScale(6_020, 3)), '-:--.---')
  })

  it('shows a value above the longest as the longest', () => {
    const scale = clockScale(20_640)
    assert.equal(at(20_641, scale), at(20_640, scale))
    assert.equal(at(999_999, scale), '0:20.64')
  })

  it('refuses a time that is not one', () => {
    const scale = clockScale(20_640)
    for (const bad of [-1, Number.NaN, Number.POSITIVE_INFINITY]) {
      assert.throws(() => at(bad, scale), RangeError)
      assert.throws(() => clockScale(bad), RangeError)
    }
  })
})

describe('tenthsCell', () => {
  it('writes one decimal in a cell as wide as the longest value, whatever the value', () => {
    const widths = new Set<number>()
    for (let t = 5; t <= 600; t += 1) {
      widths.add(tenthsCell(t, 600).ch)
    }
    assert.deepEqual([...widths], [4])
    assert.equal(tenthsCell(40, 600).text, '4.0')
    assert.equal(tenthsCell(5, 600).text, '0.5')
    assert.equal(tenthsCell(900, 600).text, '60.0')
  })

  it('refuses a value that is not a time', () => {
    assert.throws(() => tenthsCell(-1, 600), RangeError)
    assert.throws(() => tenthsCell(Number.NaN, 600), RangeError)
  })
})
