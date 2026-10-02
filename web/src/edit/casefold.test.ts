import assert from 'node:assert/strict'
import { test } from 'node:test'

import { casefold, foldEntries } from './casefold.ts'

// Expected values are Python 3.14.7 `str.casefold()` (Unicode 16.0.0), written as code points.
const FROM_PYTHON: ReadonlyArray<[string, string]> = [
  ['ß', 'ss'], // ß
  ['ẞ', 'ss'], // ẞ
  ['ſ', 's'], // ſ
  ['ς', 'σ'], // final ς -> σ
  ['Σ', 'σ'], // Σ -> σ
  ['ı', 'ı'], // dotless ı stays apart from i
  ['İ', 'i̇'], // İ -> i + combining dot
  ['ﬃ', 'ffi'], // ﬃ
  ['Ꭰ', 'Ꭰ'], // Cherokee capital stays
  ['ꭰ', 'Ꭰ'], // Cherokee small -> capital
  ['ᏸ', 'Ᏸ'],
  ['ᾳ', 'αι'], // ᾳ (Greek with ypogegrammeni)
  ['ᾼ', 'αι'], // ᾼ
  ['ǅ', 'ǆ'], // ǅ
  ['K', 'k'], // Kelvin sign
  ['ΐ', 'ΐ'], // ΐ
  ['Straße', 'strasse'],
  ['KVÄLLEN', 'kvällen'],
  ['Kvällen', 'kvällen'],
  ['', ''],
  ['already folded 123', 'already folded 123'],
]

test('casefold equals Python str.casefold on the pinned spot values', () => {
  for (const [input, expected] of FROM_PYTHON) {
    assert.equal(casefold(input), expected, JSON.stringify(input))
  }
})

test('ı and i are kept apart; ß, ss and ẞ are one name', () => {
  assert.notEqual(casefold('ı'), casefold('i'))
  assert.equal(casefold('STRASSE'), casefold('Straße'))
  assert.equal(casefold('ẞ'), casefold('SS'))
})

test('characters outside the BMP fold too, and are not split', () => {
  // U+10400 DESERET CAPITAL LETTER LONG I -> U+10428
  assert.equal(casefold('\u{10400}'), '\u{10428}')
  assert.equal(casefold('\u{10428}x'), '\u{10428}x')
})

test('the table is whole, idempotent, and every entry folds to itself', () => {
  const entries = foldEntries()
  assert.ok(entries.size > 1500, `table has ${entries.size} entries`)
  for (const [code, folded] of entries) {
    const char = String.fromCodePoint(code)
    assert.notEqual(folded, char, `entry U+${code.toString(16)} folds to something else`)
    assert.equal(casefold(folded), folded, `U+${code.toString(16)} folds to a fixed point`)
    assert.equal(casefold(char), folded)
  }
  const sample = 'Äpplen & Ärtor ẞ ǅ İ ﬃ'
  assert.equal(casefold(casefold(sample)), casefold(sample))
})
