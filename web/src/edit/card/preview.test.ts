import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { DEBOUNCE_MS, PreviewController } from './preview.ts'
import type { PreviewAnswer, PreviewDeps, PreviewView } from './preview.ts'
import type { PreviewRequest } from './model.ts'

/* A controller on fake time and a fake service: each draw waits until the test answers it. */
function rig() {
  let now = 0
  let next = 0
  const timers = new Map<number, { at: number; run: () => void }>()
  const draws: {
    request: PreviewRequest
    signal: AbortSignal
    answer: (a: PreviewAnswer) => void
  }[] = []
  const revoked: string[] = []
  let urls = 0
  const deps: PreviewDeps = {
    draw: (request, signal) =>
      new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new Error('aborted')))
        draws.push({ request, signal, answer: resolve })
      }),
    setTimer: (run, ms) => {
      next += 1
      timers.set(next, { at: now + ms, run })
      return next
    },
    clearTimer: (handle) => {
      timers.delete(handle as number)
    },
    makeUrl: () => `blob:${(urls += 1)}`,
    revokeUrl: (url) => {
      revoked.push(url)
    },
  }
  const controller = new PreviewController(deps)
  const advance = async (ms: number) => {
    now += ms
    for (const [id, timer] of [...timers]) {
      if (timer.at <= now) {
        timers.delete(id)
        timer.run()
      }
    }
    await Promise.resolve()
    await Promise.resolve()
  }
  const settle = async () => {
    for (let i = 0; i < 5; i += 1) {
      await Promise.resolve()
    }
  }
  return { controller, draws, revoked, advance, settle, timers }
}

const req = (title: string): PreviewRequest => ({ chapter: 'A', card: { title } })
const png = new Blob(['x'])
const view = (c: PreviewController): PreviewView => c.snapshot()

describe('PreviewController', () => {
  it('coalesces edits faster than the quiet time into one request with the last one', async () => {
    const { controller, draws, advance } = rig()
    for (const text of ['a', 'ab', 'abc']) {
      controller.show(req(text))
      await advance(DEBOUNCE_MS - 50)
    }
    assert.equal(draws.length, 0)
    await advance(60)
    assert.equal(draws.length, 1)
    assert.deepEqual(draws[0].request, req('abc'))
  })

  it('cancels the superseded request and drops its answer', async () => {
    const { controller, draws, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    controller.show(req('two'))
    assert.equal(draws[0].signal.aborted, true)
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'image', png })
    await settle()
    assert.equal(view(controller).url, null)
    draws[1].answer({ kind: 'image', png })
    await settle()
    assert.equal(view(controller).url, 'blob:1')
    assert.equal(view(controller).state, 'ready')
  })

  it('keeps the previous image on show while the next loads, and revokes it after', async () => {
    const { controller, draws, revoked, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'image', png })
    await settle()
    controller.show(req('two'))
    assert.equal(view(controller).state, 'updating')
    assert.equal(view(controller).url, 'blob:1')
    await advance(DEBOUNCE_MS)
    assert.equal(view(controller).url, 'blob:1')
    assert.deepEqual(revoked, [])
    draws[1].answer({ kind: 'image', png })
    await settle()
    assert.equal(view(controller).url, 'blob:2')
    assert.deepEqual(revoked, ['blob:1'])
  })

  it('keeps the previous image through a refusal and names the field', async () => {
    const { controller, draws, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'image', png })
    await settle()
    controller.show(req('two'))
    await advance(DEBOUNCE_MS)
    draws[1].answer({ kind: 'refused', detail: 'card.title_font_size must be positive' })
    await settle()
    const v = view(controller)
    assert.equal(v.state, 'error')
    assert.equal(v.url, 'blob:1')
    assert.equal(v.field, 'title_font_size')
    assert.match(v.message ?? '', /title_font_size/)
  })

  it('retries a busy answer once after Retry-After, then says so', async () => {
    const { controller, draws, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'busy', retryAfter: 2 })
    await settle()
    assert.equal(view(controller).state, 'busy')
    assert.match(view(controller).message ?? '', /busy.*2 seconds/)
    await advance(1900)
    assert.equal(draws.length, 1)
    await advance(200)
    assert.equal(draws.length, 2)
    assert.deepEqual(draws[1].request, req('one'))
    draws[1].answer({ kind: 'busy', retryAfter: 2 })
    await settle()
    assert.equal(view(controller).state, 'error')
    assert.match(view(controller).message ?? '', /still busy/)
    await advance(10_000)
    assert.equal(draws.length, 2)
  })

  it('a busy retry is dropped when an edit supersedes it', async () => {
    const { controller, draws, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'busy', retryAfter: 2 })
    await settle()
    controller.show(req('two'))
    await advance(DEBOUNCE_MS)
    assert.equal(draws.length, 2)
    await advance(5000)
    assert.equal(draws.length, 2)
  })

  it('says the service did not answer, and a 502 in its cause', async () => {
    const { controller, draws, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'unreachable' })
    await settle()
    assert.equal(view(controller).message, 'The service did not answer.')
    controller.show(req('two'))
    await advance(DEBOUNCE_MS)
    draws[1].answer({ kind: 'failed', detail: 'font file missing' })
    await settle()
    assert.match(view(controller).message ?? '', /could not be drawn: font file missing/)
  })

  it('sends nothing for a draft over the bounds, and keeps the image', async () => {
    const { controller, draws, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'image', png })
    await settle()
    controller.show(null)
    await advance(DEBOUNCE_MS * 4)
    assert.equal(draws.length, 1)
    assert.equal(view(controller).state, 'skipped')
    assert.equal(view(controller).url, 'blob:1')
  })

  it('the same request again sends nothing more', async () => {
    const { controller, draws, advance } = rig()
    controller.show(req('one'))
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    controller.show(req('one'))
    assert.equal(draws.length, 1)
  })

  it('dispose aborts the request and revokes the image', async () => {
    const { controller, draws, revoked, advance, settle } = rig()
    controller.show(req('one'))
    await advance(DEBOUNCE_MS)
    draws[0].answer({ kind: 'image', png })
    await settle()
    controller.show(req('two'))
    await advance(DEBOUNCE_MS)
    controller.dispose()
    assert.equal(draws[1].signal.aborted, true)
    assert.deepEqual(revoked, ['blob:1'])
  })
})
