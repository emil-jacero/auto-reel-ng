import type { Look } from './cardStyle.ts'

/*
 * The event's `look.decorators` switch (`title-card-toggle`), as pure functions. The page does
 * not decide whether the render draws title cards: the event detail says so (`title_cards`,
 * resolved by the engine from the event and the project's `config.yaml`). This module only
 * writes the list the switch means, in the one rule the engine reads (a list that names
 * `title`), and never infers the project's list (D-25): Off writes the event's own list, On
 * puts `title` first, and putting the switch back to the state read is no override at all.
 */

/** The decorator that draws the title cards. */
export const TITLE = 'title'

/** What `look.decorators` holds in the document as read. */
export type ReadDecorators =
  | { kind: 'absent' }
  | { kind: 'list'; names: readonly unknown[] }
  | { kind: 'invalid' }

export function readDecorators(look: Look | null | undefined): ReadDecorators {
  const raw = look?.decorators
  if (raw === undefined || raw === null) {
    return { kind: 'absent' }
  }
  return Array.isArray(raw) ? { kind: 'list', names: raw } : { kind: 'invalid' }
}

/** Whether a decorators list names `title`, as the engine reads it (`str(name) == "title"`). */
export function listsTitle(names: readonly unknown[]): boolean {
  return names.some((name) => String(name) === TITLE)
}

/**
 * The override a switch position means. `readEnabled` is what the detail said for the document as
 * read. `undefined` is no override: the position is the state read. Else the event's own list:
 * Off is the list as read without `title` (`[]` when the event has none), On is the list as read
 * without `title` and with `title` first. Non-string items and other names stay, in order. A
 * `look.decorators` that is not a list is refused (the switch is disabled for it).
 */
export function setTitleCards(
  readLook: Look | null | undefined,
  readEnabled: boolean,
  on: boolean,
): readonly unknown[] | undefined {
  const read = readDecorators(readLook)
  if (read.kind === 'invalid') {
    throw new Error('look.decorators is not a list; it cannot be switched')
  }
  if (on === readEnabled) {
    return undefined
  }
  const others = read.kind === 'list' ? read.names.filter((name) => String(name) !== TITLE) : []
  return on ? [TITLE, ...others] : others
}

/**
 * The `look` a save writes: `readLook` itself with no override (an untouched save is
 * byte-identical), else a copy whose `decorators` is the override; every other key goes back as read.
 */
export function applyDecorators(readLook: Look, override: readonly unknown[] | undefined): Look {
  return override === undefined ? readLook : { ...readLook, decorators: [...override] }
}

/** The switch position: the draft's list names `title`, else what the detail said. */
export function titleCardsNow(
  override: readonly unknown[] | undefined,
  readEnabled: boolean,
): boolean {
  return override === undefined ? readEnabled : listsTitle(override)
}
