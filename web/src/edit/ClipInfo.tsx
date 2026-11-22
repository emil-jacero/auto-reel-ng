import './clipInfo.css'

import { useId, useMemo, useState } from 'react'

import type { Clip } from '../api/event'
import type { Turn } from '../rotate/turn.ts'
import { Icon } from '../ui/Icon'
import { rowPlace } from './binList.ts'
import type { BinRow } from './binList.ts'
import { setBinInfoHidden, useBinInfoHidden } from './binInfoPref.ts'
import { clipInfo } from './clipInfo.ts'
import type { InfoLine, InfoSection, ProxyFacts } from './clipInfo.ts'
import { shownClip } from './binPlayer.ts'
import type { DraftCut } from './draft'
import type { Selection } from './workspace/selection.ts'

/*
 * The clip bin's information (`plain-clip-bin`, design D3): under the list, what the page knows
 * of the clip the player shows. It makes no request: every line is the event read's, the ready
 * proxy's facts (already in the read) or the draft's cuts, worded by `clipInfo`. It follows the
 * selection as the player does, except that a missing clip is shown too (it has no file to play,
 * but it has a status, a place and cuts). Hide information collapses it to its heading and the
 * choice is kept (`binInfoPref`); its body is capped at 30 % of the bin's height and scrolls
 * inside itself, so the list keeps the rest.
 */

const NO_CLIP = 'Select a clip to see its information.'
export const HIDE_INFO = 'Hide information'
export const SHOW_INFO = 'Show information'

const SECTION_LABEL: Record<InfoSection, string> = {
  read: 'Clip',
  proxy: 'Proxy facts',
  cuts: 'Cuts',
}
const SECTIONS: readonly InfoSection[] = ['read', 'proxy', 'cuts']

/** A ready proxy's facts, else none: only a ready proxy has facts the page may state. */
function readyFacts(clip: Clip): ProxyFacts | null {
  const proxy = clip.proxy
  return proxy?.state === 'ready' ? (proxy.facts ?? null) : null
}

export function ClipInfo({
  selection,
  clips,
  rows,
  nameOf,
  cutsOf,
  turnOf,
}: {
  /** The page's one selection: it names the clip shown. */
  selection: Selection
  /** The clips the event lists, as the draft has them. */
  clips: ReadonlyMap<string, Clip>
  /** The bin's rows: a clip's chapter and position are its row's. */
  rows: readonly BinRow[]
  /** The clip's name as its row names it. */
  nameOf: (identity: string) => string
  /** The clip's cuts as listed now. */
  cutsOf: (identity: string) => readonly DraftCut[]
  /** The clip's turn in the draft. */
  turnOf: (identity: string) => Turn
}) {
  const id = useId()
  const hidden = useBinInfoHidden()
  const [was, setWas] = useState<string | null>(null)
  const listed = useMemo(() => new Set(clips.keys()), [clips])
  // The player's rule, but for every clip the event lists: a missing one is shown as well.
  const shown = shownClip(selection, was, listed, () => true)
  if (shown !== was) {
    setWas(shown)
  }
  const clip = shown === null ? undefined : clips.get(shown)
  const row = useMemo(
    () => (shown === null ? undefined : rows.find((candidate) => candidate.identity === shown)),
    [rows, shown],
  )
  const lines: InfoLine[] | null =
    shown === null || clip === undefined
      ? null
      : clipInfo(
          clip,
          readyFacts(clip),
          cutsOf(shown),
          row === undefined ? null : rowPlace(row),
          turnOf(shown),
        )
  const name = shown === null ? null : nameOf(shown)

  return (
    <section
      className="bin-info"
      aria-label="Clip information"
      data-hidden={hidden || undefined}
    >
      <div className="bin-info-head">
        <h2 className="bin-info-title">
          <span>Information</span>
          {name !== null && !hidden && <span className="bin-info-clip">{name}</span>}
        </h2>
        <button
          type="button"
          className="btn btn-ghost btn-compact bin-info-toggle"
          aria-expanded={!hidden}
          aria-controls={`${id}-body`}
          onClick={() => setBinInfoHidden(!hidden)}
        >
          <Icon name={hidden ? 'info' : 'eye-off'} />
          {hidden ? SHOW_INFO : HIDE_INFO}
        </button>
      </div>
      <div id={`${id}-body`} className="bin-info-body" hidden={hidden}>
        {lines === null ? (
          <p className="bin-info-empty">{NO_CLIP}</p>
        ) : (
          SECTIONS.map((section) => {
            const own = lines.filter((line) => line.section === section)
            return own.length === 0 ? null : (
              <dl key={section} className="bin-info-list" aria-label={SECTION_LABEL[section]}>
                {own.map((line) => (
                  <div key={line.label} className="bin-info-line" data-label={line.label}>
                    <dt>{line.label}</dt>
                    <dd>
                      {line.dateTime === undefined ? (
                        line.value
                      ) : (
                        <time dateTime={line.dateTime}>{line.value}</time>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            )
          })
        )}
      </div>
    </section>
  )
}
