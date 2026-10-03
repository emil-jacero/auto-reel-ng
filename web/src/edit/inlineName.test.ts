import assert from 'node:assert/strict'
import { test } from 'node:test'

import { NAME_REFUSAL, checkName } from './chapterNames.ts'
import type { DraftChapter } from './draft.ts'
import {
  FILE_NAME_NOTE,
  UNTITLED,
  acceptAnything,
  decideName,
  nameUnsent,
  titleLine,
} from './inlineName.ts'

const chapter = (key: string, name: string, deleted = false): DraftChapter => ({
  key,
  readName: name,
  name,
  deleted,
})
const chapters = [chapter('r0', ''), chapter('r1', 'Kvällen'), chapter('r2', 'Straße')]
const check = (typed: string) => checkName(chapters, typed, 'r1')

test('a new name is kept, stripped; the same name, spaces aside, changes nothing', () => {
  assert.deepEqual(decideName('Kväll', 'Kvällen', check), { kind: 'keep', name: 'Kväll' })
  assert.deepEqual(decideName(' Kväll på stranden ', 'Kvällen', check), {
    kind: 'keep',
    name: 'Kväll på stranden',
  })
  assert.deepEqual(decideName(' Kvällen ', 'Kvällen', check), { kind: 'unchanged' })
  assert.deepEqual(decideName('Kvällen', 'Kvällen', check), { kind: 'unchanged' })
})

test('an empty, reserved or taken name is refused in the words of the name rules', () => {
  for (const [typed, refusal, clash] of [
    ['', 'empty', null],
    ['  ', 'empty', null],
    ['main', 'reserved', 'Main'],
    ['STRASSE', 'taken', 'Straße'],
  ] as const) {
    const decision = decideName(typed, 'Kvällen', check)
    assert.equal(decision.kind, 'refused', typed)
    if (decision.kind === 'refused') {
      assert.equal(decision.refusal, refusal)
      assert.equal(decision.clash, clash)
      assert.match(NAME_REFUSAL[decision.refusal](decision.clash ?? ''), /\S/)
    }
  }
})

test('a deleted chapter keeps its name taken', () => {
  const withDeleted = [...chapters, chapter('r3', 'Gammal', true)]
  const decision = decideName('gammal', 'Kvällen', (typed) => checkName(withDeleted, typed, 'r1'))
  assert.equal(decision.kind, 'refused')
  assert.equal(decision.kind === 'refused' && decision.refusal, 'taken-deleted')
})

test('the title is kept as typed: empty, spaces and any text', () => {
  assert.deepEqual(decideName('', 'Grillning', acceptAnything), { kind: 'keep', name: '' })
  assert.deepEqual(decideName('Grillkväll  ', 'Grillning', acceptAnything), {
    kind: 'keep',
    name: 'Grillkväll  ',
  })
  assert.deepEqual(decideName('main', 'Grillning', acceptAnything), { kind: 'keep', name: 'main' })
  // Nothing typed over an inherited (empty) title, or spaces over it, changes nothing.
  assert.deepEqual(decideName('   ', '', acceptAnything), { kind: 'unchanged' })
})

test('the title line prefers the draft, then the folder title, then Untitled', () => {
  assert.deepEqual(titleLine('Eget', 'Mapp'), { text: 'Eget', source: 'draft' })
  assert.deepEqual(titleLine('', 'Mapp'), { text: 'Mapp', source: 'folder' })
  assert.deepEqual(titleLine('   ', 'Mapp'), { text: 'Mapp', source: 'folder' })
  assert.deepEqual(titleLine('', null), { text: UNTITLED, source: 'none' })
  assert.deepEqual(titleLine(' ', '  '), { text: UNTITLED, source: 'none' })
})

test('a name is unsent when the stripped text differs from the current name', () => {
  assert.equal(nameUnsent('Kvällen', 'Kvällen'), false)
  assert.equal(nameUnsent(' Kvällen ', 'Kvällen'), false)
  assert.equal(nameUnsent('Kväll', 'Kvällen'), true)
  assert.equal(nameUnsent('', 'Kvällen'), true)
  assert.equal(nameUnsent('', ''), false)
})

test('the file-name note names no file', () => {
  assert.match(FILE_NAME_NOTE, /file name/)
  assert.match(FILE_NAME_NOTE, /old name stays on disk/)
  assert.doesNotMatch(FILE_NAME_NOTE, /\.mp4|\.mkv/)
})
