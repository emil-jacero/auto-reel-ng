import { Fragment, useId } from 'react'

import { SHORTCUT_GROUPS, SHORTCUTS } from './shortcuts.ts'
import type { Shortcut } from './shortcuts.ts'
import { setShortcutsEnabled, useShortcutsEnabled } from './shortcutSwitch.ts'

/*
 * The Keyboard shortcuts list (`editor-shortcuts`, D4): a non-modal native popover (`#ws-keys`)
 * under the top bar, drawn from `SHORTCUTS` so that it and the keys cannot disagree. The operator
 * can read it and try the keys at once. Light dismiss and Escape close it natively; the `?` key
 * toggles it (`useTimeline`). It holds the single-key switch (D5).
 */

export const KEYS_LIST_ID = 'ws-keys'

/** One alternative of a row: key caps joined by `+`. A mouse row is words, not caps. */
function Chord({ parts, mouse }: { parts: readonly string[]; mouse: boolean }) {
  if (mouse) {
    // `Ctrl+wheel over the Timeline`: the first part a cap when a chord follows, the rest words.
    const [first, ...rest] = parts
    return rest.length === 0 ? (
      <>{first}</>
    ) : (
      <>
        <kbd>{first}</kbd>+{rest.join(' ')}
      </>
    )
  }
  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={part}>
          {index > 0 && '+'}
          <kbd>{part}</kbd>
        </Fragment>
      ))}
    </>
  )
}

function Row({ row }: { row: Shortcut }) {
  return (
    <>
      <dt>
        {row.keys.map((chord, index) => (
          <Fragment key={chord.join('+')}>
            {index > 0 && <span className="ws-keys-or"> or </span>}
            <Chord parts={chord} mouse={row.scope === 'mouse'} />
          </Fragment>
        ))}
      </dt>
      <dd>{row.words}</dd>
    </>
  )
}

export function KeysList() {
  const heading = useId()
  const on = useShortcutsEnabled()
  const switchId = useId()
  const hintId = useId()
  return (
    <section id={KEYS_LIST_ID} className="ws-keys" popover="auto" aria-labelledby={heading}>
      <h2 id={heading} className="ws-keys-title">
        Keyboard shortcuts
      </h2>
      <div className="ws-keys-switch">
        <input
          id={switchId}
          type="checkbox"
          role="switch"
          checked={on}
          aria-describedby={hintId}
          onChange={(event) => setShortcutsEnabled(event.currentTarget.checked)}
        />
        <label htmlFor={switchId}>Single-key shortcuts</label>
        <p id={hintId} className="ws-keys-hint">
          Off, Space, the arrows, Q, W, S, the zoom keys and ? act only when the playhead, the
          track or a handle has focus. Ctrl and Cmd shortcuts stay.
        </p>
      </div>
      {SHORTCUT_GROUPS.map((group) => (
        <Fragment key={group}>
          <h3>{group}</h3>
          <dl>
            {SHORTCUTS.filter((row) => row.group === group).map((row) => (
              <Row key={row.keys.map((chord) => chord.join('+')).join('|')} row={row} />
            ))}
          </dl>
        </Fragment>
      ))}
    </section>
  )
}
