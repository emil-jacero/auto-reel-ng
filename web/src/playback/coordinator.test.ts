import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  anotherPlays,
  installPagePlayback,
  keepOneVideoPlaying,
  pauseOthers,
  watchOtherStarts,
} from './coordinator.ts'
import type { VideoRoot } from './coordinator.ts'

/*
 * One video plays at a time on the event page (`coordinator.ts`), run by `npm test` with
 * stand-ins for the root and the videos: an EventTarget, no DOM.
 */

/** A video that records what was done to it: only `pause()` is ever expected. */
class FakeVideo extends EventTarget {
  paused = true
  calls: string[] = []
  pause(): void {
    this.calls.push('pause')
    this.paused = true
  }
  /** What the browser does: it plays, then the capturing listener at the root hears it. */
  start(root: FakeRoot): void {
    this.paused = false
    root.dispatch(this)
  }
}

class FakeRoot implements VideoRoot {
  readonly all: FakeVideo[] = []
  readonly heard = new Set<(event: Event) => void>()
  captures: boolean[] = []
  addEventListener(_type: 'play', listener: (event: Event) => void, capture: boolean): void {
    this.captures.push(capture)
    this.heard.add(listener)
  }
  removeEventListener(_type: 'play', listener: (event: Event) => void): void {
    this.heard.delete(listener)
  }
  videos(): Iterable<FakeVideo> {
    return this.all
  }
  isVideo(target: EventTarget | null): target is FakeVideo {
    return target instanceof FakeVideo
  }
  video(): FakeVideo {
    const video = new FakeVideo()
    this.all.push(video)
    return video
  }
  /** A `play` event aimed at `target`, as the page's capturing listener hears it. */
  dispatch(target: EventTarget): void {
    const event = new Event('play')
    // A real capture listener sees the video as `target`; an EventTarget would retarget it.
    Object.defineProperty(event, 'target', { value: target })
    for (const listener of this.heard) {
      listener(event)
    }
  }
}

const rooted = () => new FakeRoot()

describe('pauseOthers', () => {
  it('pauses the video that plays and not the ones that are paused', () => {
    const root = rooted()
    const [started, playing, idle] = [root.video(), root.video(), root.video()]
    started.paused = false
    playing.paused = false
    pauseOthers(started, root.all)
    assert.deepEqual(playing.calls, ['pause'])
    assert.deepEqual(idle.calls, [])
  })

  it('does not pause the video that started', () => {
    const root = rooted()
    const started = root.video()
    started.paused = false
    pauseOthers(started, root.all)
    assert.deepEqual(started.calls, [])
    assert.equal(started.paused, false)
  })
})

describe('keepOneVideoPlaying', () => {
  it('pauses a playing video when another starts, and nothing else is done to it', () => {
    const root = rooted()
    const stop = keepOneVideoPlaying(root)
    const [movie, clip] = [root.video(), root.video()]
    movie.start(root)
    assert.deepEqual(movie.calls, [])
    clip.start(root)
    // Only `pause()`: no load, no seek, no removal (nothing else exists on a stand-in).
    assert.deepEqual(movie.calls, ['pause'])
    assert.equal(movie.paused, true)
    assert.equal(clip.paused, false)
    assert.deepEqual(clip.calls, [])
    assert.equal(root.all.length, 2)
    stop()
  })

  it('listens in the capture phase, since play does not bubble', () => {
    const root = rooted()
    keepOneVideoPlaying(root)
    assert.deepEqual(root.captures, [true])
  })

  it('pauses nothing for a play from a target that is no video', () => {
    const root = rooted()
    keepOneVideoPlaying(root)
    const playing = root.video()
    playing.paused = false
    root.dispatch(new EventTarget())
    assert.deepEqual(playing.calls, [])
    assert.equal(playing.paused, false)
  })

  it('pauses nothing for a start that was paused again before its event was heard', () => {
    const root = rooted()
    keepOneVideoPlaying(root)
    const [playing, quick] = [root.video(), root.video()]
    playing.paused = false
    quick.paused = true // started and paused in one task: the queued play event arrives late
    root.dispatch(quick)
    assert.deepEqual(playing.calls, [])
    assert.equal(playing.paused, false)
  })

  it('stops listening once removed', () => {
    const root = rooted()
    const stop = keepOneVideoPlaying(root)
    const [first, second] = [root.video(), root.video()]
    first.start(root)
    stop()
    assert.equal(root.heard.size, 0)
    second.start(root)
    assert.deepEqual(first.calls, [])
    assert.equal(first.paused, false)
  })

  it('leaves only the latest playing after two starts in a row', () => {
    const root = rooted()
    keepOneVideoPlaying(root)
    const [a, b, c] = [root.video(), root.video(), root.video()]
    a.start(root)
    b.start(root)
    c.start(root)
    assert.deepEqual(
      root.all.map((video) => video.paused),
      [true, true, false],
    )
  })
})

describe('the rule is pair-agnostic', () => {
  it('a start pauses whichever other video plays, and only pauses it', () => {
    const root = rooted()
    keepOneVideoPlaying(root)
    const [a, b, bystander] = [root.video(), root.video(), root.video()]
    a.start(root)
    b.start(root)
    assert.deepEqual(a.calls, ['pause'])
    assert.equal(b.paused, false)
    assert.deepEqual(b.calls, [])
    assert.deepEqual(bystander.calls, [])
  })

  it('a player started while two others play pauses both, once each', () => {
    const root = rooted()
    keepOneVideoPlaying(root)
    const [a, b, c] = [root.video(), root.video(), root.video()]
    // Two playing at once (the page was open before the listener): both are paused.
    a.paused = false
    b.paused = false
    c.start(root)
    assert.deepEqual(a.calls, ['pause'])
    assert.deepEqual(b.calls, ['pause'])
    assert.deepEqual(c.calls, [])
  })
})

describe('anotherPlays', () => {
  it('is false for a lone playing self', () => {
    const root = rooted()
    const self = root.video()
    self.paused = false
    assert.equal(anotherPlays(self, root.all), false)
  })

  it('is true with one other playing', () => {
    const root = rooted()
    const [self, other] = [root.video(), root.video()]
    other.paused = false
    assert.equal(anotherPlays(self, root.all), true)
  })

  it('is false when the others are paused', () => {
    const root = rooted()
    const [self, other] = [root.video(), root.video()]
    self.paused = false
    assert.equal(other.paused, true)
    assert.equal(anotherPlays(self, root.all), false)
  })
})

describe('watchOtherStarts', () => {
  it('fires for a video other than self, not for self or a non-video', () => {
    const root = rooted()
    const [self, other] = [root.video(), root.video()]
    let heard = 0
    const stop = watchOtherStarts(root, () => self, () => (heard += 1))
    self.start(root)
    assert.equal(heard, 0)
    root.dispatch(new EventTarget())
    assert.equal(heard, 0)
    other.start(root)
    assert.equal(heard, 1)
    stop()
    other.start(root)
    assert.equal(heard, 1)
  })
})

describe('installPagePlayback', () => {
  it('adds a capturing play listener to the document, and removes it', () => {
    const added: Array<[string, boolean]> = []
    const removed: string[] = []
    const doc = {
      addEventListener: (type: string, _l: unknown, capture?: unknown) =>
        added.push([type, capture === true]),
      removeEventListener: (type: string) => removed.push(type),
      querySelectorAll: () => [],
    }
    const stop = installPagePlayback(doc as never)
    assert.deepEqual(added, [['play', true]])
    stop()
    assert.deepEqual(removed, ['play'])
  })
})
