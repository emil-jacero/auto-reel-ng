import assert from 'node:assert/strict'
import { test } from 'node:test'

import { clipPlace, clipSelectedWords, cutSelectedWords, lengthWords, placeWords } from './clipPanel.ts'

const clips = [
  { identity: 'a.mp4', name: 'a.mp4', chapter: 0, kept: { inMs: 0, outMs: 5000 }, drawn: [] },
  { identity: 'b.mp4', name: 'b.mp4', chapter: 1, kept: { inMs: 1000, outMs: 13500 }, drawn: [] },
  { identity: 'c.mp4', name: 'c.mp4', chapter: 1, kept: { inMs: 0, outMs: 2000 }, drawn: [{ from: 500, to: 1000 }] },
]

test('a clip is placed among its chapter’s clips, by the chapter’s name', () => {
  const place = clipPlace(clips, 'b.mp4', ['', 'Kvällen'])
  assert.ok(place !== null)
  assert.equal(placeWords(place), 'Kvällen · clip 1 of 2')
  assert.equal(clipPlace(clips, 'c.mp4', ['', 'Kvällen'])?.n, 2)
})

test('the unnamed chapter is called as the bin calls it', () => {
  const place = clipPlace(clips, 'a.mp4', ['', 'Kvällen'])
  assert.equal(place === null ? '' : placeWords(place), 'Main · clip 1 of 1')
  const alone = clipPlace(clips.slice(0, 1), 'a.mp4', [''])
  assert.equal(alone === null ? '' : placeWords(alone), 'Clips · clip 1 of 1')
})

test('the length is the kept extent, in words', () => {
  const place = clipPlace(clips, 'b.mp4', ['', 'Kvällen'])
  assert.ok(place !== null)
  assert.equal(place.lengthMs, 12500)
  assert.equal(lengthWords(place), '12.5 s in the movie')
})

test('cuts inside the clip are not in its length in the movie', () => {
  assert.equal(clipPlace(clips, 'c.mp4', ['', 'Kvällen'])?.lengthMs, 1500)
})

test('a clip the track does not have has no place', () => {
  assert.equal(clipPlace(clips, 'x.mp4', ['']), null)
})

test('the announcements name the clip or the cut once', () => {
  const place = clipPlace(clips, 'b.mp4', ['', 'Kvällen'])
  assert.ok(place !== null)
  assert.equal(clipSelectedWords(place), 'b.mp4 selected, Kvällen · clip 1 of 2')
  assert.equal(cutSelectedWords(2, 'b.mp4'), 'Cut 2 of b.mp4 selected')
})
