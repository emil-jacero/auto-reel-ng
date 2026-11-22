import { useEffect, useId, useRef, useState } from 'react'

import { RotateButtons } from '../rotate/RotateButtons'
import type { Way } from '../rotate/turn'
import { MoveTo } from '../timeline/MoveTo'
import { groupBusy, groupHeading, groupNames } from '../timeline/moveTo'
import type { EditBinding } from '../timeline/editing'
import { Icon } from '../ui/Icon'
import type { ChapterKey } from './draft'

/*
 * The Clip tab of two or more selected clips (`clip-multi-select` D5), built by the editor since
 * `clip-tab-and-player` (every edit it makes is a draft edit, so it needs no track): how many and
 * which, then what acts on all of them: Rotate left and right (each clip from its own turn), Move
 * to… (the clips at the end of a chapter, in play order), Ignore clips, and Include clips when some
 * of them are ignored (`plain-clip-bin` D5). Each is one draft edit and one Undo step; `editing`
 * ignores a clip that is not on disk or that no chapter plays, and Include clips one that is played.
 * A set of ignored clips only offers Include clips: nothing else applies to a clip no chapter plays.
 */
export function ClipGroupTab({
  clips,
  chapters,
  editing,
  onIgnored,
}: {
  /**
   * The selected clips in the bin's order (the ones a chapter plays, then the ignored ones), as their
   * rows name them.
   */
  clips: readonly { identity: string; name: string; ignored: boolean }[]
  /** The chapters the draft lists: Move to… lists them all. */
  chapters: readonly { key: ChapterKey; name?: string }[]
  editing: EditBinding
  /** Ignore clips ignored these clips: they are no longer played, so nothing stays selected. */
  onIgnored: (identities: readonly string[]) => void
}) {
  const busyId = useId()
  const locked = editing.locked
  const busy = groupBusy(editing.moving)
  const identities = clips.map((clip) => clip.identity)
  const { shown, more } = groupNames(clips.map((clip) => clip.name))
  const rotate = (_identity: string, way: Way) => editing.onRotateMany(identities, way)
  const ignoredCount = clips.filter((clip) => clip.ignored).length
  const playsAny = ignoredCount < clips.length
  // After Include clips the last ignored clip is played, and Ignore clips takes the place of the
  // button that held focus: focus goes there, not to the page.
  const ignoreButton = useRef<HTMLButtonElement>(null)
  const [included, setIncluded] = useState(false)
  useEffect(() => {
    if (included && ignoredCount === 0) {
      ignoreButton.current?.focus({ preventScroll: true })
      setIncluded(false)
    }
  }, [included, ignoredCount])
  const guarded = (act: () => void) => () => {
    if (locked) {
      editing.announce(busy)
      return
    }
    act()
  }
  return (
    <div className="ct-tab ct-group">
      <header className="tl-clip-head">
        <h3 className="tl-clip-name">{groupHeading(clips.length)}</h3>
        <ul className="ct-names" aria-label="Selected clips">
          {shown.map((name, at) => (
            <li key={identities[at]}>{name}</li>
          ))}
        </ul>
        {more !== null && <p className="tl-clip-where">{more}</p>}
      </header>
      {playsAny && (
        <div className="ct-row">
          <RotateButtons
            identity=""
            name={`${clips.length} clips`}
            locked={locked}
            onRotate={rotate}
            describedBy={busyId}
          />
        </div>
      )}
      {playsAny && (
        <MoveTo
          selectLabel="Chapter to move the selected clips to"
          chapters={chapters}
          own={null}
          locked={locked}
          moving={editing.moving}
          announce={editing.announce}
          onMove={(to) => editing.onMoveSelection(identities, to)}
        />
      )}
      {playsAny && (
        <button
          ref={ignoreButton}
          type="button"
          className="btn btn-secondary ct-ignore"
          aria-disabled={locked || undefined}
          aria-describedby={locked ? busyId : undefined}
          title={locked ? busy : undefined}
          onClick={guarded(() => {
            if (editing.onIgnoreMany(identities)) {
              onIgnored(identities)
            }
          })}
        >
          <Icon name="eye-off" />
          Ignore clips
        </button>
      )}
      {ignoredCount > 0 && (
        <button
          type="button"
          className="btn btn-secondary ct-ignore"
          aria-disabled={locked || undefined}
          aria-describedby={locked ? busyId : undefined}
          title={locked ? busy : undefined}
          onClick={guarded(() => {
            if (editing.onIncludeMany(identities)) {
              setIncluded(true)
            }
          })}
        >
          <Icon name="plus" />
          Include clips
        </button>
      )}
      <p id={busyId} className={locked ? 'tl-fields-locked' : 'visually-hidden'}>
        {locked ? busy : ''}
      </p>
    </div>
  )
}
