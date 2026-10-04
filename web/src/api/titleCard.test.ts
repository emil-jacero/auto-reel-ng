import assert from 'node:assert/strict'
import { afterEach, before, describe, it } from 'node:test'

/*
 * The preview and fonts clients (`api/titleCard.ts`, `api/fonts.ts`), run by `npm test`.
 * `fetch` is a stand-in, and `route.ts` reads `window` when it loads, so the test gives it a bare one.
 */
type TitleCard = typeof import('./titleCard.ts')
type Fonts = typeof import('./fonts.ts')
let card: TitleCard
let fonts: Fonts
const realFetch = globalThis.fetch

before(async () => {
  Object.assign(globalThis, {
    window: { location: { hash: '' }, history: { state: {}, replaceState: () => undefined } },
  })
  card = await import('./titleCard.ts')
  fonts = await import('./fonts.ts')
})

afterEach(() => {
  globalThis.fetch = realFetch
})

function answer(status: number, body: unknown, headers: Record<string, string> = {}): void {
  globalThis.fetch = (async () =>
    new Response(typeof body === 'string' ? body : JSON.stringify(body), {
      status,
      statusText: 'X',
      headers: { 'Content-Type': 'application/json', ...headers },
    })) as typeof fetch
}

const problem = (status: number, detail: string) => ({ title: 'T', status, detail })
const draw = () =>
  card.previewCard('2025/e', { chapter: 'A', card: { title: 'x' } }, new AbortController().signal)

describe('previewCard', () => {
  it('posts the draft as JSON to the event, encoded per segment, uncached', async () => {
    let seen: { url: unknown; init: RequestInit | undefined } | null = null
    globalThis.fetch = (async (url: unknown, init?: RequestInit) => {
      seen = { url, init }
      return new Response(new Blob(['png']), { status: 200, headers: { 'Content-Type': 'image/png' } })
    }) as typeof fetch
    const result = await draw()
    assert.equal(result.kind, 'image')
    assert.equal(seen!.url, '/api/v1/events/2025/e/title-card/preview')
    assert.equal(seen!.init?.method, 'POST')
    assert.equal(seen!.init?.cache, 'no-store')
    assert.deepEqual(JSON.parse(String(seen!.init?.body)), { chapter: 'A', card: { title: 'x' } })
  })

  it('maps each status by its cause', async () => {
    answer(400, problem(400, 'card.position must be one of x'))
    assert.deepEqual(await draw(), { kind: 'refused', problem: problem(400, 'card.position must be one of x') })
    answer(404, problem(404, 'no event'))
    assert.equal((await draw()).kind, 'gone')
    answer(502, problem(502, 'font'))
    assert.equal((await draw()).kind, 'failed')
    answer(500, 'boom')
    const other = await draw()
    assert.equal(other.kind, 'unpublished')
  })

  it('reads the 422 bound as its first message with the field', async () => {
    answer(422, { detail: [{ loc: ['body', 'card', 'title'], msg: 'String should have at most 200 characters' }] })
    assert.deepEqual(await draw(), {
      kind: 'bound',
      message: 'card.title: String should have at most 200 characters',
    })
  })

  it('reads Retry-After of a 503, null when it says none', async () => {
    answer(503, problem(503, 'busy'), { 'Retry-After': '2' })
    assert.deepEqual(await draw(), { kind: 'busy', retryAfter: 2, problem: problem(503, 'busy') })
    answer(503, problem(503, 'busy'))
    assert.equal(((await draw()) as { retryAfter: unknown }).retryAfter, null)
  })

  it('a 200 that is not a PNG is unpublished', async () => {
    answer(200, '{}')
    assert.equal((await draw()).kind, 'unpublished')
  })

  it('no answer is unreachable, an abort is thrown', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('network')
    }) as typeof fetch
    assert.equal((await draw()).kind, 'unreachable')
    const controller = new AbortController()
    globalThis.fetch = (async () => {
      controller.abort()
      throw new DOMException('aborted', 'AbortError')
    }) as typeof fetch
    await assert.rejects(card.previewCard('e', { chapter: '' }, controller.signal), /aborted/)
  })
})

describe('fetchFonts', () => {
  const font = { family: 'DejaVu Sans', display_name: 'DejaVu Sans', weights: [400], default: true }

  it('reads the list as given', async () => {
    answer(200, [font])
    const result = await fonts.fetchFonts(new AbortController().signal)
    assert.deepEqual(result, { kind: 'ok', fonts: [font] })
  })

  it('a body that is not a list of fonts is unpublished', async () => {
    answer(200, [{ family: 1 }])
    assert.equal((await fonts.fetchFonts(new AbortController().signal)).kind, 'unpublished')
    answer(500, 'x')
    assert.equal((await fonts.fetchFonts(new AbortController().signal)).kind, 'unpublished')
  })

  it('no answer is unreachable', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('network')
    }) as typeof fetch
    assert.equal((await fonts.fetchFonts(new AbortController().signal)).kind, 'unreachable')
  })
})
