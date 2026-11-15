import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { ignoredGroups } from './wideBin.ts'

const heading = (name: string) => (name === '' ? 'Main' : name)
const chapter = (key: string, name: string, deleted = false) => ({ key, name, deleted })

describe('ignoredGroups', () => {
  it('gives one group for the own chapter on Tjörn', () => {
    const groups = ignoredGroups(
      [chapter('r0', ''), chapter('r1', 'Kvällen')],
      new Map([['r0', ['s1710004.mp4']]]),
      heading,
    )
    assert.deepEqual(groups, [
      { key: 'r0', name: '', heading: 'Main', identities: ['s1710004.mp4'] },
    ])
  })

  it('groups named chapters in chapter order, each in its own order', () => {
    const groups = ignoredGroups(
      [chapter('r0', 'B'), chapter('r1', 'A')],
      new Map([
        ['r1', ['a2.mp4', 'a1.mp4']],
        ['r0', ['b.mp4']],
      ]),
      heading,
    )
    assert.deepEqual(
      groups.map((group) => [group.heading, group.identities]),
      [
        ['B', ['b.mp4']],
        ['A', ['a2.mp4', 'a1.mp4']],
      ],
    )
  })

  it('skips a deleted chapter and leaves out an empty group', () => {
    const groups = ignoredGroups(
      [chapter('r0', 'A', true), chapter('r1', 'B'), chapter('r2', 'C')],
      new Map([
        ['r0', ['x.mp4']],
        ['r1', []],
      ]),
      heading,
    )
    assert.deepEqual(groups, [])
  })

  it('gives none when nothing is ignored', () => {
    assert.deepEqual(ignoredGroups([chapter('r0', '')], new Map(), heading), [])
  })
})
