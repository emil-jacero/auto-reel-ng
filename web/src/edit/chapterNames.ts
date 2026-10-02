import type { Clip } from '../api/event'
import { casefold } from './casefold.ts'
import type { ChapterKey, DraftChapter } from './draft'

/*
 * Chapter names: which ones Edit mode accepts, and what a name means for clips
 * added later. Pure, with only a sibling pure import (the case fold), like `draft.ts`.
 *
 * The page follows the engine's chapter-name rules (D-12, D-13), so that a name
 * it accepts is a name `reel.yaml` loads: a name is stripped as Python's
 * `str.strip()` strips it and is not empty, and two names equal under
 * `str.casefold()` are one name (`stripLikePython`, `casefold`). `Main` is the
 * page's own reservation; the engine has none.
 *
 * A clip that appears in an event's folder after its `reel.yaml` exists joins,
 * at the next read or render, the chapter whose name equals its folder's under
 * that fold (the engine tries the exact name first; names are unique under the
 * fold, so it is the same chapter), else the event's own chapter (D-12); an
 * ignored clip is listed the same way. So a chapter's name decides where its
 * folder's later clips go, and the notes below say so wherever an edit changes that.
 */

/** How the page names the event's own chapter (`''`) while another chapter is listed. */
export const OWN_CHAPTER_HEADING = 'Main'

/** Why a typed name is refused. */
export type NameRefusal = 'empty' | 'taken' | 'taken-deleted' | 'reserved'

/** The refusal at the name field, by cause; `clash` is the name it clashes with. */
export const NAME_REFUSAL: Record<NameRefusal, (clash: string) => string> = {
  empty: () => "Enter a name. A chapter's name is the heading of its title card.",
  taken: (clash) =>
    `A chapter called “${clash}” already exists. Names that differ only in letter case, ` +
    'such as ß and ss, count as the same.',
  'taken-deleted': (clash) =>
    `“${clash}” is deleted when you save. Undo that, or pick another name.`,
  reserved: () =>
    `“${OWN_CHAPTER_HEADING}” is how the page names the event's own chapter. Pick another name.`,
}

/** The event's own chapter's note in its tools row, while another chapter is listed. */
export const OWN_CHAPTER_NOTE =
  "The event's own chapter: its title card shows the event's title, and clips without a " +
  'chapter of their own join it.'

/**
 * The chapter's later-clips notes, as Edit mode shows them. `own` is the event's
 * own chapter's heading at that moment (`Main`, or `Clips` when it is the only
 * chapter listed); null when it is deleted or not listed, so that such clips start
 * a new `Main` chapter at the end.
 */
export const LATER_CLIP_NOTE = {
  folderUnnamed: (folder: string, own: string | null) =>
    `No chapter will be named after the folder “${folder}”, so clips added to it later will ` +
    (own === null ? `start a new ${OWN_CHAPTER_HEADING} chapter at the end.` : `join ${own}.`),
  folderJoins: (folder: string) =>
    `Clips added to the folder “${folder}” later will join this chapter. Clips from it that ` +
    'other chapters list stay where they are.',
  ignoredHere: (count: number) =>
    `Its ${plural(count, 'ignored clip', 'ignored clips')} will be listed here.`,
  ignoredToMain: (count: number, own: string | null) =>
    `Its ${plural(count, 'ignored clip', 'ignored clips')} will be listed under ` +
    (own === null ? `a new ${OWN_CHAPTER_HEADING} chapter at the end.` : `${own}.`),
  ownDeleted:
    'Clips added to the event folder later will start a new ' +
    `${OWN_CHAPTER_HEADING} chapter at the end.`,
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}

/** The identity's folder: '' for a file at the event folder's root. */
function folderOf(identity: string): string {
  const slash = identity.lastIndexOf('/')
  return slash === -1 ? '' : identity.slice(0, slash)
}

// What Python's `str.strip()` removes (`chr(c).isspace()`): U+0009..U+000D, U+001C..U+001F,
// U+0020, U+0085, U+00A0, U+1680, U+2000..U+200A, U+2028, U+2029, U+202F, U+205F, U+3000.
// Not `trim()`: that removes U+FEFF and keeps U+001C..U+001F and U+0085.
const PYTHON_SPACE =
  '[\\t-\\r\\u001c-\\u001f \\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029' +
  '\\u202f\\u205f\\u3000]'
const PADDING = new RegExp(`^${PYTHON_SPACE}+|${PYTHON_SPACE}+$`, 'g')

/** `s` without the characters around it that Python's `s.strip()` removes. */
export function stripLikePython(s: string): string {
  return s.replace(PADDING, '')
}

/** The listed chapter whose name equals `folder` under the case fold (the engine's placement). */
export function chapterForFolder<T extends { name: string }>(
  listed: readonly T[],
  folder: string,
): T | null {
  const key = casefold(folder)
  return listed.find((chapter) => casefold(chapter.name) === key) ?? null
}

/**
 * The spelling of the disk folder `name` matches under the case fold, or null
 * when none does. With several (`a/` and `A/` on a case-sensitive file system)
 * the exact one if it is among them, else the first in code-unit order.
 */
export function folderSpelling(folders: ReadonlySet<string>, name: string): string | null {
  const key = casefold(name)
  const found = [...folders].filter((folder) => casefold(folder) === key)
  if (found.length === 0) {
    return null
  }
  return found.includes(name) ? name : found.sort()[0]
}

/**
 * Whether `typed` is an acceptable name for chapter `self` (null: a chapter
 * being added). The name is stripped as Python strips it and must not be empty.
 * Under the case fold, it must differ from every other chapter's name, a deleted
 * one's included (its Undo would bring the clash back): the engine's rule. It
 * must also differ from `Main`, which is the page's alone. Its own name back
 * (spaces around it aside) is accepted: the dialog then changes nothing.
 */
export function checkName(
  chapters: readonly DraftChapter[],
  typed: string,
  self: ChapterKey | null,
): { ok: true; name: string } | { ok: false; refusal: NameRefusal; clash: string | null } {
  const name = stripLikePython(typed)
  if (name === '') {
    return { ok: false, refusal: 'empty', clash: null }
  }
  const current = chapters.find((chapter) => chapter.key === self)
  if (current !== undefined && current.name === name) {
    return { ok: true, name }
  }
  if (casefold(name) === casefold(OWN_CHAPTER_HEADING)) {
    return { ok: false, refusal: 'reserved', clash: OWN_CHAPTER_HEADING }
  }
  const key = casefold(name)
  const clashes = chapters.filter(
    (chapter) => chapter.key !== self && chapter.name !== '' && casefold(chapter.name) === key,
  )
  const listed = clashes.find((chapter) => !chapter.deleted)
  if (listed !== undefined) {
    return { ok: false, refusal: 'taken', clash: listed.name }
  }
  if (clashes.length > 0) {
    return { ok: false, refusal: 'taken-deleted', clash: clashes[0].name }
  }
  return { ok: true, name }
}

/**
 * Folders holding a clip on disk ('' = the event folder): from the detail's
 * identities, missing ones excluded.
 */
export function diskFolders(clips: Iterable<Clip>): ReadonlySet<string> {
  const folders = new Set<string>()
  for (const clip of clips) {
    if (clip.status !== 'missing') {
      folders.add(folderOf(clip.identity))
    }
  }
  return folders
}

/**
 * How the page heads the event's own chapter: `Main` while another chapter a save
 * keeps is listed, `Clips` otherwise (the read view's rule).
 */
export function ownChapterHeading(chapters: readonly DraftChapter[]): string {
  return chapters.some((chapter) => !chapter.deleted && chapter.name !== '')
    ? OWN_CHAPTER_HEADING
    : 'Clips'
}

/**
 * How many of `identities` (ignored clips the event's own chapter lists) the page
 * would list under that chapter again after the save: those of the event folder,
 * and those of a folder no chapter a save keeps is named after (under the case
 * fold, as the engine matches). The others move to the chapter named after their
 * folder.
 */
export function ignoredStaying(
  chapters: readonly DraftChapter[],
  identities: readonly string[],
): number {
  const listed = chapters.filter((chapter) => !chapter.deleted)
  return identities.filter((identity) => {
    const folder = folderOf(identity)
    return folder === '' || chapterForFolder(listed, folder) === null
  }).length
}

export type NoteInput = {
  chapters: readonly DraftChapter[]
  /** `diskFolders` of the event. */
  folders: ReadonlySet<string>
  /** Each chapter's ignored clips, as the page lists them (an added chapter lists none). */
  ignored: ReadonlyMap<ChapterKey, readonly string[]>
}

/**
 * The later-clips notes of every chapter, deleted ones included, each in this
 * order (names compared under the case fold, as the engine does; "Main" below is the event's
 * own chapter, named by its heading now, `Main` or `Clips`, or a new `Main` chapter
 * at the end when it is deleted or not listed):
 *
 * 1. a read chapter named after a folder holding clips, renamed away or
 *    deleted, while no other listed chapter takes that name: the folder's later
 *    clips will join Main
 * 2. a chapter added with, or renamed to, such a folder's name: they will join
 *    it, and the folder's ignored clips other chapters list will be listed here
 * 3. a chapter whose ignored clips no longer have a chapter named after their
 *    folder: they will be listed under Main
 * 4. the event's own chapter deleted: the event folder's later clips will
 *    start a new Main chapter
 */
export function laterClipNotes(input: NoteInput): ReadonlyMap<ChapterKey, readonly string[]> {
  const { chapters, folders, ignored } = input
  const listed = chapters.filter((chapter) => !chapter.deleted)
  const own = listed.find((chapter) => chapter.name === '') ?? null
  const ownHeading = own === null ? null : ownChapterHeading(chapters)
  // Where an ignored clip of folder F is listed after the save: the chapter named F, else Main.
  const homeOf = (folder: string): ChapterKey | null =>
    chapterForFolder(listed, folder)?.key ?? own?.key ?? null
  const arriving = new Map<ChapterKey, number>()
  const leaving = new Map<ChapterKey, number>()
  for (const chapter of chapters) {
    for (const identity of ignored.get(chapter.key) ?? []) {
      const home = homeOf(folderOf(identity))
      if (home === chapter.key) {
        continue
      }
      if (home !== null && home !== own?.key) {
        arriving.set(home, (arriving.get(home) ?? 0) + 1)
      } else {
        leaving.set(chapter.key, (leaving.get(chapter.key) ?? 0) + 1)
      }
    }
  }
  const notes = new Map<ChapterKey, readonly string[]>()
  for (const chapter of chapters) {
    const lines: string[] = []
    const { readName } = chapter
    const readFolder =
      readName === null || readName === '' ? null : folderSpelling(folders, readName)
    // A rename between two spellings of the same fold changes nothing for later clips.
    const sameFold = readName !== null && casefold(chapter.name) === casefold(readName)
    if (
      readFolder !== null &&
      (chapter.deleted || !sameFold) &&
      chapterForFolder(listed, readFolder) === null
    ) {
      lines.push(LATER_CLIP_NOTE.folderUnnamed(readFolder, ownHeading))
    }
    const folder =
      chapter.deleted || chapter.name === '' ? null : folderSpelling(folders, chapter.name)
    if (folder !== null && !sameFold) {
      lines.push(LATER_CLIP_NOTE.folderJoins(folder))
      const count = arriving.get(chapter.key) ?? 0
      if (count > 0) {
        lines.push(LATER_CLIP_NOTE.ignoredHere(count))
      }
    }
    const count = leaving.get(chapter.key) ?? 0
    if (count > 0) {
      lines.push(LATER_CLIP_NOTE.ignoredToMain(count, ownHeading))
    }
    if (chapter.readName === '' && chapter.deleted) {
      lines.push(LATER_CLIP_NOTE.ownDeleted)
    }
    if (lines.length > 0) {
      notes.set(chapter.key, lines)
    }
  }
  return notes
}

// The key a chapter being added has while its name is typed: no chapter's.
const TYPED = '\u0000typed'

/**
 * The notes the name dialog shows for `typed` on chapter `self` (null: a chapter
 * being added): those the chapter would get once the name is confirmed. None
 * while the name would be refused, since it would change nothing.
 */
export function nameDialogNote(
  input: NoteInput,
  self: ChapterKey | null,
  typed: string,
): readonly string[] {
  const checked = checkName(input.chapters, typed, self)
  if (!checked.ok) {
    return []
  }
  const key = self ?? TYPED
  const chapters =
    self === null
      ? [...input.chapters, { key, readName: null, name: checked.name, deleted: false }]
      : input.chapters.map((chapter) =>
          chapter.key === self ? { ...chapter, name: checked.name } : chapter,
        )
  return laterClipNotes({ ...input, chapters }).get(key) ?? []
}
