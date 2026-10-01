/*
 * The editor's clip previews (D-16): which clip's preview is open, one on the page
 * at a time, and what a remount or a later check needs. A module store, not editor
 * state: opening a preview must re-render no list (G1's rule), only the two panels
 * whose answer changed. Pure, with no imports.
 *
 * Its life is the editor's: leaving Edit mode drops it, and with it every length.
 */

/** Who opened a preview: where Close and Escape return keyboard focus. */
export type Opener = 'toggle' | 'thumb'

/** The editor's previews: which clip's is open, and what a remount or a later check needs. */
export type ClipPreviews = {
  /** The identity whose preview is open, or null: one on the page at a time. */
  open(): string | null
  /** Opens `identity`'s preview, closing any other; records the opener and asks once for focus on Play. */
  show(identity: string, from: Opener): void
  /** Who opened `identity`'s open preview: where Close and Escape return focus. */
  opener(identity: string): Opener | null
  /** True once after each `show(identity, …)`: `ClipPreview` then focuses Play. A remount finds false. */
  takeFocus(identity: string): boolean
  /** Changes on every `show`, so a mounted `ClipPreview` re-runs its focus effect. */
  showCount(): number
  /** Closes `identity`'s preview if it is the open one, and forgets its kept playhead. */
  hide(identity: string): void
  /** Reset: no preview open, no playhead kept. Lengths stay: they are facts of files, not edits. */
  hideAll(): void
  subscribe(listener: () => void): () => void
  /** Where an open preview's playhead stood when its element unmounted (a move to another chapter). */
  playhead(identity: string): number | undefined
  keepPlayhead(identity: string, seconds: number | undefined): void
  /** A clip's length as this browser read it, by its media address (`v` = mtime: a new file, a new key). */
  length(src: string): number | undefined
  setLength(src: string, seconds: number): void
}

export function createClipPreviews(): ClipPreviews {
  let current: string | null = null
  let from: Opener | null = null
  // The one-shot focus request, for `current` only.
  let focusAsked = false
  let shows = 0
  const playheads = new Map<string, number>()
  const lengths = new Map<string, number>()
  const listeners = new Set<() => void>()
  const notify = () => {
    for (const listener of listeners) {
      listener()
    }
  }
  return {
    open: () => current,
    show(identity, opener) {
      if (current !== null && current !== identity) {
        playheads.delete(current)
      }
      current = identity
      from = opener
      focusAsked = true
      shows += 1
      notify()
    },
    opener: (identity) => (current === identity ? from : null),
    takeFocus(identity) {
      if (current !== identity || !focusAsked) {
        return false
      }
      focusAsked = false
      return true
    },
    showCount: () => shows,
    hide(identity) {
      playheads.delete(identity)
      if (current !== identity) {
        return
      }
      current = null
      from = null
      focusAsked = false
      notify()
    },
    hideAll() {
      playheads.clear()
      if (current === null) {
        return
      }
      current = null
      from = null
      focusAsked = false
      notify()
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    playhead: (identity) => playheads.get(identity),
    keepPlayhead(identity, seconds) {
      if (seconds === undefined) {
        playheads.delete(identity)
      } else {
        playheads.set(identity, seconds)
      }
    },
    length: (src) => lengths.get(src),
    setLength(src, seconds) {
      if (lengths.get(src) === seconds) {
        return
      }
      lengths.set(src, seconds)
      notify()
    },
  }
}
