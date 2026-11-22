import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Clip } from '../api/event.ts'
import { formatBytes, formatInstant } from '../format.ts'
import {
  AWAITING_PROXY,
  clipInfo,
  containerRotationWords,
  frameRateWords,
  keptSeconds,
  pictureWords,
  soundWords,
  UNKNOWN,
} from './clipInfo.ts'
import type { InfoLine, ProxyFacts } from './clipInfo.ts'
import type { DraftCut } from './draft.ts'

const clip = (over: Partial<Clip> = {}): Clip => ({
  identity: 'Kvällen/s1710004.mp4',
  status: 'active',
  size: 4_300_000,
  mtime: '2025-07-04T18:30:00Z',
  duration: 10,
  excluded: false,
  ...over,
})

const facts = (over: Partial<ProxyFacts> = {}): ProxyFacts => ({
  duration: 10,
  fps_num: 25,
  fps_den: 1,
  vfr: false,
  width: 960,
  height: 540,
  rotation: 0,
  audio_codec: 'aac',
  filmstrip: { tile_width: 96, tile_height: 54, columns: 10, tiles: 10, interval: 1 },
  ...over,
})

const cut = (from: number, to: number, over: Partial<DraftCut> = {}): DraftCut => ({
  key: `r${from}`,
  in: from,
  out: to,
  reason: null,
  removed: false,
  ...over,
})

const value = (lines: readonly InfoLine[], label: string) =>
  lines.find((line) => line.label === label)?.value

describe('the clip information’s frame rate', () => {
  it('writes a whole rate without decimals', () => {
    assert.equal(frameRateWords({ fps_num: 25, fps_den: 1, vfr: false }), '25 fps')
  })

  it('rounds a fractional rate to two decimals', () => {
    assert.equal(frameRateWords({ fps_num: 30000, fps_den: 1001, vfr: false }), '29.97 fps')
  })

  it('says a variable rate is about its average', () => {
    assert.equal(
      frameRateWords({ fps_num: 30000, fps_den: 1001, vfr: true }),
      'variable, about 29.97 fps',
    )
  })

  it('does not call a rate variable when the facts do not say so', () => {
    assert.equal(frameRateWords({ fps_num: 25, fps_den: 1, vfr: null }), '25 fps')
  })

  it('is unknown, not infinite or zero, for a rate that cannot be read', () => {
    assert.equal(frameRateWords({ fps_num: 25, fps_den: 0, vfr: false }), UNKNOWN)
    assert.equal(frameRateWords({ fps_num: 0, fps_den: 1, vfr: false }), UNKNOWN)
  })
})

describe('the clip information’s picture', () => {
  it('names the usual ratios, landscape and portrait', () => {
    assert.equal(pictureWords(1920, 1080), 'Landscape, 16:9')
    assert.equal(pictureWords(540, 960), 'Portrait, 9:16')
    assert.equal(pictureWords(1440, 1080), 'Landscape, 4:3')
    assert.equal(pictureWords(810, 540), 'Landscape, 3:2')
    assert.equal(pictureWords(540, 810), 'Portrait, 2:3')
    assert.equal(pictureWords(1260, 540), 'Landscape, 21:9')
  })

  it('calls a square picture square', () => {
    assert.equal(pictureWords(540, 540), 'Square, 1:1')
  })

  it('matches within 1 %', () => {
    // 960 × 540 stands for 16:9 even at 958 × 540 (0.2 % off).
    assert.equal(pictureWords(958, 540), 'Landscape, 16:9')
  })

  it('says "about" for an odd ratio, long side first', () => {
    assert.equal(pictureWords(999, 540), 'Landscape, about 1.85:1')
    assert.equal(pictureWords(540, 999), 'Portrait, about 1:1.85')
  })

  it('shows no pixel size', () => {
    assert.doesNotMatch(pictureWords(960, 540) ?? '', /540|960|×/)
  })

  it('is null when the size is not a size', () => {
    assert.equal(pictureWords(0, 540), null)
    assert.equal(pictureWords(960, Number.NaN), null)
  })
})

describe('the clip information’s rotation and sound', () => {
  it('names a container rotation of 90 degrees', () => {
    assert.equal(containerRotationWords(90), 'Turned 90° by its container')
    assert.equal(containerRotationWords(180), 'Turned 180° by its container')
    assert.equal(containerRotationWords(-90), 'Turned 270° by its container')
  })

  it('says nothing of no rotation', () => {
    assert.equal(containerRotationWords(0), null)
    assert.equal(containerRotationWords(null), null)
    assert.equal(containerRotationWords(360), null)
  })

  it('shows a value that is not a quarter-turn as it is', () => {
    assert.equal(containerRotationWords(45), 'Turned 45° by its container')
  })

  it('writes the codec in capitals, PCM for any pcm_*, and No sound for none', () => {
    assert.equal(soundWords('aac'), 'AAC')
    assert.equal(soundWords('pcm_s16le'), 'PCM')
    assert.equal(soundWords('pcm_s24be'), 'PCM')
    assert.equal(soundWords(null), 'No sound')
  })
})

describe('the clip information’s lines', () => {
  it('reads the event and the proxy’s facts', () => {
    const lines = clipInfo(clip(), facts({ rotation: 90, vfr: true, fps_num: 30000, fps_den: 1001 }), [], 'Kvällen · 2 of 3')
    assert.equal(value(lines, 'Status'), 'Included')
    assert.equal(value(lines, 'Chapter'), 'Kvällen · 2 of 3')
    assert.equal(value(lines, 'Size'), formatBytes(4_300_000))
    assert.equal(value(lines, 'Modified'), formatInstant('2025-07-04T18:30:00Z'))
    assert.equal(value(lines, 'Length'), '0:10')
    assert.equal(value(lines, 'Kept length'), undefined)
    assert.equal(value(lines, 'Frame rate'), 'variable, about 29.97 fps')
    assert.equal(value(lines, 'Picture'), 'Landscape, 16:9')
    assert.equal(value(lines, 'Rotation'), 'Turned 90° by its container')
    assert.equal(value(lines, 'Sound'), 'AAC')
    assert.equal(value(lines, 'Cuts'), 'None')
  })

  it('leaves out the chapter line for a clip with no place and the rotation line for no rotation', () => {
    const lines = clipInfo(clip({ status: 'ignored' }), facts(), [], null)
    assert.equal(value(lines, 'Chapter'), undefined)
    assert.equal(value(lines, 'Rotation'), undefined)
    assert.equal(value(lines, 'Status'), 'Ignored')
  })

  it('says Excluded for an excluded clip, and Missing then Excluded for a missing one', () => {
    assert.equal(value(clipInfo(clip({ excluded: true }), null, [], null), 'Status'), 'Excluded')
    assert.equal(
      value(clipInfo(clip({ status: 'missing', excluded: true }), null, [], null), 'Status'),
      'Missing from disk · Excluded',
    )
  })

  it('shows the draft’s turn in the rotation words', () => {
    assert.equal(value(clipInfo(clip(), null, [], null, 270), 'Turn'), 'Rotated 270 degrees')
    assert.equal(value(clipInfo(clip(), null, [], null), 'Turn'), undefined)
  })

  it('shows a no-sound clip as No sound', () => {
    assert.equal(value(clipInfo(clip(), facts({ audio_codec: null }), [], null), 'Sound'), 'No sound')
  })
})

describe('the clip information without what it has not got', () => {
  it('says "unknown" for a null duration, never a zero', () => {
    const lines = clipInfo(clip({ duration: null }), null, [cut(1, 2)], null)
    assert.equal(value(lines, 'Length'), UNKNOWN)
    assert.equal(value(lines, 'Kept length'), UNKNOWN)
    assert.ok(lines.every((line) => !/^0(:00)?$/.test(line.value)))
  })

  it('takes the length from the facts when the read has none', () => {
    const lines = clipInfo(clip({ duration: null }), facts({ duration: 7.5 }), [], null)
    assert.equal(value(lines, 'Length'), '0:07.5')
  })

  it('does not take a zero duration for a length', () => {
    assert.equal(value(clipInfo(clip({ duration: 0 }), null, [], null), 'Length'), UNKNOWN)
  })

  it('says size and time are unknown when the read has none', () => {
    const lines = clipInfo(clip({ size: null, mtime: null }), null, [], null)
    assert.equal(value(lines, 'Size'), UNKNOWN)
    assert.equal(value(lines, 'Modified'), UNKNOWN)
  })

  it('without facts, shows one line that says what waits for the proxy and invents no fact', () => {
    const lines = clipInfo(clip(), null, [], null)
    const proxy = lines.filter((line) => line.section === 'proxy')
    assert.deepEqual(proxy, [{ section: 'proxy', label: 'Proxy', value: AWAITING_PROXY }])
    for (const label of ['Frame rate', 'Picture', 'Rotation', 'Sound']) {
      assert.equal(value(lines, label), undefined)
    }
  })
})

describe('the clip information of a missing clip', () => {
  const sommarlov = clip({
    identity: 'borttagen.mp4',
    status: 'missing',
    size: null,
    mtime: null,
    duration: null,
  })

  it('says it is missing, where it is and its cuts, and no size, time, length or proxy', () => {
    const lines = clipInfo(
      sommarlov,
      null,
      [cut(1, 2.5, { reason: 'manual' }), cut(4, 5)],
      'Clips · 3 of 3',
    )
    assert.deepEqual(
      lines.map((line) => [line.section, line.label, line.value]),
      [
        ['read', 'Status', 'Missing from disk'],
        ['read', 'Chapter', 'Clips · 3 of 3'],
        ['cuts', 'Cut 1', '0:01 to 0:02.5 · 1.5 s · Cut by hand'],
        ['cuts', 'Cut 2', '0:04 to 0:05 · 1 s'],
      ],
    )
  })

  it('has no cuts line but "None" when it has no cuts, and still no proxy line', () => {
    const lines = clipInfo(sommarlov, null, [], 'Clips · 3 of 3')
    assert.deepEqual(
      lines.map((line) => line.label),
      ['Status', 'Chapter', 'Cuts'],
    )
  })
})

describe('the clip information’s status', () => {
  it('says what the clip passed in says: the caller passes the draft’s view of it', () => {
    assert.equal(value(clipInfo(clip({ status: 'ignored' }), null, [], null), 'Status'), 'Ignored')
    assert.equal(value(clipInfo(clip({ status: 'active' }), null, [], null), 'Status'), 'Included')
  })
})

describe('the clip information’s cuts', () => {
  it('lists each cut in the Cuts panel’s time format with its reason', () => {
    const lines = clipInfo(
      clip(),
      null,
      [cut(0, 1.5, { reason: 'black' }), cut(62.35, 70, { reason: 'Shaky' }), cut(3, 4)],
      null,
    )
    const cuts = lines.filter((line) => line.section === 'cuts')
    assert.deepEqual(cuts, [
      { section: 'cuts', label: 'Cut 1', value: '0:00 to 0:01.5 · 1.5 s · Black frames' },
      { section: 'cuts', label: 'Cut 2', value: '1:02.35 to 1:10 · 7.65 s · “Shaky”' },
      { section: 'cuts', label: 'Cut 3', value: '0:03 to 0:04 · 1 s' },
    ])
  })

  it('leaves a removed cut out and keeps the others’ numbers as the panel numbers them', () => {
    const lines = clipInfo(clip(), null, [cut(0, 1, { removed: true }), cut(3, 4)], null)
    const cuts = lines.filter((line) => line.section === 'cuts')
    assert.deepEqual(cuts, [{ section: 'cuts', label: 'Cut 2', value: '0:03 to 0:04 · 1 s' }])
    // The removed cut still plays: only the 1 s cut at 3–4 is taken from the 10 s.
    assert.equal(value(lines, 'Kept length'), '0:09')
  })

  it('subtracts the union of overlapping cuts from the kept length, once', () => {
    // 1–2.5 and 2–3 cover 1–3: 2 s of a 10 s clip.
    const cuts = [cut(1, 2.5), cut(2, 3)]
    assert.equal(keptSeconds(10, cuts), 8)
    const lines = clipInfo(clip(), null, cuts, null)
    assert.equal(value(lines, 'Length'), '0:10')
    assert.equal(value(lines, 'Kept length'), '0:08')
  })

  it('counts a cut past the clip’s end only up to the end', () => {
    assert.equal(keptSeconds(5, [cut(4, 9)]), 4)
  })

  it('has no kept length for an unknown length', () => {
    assert.equal(keptSeconds(null, [cut(1, 2)]), null)
  })
})
