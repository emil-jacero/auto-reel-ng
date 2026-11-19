import assert from 'node:assert/strict'
import { test } from 'node:test'

import { readEnabled, SHORTCUTS_KEY, writeEnabled } from './shortcutSwitch.ts'
import type { SwitchStorage } from './shortcutSwitch.ts'

const memory = (): SwitchStorage & { data: Map<string, string> } => {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  }
}

const refusing: SwitchStorage = {
  getItem() {
    throw new Error('blocked')
  },
  setItem() {
    throw new Error('blocked')
  },
  removeItem() {
    throw new Error('blocked')
  },
}

test('absent means on, and off is read as off', () => {
  const storage = memory()
  assert.equal(readEnabled(storage), true)
  storage.setItem(SHORTCUTS_KEY, 'off')
  assert.equal(readEnabled(storage), false)
})

test('anything but off reads as on', () => {
  const storage = memory()
  storage.setItem(SHORTCUTS_KEY, 'on')
  assert.equal(readEnabled(storage), true)
  storage.setItem(SHORTCUTS_KEY, 'garbage')
  assert.equal(readEnabled(storage), true)
})

test('off is stored as auto-reel:shortcuts=off and on clears it', () => {
  const storage = memory()
  writeEnabled(false, storage)
  assert.equal(storage.data.get('auto-reel:shortcuts'), 'off')
  writeEnabled(true, storage)
  assert.equal(storage.data.has('auto-reel:shortcuts'), false)
})

test('a storage that throws or is absent falls back to on, silently', () => {
  assert.equal(readEnabled(refusing), true)
  assert.equal(readEnabled(null), true)
  assert.doesNotThrow(() => writeEnabled(false, refusing))
  assert.doesNotThrow(() => writeEnabled(false, null))
})
