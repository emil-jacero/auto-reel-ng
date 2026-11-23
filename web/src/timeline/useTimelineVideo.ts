import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { probeProxy, proxyUrl } from '../api/clipMedia'
import { turnAttr } from '../rotate/turn.ts'
import { mediaErrorWords } from '../movie/labels'
import type { ClipTurns } from '../cuts/ReadCuts'
import { anotherPlays, documentRoot, pauseOthers, watchOtherStarts } from '../playback/coordinator'
import { nextClip, onFrame, resumeOrYield, startFrom } from './follow'
import {
  earlyTimes,
  frameClock,
  FRESH,
  keptEndOf,
  leadOf,
  median,
  preRollOf,
  resetCalibration,
  withAlignmentSample,
  withLeadSample,
} from './lead'
import type { Calibration, FrameSample } from './lead'
import { atBoundary, IDLE, standbyAim, standbyStep, standbyTarget } from './standby'
import type { Standby, Target } from './standby'
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
 * The Timeline's player (D-20; change `seamless-playback`). Two `<video>` slots form one
 * player: the SHOWN slot shows the proxy of the clip the playhead is in, at the playhead's
 * time, and the STANDBY slot (`data-standby`, opacity 0, muted) holds the next clip, loaded
 * and sought to its first kept frame less a learned pre-roll P while Play holds. A move of
 * the playhead into another clip loads the shown slot (a short flash is accepted) and seeks
 * through the coalescer, so a scrub keeps one load or seek in flight and ends at the last
 * target. While playing, each presented frame moves the playhead and skips the cuts as the
 * movie will (`follow.ts`).
 *
 * A PLAIN CLIP BOUNDARY hands over to the standby (design D3, D4), with no request, load or
 * seek at the boundary. Timed on the shown slot's frame clock (callback time minus media
 * time, `lead.ts`), two timers run: one LEAD before the kept end the standby starts,
 * unmuted and still invisible (its audio start-up and clock run while the shown clip plays
 * its last frames); at the last kept frame the DECISION pauses the shown slot, binds the
 * coalescer and the playhead to the standby, and one frame interval later, on the standby's
 * first presented frame at or past its first kept frame, the SWAP exchanges the roles. The
 * shown slot then loads the clip after. `onFrame` ending a clip and `ended` are BACKSTOPS
 * that run the same decision late; a standby still loading or seeking holds the boundary
 * (`wait`: the last frame stays, the standby's `seeked` runs the hand-over), and one that is
 * not on the next clip loads into the shown slot as before (`load`). LEAD (play start-up)
 * and P (pre-roll, closed loop on the signed alignment error) are sampled at every
 * hand-over and reset on `devicechange`. A pause, scrub, seek, yield or reload during the
 * lead pauses the standby and seeks it back to its pre-sought position; it is `seeking`
 * (not ready) until that lands. A swap leaves `data-handover` (what ran the decision),
 * `data-lead` and `data-preroll` (the values used) on the shown slot, for measurements.
 *
 * One player on the page (`playback/coordinator.ts`, installed in `main.tsx`): both slots
 * are this player's own (`data-player`), so the lead's two playing slots are not "another".
 * The hook yields its own resume when another video plays. A proxy that fails to play is
 * diagnosed by one request for its first byte, as the clip preview does; a standby that
 * fails to load is dropped silently and the boundary loads as before.
 *
 * A black title card (`timeline-plays-cards`) plays on the card clock (`play.ts`): nothing
 * plays in the video, the playhead advances by elapsed real time, and the card's anchor clip
 * is loaded and sought in the shown slot while the card lasts, so that the hand-over shows
 * its first frame at once. A card whose time is up while that is not ready holds its last
 * frame until it is. The standby does not cross black cards. Both slots are released when
 * another video holds the page (`held`) and on unmount.
 */

/** The media events of one slot; which role they act for is read when they arrive (it swaps). */
export type SlotHandlers = {
  onLoadedMetadata: () => void
  onLoadedData: () => void
  onCanPlay: () => void
  onSeeked: () => void
  onError: () => void
  onPlay: () => void
  onPlaying: () => void
  onPause: () => void
  onEnded: () => void
}

export type TimelineVideo = {
  /** Slot A of the stage. Which slot is shown changes at a hand-over: read `shown()` for it. */
  videoRef: React.RefObject<HTMLVideoElement | null>
  /** Slot B of the stage (seamless-playback D1). */
  standbyRef: React.RefObject<HTMLVideoElement | null>
  /** The slot that shows the playhead's frame now (null while neither is rendered). */
  shown: () => HTMLVideoElement | null
  /** Calls `listener` after each swap of the slots' roles; returns the remover. */
  onSwap: (listener: () => void) => () => void
  playing: boolean
  note: (PlaybackNote | Notice) | null
  /** Put the playhead at `pos` and show it (a click, a key, a scrub move). */
  seekTo: (pos: Position) => void
  /** A scrub begins / ends: the video pauses meanwhile, and goes on after if it was playing. */
  scrubStart: () => void
  scrubEnd: () => void
  toggle: () => void
  /** Spread on slot A (`[0]`) and slot B (`[1]`). */
  slotHandlers: readonly [SlotHandlers, SlotHandlers]
}

type FrameMeta = { mediaTime: number }
type FrameVideo = HTMLVideoElement & {
  requestVideoFrameCallback?: (callback: (now: number, meta: FrameMeta) => void) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

type Slot = 0 | 1
type Source = 'timer' | 'frame' | 'ended' | 'seeked'

/**
 * One early start of the standby, from its `play()` to the samples taken of it: the lead's
 * numbers, and the swap that follows the decision.
 */
type LeadRun = {
  slot: Slot
  /** The position the standby was pre-sought to, in ms, and the pre-roll applied. */
  soughtMs: number
  preRollMs: number
  inMs: number
  playAt: number
  /** The predicted real time of the incoming clip's first kept frame (timer path), else null. */
  endAt: number | null
  source: Source
  want: Target
  /** Presented frames newer than the pre-sought one: `atMs` and `mediaMs`. */
  samples: FrameSample[]
  leadSampled: boolean
  aligned: boolean
  committed: boolean
  swapped: boolean
  /** The earliest real time of the swap (one frame interval after the decision). */
  swapAt: number
  /** A cancel after the decision: swap once the standby is at the first kept frame. */
  finishOnSeek: boolean
  watchdog: number | null
  chain: number | null
}

/** The session's LEAD and P: kept across Timeline remounts, reset on `devicechange`. */
let calibration: Calibration = FRESH

/** The clips as `follow.ts` plays them. */
function playable(clips: readonly TrackClip[]) {
  return clips.map((c) => ({ durationMs: c.facts.durationMs, spans: c.spans }))
}

/** The decision was made and the swap of the pictures has not run. */
function windowOpen(run: LeadRun | null): boolean {
  return run !== null && run.committed && !run.swapped
}

const SWAP_WATCHDOG_MS = 1500
const ALIGN_SAMPLES = 4
/** A timer fires only while the shown slot is this close to its kept end (a stale timer is dropped). */
const NEAR_END_MS = 250

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
  /** The black cards among the clips, and the drawn chapters' names by index. */
  map: CardMap
  names: readonly string[]
  /**
   * Each clip's editorial turn (`rotate`; the draft's in Edit mode). Each slot is shown turned
   * by the turn of the clip it holds, set with its `src` and again when a turn changes
   * (a CSS attribute only: nothing is requested).
   */
  turns: ClipTurns
  /**
   * Another video holds the page (Edit mode's open clip preview): the Timeline renders no
   * `<video>`, so this lets go of both and keeps the playhead and plays nothing. When it is
   * false again the video is created and loads at the playhead.
   */
  held?: boolean
}): TimelineVideo {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const standbyRef = useRef<HTMLVideoElement | null>(null)
  const slotRefs = useMemo(() => [videoRef, standbyRef] as const, [])
  const shownSlot = useRef<Slot>(0) // the slot of the playhead's clip: the coalescer, the frame loop and the shown handlers
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
  // The hook paused a playing slot itself: that slot's `pause` event is not the operator's.
  const ownPause = useRef<[boolean, boolean]>([false, false])
  const swapping = useRef(false) // a new src is loading in the shown slot: its old events are ignored
  const loadedClip = useRef<number | null>(null)
  const loadedAddress = useRef<string | null>(null)
  const loop = useRef<number | null>(null)
  const diagnosis = useRef<AbortController | null>(null)
  const slotClips = useRef<[number | null, number | null]>([null, null])

  // The standby (design D2, D3, D4).
  const standby = useRef<Standby>(IDLE)
  const standbyFailedKey = useRef<string | null>(null)
  /** The pre-roll and the position the standby was sought to, for the cancel's seek back. */
  const standbyPlace = useRef<{ preRollMs: number; seconds: number } | null>(null)
  const standbyWait = useRef<Target | null>(null) // the boundary holds for the standby (`wait`)
  const leadRun = useRef<LeadRun | null>(null)
  const frames = useRef<FrameSample[]>([]) // the shown slot's presented frames (the frame clock)
  const timers = useRef<{ start: number | null; decide: number | null; endAt: number }>({
    start: null,
    decide: null,
    endAt: 0,
  })
  const swapListeners = useRef(new Set<() => void>())

  const shownEl = useCallback(() => slotRefs[shownSlot.current].current, [slotRefs])
  const standbyEl = useCallback(() => slotRefs[shownSlot.current === 0 ? 1 : 0].current, [slotRefs])
  const standbySlot = useCallback((): Slot => (shownSlot.current === 0 ? 1 : 0), [])
  const isOwn = useCallback(
    (video: unknown) => video === videoRef.current || video === standbyRef.current,
    [],
  )

  const addressOf = useCallback(
    (clip: number) => {
      const c = clipsRef.current[clip]
      return proxyUrl(eventId, { identity: c.identity }, c.version)
    },
    [eventId],
  )

  const settleRef = useRef<() => void>(() => undefined)
  const swapRef = useRef<(run: LeadRun) => void>(() => undefined)
  const handOverRef = useRef<() => void>(() => undefined)
  // What the hand-over needs of a clip: its length and its spans (its kept start, `handOverMs`).
  const handOverOf = useCallback((clip: number) => {
    const c = clipsRef.current[clip]
    return c === undefined ? undefined : { durationMs: c.facts.durationMs, spans: c.spans }
  }, [])

  /** Show `slot` turned by clip `clip`'s turn (the attribute `rotate.css` styles by). */
  const applyTurnTo = useCallback((slot: Slot, clip: number | null) => {
    slotClips.current[slot] = clip
    const video = slotRefs[slot].current
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
  }, [slotRefs])
  const applyTurn = useCallback(
    (clip: number | null) => applyTurnTo(shownSlot.current, clip),
    [applyTurnTo],
  )

  /** Cancel the pending frame callback: a new src or a stop ends the old chain (Firefox drops it, never calling it). */
  const disarm = useCallback(() => {
    const video = shownEl() as FrameVideo | null
    if (video !== null && loop.current !== null) {
      if (video.cancelVideoFrameCallback !== undefined) {
        video.cancelVideoFrameCallback(loop.current)
      } else {
        cancelAnimationFrame(loop.current)
      }
    }
    loop.current = null
  }, [shownEl])

  const clearTimers = useCallback(() => {
    if (timers.current.start !== null) {
      clearTimeout(timers.current.start)
    }
    if (timers.current.decide !== null) {
      clearTimeout(timers.current.decide)
    }
    timers.current.start = null
    timers.current.decide = null
  }, [])

  /** Pause `slot` as the hook's own act: its `pause` event is not the operator's. */
  const pauseOwn = useCallback(
    (slot: Slot) => {
      const video = slotRefs[slot].current
      if (video !== null && !video.paused) {
        ownPause.current[slot] = true
        video.pause()
      }
    },
    [slotRefs],
  )

  const stopChain = useCallback(
    (run: LeadRun) => {
      const video = slotRefs[run.slot].current as FrameVideo | null
      if (run.chain !== null && video !== null) {
        if (video.cancelVideoFrameCallback !== undefined) {
          video.cancelVideoFrameCallback(run.chain)
        }
      }
      run.chain = null
      if (run.watchdog !== null) {
        clearTimeout(run.watchdog)
        run.watchdog = null
      }
    },
    [slotRefs],
  )

  /** The standby's seek landed (or there was none to land): it is ready when it has a frame. */
  const standbyLanded = useCallback((handOver: (want: Target) => void) => {
    const video = standbyEl()
    const s = standby.current
    if (video === null || s.kind !== 'seeking' || video.seeking || video.readyState < 2) {
      return
    }
    standby.current = standbyStep(s, 'seeked')
    const wait = standbyWait.current
    if (wait !== null && wantPlay.current) {
      handOver(wait)
    }
  }, [standbyEl])
  const standbyLandedRef = useRef<() => void>(() => undefined)

  /** The lead is over before the decision: the standby pauses and goes back to its pre-sought position. */
  const cancelLead = useCallback(() => {
    const run = leadRun.current
    const s = standby.current
    if (run !== null && run.committed && !run.swapped) {
      // After the decision (the shown role is the standby's): pause it, and swap once it is at the first kept frame.
      const video = slotRefs[run.slot].current
      stopChain(run)
      if (video === null) {
        return
      }
      pauseOwn(run.slot)
      run.finishOnSeek = true
      const clip = clipsRef.current[run.want.clip]
      const target = clip === undefined ? 0 : seekSeconds(run.want.ms, clip.facts.fps)
      if (Math.abs(video.currentTime * 1000 - run.want.ms) < 1 || video.currentTime >= target) {
        // Already at the first kept frame: swap directly. A settle here would mark a seek of the
        // coalescer as done while it is still in flight.
        swapRef.current(run)
      } else {
        video.currentTime = target
      }
      return
    }
    if (s.kind !== 'started') {
      return
    }
    if (run !== null) {
      stopChain(run)
    }
    leadRun.current = null
    const video = standbyEl()
    if (video === null) {
      return
    }
    pauseOwn(standbySlot())
    video.muted = true
    standby.current = standbyStep(s, 'cancelled')
    const back = standbyPlace.current?.seconds ?? 0
    if (Math.abs(video.currentTime - back) < 0.0005 && !video.seeking) {
      queueMicrotask(() => standbyLandedRef.current())
    } else {
      video.currentTime = back
    }
  }, [pauseOwn, slotRefs, standbyEl, standbySlot, stopChain])

  /** The timers, the lead and the boundary wait end: the shown clip goes on as the caller says. */
  const cancelEarly = useCallback(() => {
    clearTimers()
    standbyWait.current = null
    cancelLead()
  }, [cancelLead, clearTimers])

  // The coalescer's two calls are the only writers of the shown slot's `src` and of a scrub's `currentTime`.
  const coalescer = useMemo(
    () =>
      createCoalescer({
        load(clip) {
          const video = shownEl()
          if (video === null) {
            return
          }
          disarm()
          cancelEarly()
          frames.current = []
          swapping.current = true
          loadedClip.current = clip
          loadedAddress.current = addressOf(clip)
          applyTurn(clip)
          video.src = loadedAddress.current
        },
        seek(ms) {
          const video = shownEl()
          const clip = loadedClip.current
          if (video === null || clip === null) {
            return
          }
          const shownClip = clipsRef.current[clip]
          if (shownClip === undefined) {
            return // the page read fewer clips; the playhead is moved on its way
          }
          cancelEarly()
          frames.current = []
          const target = seekSeconds(ms, shownClip.facts.fps)
          if (Math.abs(video.currentTime - target) < 0.0005) {
            // No seek happens, so no `seeked` follows.
            queueMicrotask(() => settleRef.current())
          } else {
            video.currentTime = target
          }
        },
      }),
    [addressOf, applyTurn, cancelEarly, disarm, shownEl],
  )

  const stopRef = useRef<() => void>(() => undefined)

  // Another video that starts while the operator's Play is still loading is the last start:
  // the Timeline's claim on playing ends, and it yields when it would start. Either slot's
  // start is the Timeline's own.
  useEffect(
    () =>
      watchOtherStarts(
        documentRoot(document),
        isOwn,
        () => {
          operatorStart.current = false
          stopRef.current()
        },
      ),
    [isOwn],
  )

  const startVideo = useCallback(() => {
    const video = shownEl()
    if (video === null || !wantPlay.current) {
      return
    }
    const own = operatorStart.current
    operatorStart.current = false
    if (resumeOrYield(own, anotherPlays(isOwn, document.querySelectorAll('video'))) === 'yield') {
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
  }, [isOwn, shownEl])

  // --- the standby ----------------------------------------------------------------------

  /** Release a slot: pause, no `src`, no decoder. */
  const release = useCallback((video: HTMLVideoElement | null) => {
    if (video !== null) {
      video.pause()
      video.removeAttribute('src')
      video.load()
    }
  }, [])

  /**
   * Point the standby at the clip after the shown one, while Play holds: loads it, seeks it
   * to its first kept frame less P, and re-points it when the target changed (a draft edit,
   * a seek). An unchanged target leaves it as it is.
   */
  const aimStandby = useCallback(() => {
    const from = loadedClip.current
    const video = standbyEl()
    if (
      heldRef.current ||
      !wantPlay.current ||
      from === null ||
      video === null ||
      swapping.current ||
      windowOpen(leadRun.current)
    ) {
      return
    }
    const target = standbyTarget(playable(clipsRef.current), mapRef.current.gaps, from)
    const address = target === null ? '' : addressOf(target.clip)
    const key = target === null ? null : `${address}|${target.clip}|${target.ms}`
    if (key !== null && key === standbyFailedKey.current) {
      return
    }
    const cur = standby.current
    const next = standbyAim(cur, target, address)
    if (next === cur) {
      if (target === null && video.hasAttribute('src')) {
        release(video)
        slotClips.current[standbySlot()] = null
      }
      return
    }
    if (cur.kind === 'started') {
      cancelLead()
    }
    standbyWait.current = standbyWait.current !== null && target !== null ? standbyWait.current : null
    standby.current = next
    if (target === null) {
      release(video)
      slotClips.current[standbySlot()] = null
      return
    }
    video.muted = true
    applyTurnTo(standbySlot(), target.clip)
    video.src = address
  }, [addressOf, applyTurnTo, cancelLead, release, standbyEl, standbySlot])

  /**
   * `aimStandby` in its own task. Firefox ends a slot's frame-callback chain when another
   * slot's `src` is written from inside one of its callbacks (the frame loop, the swap), so a
   * write from a frame callback goes through here.
   */
  const aimTimer = useRef<number | null>(null)
  const aimSoon = useCallback(() => {
    if (aimTimer.current === null) {
      aimTimer.current = window.setTimeout(() => {
        aimTimer.current = null
        aimStandby()
      }, 0)
    }
  }, [aimStandby])
  const aimSoonRef = useRef<() => void>(() => undefined)
  useEffect(() => {
    aimSoonRef.current = aimSoon
    return () => {
      if (aimTimer.current !== null) {
        clearTimeout(aimTimer.current)
        aimTimer.current = null
      }
    }
  }, [aimSoon])

  /** The standby's metadata arrived: seek it to its first kept frame less P. */
  const standbyLoaded = useCallback(() => {
    const video = standbyEl()
    const s = standby.current
    if (video === null || s.kind !== 'loading') {
      return
    }
    const clip = clipsRef.current[s.target.clip]
    if (clip === undefined) {
      return
    }
    standby.current = standbyStep(s, 'loadedmetadata')
    const preRollMs = preRollOf(calibration, s.target.ms)
    const seconds = seekSeconds(s.target.ms - preRollMs, clip.facts.fps)
    standbyPlace.current = { preRollMs, seconds }
    if (Math.abs(video.currentTime - seconds) < 0.0005) {
      queueMicrotask(() => standbyLandedRef.current())
    } else {
      video.currentTime = seconds
    }
  }, [standbyEl])

  const standbyFailed = useCallback(() => {
    const s = standby.current
    if (s.kind !== 'idle') {
      standbyFailedKey.current = `${s.address}|${s.target.clip}|${s.target.ms}`
    }
    const run = leadRun.current
    if (run !== null && !run.swapped) {
      stopChain(run)
      leadRun.current = null
    }
    standby.current = standbyStep(standby.current, 'error')
    const wait = standbyWait.current
    if (wait !== null) {
      standbyWait.current = null
      playhead.set(wait)
      afterSettle.current = true
      coalescer.request(videoTarget(wait, handOverOf))
    }
  }, [coalescer, handOverOf, playhead, stopChain])

  /** The roles swap: the standby is the picture, the shown slot is the standby of the clip after. */
  const swap = useCallback(
    (run: LeadRun) => {
      if (run.swapped) {
        return
      }
      run.swapped = true
      const incoming = slotRefs[run.slot].current
      const outgoing = slotRefs[run.slot === 0 ? 1 : 0].current
      if (run.watchdog !== null) {
        clearTimeout(run.watchdog)
        run.watchdog = null
      }
      if (incoming === null || outgoing === null) {
        return
      }
      incoming.removeAttribute('data-standby')
      incoming.muted = false
      outgoing.setAttribute('data-standby', '')
      outgoing.muted = true
      delete outgoing.dataset.handover
      incoming.dataset.handover = run.source
      incoming.dataset.lead = String(Math.round(leadOf(calibration)))
      incoming.dataset.preroll = String(Math.round(run.preRollMs))
      for (const listener of swapListeners.current) {
        listener()
      }
      frames.current = []
      armRef.current()
      aimSoonRef.current()
    },
    [slotRefs],
  )
  const armRef = useRef<() => void>(() => undefined)
  useEffect(() => {
    swapRef.current = swap
  }, [swap])

  /**
   * Watch the incoming slot's presented frames from its `play()`: the first one newer than the
   * pre-sought frame gives the LEAD sample, the swap waits for its first frame at or past the
   * first kept frame (and the decision's frame interval), and the first few give the signed
   * alignment error that closes the P loop.
   */
  const watchIncoming = useCallback(
    (run: LeadRun) => {
      const video = slotRefs[run.slot].current as FrameVideo | null
      if (video === null) {
        return
      }
      const clip = clipsRef.current[run.want.clip]
      const stepMs = clip === undefined ? 40 : 1000 / clip.facts.fps
      const onFrameOf = (now: number, meta: FrameMeta) => {
        run.chain = null
        if (leadRun.current !== run) {
          return
        }
        const mediaMs = meta.mediaTime * 1000
        // A frame of the running clock: the pre-sought frame, presented again at `play()`, is not one
        // (Firefox reports it at once, with `currentTime` still at the sought position).
        if (mediaMs > run.soughtMs + 1 && video.currentTime * 1000 > run.soughtMs + 2) {
          if (!run.leadSampled) {
            run.leadSampled = true
            calibration = withLeadSample(calibration, now - run.playAt)
          }
          run.samples.push({ atMs: now, mediaMs })
          if (!run.aligned && run.samples.length >= ALIGN_SAMPLES) {
            run.aligned = true
            if (run.endAt !== null) {
              const incomingClock = median(run.samples.map((sample) => sample.atMs - sample.mediaMs))
              const error = run.endAt - run.want.ms - incomingClock
              calibration = withAlignmentSample(calibration, error, run.preRollMs, run.inMs)
            }
          }
        }
        if (
          run.committed &&
          !run.swapped &&
          now >= run.swapAt &&
          mediaMs >= run.want.ms - stepMs / 2
        ) {
          swap(run)
        }
        if (!run.aligned || !run.swapped) {
          if (video.requestVideoFrameCallback !== undefined && !video.paused) {
            run.chain = video.requestVideoFrameCallback(onFrameOf)
          }
        }
      }
      if (video.requestVideoFrameCallback !== undefined) {
        run.chain = video.requestVideoFrameCallback(onFrameOf)
      }
    },
    [slotRefs, swap],
  )

  /** `play()` the standby (unmuted, invisible) and begin watching it. False when the Timeline yielded or could not. */
  const startStandby = useCallback(
    (want: Target, source: Source, endAt: number | null): boolean => {
      const video = standbyEl()
      const s = standby.current
      if (video === null || s.kind !== 'ready') {
        return false
      }
      if (resumeOrYield(false, anotherPlays(isOwn, document.querySelectorAll('video'))) === 'yield') {
        wantPlay.current = false
        setPlaying(false)
        cancelEarly()
        return false
      }
      const place = standbyPlace.current ?? { preRollMs: 0, seconds: 0 }
      const playAt = performance.now()
      const run: LeadRun = {
        slot: standbySlot(),
        soughtMs: place.seconds * 1000,
        preRollMs: place.preRollMs,
        inMs: want.ms,
        playAt,
        endAt,
        source,
        want,
        samples: [],
        leadSampled: false,
        aligned: false,
        committed: false,
        swapped: false,
        swapAt: 0,
        finishOnSeek: false,
        watchdog: null,
        chain: null,
      }
      leadRun.current = run
      standby.current = standbyStep(s, { type: 'started', playAt })
      video.muted = false
      watchIncoming(run)
      video.play().catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        cancelEarly()
        wantPlay.current = false
        setPlaying(false)
        if (error instanceof DOMException && error.name === 'NotAllowedError') {
          setNote({ tone: 'warn', title: NOT_STARTED, detail: null })
        }
      })
      return true
    },
    [cancelEarly, isOwn, standbyEl, standbySlot, watchIncoming],
  )

  /**
   * The decision: the shown slot holds its last frame, and the coalescer, the clip and the
   * playhead are the standby's now. The swap of the pictures follows on its first frame.
   */
  const handOver = useCallback(
    (want: Target, source: Source) => {
      const incoming = standbyEl()
      if (incoming === null || windowOpen(leadRun.current)) {
        return
      }
      standbyWait.current = null
      clearTimers()
      if (standby.current.kind === 'ready') {
        const endAt = source === 'timer' ? timers.current.endAt : null
        if (!startStandby(want, source, endAt)) {
          return
        }
      }
      const run = leadRun.current
      if (run === null || standby.current.kind !== 'started') {
        return
      }
      const now = performance.now()
      const clip = clipsRef.current[want.clip]
      const stepMs = clip === undefined ? 40 : 1000 / clip.facts.fps
      pauseOwn(shownSlot.current)
      disarm()
      run.committed = true
      run.source = source
      run.swapAt = source === 'timer' ? now + stepMs : now
      run.watchdog = window.setTimeout(() => {
        if (leadRun.current === run && !run.swapped) {
          swap(run)
        }
      }, SWAP_WATCHDOG_MS)
      shownSlot.current = run.slot
      loadedClip.current = want.clip
      loadedAddress.current = addressOf(want.clip)
      standby.current = IDLE
      standbyPlace.current = null
      swapping.current = false
      playhead.set(want)
      coalescer.sync(want)
      frames.current = []
    },
    [addressOf, clearTimers, coalescer, disarm, pauseOwn, playhead, standbyEl, startStandby, swap],
  )

  /** The boundary holds on the last frame until the standby has landed (`wait`). */
  const holdForStandby = useCallback(
    (want: Target) => {
      clearTimers()
      disarm()
      pauseOwn(shownSlot.current)
      standbyWait.current = want
    },
    [clearTimers, disarm, pauseOwn],
  )
  useEffect(() => {
    standbyLandedRef.current = () => standbyLanded((want) => handOver(want, 'seeked'))
  }, [handOver, standbyLanded])

  /** The load or seek in flight finished: on to the latest target, or start playing. */
  const settle = useCallback(() => {
    coalescer.settled()
    const run = leadRun.current
    if (run !== null && run.committed && !run.swapped && run.finishOnSeek) {
      stopChain(run)
      swap(run)
    }
    if (handOverWait.current) {
      handOverRef.current()
    }
    if (!coalescer.busy() && afterSettle.current) {
      afterSettle.current = false
      startVideo()
    }
    aimStandby()
  }, [aimStandby, coalescer, startVideo, stopChain, swap])
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
      coalescer.request(videoTarget(pos, handOverOf))
      if (!coalescer.busy() && afterSettle.current) {
        afterSettle.current = false
        startVideo()
      }
    },
    [coalescer, handOverOf, startVideo],
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
    cancelEarly()
    shownEl()?.pause()
  }, [cancelEarly, disarm, pauseCard, shownEl])
  useEffect(() => {
    stopRef.current = () => {
      if (clock.running() || handOverWait.current || standbyWait.current !== null) {
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
    moveVideo({ clip: anchor, ms: handOverMs(handOverOf(anchor)) })
  }, [clock, moveVideo, playhead, handOverOf])

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
    cancelEarly()
    const video = shownEl()
    pauseOwn(shownSlot.current)
    disarm()
    // The Timeline's own start pauses every other player, as a start of its video does.
    pauseOthers(video, document.querySelectorAll('video'), isOwn)
    handOverWait.current = false
    if (cardLoop.current !== null) {
      cancelAnimationFrame(cardLoop.current)
    }
    clock.start(performance.now(), card.ms, card.lengthMs)
    cardLoop.current = requestAnimationFrame(tickCard)
  }, [cancelEarly, clock, disarm, isOwn, pauseOwn, playhead, shownEl, tickCard])

  /** Put the playhead in a card, load its clip behind it, and run the clock if the operator is playing. */
  const enterCard = useCallback(
    (pos: Position) => {
      pauseCard()
      cancelEarly()
      playhead.set(pos)
      afterSettle.current = false
      moveVideo(pos)
      if (wantPlay.current && !suspended.current) {
        runCard()
      }
    },
    [cancelEarly, moveVideo, pauseCard, playhead, runCard],
  )

  const advance = useCallback(
    (source: 'timer' | 'frame' | 'ended') => {
      if (windowOpen(leadRun.current)) {
        return // the decision was made: the swap is on its way
      }
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
      const want: Target = { clip: next.clip, ms: next.ms }
      if (!heldRef.current && !coalescer.busy()) {
        const verdict = atBoundary(standby.current, want, addressOf(next.clip))
        if (verdict === 'hand-over') {
          handOver(want, source)
          return
        }
        if (verdict === 'wait') {
          holdForStandby(want)
          return
        }
      }
      if (source === 'timer') {
        return // the standby is not on the next clip: the backstops load it, as before
      }
      playhead.set(next)
      afterSettle.current = true
      moveVideo(next)
    },
    [addressOf, coalescer, enterCard, handOver, holdForStandby, moveVideo, playhead, stopPlaying],
  )

  /** Whether a timer of the early start may act now on the clip it was set for. */
  const timerValid = useCallback(
    (clip: number) => {
      const video = shownEl()
      const c = clipsRef.current[clip]
      if (
        video === null ||
        c === undefined ||
        heldRef.current ||
        !wantPlay.current ||
        suspended.current ||
        swapping.current ||
        coalescer.busy() ||
        video.paused ||
        loadedClip.current !== clip ||
        windowOpen(leadRun.current)
      ) {
        return false
      }
      const left = keptEndOf(c.spans, c.facts.durationMs) - video.currentTime * 1000
      return left < NEAR_END_MS + leadOf(calibration)
    },
    [coalescer, shownEl],
  )

  /** Set the two timers of the early start from the shown slot's frame clock (each presented frame sets them again). */
  const scheduleEarly = useCallback(
    (clip: number) => {
      clearTimers()
      const c = clipsRef.current[clip]
      const target = standbyTarget(playable(clipsRef.current), mapRef.current.gaps, clip)
      const s = standby.current
      if (c === undefined || target === null || s.kind === 'idle') {
        return
      }
      const now = performance.now()
      const fclock = frameClock(frames.current, now)
      if (fclock === null || frames.current.length < 2) {
        return
      }
      const times = earlyTimes(
        fclock,
        keptEndOf(c.spans, c.facts.durationMs),
        leadOf(calibration),
        1000 / c.facts.fps,
        now,
      )
      if (times.decideAt - now > 3000) {
        return
      }
      timers.current.endAt = fclock + keptEndOf(c.spans, c.facts.durationMs)
      if (s.kind === 'ready') {
        timers.current.start = window.setTimeout(() => {
          timers.current.start = null
          const st = standby.current
          const next = standbyTarget(playable(clipsRef.current), mapRef.current.gaps, clip)
          if (
            next !== null &&
            timerValid(clip) &&
            atBoundary(st, next, addressOf(next.clip)) === 'hand-over' &&
            st.kind === 'ready'
          ) {
            startStandby(next, 'timer', timers.current.endAt)
          }
        }, times.startAt - now)
      }
      timers.current.decide = window.setTimeout(() => {
        timers.current.decide = null
        if (timerValid(clip)) {
          advance('timer')
        }
      }, times.decideAt - now)
    },
    [addressOf, advance, clearTimers, startStandby, timerValid],
  )

  // Each presented frame while playing: move the playhead, skip a cut, or end the clip.
  const arm = useCallback(() => {
    const video = shownEl() as FrameVideo | null
    if (video === null) {
      return
    }
    disarm()
    const frame = (now: number, meta: FrameMeta) => {
      loop.current = null
      if (shownEl() !== video || !wantPlay.current || video.paused) {
        return
      }
      if (windowOpen(leadRun.current)) {
        // The pre-roll of the incoming slot is not the playhead's clip: keep waiting for the swap.
        arm()
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
          clearTimers()
          advance('frame')
          return
        }
        const at = next.kind === 'seek' ? next.ms : ms
        if (next.kind === 'seek') {
          // A jump over a cut: the frame clock restarts, and a started standby goes back.
          clearTimers()
          frames.current = []
          cancelLead()
          video.currentTime = seekSeconds(next.ms, c.facts.fps)
        } else {
          frames.current = [...frames.current.filter((f) => now - f.atMs <= 1000), { atMs: now, mediaMs: ms }]
        }
        playhead.set({ clip, ms: Math.min(at, c.facts.durationMs) })
        coalescer.sync({ clip, ms: at })
        aimSoon()
        if (next.kind !== 'seek') {
          scheduleEarly(clip)
        }
      }
      arm()
    }
    loop.current =
      video.requestVideoFrameCallback !== undefined
        ? video.requestVideoFrameCallback(frame)
        : requestAnimationFrame((t) => frame(t, { mediaTime: video.currentTime }))
  }, [advance, aimSoon, cancelLead, clearTimers, coalescer, disarm, playhead, scheduleEarly, shownEl])
  useEffect(() => {
    armRef.current = arm
  }, [arm])

  const diagnose = useCallback(() => {
    const video = shownEl()
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
  }, [eventId, shownEl])

  const makeHandlers = useCallback(
    (slot: Slot): SlotHandlers => {
      const isShown = () => shownSlot.current === slot
      const landed = () => standbyLandedRef.current()
      return {
        onLoadedMetadata() {
          if (!isShown()) {
            standbyLoaded()
            return
          }
          swapping.current = false
          setNote(null)
          settle()
        },
        onLoadedData() {
          if (!isShown()) {
            landed()
          }
        },
        onCanPlay() {
          if (!isShown()) {
            landed()
          }
        },
        onSeeked() {
          if (isShown()) {
            settle()
          } else {
            landed()
          }
        },
        onError() {
          if (slotRefs[slot].current?.getAttribute('src') == null) {
            return
          }
          if (!isShown()) {
            standbyFailed()
            return
          }
          swapping.current = false
          coalescer.failed()
          stopPlaying()
          diagnose()
        },
        onPlay() {
          ownPause.current[slot] = false // a pause that raised no event leaves nothing behind
        },
        onPlaying() {
          // While the swap is pending the incoming frames are pre-roll: the swap arms the loop itself.
          if (isShown() && !windowOpen(leadRun.current)) {
            arm()
          }
        },
        onPause() {
          if (!isShown()) {
            // The standby's pause never reaches the operator's state. One that nobody made
            // while it ran its lead (another player took the page) cancels the lead.
            const own = ownPause.current[slot]
            ownPause.current[slot] = false
            if (!own && standby.current.kind === 'started') {
              cancelLead()
            }
            return
          }
          const video = slotRefs[slot].current
          // The hook's own pause (a scrub), the end of a clip and a swap pause it too; none is the
          // operator's pause. The event is queued, so it can arrive after a quick scrub has ended.
          if (ownPause.current[slot]) {
            ownPause.current[slot] = false
            return
          }
          if (video === null || video.ended || swapping.current || suspended.current) {
            return
          }
          if (wantPlay.current) {
            wantPlay.current = false
            afterSettle.current = false
            setPlaying(false)
            cancelEarly()
          }
        },
        onEnded() {
          if (isShown() && wantPlay.current && !swapping.current) {
            advance('ended')
          }
        },
      }
    },
    [advance, arm, cancelEarly, cancelLead, coalescer, diagnose, settle, slotRefs, standbyFailed, standbyLoaded, stopPlaying],
  )
  const slotHandlers = useMemo(
    () => [makeHandlers(0), makeHandlers(1)] as const,
    [makeHandlers],
  )

  const seekTo = useCallback(
    (pos: Position) => {
      cancelEarly()
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
    [cancelEarly, enterCard, moveVideo, pauseCard, playhead],
  )

  const scrubStart = useCallback(() => {
    if (wantPlay.current && !suspended.current) {
      suspended.current = true
      afterSettle.current = false
      pauseCard()
      cancelEarly()
      disarm()
      pauseOwn(shownSlot.current)
    }
  }, [cancelEarly, disarm, pauseCard, pauseOwn])

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

  // A new audio device has another start-up latency: LEAD and P are learned again.
  useEffect(() => {
    const devices = typeof navigator === 'undefined' ? undefined : navigator.mediaDevices
    if (devices === undefined) {
      return undefined
    }
    const reset = () => {
      calibration = resetCalibration()
    }
    devices.addEventListener('devicechange', reset)
    return () => devices.removeEventListener('devicechange', reset)
  }, [])

  // A turn changed in the draft (or read anew): each slot shows it at once, with no request.
  useEffect(() => {
    applyTurnTo(0, slotClips.current[0])
    applyTurnTo(1, slotClips.current[1])
  }, [turns, clips, applyTurnTo])

  // The clips as the page last read them: a proxy made again has a new address.
  useEffect(() => {
    clipsRef.current = clips
    const loaded = loadedClip.current
    if (loaded !== null && loaded < clips.length && addressOf(loaded) !== loadedAddress.current) {
      coalescer.reset()
    }
    // A reorder or an edit may have changed the clip after the shown one: the standby follows.
    aimStandby()
  }, [clips, addressOf, aimStandby, coalescer])

  // Another video took the page: nothing plays here until the Timeline has its video again.
  useEffect(() => {
    if (held) {
      stopPlaying()
    }
  }, [held, stopPlaying])

  // Open on the playhead's clip, and let go of both slots and their decoders on close (or when
  // another video holds the page: then there is no element, and nothing to load).
  useEffect(() => {
    if (held) {
      return undefined
    }
    const slots = [videoRef.current, standbyRef.current]
    moveVideo(playhead.get())
    return () => {
      diagnosis.current?.abort()
      disarm()
      clearTimers()
      pauseCard()
      const run = leadRun.current
      if (run !== null) {
        stopChain(run)
      }
      leadRun.current = null
      ownPause.current = [false, false]
      for (const video of slots) {
        release(video)
      }
      // Nothing is loaded any more: a remount (or a second effect run) loads again, in slot A.
      shownSlot.current = 0
      standby.current = IDLE
      standbyPlace.current = null
      standbyWait.current = null
      slotClips.current = [null, null]
      swapping.current = false
      loadedClip.current = null
      loadedAddress.current = null
      coalescer.failed()
    }
  }, [clearTimers, coalescer, disarm, held, moveVideo, pauseCard, playhead, release, stopChain])

  // Play was pressed while a clip preview held the video: it goes on once the video is the Timeline's.
  useEffect(() => {
    if (!held && playWhenFree.current) {
      playWhenFree.current = false
      play()
    }
  }, [held, play])

  const onSwap = useCallback((listener: () => void) => {
    swapListeners.current.add(listener)
    return () => {
      swapListeners.current.delete(listener)
    }
  }, [])

  return {
    videoRef,
    standbyRef,
    shown: shownEl,
    onSwap,
    playing,
    note,
    seekTo,
    scrubStart,
    scrubEnd,
    toggle,
    slotHandlers,
  }
}
