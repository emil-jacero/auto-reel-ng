import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { SETTLE_MS, createZoomSettle, edgeToolShown } from './zoomSettle.ts'
import type { SettleTimer } from './zoomSettle.ts'

/** A fake clock: `advance` runs the timers that fall due, in order. */
function clock(): SettleTimer & { advance: (ms: number) => void; live: () => number } {
  let now = 0
  let next = 1
  const timers = new Map<number, { at: number; run: () => void }>()
  return {
    set(run, ms) {
      const id = next
      next += 1
      timers.set(id, { at: now + ms, run })
      return id
    },
    clear(id) {
      timers.delete(id)
    },
    advance(ms) {
      const until = now + ms
      for (;;) {
        const due = [...timers.entries()].filter(([, t]) => t.at <= until).sort((a, b) => a[1].at - b[1].at)[0]
        if (due === undefined) {
          break
        }
        timers.delete(due[0])
        now = due[1].at
        due[1].run()
      }
      now = until
    },
    live: () => timers.size,
  }
}

function setup() {
  const time = clock()
  const changes: boolean[] = []
  const settle = createZoomSettle((z) => changes.push(z), time)
  return { time, changes, settle }
}

describe('createZoomSettle', () => {
  it('is not zooming before any input', () => {
    const { settle, changes } = setup()
    assert.equal(settle.zooming(), false)
    assert.deepEqual(changes, [])
  })

  it('a burst of wheel inputs 40 ms apart is one zoom, settling SETTLE_MS after the last', () => {
    const { settle, changes, time } = setup()
    for (let i = 0; i < 5; i += 1) {
      settle.input()
      time.advance(40)
      assert.equal(settle.zooming(), true, `step ${i}`)
    }
    // The last input was 40 ms ago: still open until SETTLE_MS after it.
    time.advance(SETTLE_MS - 40 - 1)
    assert.equal(settle.zooming(), true)
    time.advance(1)
    assert.equal(settle.zooming(), false)
    // One start and one settle for the whole burst: two renders, not one per input.
    assert.deepEqual(changes, [true, false])
    assert.equal(time.live(), 0)
  })

  it('key repeat (about 33 ms apart) keeps one zoom open; a pause settles it', () => {
    const { settle, changes, time } = setup()
    for (let i = 0; i < 30; i += 1) {
      settle.input()
      time.advance(33)
    }
    assert.equal(settle.zooming(), true)
    time.advance(SETTLE_MS)
    assert.deepEqual(changes, [true, false])
    // A second press later is a second zoom.
    settle.input()
    time.advance(SETTLE_MS)
    assert.deepEqual(changes, [true, false, true, false])
  })

  it('a slider press held 2 s stays open, and settles on release at once', () => {
    const { settle, changes, time } = setup()
    settle.press()
    assert.equal(settle.zooming(), false, 'a press alone is not a zoom')
    settle.input()
    time.advance(2000)
    assert.equal(settle.zooming(), true)
    settle.input()
    time.advance(2000)
    assert.equal(settle.zooming(), true)
    settle.release()
    assert.equal(settle.zooming(), false)
    assert.deepEqual(changes, [true, false])
    assert.equal(time.live(), 0)
  })

  it('a press after a wheel zoom started holds it open until release', () => {
    const { settle, time } = setup()
    settle.input()
    settle.press()
    time.advance(SETTLE_MS * 4)
    assert.equal(settle.zooming(), true)
    settle.release()
    assert.equal(settle.zooming(), false)
  })

  it('a press and release without a zoom changes nothing', () => {
    const { settle, changes, time } = setup()
    settle.press()
    settle.release()
    time.advance(SETTLE_MS * 2)
    assert.deepEqual(changes, [])
  })

  it('a key on the slider (no press) settles on the timer like any other input', () => {
    const { settle, time } = setup()
    settle.release() // a stray release without a press does nothing
    settle.input()
    time.advance(SETTLE_MS)
    assert.equal(settle.zooming(), false)
  })

  it('cancel stops the timer and calls nothing', () => {
    const { settle, changes, time } = setup()
    settle.input()
    settle.cancel()
    assert.equal(time.live(), 0)
    time.advance(SETTLE_MS * 2)
    assert.deepEqual(changes, [true])
    assert.equal(settle.zooming(), false)
  })
})

describe('edgeToolShown', () => {
  const tool = { identity: 's1710001.mp4', side: 'end' as const }
  it('shows every tool in the window when no zoom is in progress', () => {
    assert.equal(edgeToolShown(tool, { after: false, zooming: false, kept: null }), true)
  })

  it('shows no tool behind a rippling drag', () => {
    assert.equal(edgeToolShown(tool, { after: true, zooming: false, kept: null }), false)
  })

  it('while zooming shows only the tool that held focus when the zoom started', () => {
    const kept = { identity: 's1710001.mp4', side: 'end' as const }
    assert.equal(edgeToolShown(tool, { after: false, zooming: true, kept }), true)
    assert.equal(edgeToolShown({ ...tool, side: 'start' }, { after: false, zooming: true, kept }), false)
    assert.equal(edgeToolShown({ ...tool, identity: 's1710002.mp4' }, { after: false, zooming: true, kept }), false)
    assert.equal(edgeToolShown(tool, { after: false, zooming: true, kept: null }), false)
  })
})
