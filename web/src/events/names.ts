/*
 * How the event screens name things, kept apart from `common.tsx` (JSX) so that the
 * runner of `npm test` can load it, and the timeline's pure layer with it.
 */

/** The event folder's name: the last segment of its id. */
export function folderName(eventId: string): string {
  return eventId.split('/').pop() ?? eventId
}

/** The identity's last segment: the file name inside its chapter folder. */
export function fileName(identity: string): string {
  return identity.split('/').pop() ?? identity
}

/** The identity's folder: '' for a file at the event folder's root. */
function folderOf(identity: string): string {
  const slash = identity.lastIndexOf('/')
  return slash === -1 ? '' : identity.slice(0, slash)
}

/**
 * How a chapter names its clips: by file name while every clip it lists lies in its
 * own folder (the event folder for the default chapter ''), else each by its path in
 * the event folder, so that no two of its rows read alike. Identities are unique
 * within an event, and the names come from them alone, never from a guess about
 * where a chapter's folder is. Edit mode's rows adopt it too, with `ClipName`, so both
 * keep their names, signatures and markup.
 */
export function clipNames(
  chapter: string,
  identities: readonly string[],
): (identity: string) => string {
  const own = identities.every((identity) => folderOf(identity) === chapter)
  return own ? fileName : (identity) => identity
}

export function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}
