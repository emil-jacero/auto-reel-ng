import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { HELP_SECTIONS, helpKey, readHelp, writeHelp } from './helpState.ts'
import type { HelpStorage } from './helpState.ts'

function memory(initial: Record<string, string> = {}): HelpStorage & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial))
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
  }
}

const THROWING: HelpStorage = {
  getItem: () => {
    throw new Error('SecurityError')
  },
  setItem: () => {
    throw new Error('QuotaExceededError')
  },
}

describe('help state', () => {
  it('is closed by default, for every section', () => {
    const storage = memory()
    for (const section of HELP_SECTIONS) {
      assert.equal(readHelp(section, storage), false)
    }
  })

  it('round-trips per section without touching the others', () => {
    const storage = memory()
    writeHelp('clips', true, storage)
    assert.equal(readHelp('clips', storage), true)
    for (const section of HELP_SECTIONS.filter((s) => s !== 'clips')) {
      assert.equal(readHelp(section, storage), false)
    }
    writeHelp('clips', false, storage)
    assert.equal(readHelp('clips', storage), false)
  })

  it('keeps one key per section and leaves unrelated keys alone', () => {
    const storage = memory({ 'auto-reel:theme': 'dark' })
    writeHelp('timeline', true, storage)
    assert.deepEqual([...storage.data.keys()].sort(), ['auto-reel.help.timeline', 'auto-reel:theme'])
    assert.equal(storage.data.get('auto-reel:theme'), 'dark')
    assert.equal(new Set(HELP_SECTIONS.map(helpKey)).size, HELP_SECTIONS.length)
  })

  it('reads anything but the open value as closed', () => {
    assert.equal(readHelp('details', memory({ [helpKey('details')]: 'yes' })), false)
    assert.equal(readHelp('details', memory({ [helpKey('details')]: '' })), false)
  })

  it('does not throw when the storage throws, and reads closed', () => {
    assert.equal(readHelp('poster', THROWING), false)
    assert.doesNotThrow(() => writeHelp('poster', true, THROWING))
  })

  it('does not throw without a storage', () => {
    assert.equal(readHelp('cards', null), false)
    assert.doesNotThrow(() => writeHelp('cards', true, null))
  })
})
