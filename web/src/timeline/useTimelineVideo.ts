import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { probeProxy, proxyUrl } from '../api/clipMedia'
import { turnAttr } from '../rotate/turn.ts'
import { mediaErrorWords } from '../movie/labels'
import type { ClipTurns } from '../cuts/ReadCuts'
import { anotherPlays, documentRoot, pauseOthers, watchOtherStarts } from '../playback/coordinator'
import { nextClip, onFrame, resumeOrYield, startFrom } from './follow'
import { NOT_STARTED, playbackNote } from './labels'
import type { Notice, PlaybackNote } from './labels'
import type { CardMap } from './cards'
import type { TrackClip } from './layout'
import type { Playhead } from './playhead'
import { createCardClock, handOverMs, handOverReady, videoTarget } from './play'
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
 *
 * A black title card (`timeline-plays-cards`) plays on the card clock (`play.ts`): nothing
 * plays in the video, the playhead advances by elapsed real time, and the card's anchor clip
 * is loaded and sought while the card lasts, so that the hand-over shows its first frame at
 * once. A card whose time is up while that is not ready holds its last frame until it is.
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
  turns,
  held = false,
  map,
  names,
}: {
  eventId: string
  clips: readonly TrackClip[]
  playhead: Playhead
  /** The black cards among the clips, and the chapters' saved names by index. */
  map: CardMap
  names: readonly string[]
  /**
   * Each clip's editorial turn (`rotate`; the draft's in Edit mode). The video is shown turned
   * by the turn of the clip it holds, set with its `src` at a swap and again when a turn changes
   * (a CSS attribute only: nothing is requested).
   */
  turns: ClipTurns
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
  const mapRef = useRef(map)
  mapRef.current = map
  const namesRef = useRef(names)
  namesRef.current = names
  const clock = useMemo(() => createCardClock(), [])
  const cardLoop = useRef<number | null>(null)
  const handOverWait = useRef(false) // a card's time is up and its clip is not ready: the card holds
  const turnsRef = useRef(turns)
  turnsRef.current = turns
  const heldRef = useRef(held)
  heldRef.current = held
  /** Play was pressed while a clip preview held the video. */
  const playWhenFree = useRef(false)
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
  const handOverRef = useRef<() => void>(() => undefined)
  const spansOf = useCallback((clip: number) => clipsRef.current[clip]?.spans ?? [], [])

  /** Show the video turned by clip `clip`'s turn (the attribute `rotate.css` styles by). */
  const applyTurn = useCallback((clip: number | null) => {
    const video = videoRef.current
    if (video === null) {
      return
    }
    const identity = clip === null ? undefined : clipsRef.current[clip]?.identity
    const value = turnAttr(identity === undefined ? 0 : (turnsRef.current.get(identity) ?? 0))
    if (value === undefined) {
      video.removeAttribute('data-turn')
    } else {
      video.setAttribute('data-turn', value)
    }
  }, [])

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
          applyTurn(clip)
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
    [addressOf, applyTurn, disarm],
  )

  const stopRef = useRef<() => void>(() => undefined)

  // Another video that starts while the operator's Play is still loading is the last start:
  // the Timeline's claim on playing ends, and it yields when it would start.
  useEffect(
    () =>
      watchOtherStarts(
        documentRoot(document),
        () => videoRef.current,
        () => {
          operatorStart.current = false
          stopRef.current()
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
    if (handOverWait.current) {
      handOverRef.current()
    }
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
      // In a card the video holds the anchor clip at its first kept time, ready for the hand-over.
      coalescer.request(videoTarget(pos, spansOf))
      if (!coalescer.busy() && afterSettle.current) {
        afterSettle.current = false
        startVideo()
      }
    },
    [coalescer, spansOf, startVideo],
  )

  /** Stop the card clock where it is, and the playhead with it. */
  const pauseCard = useCallback(() => {
    if (cardLoop.current !== null) {
      cancelAnimationFrame(cardLoop.current)
      cardLoop.current = null
    }
    const at = playhead.get()
    if (clock.running() && at.card != null) {
      playhead.set({ ...at, card: { ...at.card, ms: clock.stop(performance.now()) } })
    }
    clock.stop(performance.now())
    handOverWait.current = false
  }, [clock, playhead])

  const stopPlaying = useCallback(() => {
    playWhenFree.current = false
    pauseCard()
    wantPlay.current = false
    afterSettle.current = false
    operatorStart.current = false
    setPlaying(false)
    disarm()
    videoRef.current?.pause()
  }, [disarm, pauseCard])
  useEffect(() => {
    stopRef.current = () => {
      if (clock.running() || handOverWait.current) {
        stopPlaying()
      }
    }
  }, [clock, stopPlaying])

  /** The card's time is up and its clip is ready: the clip starts from its first kept frame, and the card goes with its first presented frame. */
  const completeHandOver = useCallback(() => {
    handOverWait.current = false
    const anchor = playhead.get().clip
    clock.stop(performance.now())
    // The playhead stays at the end of the card, whose image is at opacity 0 over black: the card
    // goes when the video presents its first frame (`arm`), so the picture is never the bare page.
    afterSettle.current = true
    moveVideo({ clip: anchor, ms: handOverMs(spansOf(anchor)) })
  }, [clock, moveVideo, playhead, spansOf])

  const finishCard = useCallback(() => {
    const anchor = playhead.get().clip
    if (handOverReady({ busy: coalescer.busy(), loadedClip: loadedClip.current, anchor })) {
      completeHandOver()
    } else {
      handOverWait.current = true
    }
  }, [coalescer, completeHandOver, playhead])
  useEffect(() => {
    handOverRef.current = () => {
      const anchor = playhead.get().clip
      if (handOverReady({ busy: coalescer.busy(), loadedClip: loadedClip.current, anchor })) {
        completeHandOver()
      }
    }
  }, [coalescer, completeHandOver, playhead])

  /** The frame clock of a card: the time reached is elapsed real time, never a count of frames. */
  const tickCard = useCallback(() => {
    cardLoop.current = null
    const at = playhead.get()
    if (!wantPlay.current || !clock.running() || at.card == null) {
      return
    }
    const { ms, due } = clock.read(performance.now())
    playhead.set({ ...at, card: { ...at.card, ms } })
    if (due) {
      clock.stop(performance.now())
      finishCard()
      return
    }
    cardLoop.current = requestAnimationFrame(tickCard)
  }, [clock, finishCard, playhead])

  /** Run the card clock from the playhead's place in a card; nothing plays in the video meanwhile. */
  const runCard = useCallback(() => {
    const at = playhead.get()
    const card = at.card
    if (card == null) {
      return
    }
    const video = videoRef.current
    if (video !== null && !video.paused) {
      ownPause.current = true
      video.pause()
    }
    disarm()
    // The Timeline's own start pauses every other player, as a start of its video does.
    pauseOthers(video, document.querySelectorAll('video'))
    handOverWait.current = false
    if (cardLoop.current !== null) {
      cancelAnimationFrame(cardLoop.current)
    }
    clock.start(performance.now(), card.ms, card.lengthMs)
    cardLoop.current = requestAnimationFrame(tickCard)
  }, [clock, disarm, playhead, tickCard])

  /** Put the playhead in a card, load its clip behind it, and run the clock if the operator is playing. */
  const enterCard = useCallback(
    (pos: Position) => {
      pauseCard()
      playhead.set(pos)
      afterSettle.current = false
      moveVideo(pos)
      if (wantPlay.current && !suspended.current) {
        runCard()
      }
    },
    [moveVideo, pauseCard, playhead, runCard],
  )

  const advance = useCallback(() => {
    const from = loadedClip.current ?? playhead.get().clip
    const next = nextClip(playable(clipsRef.current), from)
    if (next === null) {
      stopPlaying()
      playhead.set(endPosition(clipsRef.current.map((c) => c.facts)))
      return
    }
    const gap = mapRef.current.gaps.find((g) => g.clip === next.clip)
    if (gap !== undefined) {
      // The chapter opens with a black card: it plays first, the clip loads behind it.
      enterCard({
        clip: gap.clip,
        ms: 0,
        card: {
          chapter: gap.chapter,
          name: namesRef.current[gap.chapter] ?? '',
          ms: 0,
          lengthMs: gap.lengthMs,
        },
      })
      return
    }
    playhead.set(next)
    afterSettle.current = true
    moveVideo(next)
  }, [enterCard, moveVideo, playhead, stopPlaying])

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
      if (pos.card != null) {
        enterCard(pos)
        return
      }
      pauseCard()
      playhead.set(pos)
      if (wantPlay.current && !suspended.current) {
        afterSettle.current = true
      }
      moveVideo(pos)
    },
    [enterCard, moveVideo, pauseCard, playhead],
  )

  const scrubStart = useCallback(() => {
    if (wantPlay.current && !suspended.current) {
      suspended.current = true
      afterSettle.current = false
      pauseCard()
      const video = videoRef.current
      if (video !== null && !video.paused) {
        ownPause.current = true
        video.pause()
      }
    }
  }, [pauseCard])

  const scrubEnd = useCallback(() => {
    if (suspended.current) {
      suspended.current = false
      if (playhead.get().card != null) {
        afterSettle.current = false
        moveVideo(playhead.get())
        runCard()
        return
      }
      afterSettle.current = true
      moveVideo(playhead.get())
    }
  }, [moveVideo, playhead, runCard])

  const play = useCallback(() => {
    if (heldRef.current) {
      // A clip preview still holds the page's video (it is being closed): no card clock now, or it
      // would run over the preview and hand over to a video that is not there. Play goes on when
      // the Timeline has its video back.
      playWhenFree.current = true
      return
    }
    const spans = playable(clipsRef.current)
    const at = playhead.get()
    if (at.card != null) {
      // Play from inside a card goes on from there to the end of the card, then into the clip.
      setNote(null)
      wantPlay.current = true
      operatorStart.current = true
      setPlaying(true)
      enterCard(at)
      return
    }
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
  }, [enterCard, moveVideo, playhead])

  const toggle = useCallback(() => {
    if (wantPlay.current) {
      stopPlaying()
    } else {
      play()
    }
  }, [play, stopPlaying])

  // A page that is hidden pauses the card clock as it pauses a video.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden && clock.running()) {
        stopPlaying()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [clock, stopPlaying])

  // A turn changed in the draft (or read anew): the video shows it at once, with no request.
  useEffect(() => {
    applyTurn(loadedClip.current)
  }, [turns, clips, applyTurn])

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
      pauseCard()
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
  }, [coalescer, disarm, held, moveVideo, pauseCard, playhead])

  // Play was pressed while a clip preview held the video: it goes on once the video is the Timeline's.
  useEffect(() => {
    if (!held && playWhenFree.current) {
      playWhenFree.current = false
      play()
    }
  }, [held, play])

  return { videoRef, playing, note, seekTo, scrubStart, scrubEnd, toggle, handlers }
}
