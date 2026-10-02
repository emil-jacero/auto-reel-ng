import assert from 'node:assert/strict'
import { test } from 'node:test'

import { checkCut, clipLength, lengthHint, pastEnd } from './times.ts'

test('the preview length wins over the detail duration', () => {
  assert.equal(clipLength(6.08, 6.02), 6.08)
})

test('the detail duration is the length before any preview', () => {
  assert.equal(clipLength(undefined, 6.02), 6.02)
})

test('with neither source the length is unknown', () => {
  assert.equal(clipLength(undefined, null), undefined)
  assert.equal(clipLength(undefined, undefined), undefined)
})

test('a null or unusable duration is never a length of zero', () => {
  for (const duration of [null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.equal(clipLength(undefined, duration), undefined)
  }
})

test('a cut past the detail duration is refused at the end field, one up to it is accepted', () => {
  const length = clipLength(undefined, 6.02)
  const refused = checkCut([], '5', '7', length)
  assert.equal(refused.ok, false)
  if (!refused.ok) {
    assert.equal(refused.refusal.kind, 'past-end')
    assert.equal(refused.refusal.field, 'end')
  }
  assert.deepEqual(checkCut([], '5', '6.02', length), { ok: true, in: 5, out: 6.02 })
})

test('without a length a cut past the end passes, as before', () => {
  assert.equal(checkCut([], '5', '7', clipLength(undefined, null)).ok, true)
})

test('a listed cut past the detail duration is marked', () => {
  assert.equal(pastEnd({ in: 3723.125, out: 3725.5 }, 6.02), true)
  assert.equal(pastEnd({ in: 5, out: 6.02 }, 6.02), false)
})

test('the hint names where the clip ends and whose length it is', () => {
  assert.match(lengthHint(6.02, false), /ends at 0:06\.02, as measured for its thumbnail/)
  assert.match(lengthHint(6.08), /ends at 0:06\.08, as this browser reads it/)
})
