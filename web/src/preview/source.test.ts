import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { toMs } from './playback.ts'
import type { ClipProxy } from './source.ts'
import {
  COPY_HAS_SOUND,
  copyHasSound,
  ORIGINAL_WHY,
  copyCannotPlayTitle,
  copyEmptyTitle,
  copyGoneDetail,
  copyGoneTitle,
  copyLengthMs,
  copyUnreadableTitle,
  playCopyName,
  playOriginalName,
  playingCopyWords,
  playingOriginalWords,
  previewSource,
  sourceLine,
  withCopySentence,
} from './source.ts'

/*
 * Which file a clip's preview plays and the words that say so (`source.ts`), run by
 * `npm test`: a pure table of the detail's proxy state.
 */

const FACTS = {
  duration: 6.02,
  fps_num: 50,
  fps_den: 1,
  vfr: false,
  width: 960,
  height: 540,
  rotation: null,
  audio_codec: 'pcm_s16le',
  filmstrip: { tile_width: 96, tile_height: 54, columns: 6, tiles: 6, interval: 1 },
}

function proxy(state: string, facts: unknown = null): ClipProxy {
  return { state, facts, version: null, reason: null } as ClipProxy
}

describe('previewSource', () => {
  it('plays the copy when it is ready with a usable duration, and says its length in ms', () => {
    assert.deepEqual(previewSource(proxy('ready', FACTS)), {
      kind: 'copy',
      durationMs: 6020,
      hasSound: true,
    })
    assert.deepEqual(previewSource(proxy('ready', { ...FACTS, duration: 25.003 })), {
      kind: 'copy',
      durationMs: 25003,
      hasSound: true,
    })
  })

  it('says whether the copy carries sound from the facts audio codec, never guessing', () => {
    const sound = (audio_codec: unknown) => {
      const source = previewSource(proxy('ready', { ...FACTS, audio_codec }))
      assert.equal(source.kind, 'copy')
      return source.kind === 'copy' ? source.hasSound : null
    }
    assert.equal(sound('pcm_s16le'), true)
    assert.equal(sound('aac'), true)
    assert.equal(sound(null), false)
    assert.equal(sound(undefined), false)
    assert.equal(sound(''), false)
  })

  it('plays the original, unusable, for a ready state without a usable duration', () => {
    for (const duration of [null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY, '6.02', 0.0001]) {
      assert.deepEqual(previewSource(proxy('ready', { ...FACTS, duration })), {
        kind: 'original',
        why: 'unusable',
      })
    }
    assert.deepEqual(previewSource(proxy('ready', null)), { kind: 'original', why: 'unusable' })
    assert.deepEqual(previewSource(proxy('ready')), { kind: 'original', why: 'unusable' })
  })

  it('plays the original and says why for stale and failed', () => {
    assert.deepEqual(previewSource(proxy('stale')), { kind: 'original', why: 'stale' })
    assert.deepEqual(previewSource(proxy('failed')), { kind: 'original', why: 'failed' })
    // Facts of a state that is not ready are not looked at.
    assert.deepEqual(previewSource(proxy('stale', FACTS)), { kind: 'original', why: 'stale' })
  })

  it('plays the original, absent, for absent, no proxy object, and a state it does not know', () => {
    assert.deepEqual(previewSource(proxy('absent')), { kind: 'original', why: 'absent' })
    assert.deepEqual(previewSource(null), { kind: 'original', why: 'absent' })
    assert.deepEqual(previewSource(undefined), { kind: 'original', why: 'absent' })
    assert.deepEqual(previewSource(proxy('building', FACTS)), { kind: 'original', why: 'absent' })
  })

  it('answers the same input with equal output', () => {
    const input = proxy('ready', FACTS)
    assert.deepEqual(previewSource(input), previewSource(input))
  })
})

describe('copyLengthMs', () => {
  it('rounds to whole milliseconds and refuses what is not a duration', () => {
    assert.equal(copyLengthMs({ duration: 25.003 }), 25003)
    assert.equal(copyLengthMs({ duration: 6.0204 }), 6020)
    // The sub-millisecond part decides: half a millisecond or more rounds up, as toMs does.
    assert.equal(copyLengthMs({ duration: 6.0206 }), 6021)
    assert.equal(copyLengthMs({ duration: 25.0036 }), 25004)
    for (const duration of [6.0204, 6.0206, 25.003, 25.0036]) {
      assert.equal(copyLengthMs({ duration }), toMs(duration))
    }
    assert.equal(copyLengthMs({ duration: 0 }), null)
    assert.equal(copyLengthMs({}), null)
    assert.equal(copyLengthMs(null), null)
  })
})

describe('the words', () => {
  it('says which file plays, and why the original does when the detail leads there', () => {
    assert.equal(sourceLine('copy', null), 'Playing the preview copy')
    assert.equal(sourceLine('original', 'absent'), 'Playing the original')
    assert.equal(sourceLine('original', null), 'Playing the original')
    assert.equal(
      sourceLine('original', 'stale'),
      'Playing the original: its preview copy is out of date.',
    )
    assert.equal(
      sourceLine('original', 'failed'),
      'Playing the original: its preview copy could not be built.',
    )
    assert.equal(
      sourceLine('original', 'unusable'),
      'Playing the original: its preview copy has no usable length.',
    )
    assert.deepEqual(Object.keys(ORIGINAL_WHY).sort(), ['failed', 'stale', 'unusable'])
  })

  it('names the control and announces the swap with the clip', () => {
    assert.equal(playOriginalName('s1.mp4'), 'Play original of s1.mp4')
    assert.equal(playCopyName('s1.mp4'), 'Play preview copy of s1.mp4')
    assert.equal(playingOriginalWords('s1.mp4'), 'Playing the original of s1.mp4.')
    assert.equal(playingCopyWords('s1.mp4'), 'Playing the preview copy of s1.mp4.')
  })

  it('names the preview copy in every failure, and never says it changed on disk', () => {
    const titles = [
      copyGoneTitle('s1.mp4'),
      copyUnreadableTitle('s1.mp4'),
      copyEmptyTitle('s1.mp4'),
      copyCannotPlayTitle('s1.mp4'),
    ]
    for (const title of titles) {
      assert.match(title, /preview copy/)
      assert.match(title, /s1\.mp4/)
      assert.doesNotMatch(title, /changed on disk/)
    }
    // The service's 404 detail has no full stop; one that has is not given a second.
    assert.equal(copyGoneDetail('no proxy'), "no proxy. Play original plays the clip's own file.")
    assert.equal(
      copyGoneDetail('It is gone.'),
      "It is gone. Play original plays the clip's own file.",
    )
  })

  it('points the no-sound note at the copy', () => {
    assert.match(COPY_HAS_SOUND, /preview copy plays with sound/)
    assert.match(COPY_HAS_SOUND, /Play preview copy/)
    assert.equal(withCopySentence('No sound.', true), `No sound. ${COPY_HAS_SOUND}`)
    assert.equal(withCopySentence('No sound.', false), 'No sound.')
    assert.equal(copyHasSound({ audio_codec: 'pcm_s16le' }), true)
    assert.equal(copyHasSound({ audio_codec: null }), false)
    assert.equal(copyHasSound(null), false)
  })
})
