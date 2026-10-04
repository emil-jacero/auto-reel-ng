import assert from 'node:assert/strict'
import { test } from 'node:test'

import { NAME_REFUSAL, checkName } from './chapterNames.ts'
import type { DraftChapter } from './draft.ts'
import { FILE_NAME_NOTE, decideName } from './inlineName.ts'

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

test('the file-name note names no file', () => {
  assert.match(FILE_NAME_NOTE, /file name/)
  assert.match(FILE_NAME_NOTE, /old name stays on disk/)
  assert.doesNotMatch(FILE_NAME_NOTE, /\.mp4|\.mkv/)
})
