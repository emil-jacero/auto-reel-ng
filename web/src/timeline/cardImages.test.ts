import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { QUIET_MS, TRIES, createCardImages, imageKey, waitSeconds } from './cardImages.ts'
import type { CardJob, Drawn, ImagesIo } from './cardImages.ts'

/*
 * The card images' queue (`cardImages.ts`), run by `npm test` with stand-ins for the request, the
 * timer and the URL functions: one request at a time, in play order, 503 waited out, a failure
 * said once, only an edited card fetched again, every URL revoked.
 */

type Req = { chapter: string; text: string }

function rig(answer: (request: Req, call: number) => Drawn | Promise<Drawn> = () => ({ kind: 'image', png: new Blob(['x']) })) {
  const log = {
    calls: [] as Req[],
    inFlight: 0,
    maxInFlight: 0,
    made: [] as string[],
    revoked: [] as string[],
    timers: [] as { run: () => void; ms: number; live: boolean }[],
  }
  const io: ImagesIo<Req> = {
    async draw(request) {
      log.calls.push(request)
      log.inFlight += 1
      log.maxInFlight = Math.max(log.maxInFlight, log.inFlight)
      await Promise.resolve()
      const result = await answer(request, log.calls.length)
      log.inFlight -= 1
      return result
    },
    setTimer(run, ms) {
      const timer = { run, ms, live: true }
      log.timers.push(timer)
      return timer
    },
    clearTimer(handle) {
      ;(handle as { live: boolean }).live = false
    },
    makeUrl() {
      const url = `blob:${log.made.length}`
      log.made.push(url)
      return url
    },
    revokeUrl(url) {
      log.revoked.push(url)
    },
  }
  return { log, io, images: createCardImages(io) }
}

const job = (chapter: string, text = chapter): CardJob<Req> => ({ chapter, request: { chapter, text } })
const settle = async () => {
  for (let i = 0; i < 20; i += 1) {
    await Promise.resolve()
  }
}
/** Fire the oldest live timer. */
const fire = async (log: ReturnType<typeof rig>['log']) => {
  const timer = log.timers.find((t) => t.live)
  assert.ok(timer, 'a timer is waiting')
  timer.live = false
  timer.run()
  await settle()
}

describe('waiting out a 503', () => {
  it('reads Retry-After from 1 to 30 s, 2 s when it was not said', () => {
    assert.equal(waitSeconds(null), 2)
    assert.equal(waitSeconds(0), 1)
    assert.equal(waitSeconds(5), 5)
    assert.equal(waitSeconds(600), 30)
  })

  it('keys a card by its body and style', () => {
    assert.equal(imageKey({ a: 1 }), imageKey({ a: 1 }))
    assert.notEqual(imageKey({ a: 1 }), imageKey({ a: 2 }))
  })
})

describe('the card images', () => {
  it('asks for one at a time, in play order', async () => {
    const { log, images } = rig()
    images.sync(['', 'Dag 2', 'Dag 3', 'Dag 4', 'Dag 5', 'Dag 6'].map((c) => job(c)))
    await settle()
    assert.deepEqual(log.calls.map((c) => c.chapter), ['', 'Dag 2', 'Dag 3', 'Dag 4', 'Dag 5', 'Dag 6'])
    assert.equal(log.maxInFlight, 1)
    assert.equal(images.get('Dag 6')?.state, 'ready')
  })

  it('waits out a 503 for its Retry-After and holds the others behind it', async () => {
    const { log, images } = rig((_request, call) =>
      call === 1 ? { kind: 'busy', retryAfter: 2 } : { kind: 'image', png: new Blob(['x']) },
    )
    images.sync([job(''), job('Dag 2')])
    await settle()
    assert.equal(log.calls.length, 1)
    assert.equal(images.get('')?.state, 'pending')
    assert.equal(log.timers[0].ms, 2000)
    await fire(log)
    assert.deepEqual(log.calls.map((c) => c.chapter), ['', '', 'Dag 2'])
    assert.equal(images.get('')?.state, 'ready')
    assert.equal(log.maxInFlight, 1)
  })

  it('ends in a stated failure after the third 503', async () => {
    const { log, images } = rig(() => ({ kind: 'busy', retryAfter: 1 }))
    images.sync([job('')])
    await settle()
    assert.equal(TRIES, 3)
    await fire(log)
    await fire(log)
    assert.equal(log.calls.length, 3)
    const state = images.get('')
    assert.equal(state?.state, 'failed')
    assert.equal(images.failures().length, 1)
    assert.equal(log.timers.filter((t) => t.live).length, 0)
  })

  it('does not retry a 502, and says it once', async () => {
    const { log, images } = rig(() => ({ kind: 'failed', message: 'font missing' }))
    images.sync([job('Dag 2')])
    await settle()
    images.sync([job('Dag 2')])
    await settle()
    assert.equal(log.calls.length, 1)
    assert.deepEqual(images.failures(), [{ chapter: 'Dag 2', message: 'font missing' }])
  })

  it('fetches only the edited card, after the quiet time, and keeps the old image meanwhile', async () => {
    const { log, images } = rig()
    images.sync([job('a'), job('b'), job('c')])
    await settle()
    assert.equal(log.calls.length, 3)
    const before = images.get('b')
    images.sync([job('a'), job('b', 'edited'), job('c')])
    assert.equal(log.calls.length, 3)
    assert.equal(images.get('b')?.url, before?.url)
    assert.equal(log.timers.at(-1)?.ms, QUIET_MS)
    await fire(log)
    assert.equal(log.calls.length, 4)
    assert.deepEqual(log.calls[3], { chapter: 'b', text: 'edited' })
    // The old one is revoked when the new one arrives.
    assert.deepEqual(log.revoked, [before?.url])
    assert.notEqual(images.get('b')?.url, before?.url)
  })

  it('takes only the last of several quick edits', async () => {
    const { log, images } = rig()
    images.sync([job('a')])
    await settle()
    images.sync([job('a', '1')])
    images.sync([job('a', '12')])
    images.sync([job('a', '123')])
    assert.equal(log.timers.filter((t) => t.live).length, 1)
    await fire(log)
    assert.equal(log.calls.length, 2)
    assert.equal(log.calls[1].text, '123')
  })

  it('drops the answer to a request an edit has superseded', async () => {
    const hold: { release: (() => void) | null } = { release: null }
    const { log, images } = rig((request, call) =>
      call === 1
        ? new Promise<Drawn>((resolve) => {
            hold.release = () => resolve({ kind: 'image', png: new Blob([request.text]) })
          })
        : { kind: 'image', png: new Blob(['new']) },
    )
    images.sync([job('a')])
    await settle()
    images.sync([job('a', 'edited')])
    hold.release?.()
    await settle()
    assert.equal(images.get('a')?.state, 'pending')
    await fire(log)
    assert.equal(images.get('a')?.state, 'ready')
    assert.deepEqual(log.revoked, [])
  })

  it('revokes every URL when closed and asks for nothing more', async () => {
    const { log, images } = rig()
    images.sync([job('a'), job('b')])
    await settle()
    images.dispose()
    assert.deepEqual([...log.revoked].sort(), [...log.made].sort())
    images.sync([job('c')])
    await settle()
    assert.equal(log.calls.length, 2)
  })

  it('lets go of a card that is no longer listed', async () => {
    const { log, images } = rig()
    images.sync([job('a'), job('b')])
    await settle()
    images.sync([job('a')])
    assert.equal(images.get('b'), null)
    assert.equal(log.revoked.length, 1)
  })
})
