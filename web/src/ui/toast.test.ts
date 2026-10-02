import assert from 'node:assert/strict'
import { afterEach, before, describe, it, mock } from 'node:test'

/*
 * The toast store's rules, run by `npm test` under Node's built-in runner (no
 * DOM: the store only needs `window.setTimeout`, which is `globalThis` here).
 */
type Store = typeof import('./toast.ts')
let store: Store

before(async () => {
  Object.assign(globalThis, { window: globalThis })
  store = await import('./toast.ts')
})

afterEach(() => {
  for (const held of store.getToasts()) {
    store.dismissToast(held.id)
  }
  store.pauseToasts(false)
  mock.timers.reset()
})

function shown(): string[] {
  return store.getToasts().map((held) => `${held.tone}:${held.message}`)
}

describe('a full stack', () => {
  it('keeps three errors when an info arrives', () => {
    store.toast.error('e1')
    store.toast.error('e2')
    store.toast.error('e3')
    const before = store.getToasts()
    store.toast.info('i4')
    assert.deepEqual(shown(), ['error:e1', 'error:e2', 'error:e3'])
    assert.equal(store.getToasts(), before, 'nothing was emitted')
  })

  it('keeps three errors when a success arrives', () => {
    store.toast.error('e1')
    store.toast.error('e2')
    store.toast.error('e3')
    store.toast.success('s4')
    assert.deepEqual(shown(), ['error:e1', 'error:e2', 'error:e3'])
  })

  it('lets a fourth error drop the oldest error', () => {
    store.toast.error('e1')
    store.toast.error('e2')
    store.toast.error('e3')
    store.toast.error('e4')
    assert.deepEqual(shown(), ['error:e2', 'error:e3', 'error:e4'])
  })

  it('drops the oldest non-error before touching an error', () => {
    store.toast.error('e1')
    store.toast.error('e2')
    store.toast.success('s3')
    store.toast.info('i4')
    assert.deepEqual(shown(), ['error:e1', 'error:e2', 'info:i4'])
  })

  it('clears the clock of the toast it dropped', () => {
    mock.timers.enable({ apis: ['setTimeout', 'Date'] })
    store.toast.success('s1')
    store.toast.error('e2')
    store.toast.error('e3')
    store.toast.info('i4')
    assert.deepEqual(shown(), ['error:e2', 'error:e3', 'info:i4'])
    mock.timers.tick(5000)
    assert.deepEqual(shown(), ['error:e2', 'error:e3'])
  })

  it('does not consume an id for a toast it refuses', () => {
    store.toast.error('e1')
    store.toast.error('e2')
    store.toast.error('e3')
    const last = store.getToasts()[2].id
    store.toast.info('i4')
    store.dismissToast(store.getToasts()[0].id)
    store.toast.error('e5')
    assert.equal(store.getToasts()[2].id, last + 1)
  })
})

describe('clocks under a modal dialog', () => {
  it('waits while a modal dialog is open and continues with the time left', () => {
    mock.timers.enable({ apis: ['setTimeout', 'Date'] })
    store.toast.success('s1')
    mock.timers.tick(2000)
    const release = store.enterModal()
    mock.timers.tick(10000)
    assert.deepEqual(shown(), ['success:s1'])
    release()
    mock.timers.tick(2999)
    assert.deepEqual(shown(), ['success:s1'])
    mock.timers.tick(1)
    assert.deepEqual(shown(), [])
  })

  it('gives a toast raised under a dialog its full time after the dialog closes', () => {
    mock.timers.enable({ apis: ['setTimeout', 'Date'] })
    const release = store.enterModal()
    store.toast.info('i1')
    mock.timers.tick(20000)
    assert.deepEqual(shown(), ['info:i1'])
    release()
    mock.timers.tick(4999)
    assert.deepEqual(shown(), ['info:i1'])
    mock.timers.tick(1)
    assert.deepEqual(shown(), [])
  })

  it('stays paused until every open dialog has closed', () => {
    mock.timers.enable({ apis: ['setTimeout', 'Date'] })
    store.toast.success('s1')
    const first = store.enterModal()
    const second = store.enterModal()
    first()
    first()
    mock.timers.tick(10000)
    assert.deepEqual(shown(), ['success:s1'], 'a double release does not release the other')
    second()
    mock.timers.tick(5000)
    assert.deepEqual(shown(), [])
  })

  it('resumes only when the hover pause and the dialog have both ended', () => {
    mock.timers.enable({ apis: ['setTimeout', 'Date'] })
    store.toast.success('s1')
    store.pauseToasts(true)
    const release = store.enterModal()
    store.pauseToasts(false)
    mock.timers.tick(10000)
    assert.deepEqual(shown(), ['success:s1'])
    release()
    mock.timers.tick(5000)
    assert.deepEqual(shown(), [])
  })

  it('never gives an error a clock', () => {
    mock.timers.enable({ apis: ['setTimeout', 'Date'] })
    store.toast.error('e1')
    const release = store.enterModal()
    release()
    mock.timers.tick(60000)
    assert.deepEqual(shown(), ['error:e1'])
  })

  it('tells listeners when a dialog opens', () => {
    const seen: string[] = []
    const stop = store.onModalOpened(() => seen.push('opened'))
    const release = store.enterModal()
    release()
    stop()
    store.enterModal()()
    assert.deepEqual(seen, ['opened'])
  })
})
