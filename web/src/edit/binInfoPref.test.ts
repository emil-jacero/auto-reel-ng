import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import {
  BIN_INFO_KEY,
  binInfoHidden,
  readHidden,
  resetBinInfoPref,
  setBinInfoHidden,
  subscribeBinInfo,
  writeHidden,
} from './binInfoPref.ts'
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
  resetBinInfoPref()
  delete (globalThis as { window?: unknown }).window
})

test('the information starts shown, and only a stored hidden hides it', () => {
  const storage = memory()
  assert.equal(readHidden(storage), false)
  storage.setItem(BIN_INFO_KEY, 'garbage')
  assert.equal(readHidden(storage), false)
  storage.setItem(BIN_INFO_KEY, 'shown')
  assert.equal(readHidden(storage), false)
  storage.setItem(BIN_INFO_KEY, 'hidden')
  assert.equal(readHidden(storage), true)
})

test('the choice is stored as auto-reel:bin-info=shown or hidden', () => {
  const storage = memory()
  writeHidden(true, storage)
  assert.equal(storage.data.get('auto-reel:bin-info'), 'hidden')
  writeHidden(false, storage)
  assert.equal(storage.data.get('auto-reel:bin-info'), 'shown')
})

test('a storage that throws or is absent shows the information, silently', () => {
  assert.equal(readHidden(refusing), false)
  assert.equal(readHidden(null), false)
  assert.doesNotThrow(() => writeHidden(true, refusing))
  assert.doesNotThrow(() => writeHidden(true, null))
})

test('the store reads the browser once, keeps a choice and tells its readers', () => {
  const storage = memory()
  ;(globalThis as { window?: unknown }).window = { localStorage: storage }
  assert.equal(binInfoHidden(), false)
  let told = 0
  const stop = subscribeBinInfo(() => (told += 1))
  setBinInfoHidden(true)
  assert.equal(binInfoHidden(), true)
  assert.equal(storage.data.get(BIN_INFO_KEY), 'hidden')
  setBinInfoHidden(false)
  assert.equal(binInfoHidden(), false)
  assert.equal(told, 2)
  stop()
  setBinInfoHidden(true)
  assert.equal(told, 2)
})

test('a choice stored by an earlier visit is read back', () => {
  const storage = memory()
  storage.setItem(BIN_INFO_KEY, 'hidden')
  ;(globalThis as { window?: unknown }).window = { localStorage: storage }
  assert.equal(binInfoHidden(), true)
})

test('with storage that throws on access, a made choice holds for the visit', () => {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      get localStorage(): never {
        throw new Error('blocked')
      },
    },
  })
  assert.equal(binInfoHidden(), false)
  assert.doesNotThrow(() => setBinInfoHidden(true))
  assert.equal(binInfoHidden(), true)
})
