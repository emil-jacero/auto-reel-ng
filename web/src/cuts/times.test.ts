import assert from 'node:assert/strict'
import { describe, it, test } from 'node:test'

import {
  checkCut,
  checkTrim,
  clipLength,
  CUT_HINT,
  fieldName,
  handleName,
  handleValueText,
  lengthHint,
  NOT_IN_CLIP,
  pastEnd,
  refusalWords,
  selectedName,
  TRIM_KEYS,
  trimmedWords,
  UNAVAILABLE,
} from './times.ts'

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
  assert.match(lengthHint(6.02, false), /ends at 0:06\.02, as recorded for this clip/)
  assert.match(lengthHint(6.08), /ends at 0:06\.08, as this browser reads it/)
})

/*
 * The Cuts panel's two hints, run by `npm test`: both say that a cut over the whole clip
 * leaves the clip out of the movie, and where the chapter's title card goes when it is
 * that chapter's title clip (the render's rule, `title-card-whole-clip-cut`).
 */

const LEAVES_OUT = 'a cut over the whole clip leaves the clip out of the movie.'
const CARD_MOVES =
  'If it is its chapter’s title clip, the chapter’s title card moves to the next clip that plays.'

describe('the whole-clip cut sentence', () => {
  it('ends the hint before the clip’s length is known', () => {
    assert.ok(CUT_HINT.includes(`${LEAVES_OUT} ${CARD_MOVES}`))
    assert.ok(CUT_HINT.endsWith(CARD_MOVES))
  })

  it('ends the hint once the clip’s length is known, which still names the end', () => {
    const hint = lengthHint(75.5)
    assert.ok(hint.includes('This clip ends at 1:15.5'))
    assert.ok(hint.includes(`${LEAVES_OUT} ${CARD_MOVES}`))
    assert.ok(hint.endsWith(CARD_MOVES))
  })
})

// --- trimming a cut on the timeline ----------------------------------------------------

const GRILL_CUTS = [
  { in: 1, out: 2.5 },
  { in: 4, out: 5 },
]

test('a handle is named by the Cuts panel’s number and the clip’s name', () => {
  assert.equal(handleName('in', 1, 's1710001.mp4'), 'Cut 1 start of s1710001.mp4')
  assert.equal(handleName('out', 3, 's1710001.mp4'), 'Cut 3 end of s1710001.mp4')
  assert.equal(selectedName(2, 's1710001.mp4'), 'Cut 2 of s1710001.mp4')
  assert.equal(fieldName('start', 1, 's1710001.mp4'), 'Start of cut 1 of s1710001.mp4')
  assert.equal(fieldName('end', 1, 's1710001.mp4'), 'End of cut 1 of s1710001.mp4')
})

test('a handle’s value text gives its time and the cut’s span', () => {
  assert.equal(handleValueText(1.5, { in: 1.5, out: 3 }), '0:01.5, the cut runs 0:01.5 to 0:03')
  assert.equal(handleValueText(1, GRILL_CUTS[0]), '0:01, the cut runs 0:01 to 0:02.5')
})

test('a cut past the clip’s end says so in the end handle’s value text', () => {
  assert.equal(
    handleValueText(7, { in: 5, out: 7 }, 6.02),
    '0:07, the cut runs 0:05 to 0:07, past the clip’s end',
  )
  assert.equal(handleValueText(5, { in: 5, out: 6 }, 6.02), '0:05, the cut runs 0:05 to 0:06')
})

test('an edit is announced with the cut’s number, its new span and the summary', () => {
  const after = [{ in: 1, out: 3.5 }, GRILL_CUTS[1]]
  assert.equal(
    trimmedWords(1, 's1710001.mp4', after[0], after, 'Snapped to the playhead'),
    'Cut 1 of s1710001.mp4 now 0:01 to 0:03.5, snapped to the playhead. 2 cuts, 3.5 seconds cut out.',
  )
  assert.equal(
    trimmedWords(1, 's1710001.mp4', after[0], after),
    'Cut 1 of s1710001.mp4 now 0:01 to 0:03.5. 2 cuts, 3.5 seconds cut out.',
  )
})

test('the words for the keys, a playhead elsewhere and a pending save', () => {
  assert.match(TRIM_KEYS, /Left and Right/)
  assert.match(TRIM_KEYS, /Page Up and Page Down/)
  assert.match(TRIM_KEYS, /Enter sets the edge at the playhead/)
  assert.equal(NOT_IN_CLIP('s1710002.mp4'), 'The playhead is not in s1710002.mp4.')
  assert.match(UNAVAILABLE, /unavailable/)
})

test('a typed start after the cut’s end is refused as an order at the End field', () => {
  const checked = checkTrim(GRILL_CUTS, 0, 'start', '3', '0:02.5', 6.02)
  assert.equal(checked.ok, false)
  if (!checked.ok) {
    assert.equal(checked.refusal.kind, 'order')
    assert.equal(checked.refusal.field, 'end')
    assert.equal(
      refusalWords(checked.refusal),
      'A cut must end after it starts: 0:02.5 is not after 0:03.',
    )
  }
})

test('a typed end over the next cut is refused, naming it by the panel’s number', () => {
  const checked = checkTrim(GRILL_CUTS, 0, 'end', '4.5', '0:01', 6.02)
  assert.equal(checked.ok, false)
  if (!checked.ok) {
    assert.equal(checked.refusal.kind, 'overlap')
    assert.match(refusalWords(checked.refusal), /overlaps cut 2 \(0:04 to 0:05\)/)
  }
})

test('a typed end after a 6.02 s clip is refused as past the end', () => {
  const checked = checkTrim(GRILL_CUTS, 1, 'end', '7', '0:04', 6.02)
  assert.equal(checked.ok, false)
  if (!checked.ok) {
    assert.equal(checked.refusal.kind, 'past-end')
    assert.equal(checked.refusal.field, 'end')
    assert.match(refusalWords(checked.refusal), /0:07, after the clip’s end at 0:06\.02/)
  }
})

test('the cut’s own old span is never its own clash, and the others keep their numbers', () => {
  // 1.0 to 2.5 widened to 0.5 to 3.9: it overlaps nothing but itself
  const widened = checkTrim(GRILL_CUTS, 0, 'start', '0:00.5', '0:02.5', 6.02)
  assert.deepEqual(widened, { ok: true, in: 0.5, out: 2.5 })
  const end = checkTrim(GRILL_CUTS, 0, 'end', '3.9', '0:01', 6.02)
  assert.deepEqual(end, { ok: true, in: 1, out: 3.9 })
  // cut 2 is cut 2 even when cut 1 is removed
  const second = checkTrim(
    [{ in: 1, out: 2.5, removed: true }, { in: 4, out: 5 }],
    1,
    'start',
    '2',
    '0:05',
    6.02,
  )
  assert.deepEqual(second, { ok: true, in: 2, out: 5 })
})

test('typing one field leaves the other edge at its exact value', () => {
  // read as 3.2033333, shown as 0:03.203: typing the start must not move the end
  const cuts = [{ in: 1, out: 3.2033333 }]
  const checked = checkTrim(cuts, 0, 'start', '0:00.5', '0:03.203', 6.02)
  assert.deepEqual(checked, { ok: true, in: 0.5, out: 3.2033333 })
  const typedEnd = checkTrim(cuts, 0, 'end', '0:03.5', '0:01', 6.02)
  assert.deepEqual(typedEnd, { ok: true, in: 1, out: 3.5 })
  // and the other way: the start read as 1.2033333 is shown as 0:01.203
  const early = [{ in: 1.2033333, out: 3 }]
  assert.deepEqual(checkTrim(early, 0, 'end', '4', '0:01.203', 6.02), { ok: true, in: 1.2033333, out: 4 })
  // a start that was typed over is taken as typed
  assert.deepEqual(checkTrim(early, 0, 'end', '4', '0:01.2', 6.02), { ok: true, in: 1.2, out: 4 })
})

test('a cut read past the clip’s end keeps it until its end is moved', () => {
  const cuts = [{ in: 5, out: 7 }]
  assert.deepEqual(checkTrim(cuts, 0, 'start', '5.5', '0:07', 6.02), { ok: true, in: 5.5, out: 7 })
  const typedPast = checkTrim(cuts, 0, 'start', '6.5', '0:07', 6.02)
  assert.equal(typedPast.ok, false)
  if (!typedPast.ok) {
    assert.equal(typedPast.refusal.kind, 'past-end')
    assert.equal(typedPast.refusal.field, 'start')
  }
  assert.equal(checkTrim(cuts, 0, 'end', '8', '0:05', 6.02).ok, false)
})
