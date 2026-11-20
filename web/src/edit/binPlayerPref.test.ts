import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import {
  BIN_PLAYER_KEY,
  binPlayerShown,
  readShown,
  resetBinPlayerPref,
  setBinPlayerShown,
  subscribeBinPlayer,
  writeShown,
} from './binPlayerPref.ts'
import type { PrefStorage } from './binPlayerPref.ts'

const memory = (): PrefStorage & { data: Map<string, string> } => {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  }
}

const refusing: PrefStorage = {
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

afterEach(() => {
  resetBinPlayerPref()
  delete (globalThis as { window?: unknown }).window
})

test('absent means shown, and hidden is read as hidden', () => {
  const storage = memory()
  assert.equal(readShown(storage), true)
  storage.setItem(BIN_PLAYER_KEY, 'hidden')
  assert.equal(readShown(storage), false)
})

test('anything but hidden reads as shown', () => {
  const storage = memory()
  storage.setItem(BIN_PLAYER_KEY, 'shown')
  assert.equal(readShown(storage), true)
  storage.setItem(BIN_PLAYER_KEY, 'garbage')
  assert.equal(readShown(storage), true)
})

test('hidden is stored as auto-reel:bin-player=hidden and shown clears it', () => {
  const storage = memory()
  writeShown(false, storage)
  assert.equal(storage.data.get('auto-reel:bin-player'), 'hidden')
  writeShown(true, storage)
  assert.equal(storage.data.has('auto-reel:bin-player'), false)
})

test('a storage that throws or is absent falls back to shown, silently', () => {
  assert.equal(readShown(refusing), true)
  assert.equal(readShown(null), true)
  assert.doesNotThrow(() => writeShown(false, refusing))
  assert.doesNotThrow(() => writeShown(false, null))
})

test('the store reads the browser once, holds a choice and tells its readers', () => {
  const storage = memory()
  storage.setItem(BIN_PLAYER_KEY, 'hidden')
  ;(globalThis as { window?: unknown }).window = { localStorage: storage }
  assert.equal(binPlayerShown(), false)
  let told = 0
  const stop = subscribeBinPlayer(() => (told += 1))
  setBinPlayerShown(true)
  assert.equal(binPlayerShown(), true)
  assert.equal(storage.data.has(BIN_PLAYER_KEY), false)
  setBinPlayerShown(false)
  assert.equal(storage.data.get(BIN_PLAYER_KEY), 'hidden')
  assert.equal(told, 2)
  stop()
  setBinPlayerShown(true)
  assert.equal(told, 2)
})

test('with storage that throws on access, the store is shown and keeps the visit choice', () => {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      get localStorage(): never {
        throw new Error('blocked')
      },
    },
  })
  assert.equal(binPlayerShown(), true)
  assert.doesNotThrow(() => setBinPlayerShown(false))
  assert.equal(binPlayerShown(), false)
})
