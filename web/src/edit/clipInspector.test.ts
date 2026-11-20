import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  clipState,
  draftPlace,
  draftPlaceWords,
  moveToEndWords,
  offersOf,
  statusWords,
  stepAcrossWords,
  stepWords,
} from './clipInspector.ts'

const chapters = [
  { key: 'r0', name: 'Main', deleted: false },
  { key: 'r1', name: 'Kvällen', deleted: false },
  { key: 'r2', name: 'Gone', deleted: true },
]
const orders = new Map([
  ['r0', ['a.mp4', 'b.mp4']],
  ['r1', ['c.mp4']],
])

test('a removed clip is removed, whatever its status says', () => {
  assert.equal(clipState({ status: 'missing', played: false, removed: true }), 'removed')
})

test('the state follows the status, then whether a chapter plays the clip', () => {
  assert.equal(clipState({ status: 'ignored', played: false, removed: false }), 'ignored')
  assert.equal(clipState({ status: 'missing', played: true, removed: false }), 'missing')
  assert.equal(clipState({ status: 'active', played: true, removed: false }), 'played')
  assert.equal(clipState({ status: 'new', played: true, removed: false }), 'played')
  assert.equal(clipState({ status: 'active', played: false, removed: false }), null)
  // A missing clip no chapter lists any more (and that is not removed) offers nothing to do.
  assert.equal(clipState({ status: 'missing', played: false, removed: false }), null)
})

test('each state offers its own edits', () => {
  assert.deepEqual(offersOf('played'), { step: true, edits: true, action: 'ignore' })
  assert.deepEqual(offersOf('ignored'), { step: false, edits: false, action: 'include' })
  assert.deepEqual(offersOf('missing'), { step: true, edits: false, action: 'remove' })
  assert.deepEqual(offersOf('removed'), { step: false, edits: false, action: 'undo' })
  assert.deepEqual(offersOf(null), { step: false, edits: false, action: null })
})

test('the status in words', () => {
  assert.equal(statusWords('ignored', { status: 'ignored' }), 'Ignored: not in the movie')
  assert.equal(statusWords('missing', { status: 'missing' }), 'Missing from disk')
  assert.equal(
    statusWords('removed', { status: 'missing' }),
    'Removed from reel.yaml when you save.',
  )
  assert.equal(statusWords('played', { status: 'new' }), 'New, not yet in reel.yaml')
  assert.equal(statusWords('played', { status: 'active' }), 'Included')
  assert.equal(
    statusWords('played', { status: 'active', excluded: true }),
    'Excluded: not in the movie',
  )
})

test('a played clip is placed among its chapter’s clips', () => {
  const place = draftPlace(chapters, orders, [], 'b.mp4')
  assert.deepEqual(place, { chapter: 'Main', n: 2, of: 2 })
  assert.equal(draftPlaceWords(place!), 'Main · clip 2 of 2')
  assert.equal(draftPlaceWords(draftPlace(chapters, orders, [], 'c.mp4')!), 'Kvällen · clip 1 of 1')
})

test('a clip no chapter plays is placed by the list that holds it, with no position', () => {
  const ignored = new Map([['r1', ['d.mp4']]])
  const removed = new Map([['r0', ['e.mp4']]])
  assert.deepEqual(draftPlace(chapters, orders, [ignored, removed], 'd.mp4'), {
    chapter: 'Kvällen',
    n: null,
    of: null,
  })
  assert.equal(draftPlaceWords(draftPlace(chapters, orders, [ignored, removed], 'e.mp4')!), 'Main')
  assert.equal(draftPlace(chapters, orders, [ignored, removed], 'zz.mp4'), null)
})

test('a deleted chapter holds no place, and a lone unnamed chapter is called Clips', () => {
  assert.equal(draftPlace(chapters, new Map([['r2', ['x.mp4']]]), [], 'x.mp4'), null)
  const only = [{ key: 'r0', name: '', deleted: false }]
  assert.equal(
    draftPlaceWords(draftPlace(only, new Map([['r0', ['a', 'b', 'c']]]), [], 'c')!),
    'Clips · clip 3 of 3',
  )
})

test('the announcements are the bin’s and the keys’ words', () => {
  assert.equal(stepWords('s1710002.mp4', 0, 3), 's1710002.mp4 moved to position 1 of 3.')
  assert.equal(
    stepAcrossWords('Kvällen/s1710003.mp4', 'Main', null),
    'Moved s1710003.mp4. At the end of Main.',
  )
  assert.equal(
    stepAcrossWords('Main/s1710002.mp4', 'Kvällen', 'Kvällen/s1710003.mp4'),
    'Moved s1710002.mp4. Before s1710003.mp4.',
  )
  assert.equal(
    moveToEndWords('Kvällen/s1710003.mp4', 'Main'),
    'Moved s1710003.mp4. At the end of Main.',
  )
})
