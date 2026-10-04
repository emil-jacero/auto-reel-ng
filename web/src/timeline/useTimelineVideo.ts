import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { probeProxy, proxyUrl } from '../api/clipMedia'
import { mediaErrorWords } from '../movie/labels'
import { anotherPlays, documentRoot, watchOtherStarts } from '../playback/coordinator'
import { nextClip, onFrame, resumeOrYield, startFrom } from './follow'
import { NOT_STARTED, playbackNote } from './labels'
import type { Notice, PlaybackNote } from './labels'
import type { TrackClip } from './layout'
import type { Playhead } from './playhead'
import { endPosition, seekSeconds } from './position'
import type { Position } from './position'
import { createCoalescer } from './scrub'

/*
 * The Timeline's one `<video>` (D-20, design 4 and 9). It shows the proxy of the clip the
 * playhead is in, at the playhead's time: a move into another clip swaps `src` (a short
 * flash is accepted) and seeks, through the coalescer, so a scrub keeps one load or seek
 * in flight and ends at the last target. While playing, each presented frame moves the
 * playhead and skips the cuts as the movie will (`follow.ts`). One video plays on the
 * page (`playback/coordinator.ts`, installed in `main.tsx`); this hook only yields its own
 * resume at a swap when another video plays. A proxy that fails to play is diagnosed by
 * one request for its first byte, as the clip preview does.
 */

export type TimelineVideo = {
  videoRef: React.RefObject<HTMLVideoElement | null>
  playing: boolean
  note: (PlaybackNote | Notice) | null
  /** Put the playhead at `pos` and show it (a click, a key, a scrub move). */
  seekTo: (pos: Position) => void
  /** A scrub begins / ends: the video pauses meanwhile, and goes on after if it was playing. */
  scrubStart: () => void
  scrubEnd: () => void
  toggle: () => void
  /** Spread on the `<video>`. */
  handlers: {
    onLoadedMetadata: () => void
    onSeeked: () => void
    onError: () => void
    onPlay: () => void
    onPlaying: () => void
    onPause: () => void
    onEnded: () => void
  }
}

type FrameMeta = { mediaTime: number }
type FrameVideo = HTMLVideoElement & {
  requestVideoFrameCallback?: (callback: (now: number, meta: FrameMeta) => void) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

/** The clips as `follow.ts` plays them. */
function playable(clips: readonly TrackClip[]) {
  return clips.map((c) => ({ durationMs: c.facts.durationMs, spans: c.spans }))
}

export function useTimelineVideo({
  eventId,
  clips,
  playhead,
  held = false,
}: {
  eventId: string
  clips: readonly TrackClip[]
  playhead: Playhead
  /**
   * Another video holds the page (Edit mode's open clip preview): the Timeline renders no
   * `<video>`, so this lets go of it, keeps the playhead and plays nothing. When it is
   * false again the video is created and loads at the playhead.
   */
  held?: boolean
}): TimelineVideo {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [note, setNote] = useState<(PlaybackNote | Notice) | null>(null)

  const clipsRef = useRef(clips)
  const heldRef = useRef(held)
  heldRef.current = held
  const wantPlay = useRef(false) // the operator asked for Play and has not paused
  const afterSettle = useRef(false) // start the video once it has arrived at its target
  const operatorStart = useRef(false) // the pending start is the operator's own Play
  const suspended = useRef(false) // paused by a scrub
  const ownPause = useRef(false) // the hook paused a playing video itself: its `pause` event is not the operator's
  const swapping = useRef(false) // a new src is loading: events of the old one are ignored
  const loadedClip = useRef<number | null>(null)
  const loadedAddress = useRef<string | null>(null)
  const loop = useRef<number | null>(null)
  const diagnosis = useRef<AbortController | null>(null)

  const addressOf = useCallback(
    (clip: number) => {
      const c = clipsRef.current[clip]
      return proxyUrl(eventId, { identity: c.identity }, c.version)
    },
    [eventId],
  )

  const settleRef = useRef<() => void>(() => undefined)

  /** Cancel the pending frame callback: a new src or a stop ends the old chain (Firefox drops it, never calling it). */
  const disarm = useCallback(() => {
    const video = videoRef.current as FrameVideo | null
    if (video !== null && loop.current !== null) {
      if (video.cancelVideoFrameCallback !== undefined) {
        video.cancelVideoFrameCallback(loop.current)
      } else {
        cancelAnimationFrame(loop.current)
      }
    }
    loop.current = null
  }, [])

  // The coalescer's two calls are the only writers of `src` and of a scrub's `currentTime`.
  const coalescer = useMemo(
    () =>
      createCoalescer({
        load(clip) {
          const video = videoRef.current
          if (video === null) {
            return
          }
          disarm()
          swapping.current = true
          loadedClip.current = clip
          loadedAddress.current = addressOf(clip)
          video.src = loadedAddress.current
        },
        seek(ms) {
          const video = videoRef.current
          const clip = loadedClip.current
          if (video === null || clip === null) {
            return
          }
          const shownClip = clipsRef.current[clip]
          if (shownClip === undefined) {
            return // the page read fewer clips; the playhead is moved on its way
          }
          const target = seekSeconds(ms, shownClip.facts.fps)
          if (Math.abs(video.currentTime - target) < 0.0005) {
            // No seek happens, so no `seeked` follows.
            queueMicrotask(() => settleRef.current())
          } else {
            video.currentTime = target
          }
        },
      }),
    [addressOf, disarm],
  )

  // Another video that starts while the operator's Play is still loading is the last start:
  // the Timeline's claim on playing ends, and it yields when it would start.
  useEffect(
    () =>
      watchOtherStarts(
        documentRoot(document),
        () => videoRef.current,
        () => {
          operatorStart.current = false
        },
      ),
    [],
  )

  const startVideo = useCallback(() => {
    const video = videoRef.current
    if (video === null || !wantPlay.current) {
      return
    }
    const own = operatorStart.current
    operatorStart.current = false
    if (resumeOrYield(own, anotherPlays(video, document.querySelectorAll('video'))) === 'yield') {
      // Another video started while this one was changing file: it keeps the page.
      wantPlay.current = false
      setPlaying(false)
      return
    }
    video.play().catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return // a seek or a swap interrupted it on purpose
      }
      wantPlay.current = false
      setPlaying(false)
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        setNote({ tone: 'warn', title: NOT_STARTED, detail: null })
      }
    })
  }, [])

  /** The load or seek in flight finished: on to the latest target, or start playing. */
  const settle = useCallback(() => {
    coalescer.settled()
    if (!coalescer.busy() && afterSettle.current) {
      afterSettle.current = false
      startVideo()
    }
  }, [coalescer, startVideo])
  useEffect(() => {
    settleRef.current = settle
  }, [settle])

  /** Ask the video for `pos`, going on to play there when it should. */
  const moveVideo = useCallback(
    (pos: Position) => {
      if (heldRef.current) {
        return // no video to move: the playhead has the place, and the video loads there when it is back
      }
      coalescer.request({ clip: pos.clip, ms: pos.ms })
      if (!coalescer.busy() && afterSettle.current) {
        afterSettle.current = false
        startVideo()
      }
    },
    [coalescer, startVideo],
  )

  const stopPlaying = useCallback(() => {
    wantPlay.current = false
    afterSettle.current = false
    operatorStart.current = false
    setPlaying(false)
    disarm()
    videoRef.current?.pause()
  }, [disarm])

  const advance = useCallback(() => {
    const from = loadedClip.current ?? playhead.get().clip
    const next = nextClip(playable(clipsRef.current), from)
    if (next === null) {
      stopPlaying()
      playhead.set(endPosition(clipsRef.current.map((c) => c.facts)))
      return
    }
    playhead.set(next)
    afterSettle.current = true
    moveVideo(next)
  }, [moveVideo, playhead, stopPlaying])

  // Each presented frame while playing: move the playhead, skip a cut, or end the clip.
  const arm = useCallback(() => {
    const video = videoRef.current as FrameVideo | null
    if (video === null) {
      return
    }
    disarm()
    const frame = (_now: number, meta: FrameMeta) => {
      loop.current = null
      if (!wantPlay.current || video.paused) {
        return
      }
      const clip = loadedClip.current
      if (!swapping.current && clip !== null && !coalescer.busy()) {
        const c = clipsRef.current[clip]
        if (c === undefined) {
          arm()
          return
        }
        const ms = Math.round(meta.mediaTime * 1000)
        const stepMs = Math.round(1000 / c.facts.fps)
        const next = onFrame(c.spans, ms, stepMs, c.facts.durationMs)
        if (next.kind === 'end') {
          advance()
          return
        }
        const at = next.kind === 'seek' ? next.ms : ms
        if (next.kind === 'seek') {
          video.currentTime = seekSeconds(next.ms, c.facts.fps)
        }
        playhead.set({ clip, ms: Math.min(at, c.facts.durationMs) })
        coalescer.sync({ clip, ms: at })
      }
      arm()
    }
    loop.current =
      video.requestVideoFrameCallback !== undefined
        ? video.requestVideoFrameCallback(frame)
        : requestAnimationFrame(() => frame(0, { mediaTime: video.currentTime }))
  }, [advance, coalescer, disarm, playhead])

  const diagnose = useCallback(() => {
    const video = videoRef.current
    const clip = loadedClip.current
    if (video === null || clip === null) {
      return
    }
    const c = clipsRef.current[clip]
    if (c === undefined) {
      return
    }
    const error = video.error
    diagnosis.current?.abort()
    const controller = new AbortController()
    diagnosis.current = controller
    probeProxy(eventId, c.identity, controller.signal)
      .then((probe) => {
        if (!controller.signal.aborted) {
          setNote(playbackNote(c.name, probe, mediaErrorWords(error?.code ?? 0, error?.message ?? '')))
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setNote(
            playbackNote(c.name, { kind: 'unreachable', message: String(reason) }, ''),
          )
        }
      })
  }, [eventId])

  const handlers = useMemo<TimelineVideo['handlers']>(
    () => ({
      onLoadedMetadata() {
        swapping.current = false
        setNote(null)
        settle()
      },
      onSeeked() {
        settle()
      },
      onError() {
        if (videoRef.current?.getAttribute('src') == null) {
          return
        }
        swapping.current = false
        coalescer.failed()
        stopPlaying()
        diagnose()
      },
      onPlay() {
        ownPause.current = false // a pause that raised no event leaves nothing behind
      },
      onPlaying() {
        arm()
      },
      onPause() {
        const video = videoRef.current
        // The hook's own pause (a scrub), the end of a clip and a swap pause it too; none is the
        // operator's pause. The event is queued, so it can arrive after a quick scrub has ended.
        if (ownPause.current) {
          ownPause.current = false
          return
        }
        if (video === null || video.ended || swapping.current || suspended.current) {
          return
        }
        if (wantPlay.current) {
          wantPlay.current = false
          afterSettle.current = false
          setPlaying(false)
        }
      },
      onEnded() {
        if (wantPlay.current && !swapping.current) {
          advance()
        }
      },
    }),
    [advance, arm, coalescer, diagnose, settle, stopPlaying],
  )

  const seekTo = useCallback(
    (pos: Position) => {
      playhead.set(pos)
      if (wantPlay.current && !suspended.current) {
        afterSettle.current = true
      }
      moveVideo(pos)
    },
    [moveVideo, playhead],
  )

  const scrubStart = useCallback(() => {
    if (wantPlay.current && !suspended.current) {
      suspended.current = true
      afterSettle.current = false
      const video = videoRef.current
      if (video !== null && !video.paused) {
        ownPause.current = true
        video.pause()
      }
    }
  }, [])

  const scrubEnd = useCallback(() => {
    if (suspended.current) {
      suspended.current = false
      afterSettle.current = true
      moveVideo(playhead.get())
    }
  }, [moveVideo, playhead])

  const play = useCallback(() => {
    const spans = playable(clipsRef.current)
    const at = playhead.get()
    const start = startFrom(spans, at) ?? nextClip(spans, -1)
    if (start === null) {
      setNote({
        tone: 'info',
        title: 'Nothing plays: the cuts cover the whole timeline.',
        detail: null,
      })
      return
    }
    setNote(null)
    wantPlay.current = true
    operatorStart.current = true
    setPlaying(true)
    afterSettle.current = true
    playhead.set(start)
    moveVideo(start)
  }, [moveVideo, playhead])

  const toggle = useCallback(() => {
    if (wantPlay.current) {
      stopPlaying()
    } else {
      play()
    }
  }, [play, stopPlaying])

  // The clips as the page last read them: a proxy made again has a new address.
  useEffect(() => {
    clipsRef.current = clips
    const loaded = loadedClip.current
    if (loaded !== null && loaded < clips.length && addressOf(loaded) !== loadedAddress.current) {
      coalescer.reset()
    }
  }, [clips, addressOf, coalescer])

  // Another video took the page: nothing plays here until the Timeline has its video again.
  useEffect(() => {
    if (held) {
      stopPlaying()
    }
  }, [held, stopPlaying])

  // Open on the playhead's clip, and let go of the video and its decoder on close (or when
  // another video holds the page: then there is no element, and nothing to load).
  useEffect(() => {
    if (held) {
      return undefined
    }
    const video = videoRef.current as FrameVideo | null
    moveVideo(playhead.get())
    return () => {
      diagnosis.current?.abort()
      disarm()
      ownPause.current = false
      if (video !== null) {
        video.pause()
        video.removeAttribute('src')
        video.load()
      }
      // Nothing is loaded any more: a remount (or a second effect run) loads again.
      swapping.current = false
      loadedClip.current = null
      loadedAddress.current = null
      coalescer.failed()
    }
  }, [coalescer, disarm, held, moveVideo, playhead])

  return { videoRef, playing, note, seekTo, scrubStart, scrubEnd, toggle, handlers }
}
