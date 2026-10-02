import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  NAME_REFUSAL,
  chapterForFolder,
  checkName,
  folderSpelling,
  ignoredStaying,
  laterClipNotes,
  nameDialogNote,
  stripLikePython,
} from './chapterNames.ts'
import type { DraftChapter } from './draft'

function chapter(key: string, name: string, extra: Partial<DraftChapter> = {}): DraftChapter {
  return { key, readName: name, name, deleted: false, ...extra }
}

const NEL = '\u0085'
const FEFF = '﻿'

test('stripLikePython removes exactly the characters Python strips', () => {
  assert.equal(stripLikePython(`${NEL}Hamnen${NEL}`), 'Hamnen')
  assert.equal(stripLikePython('\u001c\u001f Hamnen \u001d'), 'Hamnen')
  assert.equal(stripLikePython('　  Hamnen  \t\n'), 'Hamnen')
  assert.equal(stripLikePython('  Kväll på  stranden '), 'Kväll på  stranden')
  // Python keeps U+FEFF and a space inside the name.
  assert.equal(stripLikePython(`${FEFF}Hamnen`), `${FEFF}Hamnen`)
  assert.equal(stripLikePython(`${FEFF}`), FEFF)
  assert.equal(stripLikePython(` ${NEL} `), '')
})

test('trim() and stripLikePython disagree on U+0085 and U+FEFF', () => {
  assert.notEqual(`${NEL}x`.trim(), stripLikePython(`${NEL}x`))
  assert.notEqual(`${FEFF}x`.trim(), stripLikePython(`${FEFF}x`))
})

test('checkName strips as the engine does, and refuses what is empty after that', () => {
  const chapters = [chapter('r0', ''), chapter('r1', 'Kvällen')]
  assert.deepEqual(checkName(chapters, `${NEL}Hamnen\u001c`, null), { ok: true, name: 'Hamnen' })
  assert.deepEqual(checkName(chapters, `${NEL}\u001c　 `, null), {
    ok: false,
    refusal: 'empty',
    clash: null,
  })
  // U+FEFF is a name character for the engine, so the name is kept whole.
  assert.deepEqual(checkName(chapters, FEFF, null), { ok: true, name: FEFF })
})

test('checkName calls names equal under the case fold one name', () => {
  const chapters = [chapter('r0', ''), chapter('r1', 'Straße')]
  for (const typed of ['STRASSE', 'strasse', 'Strasse', 'STRAẞE']) {
    assert.deepEqual(
      checkName(chapters, typed, null),
      { ok: false, refusal: 'taken', clash: 'Straße' },
      typed,
    )
  }
  assert.deepEqual(checkName(chapters, 'Strasse 2', null), { ok: true, name: 'Strasse 2' })
  assert.deepEqual(checkName(chapters, 'straße', 'r1'), { ok: true, name: 'straße' })
})

test('checkName keeps ı apart from i, as the engine does', () => {
  const chapters = [chapter('r0', ''), chapter('r1', 'i')]
  assert.deepEqual(checkName(chapters, 'ı', null), { ok: true, name: 'ı' })
  assert.deepEqual(checkName([chapter('r0', ''), chapter('r1', 'ı')], 'I', null), {
    ok: true,
    name: 'I',
  })
})

test('checkName: a deleted chapter still holds its name; Main stays reserved', () => {
  const chapters = [chapter('r0', ''), chapter('r1', 'Straße', { deleted: true })]
  assert.deepEqual(checkName(chapters, 'STRASSE', null), {
    ok: false,
    refusal: 'taken-deleted',
    clash: 'Straße',
  })
  for (const typed of ['main', 'MAIN', ' Main ']) {
    assert.deepEqual(checkName(chapters, typed, null), {
      ok: false,
      refusal: 'reserved',
      clash: 'Main',
    })
  }
})

test('checkName: renaming Kvällen to KVÄLLEN is accepted', () => {
  const chapters = [chapter('r0', ''), chapter('r1', 'Kvällen')]
  assert.deepEqual(checkName(chapters, 'KVÄLLEN', 'r1'), { ok: true, name: 'KVÄLLEN' })
  assert.deepEqual(checkName(chapters, ' Kvällen ', 'r1'), { ok: true, name: 'Kvällen' })
})

test('the taken refusal says what “the same” means', () => {
  assert.equal(
    NAME_REFUSAL.taken('Straße'),
    'A chapter called “Straße” already exists. Names that differ only in letter case, such as ß ' +
      'and ss, count as the same.',
  )
})

test('chapterForFolder finds the chapter whose name folds to the folder', () => {
  const listed = [chapter('r0', ''), chapter('r1', 'Kvällen'), chapter('r2', 'Straße')]
  assert.equal(chapterForFolder(listed, 'kvällen')?.key, 'r1')
  assert.equal(chapterForFolder(listed, 'STRASSE')?.key, 'r2')
  assert.equal(chapterForFolder(listed, '')?.key, 'r0')
  assert.equal(chapterForFolder(listed, ' Kvällen'), null)
  assert.equal(chapterForFolder(listed, 'Kväll'), null)
})

test('folderSpelling prefers the exact spelling, else the first in code-unit order', () => {
  assert.equal(folderSpelling(new Set(['Kvällen']), 'kvällen'), 'Kvällen')
  assert.equal(folderSpelling(new Set(['a', 'A']), 'a'), 'a')
  assert.equal(folderSpelling(new Set(['a', 'A']), 'A'), 'A')
  assert.equal(folderSpelling(new Set(['a', 'A']), 'á'), null)
  assert.equal(folderSpelling(new Set(['b', 'B']), 'B'), 'B')
  assert.equal(folderSpelling(new Set(['a', 'A']), 'a '), null)
})

const folders = new Set(['', 'Kvällen'])
const noIgnored = new Map<string, readonly string[]>()

test('a folder is taken by the chapter named after it in another case', () => {
  const chapters = [chapter('r0', ''), chapter('r1', 'Kvällen')]
  const notes = laterClipNotes({ chapters, folders, ignored: noIgnored })
  assert.equal(notes.size, 0)
  // Renamed Kvällen -> kvällen: the folder still joins this chapter, so no note.
  const renamed = [chapter('r0', ''), chapter('r1', 'Kvällen', { name: 'kvällen' })]
  assert.equal(laterClipNotes({ chapters: renamed, folders, ignored: noIgnored }).size, 0)
  assert.deepEqual(nameDialogNote({ chapters, folders, ignored: noIgnored }, 'r1', 'kvällen'), [])
})

test('renaming to a different name leaves the folder unnamed, in the folder’s spelling', () => {
  const lower = [chapter('r0', ''), chapter('r1', 'kvällen', { name: 'Kväll' })]
  const notes = laterClipNotes({ chapters: lower, folders, ignored: noIgnored })
  assert.deepEqual(notes.get('r1'), [
    'No chapter will be named after the folder “Kvällen”, ' +
      'so clips added to it later will join Main.',
  ])
})

test('a chapter added in another case than the folder says the folder will join it', () => {
  const chapters = [
    chapter('r0', ''),
    chapter('r1', 'Kvällen', { name: 'Kväll' }),
    { key: 'a1', readName: null, name: 'KVÄLLEN', deleted: false },
  ]
  const notes = laterClipNotes({ chapters, folders, ignored: noIgnored })
  assert.deepEqual(notes.get('a1'), [
    'Clips added to the folder “Kvällen” later will join this chapter. Clips from it that other ' +
      'chapters list stay where they are.',
  ])
  const before = [chapter('r0', ''), chapter('r1', 'Kvällen', { name: 'Kväll' })]
  assert.deepEqual(
    nameDialogNote({ chapters: before, folders, ignored: noIgnored }, null, 'KVÄLLEN'),
    notes.get('a1'),
  )
})

test('folders a and A both join chapter a, named by the exact spelling', () => {
  const both = new Set(['', 'a', 'A'])
  const chapters = [
    chapter('r0', ''),
    { key: 'a1', readName: null, name: 'a', deleted: false },
  ]
  const joined = laterClipNotes({ chapters, folders: both, ignored: noIgnored }).get('a1')
  assert.deepEqual(joined, [
    'Clips added to the folder “a” later will join this chapter. Clips from it that other ' +
      'chapters list stay where they are.',
  ])
  const upper = [chapter('r0', ''), { key: 'a1', readName: null, name: 'A', deleted: false }]
  assert.match(
    laterClipNotes({ chapters: upper, folders: both, ignored: noIgnored }).get('a1')?.[0] ?? '',
    /folder “A” later/,
  )
  assert.equal(chapterForFolder(chapters.slice(1), 'A')?.key, 'a1')
})

test('an ignored clip of kvällen/ stays with Kvällen; ignoredStaying follows the fold', () => {
  const ignoredClip = 'kvällen/s1.mp4'
  const chapters = [chapter('r0', ''), chapter('r1', 'Kvällen')]
  assert.equal(ignoredStaying(chapters, [ignoredClip]), 0)
  assert.equal(ignoredStaying(chapters, ['Kvällen/s1.mp4', 's2.mp4']), 1)
  const renamed = [chapter('r0', ''), chapter('r1', 'Kvällen', { name: 'Kväll' })]
  assert.equal(ignoredStaying(renamed, [ignoredClip]), 1)
  const folderOnly = new Set(['', 'kvällen'])
  const ignored = new Map([['r1', [ignoredClip]]])
  assert.equal(laterClipNotes({ chapters, folders: folderOnly, ignored }).size, 0)
  const away = laterClipNotes({ chapters: renamed, folders: folderOnly, ignored })
  assert.deepEqual(away.get('r1'), [
    'No chapter will be named after the folder “kvällen”, so clips added to it later will join ' +
      'Main.',
    'Its 1 ignored clip will be listed under Main.',
  ])
})
