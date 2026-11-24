import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import {
  PANES_KEY,
  STACKED_QUERY,
  isPaneHidden,
  isStacked,
  panePrefs,
  readPanes,
  registerPaneShower,
  resetPanePrefs,
  setPanePrefs,
  showPane,
  subscribePanePrefs,
  writePanes,
} from './paneSizesPref.ts'
import type { PrefStorage } from './paneSizesPref.ts'

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

const fakeWindow = (storage: PrefStorage, matches: boolean) => {
  const state = { matches, queries: [] as string[] }
  ;(globalThis as { window?: unknown }).window = {
    localStorage: storage,
    matchMedia(query: string) {
      state.queries.push(query)
      return {
        get matches() {
          return state.matches
        },
        addEventListener() {},
        removeEventListener() {},
      }
    },
  }
  return state
}

afterEach(() => {
  resetPanePrefs()
  delete (globalThis as { window?: unknown }).window
})

test('a fake storage round-trips sizes and a hidden pane', () => {
  const storage = memory()
  const prefs = { sizes: { bin: 317, insp: 420, tl: 360 }, hidden: ['tl'] as const }
  writePanes(prefs, storage)
  assert.equal(storage.data.get(PANES_KEY), '{"bin":317,"insp":420,"tl":360,"hidden":["tl"]}')
  assert.deepEqual(readPanes(storage), prefs)
})

test('prefs with nothing in them remove the key', () => {
  const storage = memory()
  writePanes({ sizes: { bin: 300 }, hidden: [] }, storage)
  assert.ok(storage.data.has(PANES_KEY))
  writePanes({ sizes: {}, hidden: [] }, storage)
  assert.ok(!storage.data.has(PANES_KEY))
})

test('a storage that throws gives the empty prefs and the prefs stay in memory', () => {
  assert.deepEqual(readPanes(refusing), { sizes: {}, hidden: [] })
  assert.doesNotThrow(() => writePanes({ sizes: { bin: 300 }, hidden: [] }, refusing))
  fakeWindow(refusing, false)
  assert.deepEqual(panePrefs(), { sizes: {}, hidden: [] })
  setPanePrefs({ sizes: { bin: 300 }, hidden: ['insp'] })
  assert.deepEqual(panePrefs(), { sizes: { bin: 300 }, hidden: ['insp'] })
})

test('an unparsable stored value reads as the empty prefs', () => {
  const storage = memory()
  storage.setItem(PANES_KEY, '{"bin":')
  assert.deepEqual(readPanes(storage), { sizes: {}, hidden: [] })
  storage.setItem(PANES_KEY, '{"bin":-4}')
  assert.deepEqual(readPanes(storage), { sizes: {}, hidden: [] })
})

test('listeners are told on every set and not after they unsubscribe', () => {
  fakeWindow(memory(), false)
  let told = 0
  const stop = subscribePanePrefs(() => {
    told += 1
  })
  setPanePrefs({ sizes: { bin: 300 }, hidden: [] })
  setPanePrefs({ sizes: {}, hidden: [] })
  assert.equal(told, 2)
  stop()
  setPanePrefs({ sizes: { bin: 301 }, hidden: [] })
  assert.equal(told, 2)
})

test('panePrefs returns the same object between changes', () => {
  const storage = memory()
  storage.setItem(PANES_KEY, '{"bin":300}')
  fakeWindow(storage, false)
  assert.equal(panePrefs(), panePrefs())
  const before = panePrefs()
  setPanePrefs({ sizes: { bin: 310 }, hidden: [] })
  assert.notEqual(panePrefs(), before)
  assert.equal(panePrefs(), panePrefs())
  assert.equal(storage.data.get(PANES_KEY), '{"bin":310}')
})

test('isStacked is false without matchMedia and follows the query', () => {
  assert.equal(isStacked(), false)
  const state = fakeWindow(memory(), true)
  assert.equal(isStacked(), true)
  assert.equal(state.queries.at(-1), STACKED_QUERY)
  state.matches = false
  assert.equal(isStacked(), false)
})

test('isPaneHidden is true when wide and false when stacked', () => {
  const state = fakeWindow(memory(), false)
  setPanePrefs({ sizes: {}, hidden: ['bin'] })
  assert.equal(isPaneHidden('bin'), true)
  assert.equal(isPaneHidden('insp'), false)
  state.matches = true
  assert.equal(isPaneHidden('bin'), false)
})

test('showPane does nothing without a shower, calls the registered one, and stops after unregistering', () => {
  showPane('bin')
  const calls: string[] = []
  const off = registerPaneShower((pane) => void calls.push(pane))
  showPane('insp')
  assert.deepEqual(calls, ['insp'])
  off()
  showPane('tl')
  assert.deepEqual(calls, ['insp'])
})
