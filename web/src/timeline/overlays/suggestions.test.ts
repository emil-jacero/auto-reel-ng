import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Analysis } from '../../api/analysis.ts'
import type { ReelDocument } from '../../api/reel.ts'
import { keptCuts } from '../../cuts/times.ts'
import { addCut, buildWriteBody, cutChanges, cutsOf, isDirty, readCuts, removeCut } from '../../edit/draft.ts'
import type { Baseline, Draft } from '../../edit/draft.ts'
import {
  ANALYZED_CLEAN,
  DECISIONS_UNAVAILABLE,
  ANALYZE_COMMAND,
  NEVER_ANALYZED,
  alreadyCutWords,
  approvedWords,
  approval,
  clipNotAnalyzed,
  cutsKey,
  dismissalKey,
  dismissedWords,
  dropGone,
  eventNote,
  laneName,
  markSpan,
  decideApprove,
  decideDismiss,
  placeMarks,
  markName,
  neighbour,
  notApprovedWords,
  restoredWords,
  stackMarks,
  standingRefusal,
  stepOfKey,
  suggestionKey,
  suggestionState,
} from './suggestions.ts'
import type { Refusal, SuggestionKeyEvent } from './suggestions.ts'

const black = { start: 0, end: 3.2, kind: 'black' }
/** A read as these notes knew it: the state fields (analysis-enqueue-api) are not read here. */
const legacy = (read: Pick<Analysis, 'analyzed' | 'segments'>): Analysis => ({
  ...read,
  state: 'current',
  clips: {},
  job: null,
})
const cut = (from: number, to: number, removed = false) => ({ in: from, out: to, removed })

describe('suggestionState', () => {
  it('is pending with no cuts', () => {
    assert.equal(suggestionState([], black, false), 'pending')
  })

  it('is cut when one cut covers the span', () => {
    assert.equal(suggestionState([cut(0, 3.2)], black, false), 'cut')
    assert.equal(suggestionState([cut(0, 10)], black, false), 'cut')
  })

  it('is cut when touching cuts together cover the span to the millisecond', () => {
    const span = { start: 0, end: 3.2033333, kind: 'black' }
    assert.equal(suggestionState([cut(0, 1.5), cut(1.5, 3.203)], span, false), 'cut')
    // The same cuts in the other order and with an overlap between them.
    assert.equal(suggestionState([cut(1.4, 3.203), cut(0, 1.5)], span, false), 'cut')
  })

  it('is partly cut when a cut covers part of the span', () => {
    assert.equal(suggestionState([cut(0, 1)], black, false), 'partly-cut')
    assert.equal(suggestionState([cut(3, 9)], black, false), 'partly-cut')
    assert.equal(suggestionState([cut(1, 2)], black, false), 'partly-cut')
  })

  it('is partly cut when a gap is left between two cuts', () => {
    assert.equal(suggestionState([cut(0, 1), cut(2, 3.2)], black, false), 'partly-cut')
  })

  it('does not count a cut that only touches the span', () => {
    assert.equal(suggestionState([cut(3.2, 5)], black, false), 'pending')
    assert.equal(suggestionState([cut(-1, 0)], black, false), 'pending')
  })

  it('ignores a removed cut', () => {
    assert.equal(suggestionState([cut(0, 3.2, true)], black, false), 'pending')
    assert.equal(suggestionState([cut(0, 3.2, true), cut(0, 1)], black, false), 'partly-cut')
  })

  it('is dismissed when dismissed and no cut touches it', () => {
    assert.equal(suggestionState([], black, true), 'dismissed')
    assert.equal(suggestionState([cut(0, 3.2, true)], black, true), 'dismissed')
  })

  it('lets a cut outrank a dismissal', () => {
    assert.equal(suggestionState([cut(0, 3.2)], black, true), 'cut')
    assert.equal(suggestionState([cut(0, 1)], black, true), 'partly-cut')
  })

  it('reads a span under a millisecond as pending, whatever is cut', () => {
    const tiny = { start: 5, end: 5.0004, kind: 'freeze' }
    assert.equal(suggestionState([cut(0, 10)], tiny, false), 'pending')
  })
})

describe('approval', () => {
  it('gives the cut on a free span, to the millisecond', () => {
    assert.deepEqual(approval([cut(10, 11)], { start: 58.1, end: 60 }, 61), {
      ok: true,
      in: 58.1,
      out: 60,
    })
    assert.deepEqual(approval([], { start: 0, end: 3.2033333 }), { ok: true, in: 0, out: 3.203 })
  })

  it('refuses an overlap with a listed cut, naming its number (removed ones count)', () => {
    const result = approval([cut(9, 9.5, true), cut(0, 1)], black)
    assert.equal(result.ok, false)
    assert.deepEqual(!result.ok && result.refusal, {
      kind: 'overlap',
      field: 'start',
      number: 2,
      clash: cut(0, 1),
    })
  })

  it('ignores a removed cut', () => {
    assert.equal(approval([cut(0, 1, true)], black).ok, true)
  })

  it('refuses a span past the clip’s end when the length is known, and passes it when not', () => {
    const span = { start: 58.1, end: 60.04 }
    const refused = approval([], span, 60)
    assert.equal(refused.ok, false)
    assert.equal(!refused.ok && refused.refusal.kind, 'past-end')
    assert.equal(approval([], span).ok, true)
  })

  it('refuses a span of under a millisecond as order', () => {
    const refused = approval([], { start: 5, end: 5.0004 })
    assert.equal(refused.ok, false)
    assert.equal(!refused.ok && refused.refusal.kind, 'order')
  })

  it('passes an unknown kind through unchanged (the kind is not the check’s concern)', () => {
    assert.equal(approval([], { start: 1, end: 2 }).ok, true)
  })
})

const key = (init: Partial<SuggestionKeyEvent> & { key: string }): SuggestionKeyEvent => ({
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  repeat: false,
  isComposing: false,
  ...init,
})

describe('suggestionKey', () => {
  it('approves on a and A, dismisses on r and R', () => {
    assert.equal(suggestionKey(key({ key: 'a' })), 'approve')
    assert.equal(suggestionKey(key({ key: 'A' })), 'approve')
    assert.equal(suggestionKey(key({ key: 'r' })), 'dismiss')
    assert.equal(suggestionKey(key({ key: 'R' })), 'dismiss')
  })

  it('does nothing with Ctrl, Meta or Alt held', () => {
    assert.equal(suggestionKey(key({ key: 'a', ctrlKey: true })), null)
    assert.equal(suggestionKey(key({ key: 'a', metaKey: true })), null)
    assert.equal(suggestionKey(key({ key: 'r', altKey: true })), null)
  })

  it('does nothing on a repeat or during an IME composition', () => {
    assert.equal(suggestionKey(key({ key: 'a', repeat: true })), null)
    assert.equal(suggestionKey(key({ key: 'a', isComposing: true })), null)
  })

  it('treats Shift alone as the letter', () => {
    assert.equal(suggestionKey(key({ key: 'A' })), 'approve')
  })

  it('does nothing for any other key', () => {
    for (const other of ['b', 'Enter', ' ', 'ArrowRight', '1', 'Process']) {
      assert.equal(suggestionKey(key({ key: other })), null)
    }
  })
})

describe('stackMarks', () => {
  const at = (seconds: number, length = 0) => ({ startMs: seconds * 1000, endMs: (seconds + length) * 1000 })
  const rowsOf = (...args: Parameters<typeof stackMarks>) =>
    stackMarks(...args).placed.map((box) => box.row)

  it('gives marks far apart the same row', () => {
    const { count } = stackMarks([at(10), at(20), at(30)], 10, 44)
    assert.deepEqual(rowsOf([at(10), at(20), at(30)], 10, 44), [0, 0, 0])
    assert.equal(count, 1)
  })

  it('puts marks 10 px apart at 44 px reach on two rows, both whole', () => {
    // 1 s apart at 10 px/s.
    const { placed, count } = stackMarks([at(10), at(11)], 10, 44)
    assert.deepEqual(
      placed.map((box) => box.row),
      [0, 1],
    )
    assert.equal(count, 2)
    assert.deepEqual(
      placed.map((box) => box.width),
      [44, 44],
    )
  })

  it('lets a mark go back to row 0 once the first ended', () => {
    assert.deepEqual(rowsOf([at(10), at(11), at(15)], 10, 44), [0, 1, 0])
  })

  it('uses a wide span’s own width when it is wider than the reach', () => {
    // a 10 s span at 10 px/s is 100 px wide; a mark 60 px from its centre overlaps it.
    const { placed } = stackMarks([at(10, 10), at(21)], 10, 44)
    assert.equal(placed[0].width, 100)
    assert.deepEqual(
      placed.map((box) => box.row),
      [0, 1],
    )
  })

  it('answers in the order given whatever the marks’ order', () => {
    assert.deepEqual(rowsOf([at(11), at(10)], 10, 44), [1, 0])
  })

  it('centres a narrow mark on its span', () => {
    const { placed } = stackMarks([at(10, 1)], 10, 44)
    // the span is 100 px to 110 px; the mark is 44 wide around 105
    assert.deepEqual(placed[0], { left: 83, width: 44, row: 0 })
  })

  it('keeps a mark inside the track at both ends', () => {
    const { placed } = stackMarks([at(0), at(100)], 10, 44, 1000)
    assert.equal(placed[0].left, 0)
    assert.equal(placed[1].left, 1000 - 44)
  })

  it('needs no rows for no marks', () => {
    assert.deepEqual(stackMarks([], 10, 44), { placed: [], count: 0 })
  })
})

describe('placeMarks', () => {
  const span = (startMs: number, endMs: number) => ({ startMs, endMs })

  it('stacks the end of one clip and the start of the next across the boundary', () => {
    // 40 s track at 4 px/s: clip A 0-20 s with black 18-20 s, clip B 20-40 s with black 20-22 s.
    const a = [span(18_000, 20_000)]
    const b = [span(20_000, 22_000)]
    const { placed, count } = placeMarks([a, b], 4, 44, 160)
    assert.equal(count, 2)
    // Both are 44 px wide around their spans (54 and 62 px from the start): 36 px of overlap.
    assert.deepEqual(placed[0][0], { left: 54, width: 44, row: 0 })
    assert.deepEqual(placed[1][0], { left: 62, width: 44, row: 1 })
  })

  it('answers per clip in the order given', () => {
    const { placed } = placeMarks([[span(10_000, 10_000), span(30_000, 30_000)], [], [span(60_000, 60_000)]], 10, 44)
    assert.deepEqual(
      placed.map((group) => group.length),
      [2, 0, 1],
    )
    assert.deepEqual(
      placed.flat().map((box) => box.row),
      [0, 0, 0],
    )
  })

  it('makes the lane as high as the whole track needs', () => {
    const crowded = [span(10_000, 10_000), span(11_000, 11_000), span(12_000, 12_000)]
    const sparse = [span(40_000, 40_000), span(60_000, 60_000)]
    assert.equal(placeMarks([sparse, crowded, []], 10, 44).count, 3)
    assert.equal(placeMarks([], 10, 44).count, 0)
    // Zoomed in the crowded clip needs one row.
    assert.equal(placeMarks([crowded], 100, 44).count, 1)
  })

  it('does not depend on the clips that are drawn', () => {
    // The row of a mark is a property of the track: the same call gives the same answer.
    const groups = [[span(18_000, 20_000)], [span(20_000, 22_000)]]
    assert.deepEqual(placeMarks(groups, 4, 44, 160), placeMarks(groups, 4, 44, 160))
  })
})

describe('roving order', () => {
  const order = ['a', 'b', 'c']

  it('moves to the previous and next', () => {
    assert.equal(neighbour(order, 'b', 'previous'), 'a')
    assert.equal(neighbour(order, 'b', 'next'), 'c')
  })

  it('stops at both ends without wrapping', () => {
    assert.equal(neighbour(order, 'a', 'previous'), null)
    assert.equal(neighbour(order, 'c', 'next'), null)
  })

  it('goes to the first and last, and stays when already there', () => {
    assert.equal(neighbour(order, 'b', 'first'), 'a')
    assert.equal(neighbour(order, 'b', 'last'), 'c')
    assert.equal(neighbour(order, 'a', 'first'), null)
    assert.equal(neighbour(order, 'c', 'last'), null)
  })

  it('has nowhere to go with no marks, and starts at the first from an unknown mark', () => {
    assert.equal(neighbour([], 'a', 'next'), null)
    assert.equal(neighbour(order, 'zzz', 'next'), 'a')
  })

  it('reads the arrow keys, Home and End', () => {
    assert.equal(stepOfKey('ArrowLeft'), 'previous')
    assert.equal(stepOfKey('ArrowRight'), 'next')
    assert.equal(stepOfKey('Home'), 'first')
    assert.equal(stepOfKey('End'), 'last')
    assert.equal(stepOfKey('a'), null)
  })
})

describe('dismissals', () => {
  const segments: Analysis['segments'] = {
    'a.mp4': [{ start: 0, end: 3.2, kind: 'black', confidence: 1 }],
    'b|c.mp4': [{ start: 1, end: 2, kind: 'freeze', confidence: 1 }],
  }

  it('keys a dismissal by clip, span and kind, whatever characters the name holds', () => {
    assert.notEqual(
      dismissalKey('b|c.mp4', { start: 1, end: 2, kind: 'freeze' }),
      dismissalKey('b', { start: 1, end: 2, kind: 'freeze' }),
    )
    assert.notEqual(
      dismissalKey('a.mp4', { start: 0, end: 3.2, kind: 'black' }),
      dismissalKey('a.mp4', { start: 0, end: 3.2, kind: 'white' }),
    )
  })

  it('keeps a dismissal whose segment is still listed and drops the one that is not', () => {
    const kept = dismissalKey('a.mp4', segments['a.mp4'][0])
    const gone = dismissalKey('a.mp4', { start: 9, end: 10, kind: 'black' })
    const next = dropGone(new Set([kept, gone]), segments)
    assert.deepEqual([...next], [kept])
  })

  it('returns the same set when nothing is gone', () => {
    const held = new Set([dismissalKey('b|c.mp4', segments['b|c.mp4'][0])])
    assert.equal(dropGone(held, segments), held)
    const none: ReadonlySet<string> = new Set()
    assert.equal(dropGone(none, segments), none)
  })

  it('drops a dismissal whose clip has no entry any more', () => {
    const held = new Set([dismissalKey('a.mp4', segments['a.mp4'][0])])
    assert.equal(dropGone(held, {}).size, 0)
  })
})

describe('the words', () => {
  it('names a mark by kind, span, length and state', () => {
    assert.equal(markName(black, 'pending'), 'Black frames 0:00 to 0:03.2 (3.2 s), pending')
    assert.equal(
      markName({ start: 58.1, end: 60, kind: 'freeze' }, 'cut'),
      'Frozen picture 0:58.1 to 1:00 (1.9 s), cut',
    )
    assert.equal(markName({ start: 1, end: 2, kind: 'white' }, 'partly-cut'), 'White frames 0:01 to 0:02 (1 s), partly cut')
    assert.equal(markName({ start: 1, end: 2, kind: 'black' }, 'dismissed'), 'Black frames 0:01 to 0:02 (1 s), dismissed')
  })

  it('writes an unrecognised kind as it came, in quotes', () => {
    assert.equal(
      markName({ start: 1, end: 2.5, kind: 'speech' }, 'pending'),
      '“speech” 0:01 to 0:02.5 (1.5 s), pending',
    )
  })

  it('names the lane after the clip', () => {
    assert.equal(laneName('C0012.MP4'), 'Analysis suggestions of C0012.MP4')
  })

  it('tells the three kinds of "no suggestions" apart', () => {
    assert.equal(eventNote(legacy({ analyzed: false, segments: {} })), NEVER_ANALYZED)
    // The service says `analyzed` once the cache directory exists, and a render writes
    // its manifest there: no entries is never analysed, whatever the flag says.
    assert.equal(eventNote(legacy({ analyzed: true, segments: {} })), NEVER_ANALYZED)
    // The lane shows the badge; the command is the Timeline help's.
    assert.equal(NEVER_ANALYZED, 'Not analyzed')
    assert.equal(ANALYZE_COMMAND, 'Not analyzed. Run `auto-reel analyze <root>`, then Refresh.')
    assert.equal(eventNote(legacy({ analyzed: true, segments: { 'a.mp4': [] } })), ANALYZED_CLEAN)
    assert.equal(
      eventNote(
        legacy({
          analyzed: true,
          segments: { 'a.mp4': [{ start: 0, end: 1, kind: 'black', confidence: 1 }] },
        }),
      ),
      null,
    )
  })

  it('marks a clip with no entry "Not analyzed" only in an analysed event', () => {
    const analysed = legacy({ analyzed: true, segments: { 'a.mp4': [], 'b.mp4': [] } })
    assert.equal(clipNotAnalyzed(analysed, 'c.mp4'), true)
    assert.equal(clipNotAnalyzed(analysed, 'a.mp4'), false) // analysed, nothing found
    assert.equal(clipNotAnalyzed(legacy({ analyzed: false, segments: {} }), 'c.mp4'), false)
  })

  it('does not mark a clip of a rendered but never analysed event', () => {
    // analyzed: true with no entries (the cache holds only the render manifest).
    assert.equal(clipNotAnalyzed(legacy({ analyzed: true, segments: {} }), 'a.mp4'), false)
  })

  it('does not take a clip named like an Object prototype member as analysed', () => {
    const analysed = legacy({ analyzed: true, segments: { 'a.mp4': [] } })
    assert.equal(clipNotAnalyzed(analysed, 'constructor'), true)
    assert.equal(clipNotAnalyzed(analysed, 'toString'), true)
  })

  it('says what a decision did, with the kind lower-cased in the sentence', () => {
    assert.equal(
      approvedWords(black, 'C0012.MP4'),
      'Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added.',
    )
    assert.equal(
      dismissedWords({ start: 58.1, end: 60, kind: 'freeze' }, 'C0012.MP4'),
      'Dismissed frozen picture, 0:58.1 to 1:00, of C0012.MP4.',
    )
    assert.equal(restoredWords(black, 'a.mp4'), 'Restored black frames, 0:00 to 0:03.2, of a.mp4.')
    assert.equal(alreadyCutWords(black, 'a.mp4'), 'Already cut: black frames, 0:00 to 0:03.2, of a.mp4.')
    assert.equal(
      approvedWords({ start: 0, end: 1, kind: 'Speech' }, 'a.mp4'),
      'Approved “Speech”, 0:00 to 0:01, of a.mp4 as a cut; 1 cut added.',
    )
  })

  it('says why an approval was refused', () => {
    const overlap = approval([cut(0, 1)], black)
    assert.equal(
      !overlap.ok && notApprovedWords(overlap.refusal),
      'Not approved: this overlaps cut 1 (0:00 to 0:01). Remove that cut first.',
    )
    const past = approval([], { start: 58.1, end: 60.04 }, 60)
    assert.match(!past.ok ? notApprovedWords(past.refusal) : '', /^Not approved: This cut ends at 1:00.04, after the clip’s end at 1:00\./)
  })
})

describe('decideApprove', () => {
  const base = { segment: black, clipName: 'C0012.MP4', locked: false, listed: [], length: 60 }

  it('adds the suggestion as a cut with its kind as the reason', () => {
    assert.deepEqual(decideApprove({ ...base, state: 'pending' }), {
      kind: 'approve',
      span: { in: 0, out: 3.2 },
      reason: 'black',
      words: 'Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added.',
    })
  })

  it('passes an unrecognised kind through as the reason', () => {
    const decision = decideApprove({
      ...base,
      state: 'pending',
      segment: { start: 1, end: 2, kind: 'speech' },
    })
    assert.equal(decision.kind === 'approve' && decision.reason, 'speech')
  })

  it('says what is already cut or dismissed and adds nothing', () => {
    assert.equal(decideApprove({ ...base, state: 'cut' }).kind, 'said')
    const dismissed = decideApprove({ ...base, state: 'dismissed' })
    assert.equal(dismissed.kind, 'said')
    assert.match(dismissed.kind === 'said' ? dismissed.words : '', /Restore it first/)
  })

  it('ignores a press while locked, but still says a state that needs no write', () => {
    assert.deepEqual(decideApprove({ ...base, state: 'pending', locked: true }), { kind: 'ignored' })
    assert.equal(decideApprove({ ...base, state: 'cut', locked: true }).kind, 'said')
  })

  it('refuses an overlap naming the cut, and a span past the end', () => {
    const overlap = decideApprove({
      ...base,
      state: 'partly-cut',
      listed: [{ in: 0, out: 1 }],
    })
    assert.equal(overlap.kind, 'refused')
    assert.match(overlap.kind === 'refused' ? overlap.words : '', /^Not approved: this overlaps cut 1/)
    const past = decideApprove({
      ...base,
      state: 'pending',
      segment: { start: 58, end: 60.04, kind: 'freeze' },
    })
    assert.equal(past.kind, 'refused')
  })
})

describe('DECISIONS_UNAVAILABLE', () => {
  it('says in words that deciding waits for the save or the move', () => {
    assert.match(DECISIONS_UNAVAILABLE, /unavailable while a save or a move is pending/)
  })
})

describe('decideDismiss', () => {
  const base = { segment: black, clipName: 'C0012.MP4', locked: false }

  it('dismisses a pending suggestion and restores a dismissed one', () => {
    assert.equal(decideDismiss({ ...base, state: 'pending' }).kind, 'dismiss')
    assert.equal(decideDismiss({ ...base, state: 'dismissed' }).kind, 'restore')
  })

  it('leaves a cut or partly cut suggestion to its cuts and says so', () => {
    assert.equal(decideDismiss({ ...base, state: 'cut' }).kind, 'said')
    assert.equal(decideDismiss({ ...base, state: 'partly-cut' }).kind, 'said')
  })

  it('ignores a press while locked', () => {
    assert.deepEqual(decideDismiss({ ...base, state: 'pending', locked: true }), { kind: 'ignored' })
    assert.deepEqual(decideDismiss({ ...base, state: 'dismissed', locked: true }), { kind: 'ignored' })
  })
})

// The chain an approval is, over the real pure functions of the draft and of the decision: the
// whole path from a pending suggestion to the line `reel.yaml` gets, and back.
describe('an approval, from the suggestion to reel.yaml and back', () => {
  const read: ReelDocument = {
    metadata: { title: 'T', date: '2024-05-01' },
    look: {},
    chapters: [{ name: '', clips: ['C0012.MP4'] }],
    clips: {},
    ignore: [],
  }
  const baseline: Baseline = {
    read,
    chapters: [{ key: 'r0', readName: '', name: '', deleted: false }],
    original: new Map([['r0', ['C0012.MP4']]]),
    cuts: readCuts(read),
  }
  const empty: Draft = {
    chapters: baseline.chapters,
    orders: baseline.original,
    removed: new Map(),
    metadata: { title: 'T', date: '2024-05-01', location: '', description: '' },
    cuts: new Map(),
    rotations: new Map(),
    cards: new Map(),
  }
  const clip = 'C0012.MP4'
  const suggestion = { start: 0, end: 3.2033333, kind: 'black' }
  const listedOf = (draft: Draft) => cutsOf(baseline.cuts, draft.cuts, clip)
  const stateOf = (draft: Draft) => suggestionState(keptCuts(listedOf(draft)), suggestion, false)
  const press = (draft: Draft, state = stateOf(draft)) =>
    decideApprove({ state, segment: suggestion, clipName: clip, locked: false, listed: listedOf(draft), length: 25 })

  it('adds a cut with the span and the kind, which the clip then reads as cut', () => {
    const decision = press(empty)
    assert.equal(decision.kind, 'approve')
    if (decision.kind !== 'approve') {
      return
    }
    assert.deepEqual(decision.span, { in: 0, out: 3.203 })
    assert.equal(decision.reason, 'black')
    const approved = addCut(baseline, empty, clip, decision.span, 'a1', decision.reason)
    assert.deepEqual(listedOf(approved).map((c) => [c.in, c.out, c.reason]), [[0, 3.203, 'black']])
    assert.equal(stateOf(empty), 'pending')
    assert.equal(stateOf(approved), 'cut')
    assert.deepEqual(cutChanges(baseline, approved), { added: 1, removed: 0, trimmed: 0 })
    assert.equal(isDirty(baseline, approved), true)
    // Save writes the trim with the kind as its reason.
    assert.deepEqual(buildWriteBody(baseline, approved).clips[clip].trims, [
      { in: 0, out: 3.203, reason: 'black' },
    ])
    // A second approval over the new list adds nothing: it says it is cut.
    const again = press(approved)
    assert.equal(again.kind, 'said')
    assert.match(again.kind === 'said' ? again.words : '', /^Already cut: /)
    // Removing the cut, as the Cuts panel does, returns the mark to pending with nothing to save.
    const removed = removeCut(baseline, approved, clip, 'a1')
    assert.equal(stateOf(removed), 'pending')
    assert.equal(isDirty(baseline, removed), false)
    assert.equal(cutChanges(baseline, removed).added, 0)
  })

  it('leaves the draft alone when dismissed: nothing to save, no cut added', () => {
    const decision = decideDismiss({ state: 'pending', segment: suggestion, clipName: clip, locked: false })
    assert.equal(decision.kind, 'dismiss')
    assert.equal(isDirty(baseline, empty), false)
    assert.deepEqual(cutChanges(baseline, empty), { added: 0, removed: 0, trimmed: 0 })
  })

  it('adds nothing for an overlap or a span past the end, and names the panel’s cut number', () => {
    const withCut = addCut(baseline, empty, clip, { in: 1, out: 2 }, 'a1')
    const partly = press(withCut)
    assert.equal(partly.kind, 'refused')
    assert.match(partly.kind === 'refused' ? partly.words : '', /overlaps cut 1 \(0:01 to 0:02\)\. Remove that cut first\./)
    const past = decideApprove({
      state: 'pending',
      segment: { start: 24, end: 26, kind: 'freeze' },
      clipName: clip,
      locked: false,
      listed: listedOf(empty),
      length: 25,
    })
    assert.equal(past.kind, 'refused')
    assert.equal(listedOf(withCut).length, 1)
  })
})

describe('standingRefusal', () => {
  const listed = [{ in: 2, out: 4 }]
  const refusal: Refusal = {
    id: 'a',
    words: 'Not approved: this overlaps cut 1.',
    state: 'partly-cut',
    cuts: cutsKey(listed),
  }

  it('stands while the mark, its state and the clip’s cuts are as they were', () => {
    assert.equal(standingRefusal(refusal, 'a', 'partly-cut', [{ in: 2, out: 4 }]), refusal.words)
  })

  it('is dropped once the cut is removed or the list is back to none (a Reset)', () => {
    assert.equal(standingRefusal(refusal, 'a', 'partly-cut', [{ in: 2, out: 4, removed: true }]), null)
    assert.equal(standingRefusal(refusal, 'a', 'pending', []), null)
  })

  it('is dropped when the cut moves, or another is added, so its numbers cannot be stale', () => {
    assert.equal(standingRefusal(refusal, 'a', 'partly-cut', [{ in: 2, out: 5 }]), null)
    assert.equal(standingRefusal(refusal, 'a', 'partly-cut', [{ in: 0, out: 1 }, ...listed]), null)
  })

  it('is dropped when the state changes, and is never another mark’s', () => {
    assert.equal(standingRefusal(refusal, 'a', 'pending', listed), null)
    assert.equal(standingRefusal(refusal, 'b', 'partly-cut', listed), null)
    assert.equal(standingRefusal(null, 'a', 'partly-cut', listed), null)
  })

  it('follows the refusal decideApprove gives, and the span becomes approvable once the cut goes', () => {
    const segment = { start: 3, end: 5, kind: 'freeze' }
    const base = { state: 'partly-cut' as const, segment, clipName: 'a.mp4', locked: false, length: 60 }
    const refused = decideApprove({ ...base, listed })
    assert.equal(refused.kind, 'refused')
    const kept = {
      id: 'a',
      words: refused.kind === 'refused' ? refused.words : '',
      state: base.state,
      cuts: cutsKey(listed),
    }
    assert.notEqual(standingRefusal(kept, 'a', 'partly-cut', listed), null)
    const gone = [{ in: 2, out: 4, removed: true }]
    assert.equal(standingRefusal(kept, 'a', 'pending', gone), null)
    assert.equal(decideApprove({ ...base, state: 'pending', listed: gone }).kind, 'approve')
  })
})

describe('marks on a rippled track (timeline-ripple-layout)', () => {
  // A's leading cut runs from 0 to 2.00 s; its block starts at track time 0.
  const kept = { inMs: 2000, outMs: 10000 }

  it('a suggestion inside a leading cut is not drawn; one across it starts at the block’s left edge', () => {
    assert.equal(markSpan({ start: 0, end: 1.5 }, 0, kept), null)
    assert.deepEqual(markSpan({ start: 1, end: 3 }, 0, kept), { startMs: 0, endMs: 1000 })
    const placed = placeMarks([[markSpan({ start: 1, end: 3 }, 0, kept)!]], 40, 44)
    assert.equal(placed.placed[0][0].left, 0)
  })

  it('maps a kept suggestion by the clip’s start less its kept start, and clips one into a trailing cut', () => {
    assert.deepEqual(markSpan({ start: 4, end: 5 }, 8000, kept), { startMs: 10000, endMs: 11000 })
    assert.deepEqual(markSpan({ start: 9.5, end: 12 }, 8000, kept), { startMs: 15500, endMs: 16000 })
    assert.equal(markSpan({ start: 10, end: 11 }, 8000, kept), null)
    assert.equal(markSpan({ start: 1, end: 2 }, 8000, kept), null)
  })

  it('keeps a point mark at the kept start, and draws nothing in a clip that keeps nothing', () => {
    assert.deepEqual(markSpan({ start: 2, end: 2 }, 0, kept), { startMs: 0, endMs: 0 })
    assert.equal(markSpan({ start: 1, end: 3 }, 0, { inMs: 0, outMs: 0 }), null)
  })

  it('a clip with no edge cut maps as before', () => {
    assert.deepEqual(markSpan({ start: 1, end: 3 }, 5000, { inMs: 0, outMs: 6000 }), { startMs: 6000, endMs: 8000 })
  })
})
