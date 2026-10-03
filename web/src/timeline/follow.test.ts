import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { nextClip, onFrame, resumeOrYield, startFrom } from './follow.ts'

/*
 * Playing through the timeline (`follow.ts`), run by `npm test`: the cut rules are the
 * preview's (`skipAt`, `playFrom`), applied clip by clip.
 */

describe('onFrame', () => {
  const spans = [{ from: 2000, to: 4000 }]

  it('plays on until the next frame would fall in a cut, then skips it once', () => {
    assert.deepEqual(onFrame(spans, 1000, 40, 10000), { kind: 'play' })
    assert.deepEqual(onFrame(spans, 1920, 40, 10000), { kind: 'play' })
    assert.deepEqual(onFrame(spans, 1960, 40, 10000), { kind: 'seek', ms: 4000 })
    // after the jump: the frame at 4000 is outside the cut, nothing more to skip
    assert.deepEqual(onFrame(spans, 4000, 40, 10000), { kind: 'play' })
  })

  it('ends the clip at the start of a cut that runs to its end', () => {
    assert.deepEqual(onFrame([{ from: 8000, to: 10000 }], 7960, 40, 10000), { kind: 'end' })
  })

  it('ends the clip at a cut that ends within 0.1 s of the clip\'s length', () => {
    assert.deepEqual(onFrame([{ from: 8000, to: 9950 }], 7960, 40, 10000), { kind: 'end' })
  })

  it('plays a clip with no cuts to its natural end', () => {
    assert.deepEqual(onFrame([], 9960, 40, 10000), { kind: 'play' })
  })
})

describe('startFrom and nextClip', () => {
  const clips = [
    { durationMs: 10000, spans: [{ from: 0, to: 3000 }] }, // leading cut
    { durationMs: 5000, spans: [{ from: 0, to: 5000 }] }, // all cut
    { durationMs: 8000, spans: [{ from: 2000, to: 4000 }] },
  ]

  it('starts at the playhead, or at the end of the cut it sits in', () => {
    assert.deepEqual(startFrom(clips, { clip: 2, ms: 1000 }), { clip: 2, ms: 1000 })
    assert.deepEqual(startFrom(clips, { clip: 2, ms: 3000 }), { clip: 2, ms: 4000 })
    assert.deepEqual(startFrom(clips, { clip: 0, ms: 1000 }), { clip: 0, ms: 3000 })
  })

  it('goes into the next clip at 0 after its leading cut, skipping a clip that is all cut', () => {
    assert.deepEqual(nextClip(clips, 0), { clip: 2, ms: 0 })
    const lead = [clips[0], { durationMs: 6000, spans: [{ from: 0, to: 1500 }] }]
    assert.deepEqual(nextClip(lead, 0), { clip: 1, ms: 1500 })
  })

  it('stops at the end of the last clip: nothing after it plays', () => {
    assert.equal(nextClip(clips, 2), null)
    assert.equal(startFrom(clips, { clip: 2, ms: 7950 }), null)
  })

  it('goes on into the next clip, not back to the start of this one, from its last frames', () => {
    assert.deepEqual(startFrom(clips, { clip: 0, ms: 9960 }), { clip: 2, ms: 0 })
  })

  it('goes on into the next clip from a cut that runs to the end of this one', () => {
    const tail = [
      { durationMs: 10000, spans: [{ from: 6000, to: 10000 }] },
      { durationMs: 4000, spans: [] },
    ]
    assert.deepEqual(startFrom(tail, { clip: 0, ms: 7000 }), { clip: 1, ms: 0 })
    assert.equal(startFrom([tail[0]], { clip: 0, ms: 7000 }), null)
  })
})

describe('resumeOrYield', () => {
  it('resumes when nothing else plays', () => {
    assert.equal(resumeOrYield(false, false), 'start')
  })

  it('yields when another video plays and the operator did not ask', () => {
    assert.equal(resumeOrYield(false, true), 'yield')
  })

  it('never yields the start the operator asked for', () => {
    assert.equal(resumeOrYield(true, true), 'start')
    assert.equal(resumeOrYield(true, false), 'start')
  })
})
