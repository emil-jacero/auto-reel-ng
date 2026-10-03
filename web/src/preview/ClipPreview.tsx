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

import { changedSince, checkClipMedia, clipMediaUrl, probeProxy, proxyUrl } from '../api/clipMedia'
import type { MediaCheck, ProxyProbe } from '../api/clipMedia'
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
  readyWords,
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
import {
  PLAY_COPY,
  PLAY_ORIGINAL,
  copyCannotPlayDetail,
  copyCannotPlayTitle,
  copyEmptyDetail,
  copyEmptyTitle,
  copyGoneDetail,
  copyGoneTitle,
  copyUnreadableTitle,
  playCopyName,
  playOriginalName,
  playingCopyWords,
  playingOriginalWords,
  previewSource,
  sourceLine,
  withCopySentence,
} from './source'
import type { ClipProxy } from './source'

/*
 * A clip's preview in its Cuts panel (D-16): a native <video> with the house's own
 * controls, a cut bar, Set From / Set To at the playhead, and Skip cuts, which plays
 * the clip as the movie will. It exists only while open (`previews.ts`: one on the
 * page), and its file is fetched only from then on.
 *
 * It plays the clip's preview copy (D-21) when the event detail says one is ready, and
 * the original otherwise or when the operator presses Play original (`source.ts`). The
 * copy has the original's media time, so every time below means the same in both files.
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
      {lengthMs !== null &&
        spans.map((span, at) => (
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
        ))}
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
  /** A preview copy's failure: Play original is the way out, beside any other action. */
  original?: boolean
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

/**
 * A preview copy's failure, in words (design, Decision 5): by cause, and never by the
 * copy's `Last-Modified`, which is the copy's file and not the clip's.
 */
function copyFailureOf(
  check: MediaCheck | Exclude<ProxyProbe, { kind: 'ok' }>,
  name: string,
): Failure {
  switch (check.kind) {
    case 'served':
      return {
        words: { title: copyCannotPlayTitle(name), detail: copyCannotPlayDetail },
        original: true,
      }
    case 'empty':
      return {
        words: { title: copyEmptyTitle(name), detail: copyEmptyDetail },
        original: true,
      }
    case 'problem': {
      const { problem } = check
      if (problem.status === 404) {
        return {
          words: { title: copyGoneTitle(name), detail: copyGoneDetail(problem.detail) },
          original: true,
        }
      }
      return {
        words: { title: copyUnreadableTitle(name), detail: problem.detail },
        pill: problem.failure == null ? undefined : FAILURE_LABEL[problem.failure],
        original: true,
      }
    }
    case 'unreachable':
      return {
        words: { title: UNANSWERED_CAUSE.unreachable, detail: notReachableHint(TRY_AGAIN) },
        retry: true,
        original: true,
      }
    case 'unpublished':
      return {
        words: {
          title: UNANSWERED_CAUSE.unpublished,
          detail: `${check.message}. The service's log may say why; press ${TRY_AGAIN}.`,
        },
        retry: true,
        original: true,
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
  proxy,
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
  /** The clip's proxy as the event detail gives it: it alone says which file plays. */
  proxy: ClipProxy | null
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
  // The original's address: also the key of the clip's length, whichever file plays.
  const originalSrc = clipMediaUrl(eventId, clip)
  const source = useMemo(() => previewSource(proxy), [proxy])
  const chosenOriginal = useSyncExternalStore(previews.subscribe, () => previews.original(identity))
  const playsCopy = source.kind === 'copy' && !chosenOriginal
  const videoRef = useRef<HTMLVideoElement>(null)
  const regionRef = useRef<HTMLElement>(null)
  const playRef = useRef<HTMLButtonElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  // Try again mounts the element anew.
  const [attempt, setAttempt] = useState(0)
  // The copy's entity tag, read by one byte for this attempt: no tag, no source (design, 2).
  const [probed, setProbed] = useState<{ attempt: number; version: string } | null>(null)
  // A file swap is under way: the clip's length and the time shown stay.
  const [swapping, setSwapping] = useState(false)
  const src = playsCopy
    ? probed !== null && probed.attempt === attempt
      ? proxyUrl(eventId, clip, probed.version)
      : null
    : originalSrc
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
  const length = useSyncExternalStore(previews.subscribe, () => previews.length(originalSrc))
  const lengthMs = (phase === 'ready' || swapping) && length !== undefined ? toMs(length) : null
  const shows = useSyncExternalStore(previews.subscribe, previews.showCount)
  // Each note or failure is announced once per element.
  const announced = useRef(new Set<string>())
  // Focus was in the region: a failure that removes its control moves it to Close.
  const focusInside = useRef(false)
  const scrollAfter = useRef(false)
  // Try again opens the preview anew: Play takes focus, as on Watch.
  const focusPlay = useRef(false)
  // Play pressed before the clip's metadata was read: it plays once it can.
  const pendingPlay = useRef(false)
  // Opened by Watch, the thumbnail or Try again (not remounted by a move): say when it is ready.
  const sayReady = useRef(false)
  // The announcement of a file swap, said with the notes the new file brings.
  const swapWords = useRef<string | null>(null)

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
  // The probe's effect reads the words through this, so a rename or a new announcer
  // does not ask the service again.
  const latest = useRef({ name, announce })
  useEffect(() => {
    latest.current = { name, announce }
  }, [name, announce])

  // The source, set and dropped here (see above). The cleanup keeps the playhead while
  // the store still says this preview is open (the row is being mounted elsewhere),
  // then aborts every range request: no `src`, then `load()`.
  useLayoutEffect(() => {
    const video = videoRef.current
    if (video === null || src === null) {
      return
    }
    video.src = src
    return () => {
      // Only a playhead this element holds: one that has not read its metadata (a
      // StrictMode remount, a second move before the first loaded) leaves a kept one alone.
      if (previews.open() !== identity) {
        previews.keepPlayhead(identity, undefined)
      } else if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
        previews.keepPlayhead(identity, video.currentTime)
      }
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
      sayReady.current = true
    }
  }, [shows, previews, identity])

  // After Try again the note, and its button, gave way to the transport: focus its Play.
  useLayoutEffect(() => {
    if (focusPlay.current && playRef.current !== null) {
      focusPlay.current = false
      playRef.current.focus({ preventScroll: true })
    }
  }, [attempt])

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

  // The copy's entity tag, before the element is asked for anything: one byte, once per
  // attempt. It also names a copy that has gone, or is empty, without a `MediaError`.
  useEffect(() => {
    if (!playsCopy) {
      setProbed(null)
      return
    }
    const controller = new AbortController()
    probeProxy(eventId, identity, controller.signal).then(
      (answer) => {
        if (answer.kind === 'ok') {
          setProbed({ attempt, version: answer.version })
          return
        }
        const next = copyFailureOf(answer, latest.current.name)
        setFailure(next)
        setPhase('failed')
        latest.current.announce(next.words)
      },
      () => undefined,
    )
    return () => controller.abort()
  }, [playsCopy, attempt, eventId, identity])

  // Why the browser refused the clip: one byte, once.
  useEffect(() => {
    if (phase !== 'checking' || src === null) {
      return
    }
    const controller = new AbortController()
    checkClipMedia(src, controller.signal).then(
      (check) => {
        const next = playsCopy ? copyFailureOf(check, name) : failureOf(check, name, mtime ?? null)
        setFailure(next)
        setPhase('failed')
        announce(next.words)
      },
      () => undefined,
    )
    return () => controller.abort()
  }, [phase, src, playsCopy, name, mtime, announce])

  // While playing: the head follows each presented frame, and with Skip cuts on, the
  // frame loop jumps over a cut two frame intervals ahead (design, "Skip cuts").
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

  /** Play from where Skip cuts allows, over a clip `total` ms long (null: not read yet). */
  function startPlay(video: HTMLVideoElement, total: number | null): void {
    if (skip && total !== null) {
      const now = toMs(video.currentTime)
      const from = playFrom(skipSpans(cuts, total), now, total)
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

  function togglePlay(): void {
    const video = videoRef.current
    if (video === null || phase === 'checking' || phase === 'failed') {
      return
    }
    // Before the metadata: once it is read, it plays (a second press takes that back).
    if (phase === 'loading') {
      pendingPlay.current = !pendingPlay.current
      return
    }
    if (!video.paused) {
      video.pause()
      return
    }
    startPlay(video, lengthMs)
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>): void {
    const video = videoRef.current
    // Space plays or pauses, as on Play; never the page's own scroll.
    if (event.key === ' ') {
      event.preventDefault()
      togglePlay()
      return
    }
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

  // The no-sound note is the original's; when a copy is ready it points the way to the sound.
  const soundNote: NoteWords = {
    title: noSoundWords(name).title,
    detail: withCopySentence(noSoundWords(name).detail, source.kind === 'copy'),
  }

  /**
   * Swap the file under the playhead (design, Decision 3): the source effect's cleanup
   * keeps the time, the new element's metadata restores it, and a clip that was playing
   * plays on. The element is not remounted, so focus stays on the pressed control.
   */
  function swapFile(): void {
    if (source.kind !== 'copy') {
      return
    }
    const video = videoRef.current
    if (video === null || phase === 'checking' || phase === 'failed') {
      return
    }
    const toOriginal = playsCopy
    if (phase === 'ready') {
      pendingPlay.current = !video.paused
    }
    swapWords.current = toOriginal ? playingOriginalWords(name) : playingCopyWords(name)
    setSwapping(true)
    setNotes({ sound: false, picture: false })
    setPlaying(false)
    setPhase('loading')
    previews.setOriginal(identity, toOriginal)
  }

  /** From a copy's failure: open the original anew, with focus on its Play (as Try again). */
  function playOriginalAfterFailure(): void {
    announced.current.clear()
    focusPlay.current = true
    sayReady.current = true
    swapWords.current = null
    previews.setOriginal(identity, true)
    setSwapping(false)
    setFailure(null)
    setPhase('loading')
    setAttempt((n) => n + 1)
  }

  const onLoadedMetadata = () => {
    const video = videoRef.current as FirefoxVideo | null
    if (video === null) {
      return
    }
    // The copy's length is the facts' (the original's, as probed): the browser reads the
    // copy about 20 ms off, and not always longer (design, Decision 4).
    const lengthSeconds =
      source.kind === 'copy' && playsCopy
        ? source.durationMs / 1000
        : Number.isFinite(video.duration) && video.duration > 0
          ? video.duration
          : null
    if (lengthSeconds !== null) {
      previews.setLength(originalSrc, lengthSeconds)
    }
    setSwapping(false)
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
      // The note belongs to the original: the copy carries AAC by contract (D-21).
      sound: !playsCopy && 'mozHasAudio' in video && video.mozHasAudio === false,
    }
    setNotes(next)
    setPhase('ready')
    // One announcement: the editor's live region holds one message, so the notes and the
    // readiness go together, the notes first.
    const words: string[] = []
    if (swapWords.current !== null) {
      words.push(swapWords.current)
      swapWords.current = null
    }
    for (const note of [next.sound && soundNote, next.picture && noPictureWords(name)]) {
      const message = note === false ? null : `${note.title} ${note.detail}`
      if (message !== null && !announced.current.has(message)) {
        announced.current.add(message)
        words.push(message)
      }
    }
    if (sayReady.current) {
      sayReady.current = false
      words.push(readyWords(name, lengthSeconds ?? video.duration))
    }
    if (words.length > 0) {
      onAnnounce(words.join(' '))
    }
    if (pendingPlay.current) {
      pendingPlay.current = false
      startPlay(video, lengthSeconds === null ? null : toMs(lengthSeconds))
    }
  }

  // What the browser reads from a preview copy never changes the clip's length.
  const onDurationChange = () => {
    const video = videoRef.current
    if (!playsCopy && video !== null && Number.isFinite(video.duration) && video.duration > 0) {
      previews.setLength(originalSrc, video.duration)
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
    // Not while a file swap is under way: the element is empty and reads 0.
    if (video !== null && video.paused && !swapping) {
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
    const all = typed === null ? listed : [...listed, { kind: 'typed' as const, ...typed }]
    // Drawn up to the clip's end; a span that starts at or past it has nothing to draw.
    return lengthMs === null ? [] : all.filter((span) => toMs(span.in) < lengthMs)
  }, [cuts, typed, lengthMs])
  // The legend names only the kinds the bar draws.
  const kinds = (['cut', 'removed', 'typed'] as const).filter((kind) =>
    barSpans.some((span) => span.kind === kind),
  )

  const ready = phase === 'ready'
  const setUnavailable = locked || lengthMs === null || undefined
  const fileHref = (
    <a className="btn btn-secondary btn-compact" href={originalSrc} download={fileName(identity)}>
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
      data-source={playsCopy ? 'copy' : 'original'}
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
            ) : failure.retry === true || failure.original === true ? (
              <>
                {failure.retry === true && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    onClick={() => {
                      announced.current.clear()
                      focusPlay.current = true
                      sayReady.current = true
                      swapWords.current = null
                      setSwapping(false)
                      setFailure(null)
                      setPhase('loading')
                      setAttempt((n) => n + 1)
                    }}
                  >
                    {TRY_AGAIN}
                  </button>
                )}
                {failure.original === true && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact preview-original"
                    aria-label={playOriginalName(name)}
                    onClick={playOriginalAfterFailure}
                  >
                    {PLAY_ORIGINAL}
                  </button>
                )}
              </>
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
          <p className="preview-source">
            {sourceLine(
              playsCopy ? 'copy' : 'original',
              source.kind === 'original' ? source.why : null,
            )}
          </p>
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
            {source.kind === 'copy' && (
              <button
                type="button"
                className="btn btn-ghost btn-compact preview-original"
                aria-label={playsCopy ? playOriginalName(name) : playCopyName(name)}
                onClick={swapFile}
              >
                {playsCopy ? PLAY_ORIGINAL : PLAY_COPY}
              </button>
            )}
          </div>
          {allCut && <p className="preview-said">{ALL_CUT}</p>}
          {notes.sound && (
            <Alert tone="info" role="note" title={soundNote.title} detail={soundNote.detail} />
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
