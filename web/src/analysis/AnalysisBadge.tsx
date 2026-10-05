import './analysis.css'

import { useId } from 'react'

import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import { failedNamesWords } from './badge'
import type { Badge } from './badge'
import type { Reanalyze } from './useEventAnalysis'

/*
 * The event's analysis badge and Re-analyze (`analysis-web-controls`): one look in the page
 * header and the Timeline's control row, from the page's one binding (`useEventAnalysis`).
 * Every state is words and a glyph, never colour alone; the bar is outside any live region,
 * so progress is never announced.
 */

/** The badge, or nothing when the analysis is current (or not read yet). */
export function AnalysisBadge({ badge }: { badge: Badge | null }) {
  if (badge === null) {
    return null
  }
  const { progress, failed, detail } = badge
  return (
    <span className="analysis-badge" data-state={badge.state}>
      <Pill tone={badge.tone} icon={badge.icon}>
        {badge.words}
      </Pill>
      {progress !== undefined && (
        <span className="analysis-meter">
          {/* Keyed by mode: a waiting bar is one with no value at all. */}
          <progress
            key={progress === null ? 'indeterminate' : 'determinate'}
            className="job-bar"
            max={1}
            value={progress === null ? undefined : progress.fraction}
            aria-label="Analysis progress"
          />
          {progress !== null && <span className="analysis-percent">{progress.percent}%</span>}
        </span>
      )}
      {failed !== undefined && failed.names.length > 0 && (
        <span className="analysis-names">{failedNamesWords(failed)}</span>
      )}
      {detail !== undefined && <span className="analysis-detail">{detail}</span>}
    </span>
  )
}

/**
 * Re-analyze ("Analyze" while never analysed): busy while its request is in flight, and
 * unavailable with its reason while an analysis is queued or running — `aria-disabled`, not
 * `disabled`, so it keeps keyboard focus, and a press then sends nothing.
 */
export function ReanalyzeButton({ reanalyze }: { reanalyze: Reanalyze }) {
  const reasonId = useId()
  const { busy, reason, label } = reanalyze
  return (
    <>
      <button
        type="button"
        className="btn btn-secondary"
        aria-disabled={busy || reason !== null || undefined}
        aria-busy={busy || undefined}
        aria-describedby={reason === null ? undefined : reasonId}
        onClick={reanalyze.press}
      >
        <Icon name="scan" />
        {label}
      </button>
      {reason !== null && (
        <span id={reasonId} className="visually-hidden">
          {reason}
        </span>
      )}
    </>
  )
}

/** The alert a refused Re-analyze raised, until the next press. */
export function ReanalyzeAlert({ reanalyze }: { reanalyze: Reanalyze }) {
  const { alert } = reanalyze
  return alert === null ? null : <Alert tone="err" title={alert.title} detail={alert.detail} />
}
