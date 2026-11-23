import { useEffect, useState } from 'react'

/*
 * "Use as poster" takes the frame the Timeline's shown `<video>` shows (D-20, event-poster-gui).
 * The stage holds two slots (seamless-playback D1) and their roles swap at a clip hand-over, so
 * the readers here take `shown()` (the slot showing the playhead's frame now) and, to follow
 * it, `onSwap` (D6); they never keep an element across a swap. The frame is
 * copied into a canvas and kept as an object URL for the poster area. The page and the proxy
 * share an origin, so the canvas is never tainted; if reading it throws, nothing changes and
 * the button says so. The picture is the proxy's, upright by its display rotation: the
 * editorial turn is laid over it by CSS as for every picture (`rotate/`). It is a preview
 * only: the saved poster is the engine's frame from the original.
 */

/** The widest snapshot, in pixels: the cover is shown at most this wide. */
const SNAPSHOT_WIDTH = 640

/** Whether `video` holds a decoded frame at its time: data for the current position, not seeking. */
export function hasFrame(video: HTMLVideoElement | null): boolean {
  return (
    video !== null && video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0 && !video.seeking
  )
}

const WATCHED = ['loadstart', 'loadeddata', 'canplay', 'seeking', 'seeked', 'emptied', 'waiting'] as const

/**
 * Whether the shown slot has a decoded frame now; re-read when it loads, seeks or empties, and
 * listened to again on the slot that is shown after each swap.
 */
export function useFrameReady(
  shown: () => HTMLVideoElement | null,
  onSwap: (listener: () => void) => () => void,
  held: boolean,
): boolean {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let video: HTMLVideoElement | null = null
    const read = () => setReady(hasFrame(video))
    const detach = () => {
      if (video !== null) {
        for (const name of WATCHED) {
          video.removeEventListener(name, read)
        }
      }
    }
    const attach = () => {
      detach()
      video = shown()
      if (video !== null) {
        for (const name of WATCHED) {
          video.addEventListener(name, read)
        }
      }
      read()
    }
    attach()
    const unsubscribe = onSwap(attach)
    return () => {
      unsubscribe()
      detach()
    }
  }, [shown, onSwap, held])
  return ready
}

/** The video's current frame as a JPEG object URL (the caller revokes it). Rejects when it cannot. */
export async function snapshotOf(video: HTMLVideoElement): Promise<string> {
  if (!hasFrame(video)) {
    throw new Error('the video has no decoded frame')
  }
  const scale = Math.min(1, SNAPSHOT_WIDTH / video.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
  const context = canvas.getContext('2d')
  if (context === null) {
    throw new Error('no canvas')
  }
  context.drawImage(video, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
  if (blob === null) {
    throw new Error('the frame could not be encoded')
  }
  return URL.createObjectURL(blob)
}
