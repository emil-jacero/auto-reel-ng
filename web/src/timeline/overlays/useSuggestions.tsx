import { useCallback, useEffect, useId, useMemo, useReducer, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import { Alert } from '../../ui/Alert'
import type { TrackClip } from '../layout'
import { timeToPx } from '../model'
import type { Layout } from '../model'
import { onGrid } from '../position'
import type { Position } from '../position'
import { useAnalysis } from './useAnalysis'
import type { AnalysisControl, LaneSlot, LaneView, MarkModel } from './control'
import { SuggestionDetail } from './SuggestionDetail'
import { SuggestionLane } from './SuggestionLane'
import type { ClipMarks } from './SuggestionLane'
import {
  CUTS_WAIT_UNREADABLE,
  DISMISSAL_NOTE,
  READING_WORDS,
  READ_ONLY_NOTE,
  UNREADABLE_TITLE,
  alreadyCutWords,
  approval,
  approvedWords,
  clipNotAnalyzed,
  dismissalKey,
  dismissedWords,
  eventNote,
  neighbour,
  notApprovedWords,
  partlyCutWords,
  restoreFirstWords,
  restoredWords,
  stackMarks,
  stepOfKey,
  suggestionKey,
  suggestionState,
} from './suggestions'
import type { Suggestion } from './suggestions'

/*
 * What the Timeline calls to carry the analysis lane (D-20, "Analysis overlays"): it reads
 * the analysis once (the Timeline mounts only when its track is shown), derives every
 * mark's state from the cuts it is given, stacks the marks at the current scale, and
 * returns the lane for `Track` and the notes and detail for under the track. Without a
 * `control` it is inert: no read, no lane, nothing to show.
 */

/** A mark is at least this wide, in CSS px, whatever its span: what a finger hits. */
const MIN_MARK_PX = 44

const NO_GROUPS: readonly ClipMarks[] = []

export type Suggestions = {
  lane: LaneSlot | undefined
  /** The notes and the selected mark's detail, drawn under the track. */
  strip: ReactNode
}

type Context = {
  clips: readonly TrackClip[]
  lay: Layout
  pps: number
  /** Put the playhead at a position and show it, without playing. */
  seekTo: (pos: Position) => void
}

function bySpan(a: Suggestion, b: Suggestion): number {
  return a.start - b.start || a.end - b.end
}

export function useSuggestions(
  control: AnalysisControl | undefined,
  { clips, lay, pps, seekTo }: Context,
): Suggestions {
  const read = useAnalysis(control === undefined ? null : control.eventId)
  const detailId = useId()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [refusal, setRefusal] = useState<{ id: string; words: string } | null>(null)
  const [roving, setRoving] = useState<ReadonlyMap<string, string>>(new Map())
  // The mark that has focus, or is about to: it is drawn wherever its clip is.
  const keepId = useRef<string | null>(null)
  const refs = useRef(new Map<string, HTMLButtonElement>())
  const [, bump] = useReducer((n: number) => n + 1, 0)

  const dismissals = control?.dismissals
  const held = dismissals?.held
  useEffect(() => {
    if (read.status === 'ok') {
      dismissals?.keep(read.analysis.segments)
    }
  }, [read, dismissals])

  const cutsKnown = control?.cutsState === 'ok'
  const cutsOf = control?.cutsOf
  const base = useMemo(() => {
    if (read.status !== 'ok' || !cutsKnown || cutsOf === undefined || held === undefined) {
      return NO_GROUPS
    }
    const { analysis } = read
    return clips.map((clip, clipIndex): ClipMarks => {
      const listed = cutsOf(clip.identity)
      const found = [...(analysis.segments[clip.identity] ?? [])].sort(bySpan)
      return {
        clipIndex,
        notAnalyzed: clipNotAnalyzed(analysis, clip.identity),
        marks: found.map((segment) => {
          const id = dismissalKey(clip.identity, segment)
          return {
            id,
            identity: clip.identity,
            clipIndex,
            segment,
            state: suggestionState(listed, segment, held.has(id)),
            left: 0,
            width: 0,
            row: 0,
            barLeft: 0,
            barWidth: 0,
          }
        }),
      }
    })
  }, [read, cutsKnown, cutsOf, held, clips])

  // Where each mark sits at this scale, and how many rows the lane needs for the busiest clip.
  const { groups, rows } = useMemo(() => {
    const limit = timeToPx(lay.totalMs, pps)
    let most = 0
    let anyNote = false
    const placed = base.map((group): ClipMarks => {
      anyNote ||= group.notAnalyzed
      const spans = group.marks.map((mark) => ({
        startMs: lay.startsMs[group.clipIndex] + Math.round(mark.segment.start * 1000),
        endMs: lay.startsMs[group.clipIndex] + Math.round(mark.segment.end * 1000),
      }))
      const stacked = stackMarks(spans, pps, MIN_MARK_PX, limit)
      most = Math.max(most, stacked.count)
      return {
        ...group,
        marks: group.marks.map((mark, i): MarkModel => {
          const box = stacked.placed[i]
          const from = timeToPx(spans[i].startMs, pps)
          const to = timeToPx(spans[i].endMs, pps)
          return {
            ...mark,
            ...box,
            barLeft: from - box.left,
            barWidth: Math.max(2, to - from),
          }
        }),
      }
    })
    return { groups: placed, rows: Math.max(most, anyNote ? 1 : 0) }
  }, [base, lay, pps])

  const byId = useMemo(() => {
    const map = new Map<string, MarkModel>()
    for (const group of groups) {
      for (const mark of group.marks) {
        map.set(mark.id, mark)
      }
    }
    return map
  }, [groups])
  const selected = selectedId === null ? undefined : byId.get(selectedId)

  const tabStop = (clipIndex: number): string | null => {
    const marks = groups[clipIndex]?.marks ?? []
    if (marks.length === 0) {
      return null
    }
    const chosen = roving.get(clips[clipIndex].identity)
    return marks.some((mark) => mark.id === chosen) ? (chosen ?? null) : marks[0].id
  }

  // Focus goes to a mark once it is drawn: after an arrow or a decision by button.
  const wantFocus = useRef<string | null>(null)
  useEffect(() => {
    const id = wantFocus.current
    const element = id === null ? undefined : refs.current.get(id)
    if (element !== undefined) {
      wantFocus.current = null
      element.focus({ preventScroll: true })
    }
  })

  const register = useCallback((id: string, element: HTMLButtonElement | null) => {
    if (element === null) {
      refs.current.delete(id)
    } else {
      refs.current.set(id, element)
    }
  }, [])

  const select = (mark: MarkModel) => {
    setSelectedId(mark.id)
    setRefusal(null)
    setRoving((was) => new Map(was).set(mark.identity, mark.id))
    const clip = clips[mark.clipIndex]
    // The frame the suggestion starts on; the press does not play.
    seekTo({
      clip: mark.clipIndex,
      ms: onGrid(clip.facts, Math.round(mark.segment.start * 1000)),
    })
  }

  const focusMark = (mark: MarkModel) => {
    wantFocus.current = mark.id
    keepId.current = mark.id
    bump()
  }

  const decide = control?.decide ?? null
  const nameOf = (mark: MarkModel) => clips[mark.clipIndex].name

  const approve = (mark: MarkModel): boolean => {
    if (decide === null) {
      return false
    }
    const name = nameOf(mark)
    if (mark.state === 'cut') {
      decide.announce(alreadyCutWords(mark.segment, name))
      return true
    }
    if (mark.state === 'dismissed') {
      decide.announce(restoreFirstWords(mark.segment, name))
      return true
    }
    if (decide.locked) {
      return false
    }
    const listed = control?.cutsOf(mark.identity) ?? []
    const checked = approval(listed, mark.segment, clips[mark.clipIndex].facts.durationMs / 1000)
    if (!checked.ok) {
      const words = notApprovedWords(checked.refusal)
      setRefusal({ id: mark.id, words })
      decide.announce(words)
      return true
    }
    setRefusal(null)
    decide.onApprove(mark.identity, { in: checked.in, out: checked.out }, mark.segment.kind)
    decide.announce(approvedWords(mark.segment, name))
    return true
  }

  const dismiss = (mark: MarkModel): boolean => {
    if (decide === null || dismissals === undefined) {
      return false
    }
    const name = nameOf(mark)
    if (mark.state === 'dismissed') {
      if (decide.locked) {
        return false
      }
      dismissals.restore(mark.id)
      decide.announce(restoredWords(mark.segment, name))
      return true
    }
    if (mark.state === 'cut') {
      decide.announce(alreadyCutWords(mark.segment, name))
      return true
    }
    if (mark.state === 'partly-cut') {
      decide.announce(partlyCutWords(mark.segment, name))
      return true
    }
    if (decide.locked) {
      return false
    }
    dismissals.dismiss(mark.id)
    decide.announce(dismissedWords(mark.segment, name))
    return true
  }

  const onMarkKey = (mark: MarkModel, event: KeyboardEvent<HTMLButtonElement>) => {
    const plain = !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey
    const step = plain ? stepOfKey(event.key) : null
    if (step !== null) {
      event.preventDefault()
      const order = groups[mark.clipIndex].marks.map((m) => m.id)
      const to = neighbour(order, mark.id, step)
      const target = to === null ? undefined : byId.get(to)
      if (target !== undefined) {
        select(target)
        focusMark(target)
      }
      return
    }
    const action = suggestionKey(event.nativeEvent)
    if (action === null) {
      return
    }
    // Outside Edit mode, and while locked, the key is the browser's own.
    if ((action === 'approve' ? approve(mark) : dismiss(mark)) && !event.defaultPrevented) {
      event.preventDefault()
    }
  }

  const decideFromButton = (act: (mark: MarkModel) => boolean) => {
    if (selected !== undefined) {
      act(selected)
      focusMark(selected)
    }
  }

  const lane: LaneSlot | undefined =
    rows === 0
      ? undefined
      : {
      rows,
      render: (view: LaneView) => (
        <SuggestionLane
          view={view}
          groups={groups}
          selectedId={selectedId}
          keepId={keepId.current}
          tabStop={tabStop}
          decidable={(mark) =>
            decide !== null &&
            !decide.locked &&
            (mark.state === 'pending' || mark.state === 'partly-cut' || mark.state === 'dismissed')
          }
          detailId={detailId}
          register={register}
          onSelect={(mark) => {
            select(mark)
            focusMark(mark)
          }}
          onKeyDown={onMarkKey}
          onFocus={(id) => {
            keepId.current = id
          }}
          onBlur={(id) => {
            if (keepId.current === id) {
              keepId.current = null
            }
          }}
        />
      ),
    }

  if (control === undefined) {
    return { lane: undefined, strip: null }
  }
  return {
    lane,
    strip: (
      <Notes
        control={control}
        read={read}
        groups={groups}
        detail={
          selected === undefined ? null : (
            <SuggestionDetail
              id={detailId}
              mark={selected}
              clipName={nameOf(selected)}
              decide={decide}
              refusal={refusal?.id === selected.id ? refusal.words : null}
              onApprove={() => decideFromButton(approve)}
              onDismiss={() => decideFromButton(dismiss)}
              onRestore={() => decideFromButton(dismiss)}
            />
          )
        }
      />
    ),
  }
}

function Notes({
  control,
  read,
  groups,
  detail,
}: {
  control: AnalysisControl
  read: ReturnType<typeof useAnalysis>
  groups: readonly ClipMarks[]
  detail: ReactNode
}) {
  const { cutsState, decide } = control
  if (read.status === 'failed') {
    const { cause, detail: why } = read.failure
    return (
      <Alert
        tone="warn"
        role="note"
        title={UNREADABLE_TITLE}
        detail={why === null ? cause : `${cause} ${why}`}
      />
    )
  }
  if (read.status !== 'ok' || cutsState === 'reading') {
    return <p className="sg-note">{READING_WORDS}</p>
  }
  if (cutsState === 'unreadable') {
    return <p className="sg-note">{CUTS_WAIT_UNREADABLE}</p>
  }
  const note = eventNote(read.analysis)
  const any = groups.some((group) => group.marks.length > 0)
  return (
    <div className="sg-strip">
      {note !== null && <p className="sg-note">{note}</p>}
      {any && (
        <p className="sg-note">
          {decide === null ? READ_ONLY_NOTE : DISMISSAL_NOTE}
        </p>
      )}
      {detail}
    </div>
  )
}
