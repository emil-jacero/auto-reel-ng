import assert from 'node:assert/strict'
import { test } from 'node:test'

import { barButton, barContent, cardIdOf, editTitlecardName } from './chapterBar.ts'

test('the button is named for the chapter by its heading, Main and Clips included', () => {
  assert.equal(editTitlecardName('Kvällen'), 'Edit title card for Kvällen')
  assert.equal(editTitlecardName('Main'), 'Edit title card for Main')
  assert.equal(editTitlecardName('Clips'), 'Edit title card for Clips')
})

test('it is pressed when its card is selected, and unavailable while a save or move is pending', () => {
  assert.deepEqual(barButton('Kvällen', 'Kvällen', false), { pressed: true, unavailable: false })
  assert.deepEqual(barButton('Kvällen', '', false), { pressed: false, unavailable: false })
  assert.deepEqual(barButton(null, 'Kvällen', true), { pressed: false, unavailable: true })
})

test('a chapter read as Main and one added in the draft each get an id of their own', () => {
  assert.equal(cardIdOf({ readName: '', key: 'r0' }), '')
  assert.equal(cardIdOf({ readName: 'Kvällen', key: 'r1' }), 'Kvällen')
  assert.notEqual(cardIdOf({ readName: null, key: 'a1' }), cardIdOf({ readName: null, key: 'a2' }))
  assert.notEqual(cardIdOf({ readName: null, key: 'a1' }), 'a1')
})

test('a chapter section is its name, its button and its clip count; nothing renames it', () => {
  assert.deepEqual(barContent('Kvällen', 3), {
    name: 'Kvällen',
    button: 'Edit title card for Kvällen',
    count: '3 clips',
    editsName: false,
  })
  assert.equal(barContent('Main', 1).count, '1 clip')
})
