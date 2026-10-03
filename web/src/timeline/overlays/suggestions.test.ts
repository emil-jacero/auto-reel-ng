import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Analysis } from '../../api/analysis.ts'
import {
  ANALYZED_CLEAN,
  NEVER_ANALYZED,
  alreadyCutWords,
  approvedWords,
  approval,
  clipNotAnalyzed,
  dismissalKey,
  dismissedWords,
  dropGone,
  eventNote,
  laneName,
  laneRows,
  markName,
  neighbour,
  notApprovedWords,
  restoredWords,
  stackMarks,
  stepOfKey,
  suggestionKey,
  suggestionState,
} from './suggestions.ts'
import type { SuggestionKeyEvent } from './suggestions.ts'

const black = { start: 0, end: 3.2, kind: 'black' }
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

  it('makes the lane as high as the clip that needs the most rows', () => {
    const crowded = [at(10), at(11), at(12)]
    const sparse = [at(10), at(30)]
    assert.equal(laneRows([sparse, crowded, []], 10, 44), 3)
    assert.equal(laneRows([], 10, 44), 0)
    // Zoomed in the crowded clip needs one row.
    assert.equal(laneRows([crowded], 100, 44), 1)
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
    assert.equal(eventNote({ analyzed: false, segments: {} }), NEVER_ANALYZED)
    assert.match(NEVER_ANALYZED, /auto-reel analyze/)
    assert.equal(eventNote({ analyzed: true, segments: { 'a.mp4': [] } }), ANALYZED_CLEAN)
    assert.equal(
      eventNote({
        analyzed: true,
        segments: { 'a.mp4': [{ start: 0, end: 1, kind: 'black', confidence: 1 }] },
      }),
      null,
    )
  })

  it('marks a clip with no entry "Not analyzed" only in an analysed event', () => {
    const analysed: Analysis = { analyzed: true, segments: { 'a.mp4': [], 'b.mp4': [] } }
    assert.equal(clipNotAnalyzed(analysed, 'c.mp4'), true)
    assert.equal(clipNotAnalyzed(analysed, 'a.mp4'), false) // analysed, nothing found
    assert.equal(clipNotAnalyzed({ analyzed: false, segments: {} }, 'c.mp4'), false)
  })

  it('does not take a clip named like an Object prototype member as analysed', () => {
    const analysed: Analysis = { analyzed: true, segments: { 'a.mp4': [] } }
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
