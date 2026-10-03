import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

import { formatTime } from '../cuts/times'
import { chapterHeading } from '../events/labels'
import { Icon } from '../ui/Icon'
import { currentChapterIndex, jumpLabel } from './chapters'
import type { ChapterMark } from './chapters'
import { CHAPTERS_AS_RENDERED, CHAPTERS_HEADING, CURRENT_CHAPTER } from './labels'

/**
 * The movie's chapters as a jump list under its player (D-15, `movie-chapter-list`).
 *
 * The chapters come from the event detail and nothing else; the list belongs to the
 * player it is rendered under (that player's `key` is the file version), so a new
 * file brings a new list with its marks reset. A button moves the player to the
 * chapter's start and plays, also before the first Play. The mark follows the
 * player's position through its own events (`timeupdate`, `seeked`), however it moved,
 * and is never announced: it moves while the movie plays. No shortcut of the page's own.
 */
export function ChapterList({
  chapters,
  videoRef,
  asRendered,
}: {
  chapters: readonly ChapterMark[]
  videoRef: RefObject<HTMLVideoElement | null>
  /** The movie is outdated: these are the chapters it was rendered with. */
  asRendered: boolean
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const [current, setCurrent] = useState<number | null>(() => currentChapterIndex(chapters, 0))
  // The one-shot seek waiting for a movie with no metadata yet; a newer jump replaces it.
  const pendingSeek = useRef<(() => void) | null>(null)

  // The mark is a pure function of the player's position, read at its own events.
  useEffect(() => {
    const video = videoRef.current
    if (video === null) {
      return undefined
    }
    const follow = () => setCurrent(currentChapterIndex(chapters, video.currentTime))
    follow()
    const events = ['timeupdate', 'seeked', 'loadedmetadata', 'emptied'] as const
    for (const name of events) {
      video.addEventListener(name, follow)
    }
    return () => {
      for (const name of events) {
        video.removeEventListener(name, follow)
      }
    }
  }, [chapters, videoRef])

  // Leaving (a new player, a re-read without chapters): a jump still waiting for metadata is dropped.
  useEffect(
    () => () => {
      pendingSeek.current?.()
      pendingSeek.current = null
    },
    [],
  )

  // A re-read that leaves the player without this list while focus is in it: focus is
  // never dropped to <body>. (When the whole section goes, its own cleanup has moved
  // focus to the page's heading first, and this finds focus outside the list.)
  useLayoutEffect(() => {
    const root = rootRef.current
    return () => {
      if (root?.contains(document.activeElement) === true) {
        videoRef.current?.focus()
      }
    }
  }, [videoRef])

  const jump = (start: number) => {
    const video = videoRef.current
    if (video === null) {
      return
    }
    pendingSeek.current?.()
    pendingSeek.current = null
    if (video.readyState >= 1) {
      video.currentTime = start
    } else {
      // `preload="none"`: no metadata yet, so the position cannot be set. Play loads
      // the movie, and the first `loadedmetadata` takes the one seek.
      const seek = () => {
        video.currentTime = start
        pendingSeek.current = null
      }
      video.addEventListener('loadedmetadata', seek, { once: true })
      pendingSeek.current = () => video.removeEventListener('loadedmetadata', seek)
    }
    // A newer jump or a source change aborts a play(); any other refusal is raised
    // as the player's `error` event, which the section already diagnoses.
    video.play().catch(() => undefined)
  }

  const hasNamedChapter = chapters.some((chapter) => chapter.name !== '')
  return (
    <div className="movie-chapters" ref={rootRef}>
      <div className="movie-chapters-head">
        <h3>{CHAPTERS_HEADING}</h3>
        {asRendered && <span className="movie-chapters-note">{CHAPTERS_AS_RENDERED}</span>}
      </div>
      <ol>
        {chapters.map((chapter, index) => {
          const title = chapterHeading(chapter.name, hasNamedChapter)
          const marked = index === current
          return (
            // Starts strictly increase, so a start is a stable key.
            <li key={chapter.start} data-current={marked || undefined}>
              <button
                type="button"
                aria-label={jumpLabel(index, title, chapter.start, marked ? CURRENT_CHAPTER : undefined)}
                aria-current={marked ? 'true' : undefined}
                onClick={() => jump(chapter.start)}
              >
                <span className="chapter-number">{index + 1}</span>
                <span className="chapter-main">
                  <span className="chapter-name">{title}</span>
                  {marked && (
                    <span className="chapter-mark">
                      <Icon name="play" />
                      {CURRENT_CHAPTER}
                    </span>
                  )}
                </span>
                <span className="chapter-start">{formatTime(chapter.start)}</span>
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
