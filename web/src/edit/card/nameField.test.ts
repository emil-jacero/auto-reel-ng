import assert from 'node:assert/strict'
import { test } from 'node:test'

import { NAME_REFUSAL, checkName } from '../chapterNames.ts'
import type { DraftChapter } from '../draft.ts'
import { decideName } from '../inlineName.ts'
import {
  anyTitle,
  cardTitleShown,
  doneHeld,
  nameLabel,
  nameStep,
  notChangedWords,
  settleWords,
} from './nameField.ts'

const chapter = (key: string, name: string, deleted = false): DraftChapter => ({
  key,
  readName: name,
  name,
  deleted,
})
const chapters = [
  chapter('r0', ''),
  chapter('r1', 'Kvällen'),
  chapter('r2', 'Straße'),
  chapter('r3', 'Gone', true),
]
const check = (typed: string) => checkName(chapters, typed, 'r1')

test('an accepted name is written, stripped; the old name back is no write', () => {
  assert.deepEqual(nameStep('Kväll', 'Kvällen', check), { kind: 'write', name: 'Kväll' })
  assert.deepEqual(nameStep(' Kväll på stranden ', 'Kvällen', check), {
    kind: 'write',
    name: 'Kväll på stranden',
  })
  assert.deepEqual(nameStep(' Kvällen ', 'Kvällen', check), { kind: 'same' })
})

test('every refusal has the words of the name rules, from the originals', () => {
  for (const typed of ['', '   ', 'main', 'STRASSE', 'strasse', 'STRAẞE', 'gone', '\u0085\u0085']) {
    const result = check(typed)
    assert.equal(result.ok, false, typed)
    if (!result.ok) {
      const decided = decideName(typed, 'Kvällen', check)
      assert.equal(decided.kind, 'refused')
      assert.deepEqual(nameStep(typed, 'Kvällen', check), {
        kind: 'refused',
        words: NAME_REFUSAL[result.refusal](result.clash ?? ''),
      })
    }
  }
  assert.match((nameStep('', 'Kvällen', check) as { words: string }).words, /Enter a name/)
  assert.match((nameStep('main', 'Kvällen', check) as { words: string }).words, /Main/)
  assert.match((nameStep('gone', 'Kvällen', check) as { words: string }).words, /deleted when you save/)
})

test('a name that merely resembles another is accepted; U+0085 spaces are stripped', () => {
  assert.deepEqual(nameStep('Strasse 2', 'Kvällen', check), { kind: 'write', name: 'Strasse 2' })
  assert.deepEqual(nameStep('\u0085Hamnen\u0085', 'Kvällen', check), { kind: 'write', name: 'Hamnen' })
})

test('the event title accepts any text, a blank one too', () => {
  assert.deepEqual(nameStep('Grillkväll', 'Grillning', anyTitle), { kind: 'write', name: 'Grillkväll' })
  assert.deepEqual(nameStep('', 'Grillning', anyTitle), { kind: 'write', name: '' })
  assert.deepEqual(nameStep('main', 'Grillning', anyTitle), { kind: 'write', name: 'main' })
  assert.deepEqual(nameStep('Grillning', 'Grillning', anyTitle), { kind: 'same' })
})

test('a rename is announced once, from the settled name; the old name back says nothing', () => {
  assert.equal(settleWords('chapter', 'Kvällen', 'Kväll'), '“Kvällen” renamed to “Kväll”.')
  assert.equal(settleWords('chapter', 'Kvällen', 'Kväll', ' Notes.'), '“Kvällen” renamed to “Kväll”. Notes.')
  assert.equal(settleWords('chapter', 'Kvällen', 'Kvällen'), null)
  assert.equal(settleWords('event', 'Två kapitel', 'Grill '), 'Title set to “Grill”.')
  assert.equal(settleWords('event', 'Två kapitel', ''), 'Title cleared. It inherits from the folder name.')
  assert.equal(settleWords('event', 'Två kapitel', 'Två kapitel'), null)
})

test('leaving a refused name says it was not changed and why; nothing refused says nothing', () => {
  assert.equal(notChangedWords(null), null)
  assert.equal(notChangedWords('Enter a name.'), 'Name not changed. Enter a name.')
})

test('Done is held by a refusal only', () => {
  assert.equal(doneHeld('Enter a name.'), true)
  assert.equal(doneHeld(null), false)
})

test('the field is named for a chapter or for the event', () => {
  assert.equal(nameLabel(false, 'Kvällen'), 'Name of chapter Kvällen')
  assert.equal(nameLabel(true, 'Main'), 'Title of the event')
})

test('the card title is shown only for a card that has one; clearing it hides it', () => {
  assert.equal(cardTitleShown({ title: 'Kväll på stranden' }), true)
  assert.equal(cardTitleShown({ title: null }), false)
})
