import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  edgeAnnouncement,
  edgeAt,
  edgeCutOf,
  edgeEdit,
  edgeKey,
  edgeLimits,
  edgeNotes,
  edgePlaces,
  edgeTip,
  edgeValueText,
  playedMs,
  trimToPlayhead,
} from './edgeTrim.ts'
import { ModelError } from './model.ts'
import type { ClipFacts } from './model.ts'

/* `s1710001.mp4`: 6.02 s at 50 fps, three frames are 60 ms (the spec's clip). */
const F: ClipFacts = { durationMs: 6020, fps: 50 }
type Cut = { key: string; in: number; out: number; reason: string | null; removed: boolean }
const cut = (key: string, from: number, to: number, reason: string | null = 'manual', removed = false): Cut => ({
  key,
  in: from,
  out: to,
  reason,
  removed,
})
/** The spec's two interior cuts: cut 1 1.0–2.5 s, cut 2 4.0–5.0 s. */
const INTERIOR: Cut[] = [cut('r0', 1.0, 2.5), cut('r1', 4.0, 5.0)]
const SNAP = { playheadMs: null, snapping: true }

describe('edge places and edge cuts', () => {
  it('an untrimmed clip: start 0, end its duration, no edge cut', () => {
    assert.deepEqual(edgePlaces(INTERIOR, F.durationMs), { start: 0, end: 6020 })
    assert.equal(edgeCutOf(INTERIOR, 'start', F.durationMs), null)
    assert.equal(edgeCutOf(INTERIOR, 'end', F.durationMs), null)
  })

  it('a start trim joined with a cut it touches: the edge is the joined span’s end', () => {
    const listed = [...INTERIOR, cut('r2', 0, 1.0)]
    assert.equal(edgePlaces(listed, F.durationMs).start, 2500)
    assert.equal(edgeCutOf(listed, 'start', F.durationMs)?.cut.key, 'r2')
  })

  it('a cut read past the end is the end edge’s edge cut', () => {
    const listed = [...INTERIOR, cut('r2', 5.5, 7.0)]
    assert.equal(edgePlaces(listed, F.durationMs).end, 5500)
    assert.equal(edgeCutOf(listed, 'end', F.durationMs)?.cut.key, 'r2')
  })

  it('two cuts at the start: the one that ends later is the edge cut', () => {
    const listed = [cut('r0', 0, 1.0, 'black'), cut('r1', 0, 0.5)]
    assert.equal(edgeCutOf(listed, 'start', F.durationMs)?.cut.key, 'r0')
    // A tie: the first in list order.
    assert.equal(edgeCutOf([cut('a', 0, 1), cut('b', 0, 1)], 'start', F.durationMs)?.cut.key, 'a')
  })

  it('a removed cut is never an edge cut', () => {
    assert.equal(edgeCutOf([cut('r0', 0, 1.0, 'black', true)], 'start', F.durationMs), null)
  })

  it('a trailing cut ending less than 100 ms before the end is one (the track’s rule)', () => {
    const listed = [cut('r0', 5.0, 5.95)]
    assert.equal(edgeCutOf(listed, 'end', F.durationMs)?.cut.key, 'r0')
    assert.equal(edgePlaces(listed, F.durationMs).end, 5000)
  })

  it('refuses a duration that is not a finite number above zero', () => {
    for (const bad of [0, -1, Number.NaN, Infinity]) {
      assert.throws(() => edgePlaces(INTERIOR, bad), ModelError)
      assert.throws(() => edgeLimits(INTERIOR, 'start', { durationMs: bad, fps: 50 }), ModelError)
    }
  })
})

describe('edge limits', () => {
  it('the start edge may trim up to three played frames', () => {
    const limits = edgeLimits(INTERIOR, 'start', F)
    assert.equal(limits.lowest, 0)
    assert.equal(limits.highest, 5960)
    assert.equal(limits.lowWhy, 'file')
    assert.equal(playedMs([...INTERIOR, { in: 0, out: 5.96 }], F.durationMs), 60)
  })

  it('another cut holds the start: the lowest place is its end, not the file’s start', () => {
    const listed = [cut('r0', 0, 1.0, 'black'), cut('r1', 0, 3.0)]
    assert.equal(edgeCutOf(listed, 'start', F.durationMs)?.cut.key, 'r1')
    const limits = edgeLimits(listed, 'start', F)
    assert.equal(limits.lowest, 1000)
    assert.equal(limits.lowWhy, 'cut')
    assert.equal(limits.holdingCut, 1)
  })

  it('the end edge mirrors the start', () => {
    const limits = edgeLimits(INTERIOR, 'end', F)
    assert.equal(limits.lowest, 60)
    assert.equal(limits.highest, 6020)
    assert.equal(limits.highWhy, 'file')
    assert.equal(limits.lowWhy, 'frames')
  })

  it('the range holds the current place of a clip already playing fewer than three frames', () => {
    const listed = [cut('r0', 0, 6.0)]
    const limits = edgeLimits(listed, 'start', F)
    assert.ok(limits.lowest <= 6000 && limits.highest >= 6000)
    assert.ok(limits.lowest <= limits.highest)
  })
})

describe('edgeAt and edgeEdit', () => {
  it('trimming a start creates a manual cut: −0.5 s, plays 3.02 s', () => {
    const at = edgeAt(INTERIOR, 'start', 500, F, 40, SNAP)
    assert.equal(at.x, 500)
    assert.equal(at.place, 500)
    assert.equal(at.changeMs, -500)
    assert.equal(at.playsMs, 3020)
    assert.equal(at.snap, null)
    assert.deepEqual(edgeEdit(INTERIOR, 'start', at.x, F), {
      kind: 'add',
      span: { in: 0, out: 0.5 },
      reason: 'manual',
    })
    assert.equal(edgeTip(at), '−0:00.5 · 0:03.02')
  })

  it('extending an approved black cut keeps its reason and key (a trim)', () => {
    const listed = [cut('r0', 0, 0.5, 'black'), ...INTERIOR.map((c, i) => ({ ...c, key: `r${i + 1}` }))]
    const at = edgeAt(listed, 'start', 800, F, 40, { playheadMs: null, snapping: false })
    assert.deepEqual(edgeEdit(listed, 'start', at.x, F), { kind: 'trim', key: 'r0', span: { in: 0, out: 0.8 } })
  })

  it('back to the start of the file removes the edge cut', () => {
    const listed = [cut('a1', 0, 0.8), ...INTERIOR]
    const at = edgeAt(listed, 'start', -300, F, 40, SNAP)
    assert.equal(at.x, 0)
    assert.equal(at.place, 0)
    assert.equal(at.limit, 'file')
    assert.deepEqual(edgeEdit(listed, 'start', at.x, F), { kind: 'remove', key: 'a1' })
    assert.deepEqual(edgeNotes('start', at, null), ['Start of the file'])
  })

  it('reaching an interior cut joins it, and moving back un-joins it', () => {
    const at = edgeAt(INTERIOR, 'start', 1200, F, 40, { playheadMs: null, snapping: false })
    assert.equal(at.x, 1200)
    assert.equal(at.place, 2500)
    assert.deepEqual(at.joined, [1])
    assert.deepEqual(edgeEdit(INTERIOR, 'start', at.x, F), {
      kind: 'add',
      span: { in: 0, out: 1.2 },
      reason: 'manual',
    })
    assert.deepEqual(edgeNotes('start', at, null), ['Joined with cut 1'])
    const back = edgeAt(INTERIOR, 'start', 900, F, 40, { playheadMs: null, snapping: false })
    assert.equal(back.place, 900)
    assert.deepEqual(back.joined, [])
  })

  it('a cut that already held the start is not reported as joined', () => {
    const listed = [cut('r0', 0, 1.0, 'black'), cut('r1', 0, 3.0)]
    const at = edgeAt(listed, 'start', 3500, F, 40, { playheadMs: null, snapping: false })
    assert.equal(at.place, 3500)
    assert.deepEqual(at.joined, [])
    assert.deepEqual(edgeEdit(listed, 'start', at.x, F), { kind: 'trim', key: 'r1', span: { in: 0, out: 3.5 } })
  })

  it('the end edge from a cut past the end keeps its listed end', () => {
    const listed = [...INTERIOR, cut('r2', 5.5, 7.0)]
    const at = edgeAt(listed, 'end', 5000, F, 40, { playheadMs: null, snapping: false })
    // 5.0 touches cut 2's end: the edge joins it and lands at its start.
    assert.equal(at.place, 4000)
    assert.deepEqual(edgeEdit(listed, 'end', at.x, F), { kind: 'trim', key: 'r2', span: { in: 5.0, out: 7.0 } })
  })

  it('trimming an end adds the span to the clip’s duration', () => {
    const at = edgeAt(INTERIOR, 'end', 5520, F, 40, SNAP)
    assert.deepEqual(edgeEdit(INTERIOR, 'end', at.x, F), {
      kind: 'add',
      span: { in: 5.52, out: 6.02 },
      reason: 'manual',
    })
    assert.equal(at.changeMs, -500)
  })

  it('a drag past the limit stops there, joining cuts 1 and 2', () => {
    const at = edgeAt(INTERIOR, 'start', 6500, F, 40, SNAP)
    assert.equal(at.place, 5960)
    assert.equal(at.playsMs, 60)
    assert.deepEqual(at.joined, [1, 2])
    assert.equal(at.limit, 'frames')
    assert.deepEqual(edgeNotes('start', at, null), ['The clip keeps three frames', 'Joined with cuts 1 and 2'])
  })

  it('snaps to a whole second within 8 px, and not when snapping is off', () => {
    const on = edgeAt(INTERIOR, 'start', 2960 + 1000, F, 40, SNAP)
    // 3.96 s: 4.0 s is cut 2's start and a whole second, 1.6 px away; the cut is named first.
    assert.equal(on.x, 4000)
    const near = edgeAt([], 'start', 2960, F, 40, SNAP)
    assert.equal(near.x, 3000)
    assert.deepEqual(near.snap, { kind: 'second', ms: 3000 })
    assert.deepEqual(edgeNotes('start', near, null), ['Snapped to 0:03'])
    const off = edgeAt([], 'start', 2960, F, 40, { playheadMs: null, snapping: false })
    assert.equal(off.x, 2960)
    assert.equal(off.snap, null)
  })

  it('snaps to the playhead in the clip and says so', () => {
    const at = edgeAt([], 'start', 1640, { durationMs: 8000, fps: 25 }, 40, { playheadMs: 1600, snapping: true })
    assert.equal(at.x, 1600)
    assert.deepEqual(at.snap, { kind: 'playhead' })
    assert.deepEqual(edgeNotes('start', at, null), ['Snapped to the playhead'])
  })

  it('a release where the drag began is no edit', () => {
    assert.deepEqual(edgeEdit(INTERIOR, 'start', 0, F), { kind: 'none' })
    // A joined edge cut moved inside the cut it joins: the place does not change.
    const listed = [cut('a1', 0, 1.2), ...INTERIOR]
    assert.equal(edgePlaces(listed, F.durationMs).start, 2500)
    assert.deepEqual(edgeEdit(listed, 'start', 2000, F), { kind: 'none' })
  })

  it('an end edge back at the end of the file removes the trailing cut', () => {
    const listed = [...INTERIOR, cut('a1', 5.5, 6.02)]
    assert.deepEqual(edgeEdit(listed, 'end', 6020, F), { kind: 'remove', key: 'a1' })
  })
})

describe('edge keys', () => {
  it('Right three times trims three frames; the value text says so', () => {
    let listed: Cut[] = [...INTERIOR]
    for (let i = 0; i < 3; i += 1) {
      const x = edgeKey('ArrowRight', false, listed, 'start', F)
      assert.notEqual(x, null)
      const edit = edgeEdit(listed, 'start', x as number, F)
      if (edit.kind === 'add') {
        listed = [cut('a1', edit.span.in, edit.span.out), ...listed]
      } else if (edit.kind === 'trim') {
        listed = listed.map((c) => (c.key === edit.key ? { ...c, ...edit.span } : c))
      }
    }
    assert.equal(edgePlaces(listed, F.durationMs).start, 60)
    assert.equal(listed[0].out, 0.06)
    assert.equal(edgeValueText('start', 60, F.durationMs, playedMs(listed, F.durationMs)), 'Start trimmed by 0.06 s, plays 0:03.46')
  })

  it('Home restores, End trims to three played frames', () => {
    const listed = [cut('a1', 0, 0.06), ...INTERIOR]
    const home = edgeKey('Home', false, listed, 'start', F)
    assert.equal(home, 0)
    assert.deepEqual(edgeEdit(listed, 'start', home as number, F), { kind: 'remove', key: 'a1' })
    const end = edgeKey('End', false, INTERIOR, 'start', F)
    assert.equal(end, 5960)
    const at = edgeAt(INTERIOR, 'start', end as number, F, 40, { playheadMs: null, snapping: false })
    assert.match(edgeAnnouncement('s1710001.mp4', 'start', at, F.durationMs), /joined cuts 1 and 2\. The clip keeps three frames\./)
  })

  it('Shift steps a second to the nearest frame; a step outward skips past a cut it would land in', () => {
    assert.equal(edgeKey('ArrowRight', true, INTERIOR, 'start', F), 1000)
    // Joined at 2.5 s by a cut 0–1.2: Left would land in cut 1, so it goes to the frame before it.
    const listed = [cut('a1', 0, 1.2), ...INTERIOR]
    assert.equal(edgeKey('ArrowLeft', false, listed, 'start', F), 980)
  })

  it('a key that is not the edge’s is null', () => {
    assert.equal(edgeKey('q', false, INTERIOR, 'start', F), null)
    assert.equal(edgeKey('Enter', false, INTERIOR, 'end', F), null)
  })

  it('value text for an untrimmed start', () => {
    assert.equal(edgeValueText('start', 0, F.durationMs, 3520), 'Start not trimmed, plays 0:03.52')
  })
})

describe('Q and W at the playhead', () => {
  const B: ClipFacts = { durationMs: 8000, fps: 25 }

  it('Q trims the start to the playhead', () => {
    const result = trimToPlayhead([], 'start', 3200, B)
    assert.equal(result.kind, 'edit')
    if (result.kind === 'edit') {
      assert.equal(result.at.place, 3200)
      assert.deepEqual(edgeEdit([], 'start', result.at.x, B), {
        kind: 'add',
        span: { in: 0, out: 3.2 },
        reason: 'manual',
      })
      assert.match(edgeAnnouncement('s1710002.mp4', 'start', result.at, B.durationMs), /^s1710002\.mp4 start trimmed by 3\.2 s, /)
    }
  })

  it('W trims the end to the playhead', () => {
    const result = trimToPlayhead([], 'end', 3200, B)
    assert.equal(result.kind === 'edit' && result.at.place, 3200)
  })

  it('in a title card nothing changes; at the edge’s own place nothing changes either', () => {
    assert.deepEqual(trimToPlayhead([], 'start', null, B), { kind: 'refused', why: 'not-in-clip' })
    assert.deepEqual(trimToPlayhead([cut('a1', 0, 3.2)], 'start', 3200, B), { kind: 'same' })
  })
})
