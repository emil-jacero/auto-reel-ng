import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { rowLength, rowPlace, rowWords } from './binList.ts'
import type { BinRow } from './binList.ts'

const row = (over: Partial<BinRow> = {}): BinRow => ({
  identity: 'Kvällen/s1710002.mp4',
  name: 's1710002.mp4',
  group: 'listed',
  place: 'Kvällen · 2 of 3',
  moved: null,
  status: 'Included',
  keptMs: 6020,
  typed: false,
  onDisk: true,
  ...over,
})

describe('rowPlace', () => {
  it('is the place, with the move after it', () => {
    assert.equal(rowPlace(row()), 'Kvällen · 2 of 3')
    assert.equal(rowPlace(row({ moved: 'was 4' })), 'Kvällen · 2 of 3 · was 4')
    assert.equal(rowPlace(row({ moved: 'from Main' })), 'Kvällen · 2 of 3 · from Main')
  })

  it('is none for an ignored or a removed clip', () => {
    assert.equal(rowPlace(row({ place: null, group: 'ignored' })), null)
  })
})

describe('rowLength', () => {
  it('writes a length as the Timeline does, and none for an unknown one', () => {
    assert.equal(rowLength(row()), '0:06.02')
    assert.equal(rowLength(row({ keptMs: null })), null)
  })
})

describe('rowWords', () => {
  it('says name, place, status and kept length', () => {
    assert.equal(rowWords(row()), 's1710002.mp4, Kvällen · 2 of 3, Included, kept 0:06.02')
  })

  it('says a move and a typed cut', () => {
    assert.equal(
      rowWords(row({ moved: 'was 4', typed: true })),
      's1710002.mp4, Kvällen · 2 of 3 · was 4, Included, kept 0:06.02, a typed cut waits',
    )
  })

  it('leaves out the place and the length when there is none, and never writes a zero', () => {
    assert.equal(
      rowWords(row({ place: null, group: 'ignored', status: 'Ignored', keptMs: null })),
      's1710002.mp4, Ignored',
    )
  })
})
