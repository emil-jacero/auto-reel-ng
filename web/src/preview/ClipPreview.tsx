import './preview.css'

import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react'

import { changedSince, checkClipMedia, clipMediaUrl } from '../api/clipMedia'
import type { MediaCheck } from '../api/clipMedia'
import type { Clip } from '../api/event'
import { thumbnailUrl } from '../api/thumbnail'
import type { CutField, ListedCut } from '../cuts/times'
import { fileName } from '../events/common'
import { FAILURE_LABEL, UNANSWERED_CAUSE, notReachableHint } from '../events/labels'
import { Alert } from '../ui/Alert'
import { Icon } from '../ui/Icon'
import { Pill } from '../ui/Pill'
import {
  ALL_CUT,
  LOADING,
  PLAYHEAD_KEYS,
  SET_WORDS,
  SKIP_CUTS,
  SPAN_LABEL,
  TRY_AGAIN,
  along,
  changedWords,
  closeName,
  downloadWords,
  emptyWords,
  formatWords,
  goneWords,
  noPictureWords,
  noSoundWords,
  playFrom,
  playName,
  playheadName,
  playheadWords,
  regionName,
  seekKey,
  setName,
  skipAt,
  skipName,
  skipSpans,
  timeWords,
  toMs,
  unreadableTitle,
} from './playback'
import type { NoteWords, SpanKind } from './playback'
import type { ClipPreviews } from './previews'

/*
 * A clip's preview in its Cuts panel (D-16): a native <video> with the house's own
 * controls, a cut bar, Set From / Set To at the playhead, and Skip cuts, which plays
 * the clip as the movie will. It exists only while open (`previews.ts`: one on the
 * page), and its file is fetched only from then on.
 *
 * Every per-frame update is this component's own state: no panel, row, list or
 * editor re-renders while a clip plays. What the browser cannot do is said by cause
 * in a note (`role="note"`), announced once through the editor's live region: Edit
 * mode speaks every edit there, and an alert would cut those words off.
 */

/** Whether `identity`'s preview is the open one. */
export function usePreviewOpen(previews: ClipPreviews, identity: string): boolean {
  return useSyncExternalStore(previews.subscribe, () => previews.open() === identity)
}

/** The clip's length as this browser read it from the file at `src`, once a preview has. */
export function useClipLength(previews: ClipPreviews, src: string): number | undefined {
  return useSyncExternalStore(previews.subscribe, () => previews.length(src))
}

/** A span on the bar, in seconds. */
type BarSpan = { kind: SpanKind; in: number; out: number }

/**
 * The bar under the picture: the clip's cuts (listed, removed, typed) and the
 * playhead, as a slider over the clip's length. It edits no cut.
 */
const CutBar = memo(function CutBar({
  spans,
  lengthMs,
  atMs,
  name,
  valueText,
  valueMs,
  keysId,
  onKey,
  onPointer,
}: {
  spans: readonly BarSpan[]
  /** Null until the preview has read the clip's length: the slider is unavailable. */
  lengthMs: number | null
  atMs: number
  name: string
  valueText: string
  /** What the slider says: follows seeks at once, playback at most once a second. */
  valueMs: number
  keysId: string
  onKey: (event: KeyboardEvent<HTMLDivElement>) => void
  onPointer: {
    down: (event: PointerEvent<HTMLDivElement>) => void
    move: (event: PointerEvent<HTMLDivElement>) => void
    up: (event: PointerEvent<HTMLDivElement>) => void
  }
}) {
  const unavailable = lengthMs === null
  return (
    <div
      className="cut-bar"
      role="slider"
      tabIndex={0}
      aria-label={playheadName(name)}
      aria-disabled={unavailable || undefined}
      aria-valuemin={0}
      aria-valuemax={lengthMs === null ? 0 : lengthMs / 1000}
      aria-valuenow={lengthMs === null ? 0 : valueMs / 1000}
      aria-valuetext={lengthMs === null ? LOADING : valueText}
      aria-describedby={keysId}
      onKeyDown={onKey}
      onPointerDown={onPointer.down}
      onPointerMove={onPointer.move}
      onPointerUp={onPointer.up}
      onPointerCancel={onPointer.up}
    >
      <span className="cut-bar-track" />
      {/* Drawn up to the clip's end; a cut that starts at or past it has nothing to draw. */}
      {lengthMs !== null &&
        spans.map(
          (span, at) =>
            toMs(span.in) < lengthMs && (
              <span
                key={at}
                className="cut-bar-span"
                data-kind={span.kind}
                style={
                  {
                    '--from': `${along(toMs(span.in), lengthMs)}%`,
                    '--to': `${along(toMs(span.out), lengthMs)}%`,
                  } as CSSProperties
                }
              />
            ),
        )}
      <span
        className="cut-bar-head"
        style={{ '--at': `${lengthMs === null ? 0 : along(atMs, lengthMs)}%` } as CSSProperties}
      />
    </div>
  )
})

/** What the browser could not do with the clip, as the preview says it. */
type Failure = {
  words: NoteWords
  /** The failure kind's words, as a pill after the title (a 502 with a `failure`). */
  pill?: string
  download?: boolean
  retry?: boolean
}

/** The one-byte check's answer, in words (design, "Copy"). */
function failureOf(check: MediaCheck, name: string, mtime: string | null): Failure {
  switch (check.kind) {
    case 'served':
      return changedSince(mtime, check.lastModified)
        ? { words: changedWords(name) }
        : { words: formatWords(name), download: true }
    case 'empty':
      return { words: emptyWords(name) }
    case 'problem': {
      const { problem } = check
      if (problem.status === 404) {
        return { words: goneWords(name, problem.detail) }
      }
      return {
        words: { title: unreadableTitle(name), detail: problem.detail },
        pill: problem.failure == null ? undefined : FAILURE_LABEL[problem.failure],
      }
    }
    // No usable answer: never "Refresh", which leaves Edit mode; Try again opens anew.
    case 'unreachable':
      return {
        words: { title: UNANSWERED_CAUSE.unreachable, detail: notReachableHint(TRY_AGAIN) },
        retry: true,
      }
    case 'unpublished':
      return {
        words: {
          title: UNANSWERED_CAUSE.unpublished,
          detail: `${check.message}. The service's log may say why; press ${TRY_AGAIN}.`,
        },
        retry: true,
      }
  }
}

const PLAY = <Icon name="play" />
const PAUSE = <Icon name="pause" />
const CLOSE = <Icon name="x" />
const SKIP = <Icon name="skip-forward" />
const DOWNLOAD = <Icon name="download" />

/** `mozHasAudio`: Firefox only, false when it finds no audio it can play (R0). */
type FirefoxVideo = HTMLVideoElement & { mozHasAudio?: boolean }

/**
 * The open preview of one clip. Its element's source is set in a layout effect,
 * never as a JSX `src`, so StrictMode's second mount and a real remount (a move to
 * another chapter) behave alike, and the cleanup aborts the loading at once.
 */
export const ClipPreview = memo(function ClipPreview({
  id,
  eventId,
  clip,
  name,
  cuts,
  typed,
  locked,
  previews,
  onSet,
  onClose,
  onAnnounce,
}: {
  id: string
  eventId: string
  clip: Pick<Clip, 'identity' | 'mtime'>
  name: string
  /** The panel's cuts as listed: removed ones too, marked. */
  cuts: readonly ListedCut[]
  /** The span the panel's fields hold, when they would make a cut; a hint for the bar. */
  typed: { in: number; out: number } | null
  /** A save or a Move clips is pending: Set From and Set To change nothing. */
  locked: boolean
  previews: ClipPreviews
  onSet: (field: CutField, seconds: number) => void
  onClose: () => void
  onAnnounce: (message: string) => void
}) {
  const { identity, mtime } = clip
  const src = clipMediaUrl(eventId, clip)
  const videoRef = useRef<HTMLVideoElement>(null)
  const regionRef = useRef<HTMLElement>(null)
  const playRef = useRef<HTMLButtonElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  // Try again mounts the element anew.
  const [attempt, setAttempt] = useState(0)
  const [phase, setPhase] = useState<'loading' | 'ready' | 'checking' | 'failed'>('loading')
  const [failure, setFailure] = useState<Failure | null>(null)
  const [notes, setNotes] = useState<{ sound: boolean; picture: boolean }>({
    sound: false,
    picture: false,
  })
  const [playing, setPlaying] = useState(false)
  const [skip, setSkip] = useState(false)
  // The shown frame's time (the head), and what the slider says (at most once a
  // second while playing, so a focused slider is not read out on every frame).
  const [atMs, setAtMs] = useState(0)
  const [valueMs, setValueMs] = useState(0)
  const [allCut, setAllCut] = useState(false)
  const length = useSyncExternalStore(previews.subscribe, () => previews.length(src))
  const lengthMs = phase === 'ready' && length !== undefined ? toMs(length) : null
  const shows = useSyncExternalStore(previews.subscribe, previews.showCount)
  // Each note or failure is announced once per element.
  const announced = useRef(new Set<string>())
  // Focus was in the region: a failure that removes its control moves it to Close.
  const focusInside = useRef(false)
  const scrollAfter = useRef(false)

  const spans = useMemo(
    () => (lengthMs === null ? [] : skipSpans(cuts, lengthMs)),
    [cuts, lengthMs],
  )
  // The latest values for the frame loop, which runs outside rendering.
  const loop = useRef({ skip, spans, lengthMs })
  useEffect(() => {
    loop.current = { skip, spans, lengthMs }
  }, [skip, spans, lengthMs])

  const announce = useCallback(
    (words: NoteWords) => {
      const message = `${words.title} ${words.detail}`
      if (!announced.current.has(message)) {
        announced.current.add(message)
        onAnnounce(message)
      }
    },
    [onAnnounce],
  )

  // The source, set and dropped here (see above). The cleanup keeps the playhead while
  // the store still says this preview is open (the row is being mounted elsewhere),
  // then aborts every range request: no `src`, then `load()`.
  useLayoutEffect(() => {
    const video = videoRef.current
    if (video === null) {
      return
    }
    video.src = src
    return () => {
      previews.keepPlayhead(identity, previews.open() === identity ? video.currentTime : undefined)
      video.pause()
      video.removeAttribute('src')
      video.load()
    }
  }, [src, identity, previews, attempt])

  // Play's focus: once per `show` of this clip (Watch, or its thumbnail), never on a
  // remount after a move. Then the region comes into view whole, in a passive effect.
  useLayoutEffect(() => {
    if (previews.takeFocus(identity)) {
      playRef.current?.focus({ preventScroll: true })
      scrollAfter.current = true
    }
  }, [shows, previews, identity])

  useEffect(() => {
    if (scrollAfter.current) {
      scrollAfter.current = false
      regionRef.current?.scrollIntoView({ block: 'nearest' })
    }
  })

  // A failure replaced the control that held focus: Close takes it.
  useLayoutEffect(() => {
    if (phase !== 'failed' || !focusInside.current) {
      return
    }
    const region = regionRef.current
    if (region !== null && !region.contains(document.activeElement)) {
      closeRef.current?.focus({ preventScroll: true })
    }
  }, [phase])

  // Why the browser refused the clip: one byte, once.
  useEffect(() => {
    if (phase !== 'checking') {
      return
    }
    const controller = new AbortController()
    checkClipMedia(src, controller.signal).then(
      (check) => {
        const next = failureOf(check, name, mtime ?? null)
        setFailure(next)
        setPhase('failed')
        announce(next.words)
      },
      () => undefined,
    )
    return () => controller.abort()
  }, [phase, src, name, mtime, announce])

  // While playing: the head follows each presented frame, and with Skip cuts on, the
  // frame loop jumps over a cut one frame ahead (design, "Skip cuts").
  useEffect(() => {
    const video = videoRef.current
    if (!playing || video === null) {
      return
    }
    let handle = 0
    let last: number | null = null
    let step = 0
    // The clip's frame interval: the shortest step seen. A browser that drops the frame
    // just before a cut would present the cut's first frame next, so the loop looks two
    // intervals ahead: at most one kept frame before a cut goes unshown, never a cut frame.
    let interval = Infinity
    // The last target sought: never sought again before playback leaves it, so a
    // frame that straddles a cut's end cannot stall playback.
    let sought: number | null = null
    let spoken = -1
    const tick = (_now: number, frame: VideoFrameCallbackMetadata) => {
      const at = Math.round(frame.mediaTime * 1000)
      if (last !== null && at > last) {
        step = at - last
        interval = Math.min(interval, step)
      }
      last = at
      setAtMs(at)
      if (Math.floor(at / 1000) !== spoken) {
        spoken = Math.floor(at / 1000)
        setValueMs(at)
      }
      const { skip: skipping, spans: skips, lengthMs: total } = loop.current
      const action =
        skipping && total !== null
          ? skipAt(skips, at, step === 0 ? 0 : Math.max(step, 2 * interval), total)
          : null
      if (action !== null && 'stop' in action) {
        video.pause()
        video.currentTime = action.stop / 1000
        return
      }
      if (action !== null && action.seek !== sought) {
        sought = action.seek
        video.currentTime = action.seek / 1000
      } else if (action === null) {
        sought = null
      }
      handle = video.requestVideoFrameCallback(tick)
    }
    // Any seek (the loop's own, a key, the pointer): the next frame's step is not a
    // frame step, so the last one is kept.
    const onSeeking = () => {
      last = null
    }
    video.addEventListener('seeking', onSeeking)
    handle = video.requestVideoFrameCallback(tick)
    return () => {
      video.removeEventListener('seeking', onSeeking)
      video.cancelVideoFrameCallback(handle)
    }
  }, [playing])

  const seekTo = useCallback((ms: number) => {
    const video = videoRef.current
    if (video === null) {
      return
    }
    video.currentTime = ms / 1000
    setAtMs(ms)
    setValueMs(ms)
    setAllCut(false)
  }, [])

  function togglePlay(): void {
    const video = videoRef.current
    if (video === null || phase !== 'ready') {
      return
    }
    if (!video.paused) {
      video.pause()
      return
    }
    if (skip && lengthMs !== null) {
      const now = toMs(video.currentTime)
      const from = playFrom(spans, now, lengthMs)
      if (from === null) {
        setAllCut(true)
        onAnnounce(ALL_CUT)
        return
      }
      if (from !== now) {
        video.currentTime = from / 1000
      }
    }
    setAllCut(false)
    void video.play().catch(() => undefined)
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>): void {
    const video = videoRef.current
    if (video === null || lengthMs === null) {
      return
    }
    const ms = seekKey(event.key, toMs(video.currentTime), lengthMs)
    if (ms === null) {
      return
    }
    event.preventDefault()
    seekTo(ms)
  }

  // A press or a drag along the bar seeks there: at once with a mouse or a pen, one seek
  // per frame while dragging. A touch seeks once it moves sideways or lifts, so that a
  // vertical swipe that starts on the bar scrolls the page (`touch-action: pan-y`).
  const drag = useRef<{ id: number; touch: boolean; x: number; y: number; moved: boolean } | null>(
    null,
  )
  const frame = useRef(0)
  const pointer = useMemo(() => {
    const timeAt = (bar: HTMLElement, x: number): number | null => {
      const total = loop.current.lengthMs
      if (total === null) {
        return null
      }
      const box = bar.getBoundingClientRect()
      const fraction = box.width > 0 ? Math.min(1, Math.max(0, (x - box.left) / box.width)) : 0
      return Math.round(fraction * total)
    }
    const seekAt = (bar: HTMLElement, x: number) => {
      cancelAnimationFrame(frame.current)
      frame.current = requestAnimationFrame(() => {
        const ms = timeAt(bar, x)
        if (ms !== null) {
          seekTo(ms)
        }
      })
    }
    return {
      down(event: PointerEvent<HTMLDivElement>) {
        if (loop.current.lengthMs === null || !event.isPrimary) {
          return
        }
        const touch = event.pointerType === 'touch'
        drag.current = {
          id: event.pointerId,
          touch,
          x: event.clientX,
          y: event.clientY,
          moved: false,
        }
        if (!touch) {
          event.currentTarget.setPointerCapture(event.pointerId)
          seekAt(event.currentTarget, event.clientX)
        }
      },
      move(event: PointerEvent<HTMLDivElement>) {
        const held = drag.current
        if (held === null || held.id !== event.pointerId) {
          return
        }
        if (held.touch && !held.moved) {
          const dx = Math.abs(event.clientX - held.x)
          const dy = Math.abs(event.clientY - held.y)
          if (dx < 4 || dx <= dy) {
            return
          }
          held.moved = true
        }
        seekAt(event.currentTarget, event.clientX)
      },
      up(event: PointerEvent<HTMLDivElement>) {
        const held = drag.current
        if (held === null || held.id !== event.pointerId) {
          return
        }
        drag.current = null
        // A tap: a touch that lifted without being taken for a scroll.
        if (held.touch && event.type === 'pointerup') {
          seekAt(event.currentTarget, event.clientX)
        }
      },
    }
  }, [seekTo])
  useEffect(() => () => cancelAnimationFrame(frame.current), [])

  const onLoadedMetadata = () => {
    const video = videoRef.current as FirefoxVideo | null
    if (video === null) {
      return
    }
    if (Number.isFinite(video.duration) && video.duration > 0) {
      previews.setLength(src, video.duration)
    }
    // A move to another chapter reopens paused where the playhead stood.
    const kept = previews.playhead(identity)
    previews.keepPlayhead(identity, undefined)
    if (kept !== undefined && kept > 0) {
      video.currentTime = kept
    }
    const at = toMs(kept ?? 0)
    setAtMs(at)
    setValueMs(at)
    const next = {
      picture: video.videoWidth === 0,
      sound: 'mozHasAudio' in video && video.mozHasAudio === false,
    }
    setNotes(next)
    if (next.sound) {
      announce(noSoundWords(name))
    }
    if (next.picture) {
      announce(noPictureWords(name))
    }
    setPhase('ready')
  }

  const onDurationChange = () => {
    const video = videoRef.current
    if (video !== null && Number.isFinite(video.duration) && video.duration > 0) {
      previews.setLength(src, video.duration)
    }
  }

  const onError = () => {
    const code = videoRef.current?.error?.code
    // 1 is our own abort (the cleanup); 2, 3 and 4 ask the service why.
    if (code === undefined || code === 1 || phase === 'checking' || phase === 'failed') {
      return
    }
    setPlaying(false)
    setPhase('checking')
  }

  const onSeeked = () => {
    const video = videoRef.current
    if (video !== null && video.paused) {
      const at = toMs(video.currentTime)
      setAtMs(at)
      setValueMs(at)
    }
  }

  const barSpans = useMemo(() => {
    const listed: BarSpan[] = cuts.map((cut) => ({
      kind: cut.removed === true ? 'removed' : 'cut',
      in: cut.in,
      out: cut.out,
    }))
    return typed === null ? listed : [...listed, { kind: 'typed' as const, ...typed }]
  }, [cuts, typed])
  const kinds = (['cut', 'removed', 'typed'] as const).filter((kind) =>
    barSpans.some((span) => span.kind === kind),
  )

  const ready = phase === 'ready'
  const setUnavailable = locked || lengthMs === null || undefined
  const fileHref = (
    <a className="btn btn-secondary btn-compact" href={src} download={fileName(identity)}>
      {DOWNLOAD}
      {downloadWords(fileName(identity))}
    </a>
  )

  return (
    <section
      ref={regionRef}
      className="clip-preview"
      id={id}
      aria-label={regionName(name)}
      data-state={phase === 'failed' ? 'failed' : phase === 'ready' ? 'ready' : 'loading'}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault()
          onClose()
        }
      }}
      onFocus={() => {
        focusInside.current = true
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          focusInside.current = false
        }
      }}
    >
      <div className="preview-head">
        <span className="preview-time" aria-hidden="true">
          {timeWords(atMs, lengthMs)}
        </span>
        <button
          ref={closeRef}
          type="button"
          className="btn btn-ghost btn-icon preview-close"
          aria-label={closeName(name)}
          onClick={onClose}
        >
          {CLOSE}
        </button>
      </div>
      {phase === 'failed' && failure !== null ? (
        <Alert
          tone={failure.download === true || failure.retry === true ? 'warn' : 'err'}
          role="note"
          title={
            failure.pill === undefined ? (
              failure.words.title
            ) : (
              <>
                {failure.words.title}{' '}
                <Pill tone="err" icon="alert-triangle">
                  {failure.pill}
                </Pill>
              </>
            )
          }
          detail={failure.words.detail}
          action={
            failure.download === true ? (
              fileHref
            ) : failure.retry === true ? (
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                onClick={() => {
                  announced.current.clear()
                  setFailure(null)
                  setPhase('loading')
                  setAttempt((n) => n + 1)
                }}
              >
                {TRY_AGAIN}
              </button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="preview-stage">
            <video
              key={attempt}
              ref={videoRef}
              className="preview-video"
              preload="metadata"
              playsInline
              poster={thumbnailUrl(eventId, clip)}
              onClick={togglePlay}
              onLoadedMetadata={onLoadedMetadata}
              onDurationChange={onDurationChange}
              onPlay={() => setPlaying(true)}
              onPause={() => {
                setPlaying(false)
                onSeeked()
              }}
              onSeeked={onSeeked}
              onError={onError}
            />
            {!ready && (
              <span className="preview-status" aria-hidden="true">
                {LOADING}
              </span>
            )}
          </div>
          <div className="preview-transport">
            <button
              ref={playRef}
              type="button"
              className="btn btn-secondary btn-icon preview-play"
              aria-label={playName(name, playing)}
              aria-disabled={!ready || undefined}
              onClick={togglePlay}
            >
              {playing ? PAUSE : PLAY}
            </button>
            <CutBar
              spans={barSpans}
              lengthMs={lengthMs}
              atMs={atMs}
              name={name}
              valueText={lengthMs === null ? '' : playheadWords(valueMs, lengthMs, cuts)}
              valueMs={valueMs}
              keysId={`${id}-keys`}
              onKey={onKey}
              onPointer={pointer}
            />
          </div>
          <p className="visually-hidden" id={`${id}-keys`}>
            {PLAYHEAD_KEYS}
          </p>
          {kinds.length > 0 && lengthMs !== null && (
            <ul className="preview-legend" aria-hidden="true">
              {kinds.map((kind) => (
                <li key={kind}>
                  <span className="cut-bar-swatch" data-kind={kind} />
                  {SPAN_LABEL[kind]}
                </li>
              ))}
            </ul>
          )}
          <div className="preview-actions">
            <button
              type="button"
              className="btn btn-ghost btn-compact preview-skip"
              aria-pressed={skip}
              aria-label={skipName(name)}
              onClick={() => {
                setSkip(!skip)
                setAllCut(false)
              }}
            >
              {SKIP}
              {SKIP_CUTS}
            </button>
            {(['start', 'end'] as const).map((field) => (
              <button
                key={field}
                type="button"
                className="btn btn-secondary btn-compact preview-set"
                data-field={field}
                aria-label={setName(field, name)}
                aria-disabled={setUnavailable}
                onClick={() => {
                  const video = videoRef.current
                  if (!setUnavailable && video !== null) {
                    onSet(field, video.currentTime)
                  }
                }}
              >
                {SET_WORDS[field]}
              </button>
            ))}
          </div>
          {allCut && <p className="preview-said">{ALL_CUT}</p>}
          {notes.sound && (
            <Alert
              tone="info"
              role="note"
              title={noSoundWords(name).title}
              detail={noSoundWords(name).detail}
            />
          )}
          {notes.picture && (
            <Alert
              tone="warn"
              role="note"
              title={noPictureWords(name).title}
              detail={noPictureWords(name).detail}
              action={fileHref}
            />
          )}
        </>
      )}
    </section>
  )
})
