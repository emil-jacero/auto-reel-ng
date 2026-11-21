import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import {
  BIN_PLAYER_KEY,
  SHORT_WINDOW_QUERY,
  binPlayerChoice,
  playerShown,
  readChoice,
  resetBinPlayerPref,
  setBinPlayerShown,
  subscribeBinPlayer,
  subscribeShortWindow,
  windowIsShort,
  writeChoice,
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

/** A window whose media query list says `matches` and keeps its change listeners. */
const fakeWindow = (storage: PrefStorage, matches: boolean) => {
  const state = { matches, queries: [] as string[], listeners: new Set<() => void>() }
  const win = {
    localStorage: storage,
    matchMedia(query: string) {
      state.queries.push(query)
      return {
        get matches() {
          return state.matches
        },
        addEventListener: (_type: string, listener: () => void) => void state.listeners.add(listener),
        removeEventListener: (_type: string, listener: () => void) =>
          void state.listeners.delete(listener),
      }
    },
  }
  ;(globalThis as { window?: unknown }).window = win
  return state
}

afterEach(() => {
  resetBinPlayerPref()
  delete (globalThis as { window?: unknown }).window
})

test('no stored choice is no choice, and shown and hidden are read as they are', () => {
  const storage = memory()
  assert.equal(readChoice(storage), null)
  storage.setItem(BIN_PLAYER_KEY, 'hidden')
  assert.equal(readChoice(storage), 'hidden')
  storage.setItem(BIN_PLAYER_KEY, 'shown')
  assert.equal(readChoice(storage), 'shown')
})

test('anything else stored is no choice', () => {
  const storage = memory()
  storage.setItem(BIN_PLAYER_KEY, 'garbage')
  assert.equal(readChoice(storage), null)
})

test('a choice is stored as auto-reel:bin-player=shown or hidden', () => {
  const storage = memory()
  writeChoice('hidden', storage)
  assert.equal(storage.data.get('auto-reel:bin-player'), 'hidden')
  writeChoice('shown', storage)
  assert.equal(storage.data.get('auto-reel:bin-player'), 'shown')
})

test('with no choice, a short window hides the player and a tall one shows it', () => {
  assert.equal(playerShown(null, true), false)
  assert.equal(playerShown(null, false), true)
})

test('an explicit choice wins over the height, short or tall', () => {
  assert.equal(playerShown('shown', true), true)
  assert.equal(playerShown('shown', false), true)
  assert.equal(playerShown('hidden', true), false)
  assert.equal(playerShown('hidden', false), false)
})

test('a storage that throws or is absent gives no choice, silently, so the height rule decides', () => {
  assert.equal(readChoice(refusing), null)
  assert.equal(readChoice(null), null)
  assert.doesNotThrow(() => writeChoice('hidden', refusing))
  assert.doesNotThrow(() => writeChoice('hidden', null))
  assert.equal(playerShown(readChoice(refusing), true), false)
  assert.equal(playerShown(readChoice(refusing), false), true)
})

test('the store reads the browser once, holds a choice and tells its readers', () => {
  const storage = memory()
  fakeWindow(storage, true)
  assert.equal(binPlayerChoice(), null)
  let told = 0
  const stop = subscribeBinPlayer(() => (told += 1))
  setBinPlayerShown(true)
  assert.equal(binPlayerChoice(), 'shown')
  assert.equal(storage.data.get(BIN_PLAYER_KEY), 'shown')
  setBinPlayerShown(false)
  assert.equal(binPlayerChoice(), 'hidden')
  assert.equal(storage.data.get(BIN_PLAYER_KEY), 'hidden')
  assert.equal(told, 2)
  stop()
  setBinPlayerShown(true)
  assert.equal(told, 2)
})

test('a choice stored by an earlier visit is read back and wins', () => {
  const storage = memory()
  storage.setItem(BIN_PLAYER_KEY, 'hidden')
  fakeWindow(storage, false)
  assert.equal(binPlayerChoice(), 'hidden')
  assert.equal(playerShown(binPlayerChoice(), windowIsShort()), false)
})

test('with storage that throws on access, there is no choice and a made choice holds for the visit', () => {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      get localStorage(): never {
        throw new Error('blocked')
      },
    },
  })
  assert.equal(binPlayerChoice(), null)
  assert.doesNotThrow(() => setBinPlayerShown(false))
  assert.equal(binPlayerChoice(), 'hidden')
})

test('the window is short by the height rule, follows a resize, and stops when unsubscribed', () => {
  const state = fakeWindow(memory(), true)
  assert.equal(windowIsShort(), true)
  let told = 0
  const stop = subscribeShortWindow(() => (told += 1))
  state.matches = false
  for (const listener of state.listeners) {
    listener()
  }
  assert.equal(windowIsShort(), false)
  assert.equal(told, 1)
  stop()
  assert.equal(state.listeners.size, 0)
  assert.ok(state.queries.every((query) => query === SHORT_WINDOW_QUERY))
})

test('a browser without matchMedia, or a window that throws, is not short', () => {
  ;(globalThis as { window?: unknown }).window = {}
  assert.equal(windowIsShort(), false)
  assert.doesNotThrow(() => subscribeShortWindow(() => undefined)())
  delete (globalThis as { window?: unknown }).window
  assert.equal(windowIsShort(), false)
})

test('the height rule is 70.125rem, the side pane layout only', () => {
  assert.match(SHORT_WINDOW_QUERY, /height < 70\.125rem/)
  assert.match(SHORT_WINDOW_QUERY, /width >= 960px/)
  assert.match(SHORT_WINDOW_QUERY, /not \(pointer: coarse\)/)
})
