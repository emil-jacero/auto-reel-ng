import type { Staleness } from '../api/events'
import { Pill } from '../ui/Pill'
import { REASON_LABEL, REASON_NOTE, UNANSWERED_CAUSE } from './labels'
import { VERDICT_LOOK } from './tones'

/** Helpers both event screens share. */

/** The failure sentences both screens use, so the same cause reads the same. */
export const DATABASE_CAUSE = "The service can't reach its database."
export const UNREACHABLE_CAUSE = UNANSWERED_CAUSE.unreachable

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

/**
 * A name, its folder part muted: <span class="clip-dir">Kvällen/</span>s1710004.mp4.
 * A narrow cell breaks it after the folder, before it breaks inside the file name.
 */
export function ClipName({ name }: { name: string }) {
  const cut = name.lastIndexOf('/') + 1
  if (cut === 0) {
    return name
  }
  return (
    <>
      <span className="clip-dir">{name.slice(0, cut)}</span>
      <wbr />
      {name.slice(cut)}
    </>
  )
}

export function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}

const BYTE_UNITS = ['KiB', 'MiB', 'GiB', 'TiB']

/** A byte count, 1024-based: whole bytes below 1 KiB, one decimal from KiB up. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(1)} ${BYTE_UNITS[unit]}`
}

/** The render verdict: a pill, and every reason in words when stale. */
export function StalenessCell({
  staleness,
  explain = false,
}: {
  staleness: Staleness
  /** The event page: each cited reason's note, when it has one, on a line of its own. */
  explain?: boolean
}) {
  const look = staleness.stale ? VERDICT_LOOK.stale : VERDICT_LOOK.fresh
  return (
    <span className="verdict">
      <Pill tone={look.tone} icon={look.icon}>
        {staleness.stale ? 'Needs render' : 'Up to date'}
      </Pill>
      {staleness.stale && staleness.reasons.length > 0 && (
        <span className="reasons">
          {staleness.reasons.map((reason) => REASON_LABEL[reason]).join(', ')}
        </span>
      )}
      {explain &&
        staleness.stale &&
        staleness.reasons.map((reason) => {
          const note = REASON_NOTE[reason]
          return (
            note !== null && (
              <span key={reason} className="reason-note">
                {note}
              </span>
            )
          )
        })}
    </span>
  )
}
