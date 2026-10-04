import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

/*
 * "Use as poster" takes the frame the Timeline's one `<video>` shows (D-20, event-poster-gui):
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

/** Whether the Timeline's video has a decoded frame now; re-read when it loads, seeks or empties. */
export function useFrameReady(videoRef: RefObject<HTMLVideoElement | null>, held: boolean): boolean {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const video = videoRef.current
    if (video === null) {
      setReady(false)
      return undefined
    }
    const read = () => setReady(hasFrame(video))
    read()
    for (const name of WATCHED) {
      video.addEventListener(name, read)
    }
    return () => {
      for (const name of WATCHED) {
        video.removeEventListener(name, read)
      }
    }
  }, [videoRef, held])
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
