import assert from 'node:assert/strict'
import { test } from 'node:test'

import { EDGE_WORDS, stepMove } from './stepMove.ts'

const chapters = [
  { key: 'r0', identities: ['a', 'b', 'c'] },
  { key: 'r1', identities: ['d', 'e'] },
  { key: 'r2', identities: ['f'] },
]

/** Every clip is on disk unless named. */
const disk =
  (...missing: string[]) =>
  (identity: string) =>
    !missing.includes(identity)
const all = disk()

test('a step inside a chapter moves one place', () => {
  assert.deepEqual(stepMove(chapters, 'b', -1, all), {
    kind: 'move',
    chapter: 'r0',
    from: 1,
    to: 0,
  })
  assert.deepEqual(stepMove(chapters, 'b', 1, all), {
    kind: 'move',
    chapter: 'r0',
    from: 1,
    to: 2,
  })
  assert.deepEqual(stepMove(chapters, 'e', -1, all), {
    kind: 'move',
    chapter: 'r1',
    from: 1,
    to: 0,
  })
})

test('a step goes past a missing clip as past any listed clip', () => {
  const lay = [{ key: 'r0', identities: ['a', 'gone', 'c'] }]
  const on = disk('gone')
  assert.deepEqual(stepMove(lay, 'a', 1, on), { kind: 'move', chapter: 'r0', from: 0, to: 1 })
  assert.deepEqual(stepMove(lay, 'c', -1, on), { kind: 'move', chapter: 'r0', from: 2, to: 1 })
  // The missing clip itself steps inside its chapter too.
  assert.deepEqual(stepMove(lay, 'gone', 1, on), { kind: 'move', chapter: 'r0', from: 1, to: 2 })
  assert.deepEqual(stepMove(lay, 'gone', -1, on), { kind: 'move', chapter: 'r0', from: 1, to: 0 })
})

test('the first clip earlier goes to the end of the previous chapter', () => {
  assert.deepEqual(stepMove(chapters, 'd', -1, all), {
    kind: 'clip-drop',
    from: 'r1',
    to: 'r0',
    at: 3,
    before: null,
  })
  assert.deepEqual(stepMove(chapters, 'f', -1, all), {
    kind: 'clip-drop',
    from: 'r2',
    to: 'r1',
    at: 2,
    before: null,
  })
})

test('the last clip later goes before the first clip of the next chapter', () => {
  assert.deepEqual(stepMove(chapters, 'c', 1, all), {
    kind: 'clip-drop',
    from: 'r0',
    to: 'r1',
    at: 0,
    before: 'd',
  })
  assert.deepEqual(stepMove(chapters, 'e', 1, all), {
    kind: 'clip-drop',
    from: 'r1',
    to: 'r2',
    at: 0,
    before: 'f',
  })
})

test('a step into a chapter with a missing edge clip lands by its clips on disk', () => {
  const on = disk('gone1', 'gone2', 'gone3')
  // Later: before the next chapter's first clip on disk, after its missing lead clip.
  const later = [
    { key: 'r0', identities: ['a', 'gone1', 'b'] },
    { key: 'r1', identities: ['gone2', 'd', 'e', 'gone3'] },
  ]
  assert.deepEqual(stepMove(later, 'b', 1, on), {
    kind: 'clip-drop',
    from: 'r0',
    to: 'r1',
    at: 1,
    before: 'd',
  })
  // Earlier: after the previous chapter's last clip on disk, before its missing tail.
  const earlier = [
    { key: 'r0', identities: ['a', 'b', 'gone1'] },
    { key: 'r1', identities: ['d', 'e'] },
  ]
  assert.deepEqual(stepMove(earlier, 'd', -1, on), {
    kind: 'clip-drop',
    from: 'r1',
    to: 'r0',
    at: 2,
    before: null,
  })
})

test('a step into a chapter with no clip on disk lands at its start', () => {
  const lay = [
    { key: 'r0', identities: ['a'] },
    { key: 'r1', identities: ['gone1', 'gone2'] },
  ]
  const on = disk('gone1', 'gone2')
  assert.deepEqual(stepMove(lay, 'a', 1, on), {
    kind: 'clip-drop',
    from: 'r0',
    to: 'r1',
    at: 0,
    before: null,
  })
  const back = [
    { key: 'r0', identities: ['gone1', 'gone2'] },
    { key: 'r1', identities: ['d'] },
  ]
  assert.deepEqual(stepMove(back, 'd', -1, on), {
    kind: 'clip-drop',
    from: 'r1',
    to: 'r0',
    at: 0,
    before: null,
  })
})

test('a step into an empty chapter lands at its only gap, earlier or later', () => {
  const later = [
    { key: 'r0', identities: ['a'] },
    { key: 'r1', identities: [] },
  ]
  assert.deepEqual(stepMove(later, 'a', 1, all), {
    kind: 'clip-drop',
    from: 'r0',
    to: 'r1',
    at: 0,
    before: null,
  })
  const earlier = [
    { key: 'r0', identities: [] },
    { key: 'r1', identities: ['d', 'e'] },
  ]
  assert.deepEqual(stepMove(earlier, 'd', -1, all), {
    kind: 'clip-drop',
    from: 'r1',
    to: 'r0',
    at: 0,
    before: null,
  })
})

test('a missing clip at its chapter edge stays, with the reason', () => {
  const lay = [
    { key: 'r0', identities: ['a', 'gone'] },
    { key: 'r1', identities: ['gone2', 'd'] },
  ]
  const on = disk('gone', 'gone2')
  assert.deepEqual(stepMove(lay, 'gone', 1, on), { kind: 'edge', words: EDGE_WORDS.missing })
  assert.deepEqual(stepMove(lay, 'gone2', -1, on), { kind: 'edge', words: EDGE_WORDS.missing })
  assert.match(EDGE_WORDS.missing, /missing/)
})

test('the first and last clip of the event return Alt and an arrow’s words', () => {
  assert.deepEqual(stepMove(chapters, 'a', -1, all), {
    kind: 'edge',
    words: 'a is already the first clip.',
  })
  assert.deepEqual(stepMove(chapters, 'f', 1, all), {
    kind: 'edge',
    words: 'f is already the last clip.',
  })
  const single = [{ key: 'r0', identities: ['Main/s1710001.mp4'] }]
  assert.deepEqual(stepMove(single, 'Main/s1710001.mp4', -1, all), {
    kind: 'edge',
    words: 's1710001.mp4 is already the first clip.',
  })
  assert.deepEqual(stepMove(single, 'Main/s1710001.mp4', 1, all), {
    kind: 'edge',
    words: EDGE_WORDS.last('Main/s1710001.mp4'),
  })
})

test('a clip no chapter lists throws', () => {
  assert.throws(() => stepMove(chapters, 'zz', 1, all), /no listed chapter/)
})
