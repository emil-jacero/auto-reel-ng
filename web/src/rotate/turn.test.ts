import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  groupTurnAnnouncement,
  normalizeTurn,
  rotatedCount,
  stepTurn,
  turnAnnouncement,
  turnAttr,
  turnWords,
  turnsOf,
} from './turn.ts'

describe('normalizeTurn', () => {
  it('maps multiples of 90 into 0..270', () => {
    const table: [unknown, number | null][] = [
      [0, 0],
      [90, 90],
      [180, 180],
      [270, 270],
      [-90, 270],
      [-180, 180],
      [360, 0],
      [450, 90],
      [-270, 90],
      [null, 0],
      [undefined, 0],
    ]
    for (const [value, expected] of table) {
      assert.equal(normalizeTurn(value), expected, String(value))
    }
  })

  it('refuses what is not a quarter turn', () => {
    for (const value of [45, 1.5, 89, NaN, Infinity, '90', {}, true]) {
      assert.equal(normalizeTurn(value), null, String(value))
    }
  })
})

describe('stepTurn', () => {
  it('turns right and left and wraps', () => {
    assert.equal(stepTurn(0, 'right'), 90)
    assert.equal(stepTurn(90, 'right'), 180)
    assert.equal(stepTurn(270, 'right'), 0)
    assert.equal(stepTurn(0, 'left'), 270)
    assert.equal(stepTurn(90, 'left'), 0)
  })
})

describe('words', () => {
  it('names a turn and says nothing for none', () => {
    assert.equal(turnWords(90), 'Rotated 90 degrees')
    assert.equal(turnWords(270), 'Rotated 270 degrees')
    assert.equal(turnWords(0), '')
    assert.equal(turnAttr(0), undefined)
    assert.equal(turnAttr(180), '180')
  })

  it('announces one press and one group press', () => {
    assert.equal(turnAnnouncement('s1.mp4', 90, 'right'), 's1.mp4 rotated 90 degrees right.')
    assert.equal(turnAnnouncement('s1.mp4', 270, 'left'), 's1.mp4 rotated 270 degrees left.')
    assert.equal(turnAnnouncement('s1.mp4', 0, 'left'), 's1.mp4 no longer rotated.')
    assert.equal(groupTurnAnnouncement(3, 'right'), '3 clips rotated right.')
    assert.equal(groupTurnAnnouncement(1, 'left'), '1 clip rotated left.')
  })

  it('counts clips for the save bar', () => {
    assert.equal(rotatedCount(1), '1 clip rotated')
    assert.equal(rotatedCount(3), '3 clips rotated')
  })
})

describe('turnsOf', () => {
  it('reads a document: -90 is 270, 45 and 0 are none', () => {
    const turns = turnsOf({
      a: { rotate: 90 },
      b: { rotate: -90 },
      c: { rotate: 45 },
      d: { rotate: 0 },
      e: { rotate: null },
      f: {},
      g: { rotate: 360 },
    })
    assert.deepEqual([...turns], [
      ['a', 90],
      ['b', 270],
    ])
  })
})
