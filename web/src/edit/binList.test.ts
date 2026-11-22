import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Clip, EventDetail } from '../api/event.ts'
import type { ReelDocument } from '../api/reel.ts'
import {
  addCut,
  deleteChapter,
  draftChapters,
  editableChapters,
  ignoreClip,
  includeClip,
  keptOriginal,
  moveClip,
  moveClipTo,
  movedSet,
  ordersOf,
  readCuts,
  removeClip,
} from './draft.ts'
import type { Baseline, Draft } from './draft.ts'
import { binOrder, binRows, ignoredCaption, removedCaption } from './binList.ts'
import type { BinRow } from './binList.ts'

type Spec = { id: string; status?: Clip['status']; duration?: number | null; excluded?: boolean }
type ChapterSpec = { name: string; clips: (string | Spec)[] }

function clipOf(spec: string | Spec): Clip {
  const s = typeof spec === 'string' ? { id: spec } : spec
  return {
    identity: s.id,
    status: s.status ?? 'active',
    duration: s.duration === undefined ? 10 : s.duration,
    excluded: s.excluded ?? false,
  } as Clip
}

/** An event as the page reads it: chapters of clips, `ignore` listing the ignored ones. */
function setup(
  chapters: ChapterSpec[],
  ignore: string[] = [],
): { detail: EventDetail; baseline: Baseline; draft: Draft } {
  const detail = {
    event_id: '2024/event',
    chapters: chapters.map((chapter) => ({
      name: chapter.name,
      clips: chapter.clips.map((spec) => {
        const clip = clipOf(spec)
        return ignore.includes(clip.identity) ? { ...clip, status: 'ignored' as const } : clip
      }),
    })),
  } as unknown as EventDetail
  const editable = editableChapters(detail)
  const read = {
    metadata: {},
    look: {},
    chapters: chapters.map((chapter) => ({
      name: chapter.name,
      clips: chapter.clips.map((spec) => clipOf(spec).identity),
    })),
    clips: {},
    ignore,
  } as unknown as ReelDocument
  const baseline: Baseline = {
    read,
    chapters: draftChapters(editable),
    original: ordersOf(editable),
    cuts: readCuts(read),
  }
  const draft: Draft = {
    chapters: baseline.chapters,
    orders: baseline.original,
    removed: new Map(),
    metadata: { title: '', date: '', location: '', description: '' },
    cuts: new Map(),
    rotations: new Map(),
    cards: new Map(),
  }
  return { detail, baseline, draft }
}

const NO_TYPED: ReadonlySet<string> = new Set()

function rowsOf(
  fixture: { detail: EventDetail; baseline: Baseline },
  draft: Draft,
  typed: ReadonlySet<string> = NO_TYPED,
  lastMoved: string | null = null,
): BinRow[] {
  return binRows(draft, fixture.baseline, fixture.detail, typed, lastMoved)
}

function row(rows: readonly BinRow[], identity: string): BinRow {
  const found = rows.find((candidate) => candidate.identity === identity)
  assert.ok(found, `no row for ${identity}`)
  return found
}

/** Tjörn: the event's own chapter holds one clip and one ignored root clip; Kvällen holds three. */
function tjorn() {
  return setup(
    [
      { name: '', clips: ['s1710001.mp4', 's1710004.mp4'] },
      {
        name: 'Kvällen',
        clips: [
          'Kvällen/s1710002.mp4',
          'Kvällen/s1710003.mp4',
          { id: 'Kvällen/s1710004.mp4', status: 'new' },
        ],
      },
    ],
    ['s1710004.mp4'],
  )
}

/** Sommarlov: the event's own chapter lists a clip that is missing from disk, last. */
function sommarlov() {
  return setup([
    {
      name: '',
      clips: ['a.mp4', 'b.mp4', { id: 'borttagen.mp4', status: 'missing', duration: null }],
    },
  ])
}

describe('the order and the groups', () => {
  it('lists Tjörn in play order, then the ignored clip, with places and statuses', () => {
    const fixture = tjorn()
    const rows = rowsOf(fixture, fixture.draft)
    assert.deepEqual(
      rows.map((r) => [r.identity, r.name, r.group, r.place, r.status]),
      [
        ['s1710001.mp4', 's1710001.mp4', 'listed', 'Main · 1 of 1', 'Included'],
        ['Kvällen/s1710002.mp4', 's1710002.mp4', 'listed', 'Kvällen · 1 of 3', 'Included'],
        ['Kvällen/s1710003.mp4', 's1710003.mp4', 'listed', 'Kvällen · 2 of 3', 'Included'],
        ['Kvällen/s1710004.mp4', 's1710004.mp4', 'listed', 'Kvällen · 3 of 3', 'New'],
        ['s1710004.mp4', 's1710004.mp4', 'ignored', null, 'Ignored'],
      ],
    )
    assert.deepEqual(binOrder(rows), [
      's1710001.mp4',
      'Kvällen/s1710002.mp4',
      'Kvällen/s1710003.mp4',
      'Kvällen/s1710004.mp4',
      's1710004.mp4',
    ])
    assert.ok(rows.every((r) => r.moved === null && r.onDisk && !r.typed))
  })

  it('heads the event\'s own chapter "Clips" when no chapter is named', () => {
    const fixture = sommarlov()
    const rows = rowsOf(fixture, fixture.draft)
    assert.deepEqual(
      rows.map((r) => [r.identity, r.group, r.place, r.status, r.onDisk]),
      [
        ['a.mp4', 'listed', 'Clips · 1 of 3', 'Included', true],
        ['b.mp4', 'listed', 'Clips · 2 of 3', 'Included', true],
        ['borttagen.mp4', 'listed', 'Clips · 3 of 3', 'Missing', false],
      ],
    )
  })

  it('keeps a missing clip in its place, then moves it to the removed group after a removal', () => {
    const { detail, baseline, draft } = sommarlov()
    const orders = removeClip(draft.orders, 'r0', 'borttagen.mp4')
    assert.ok(orders)
    const removed: Draft = { ...draft, orders, removed: new Map([['borttagen.mp4', 'r0']]) }
    const rows = binRows(removed, baseline, detail, NO_TYPED)
    assert.deepEqual(
      rows.map((r) => [r.identity, r.group, r.place, r.status, r.onDisk, r.keptMs]),
      [
        ['a.mp4', 'listed', 'Clips · 1 of 2', 'Included', true, 10000],
        ['b.mp4', 'listed', 'Clips · 2 of 2', 'Included', true, 10000],
        ['borttagen.mp4', 'removed', null, 'Missing', false, null],
      ],
    )
  })

  it('lists the ignored clips by chapter, and puts a clip ignored here in the chapter it was played in', () => {
    const fixture = tjorn()
    const ignored = ignoreClip(fixture.baseline, fixture.draft, 'r1', 'Kvällen/s1710002.mp4')
    const rows = rowsOf(fixture, ignored)
    assert.deepEqual(
      rows.map((r) => [r.identity, r.group]),
      [
        ['s1710001.mp4', 'listed'],
        ['Kvällen/s1710003.mp4', 'listed'],
        ['Kvällen/s1710004.mp4', 'listed'],
        ['s1710004.mp4', 'ignored'],
        ['Kvällen/s1710002.mp4', 'ignored'],
      ],
    )
    assert.equal(row(rows, 'Kvällen/s1710002.mp4').status, 'Ignored')
    // The two left in Kvällen close ranks.
    assert.equal(row(rows, 'Kvällen/s1710003.mp4').place, 'Kvällen · 1 of 2')
  })

  it('still lists a read-ignored clip whose chapter is deleted here', () => {
    // Kvällen plays nothing but its ignored clip, so it can be deleted.
    const fixture = setup(
      [
        { name: '', clips: ['a.mp4'] },
        { name: 'Kvällen', clips: ['Kvällen/ig.mp4'] },
      ],
      ['Kvällen/ig.mp4'],
    )
    const kvallen = fixture.draft.chapters.find((chapter) => chapter.name === 'Kvällen')
    assert.ok(kvallen)
    const deleted = deleteChapter(fixture.draft, kvallen.key)
    assert.ok(deleted.chapters.some((chapter) => chapter.deleted))
    const rows = rowsOf(fixture, deleted)
    assert.deepEqual(
      rows.map((r) => [r.identity, r.group, r.status]),
      [
        ['a.mp4', 'listed', 'Included'],
        ['Kvällen/ig.mp4', 'ignored', 'Ignored'],
      ],
    )
  })

  it('shows an ignored clip included here as played, at the end of its chapter, and not as moved', () => {
    const fixture = tjorn()
    const included = includeClip(fixture.baseline, fixture.draft, 'r1', 's1710004.mp4', 3)
    const rows = rowsOf(fixture, included)
    const back = row(rows, 's1710004.mp4')
    assert.equal(back.group, 'listed')
    assert.equal(back.status, 'Included')
    assert.equal(back.place, 'Kvällen · 4 of 4')
    assert.equal(back.moved, null)
    assert.ok(rows.every((r) => r.group === 'listed'))
    // The top bar counts the same: nothing moved.
    assert.ok(rows.every((r) => r.moved === null))
  })

  it('says Excluded for an excluded clip and counts no cuts out of it', () => {
    const fixture = setup([{ name: '', clips: [{ id: 'x.mp4', excluded: true, duration: 8 }, 'y.mp4'] }])
    const cut = addCut(fixture.baseline, fixture.draft, 'x.mp4', { in: 1, out: 3 }, 'a1')
    const rows = rowsOf(fixture, cut)
    assert.equal(row(rows, 'x.mp4').status, 'Excluded')
    assert.equal(row(rows, 'x.mp4').keptMs, 8000)
  })

  it('has the caption words of the ignored and the removed groups', () => {
    assert.equal(ignoredCaption(1), 'Ignored · 1 clip, not played')
    assert.equal(ignoredCaption(3), 'Ignored · 3 clips, not played')
    assert.equal(removedCaption(1), 'Removed from reel.yaml when you save · 1 clip')
    assert.equal(removedCaption(2), 'Removed from reel.yaml when you save · 2 clips')
  })
})

describe('a draft that lists a clip the read does not hold', () => {
  it('throws, naming the clip, rather than leave its row out of the "N of M" places', () => {
    const fixture = setup([{ name: '', clips: ['a.mp4', 'b.mp4'] }])
    const draft = { ...fixture.draft, orders: new Map([['r0', ['a.mp4', 'b.mp4', 'ghost.mp4']]]) }
    assert.throws(() => rowsOf(fixture, draft), /ghost\.mp4/)
  })
})

describe('moved', () => {
  const four = () => setup([{ name: '', clips: ['s1', 's2', 's3', 's4'] }])

  it('says "was 4" on the one clip moved within its chapter, and on no other', () => {
    const fixture = four()
    const draft = { ...fixture.draft, orders: new Map([['r0', moveClip(['s1', 's2', 's3', 's4'], 3, 0)]]) }
    const rows = rowsOf(fixture, draft, NO_TYPED, 's4')
    assert.deepEqual(binOrder(rows), ['s4', 's1', 's2', 's3'])
    assert.equal(row(rows, 's4').moved, 'was 4')
    assert.equal(row(rows, 's4').place, 'Clips · 1 of 4')
    assert.deepEqual(rows.filter((r) => r.moved !== null).map((r) => r.identity), ['s4'])
  })

  it('counts one clip moved from 1 to 5, not five', () => {
    const ids = ['a', 'b', 'c', 'd', 'e']
    const fixture = setup([{ name: '', clips: ids }])
    const draft = { ...fixture.draft, orders: new Map([['r0', moveClip(ids, 0, 4)]]) }
    const rows = rowsOf(fixture, draft, NO_TYPED, 'a')
    assert.deepEqual(rows.filter((r) => r.moved !== null).map((r) => [r.identity, r.moved]), [['a', 'was 1']])
  })

  it('says only "moved" for a moved clip that is back at its old position', () => {
    // d e c a b: c sits at its old index 3, but no run of two keeps it, so it is counted as moved
    // (whichever of d,e / a,b the ties keep), and its row must not say "was 3".
    const ids = ['a', 'b', 'c', 'd', 'e']
    const fixture = setup([{ name: '', clips: ids }])
    const next = ['d', 'e', 'c', 'a', 'b']
    const draft = { ...fixture.draft, orders: new Map([['r0', next]]) }
    const counted = movedSet(keptOriginal(ids, next), next, null)
    assert.ok(counted.has('c'))
    assert.equal(ids.indexOf('c'), next.indexOf('c'))
    const rows = rowsOf(fixture, draft)
    assert.equal(row(rows, 'c').moved, 'moved')
    assert.deepEqual(new Set(rows.filter((r) => r.moved !== null).map((r) => r.identity)), counted)
    // Every other counted clip is elsewhere than it was, and says where it was.
    for (const r of rows.filter((r) => r.moved !== null && r.identity !== 'c')) {
      assert.equal(r.moved, `was ${ids.indexOf(r.identity) + 1}`)
    }
  })

  it('says "from Main" on a clip moved in from another chapter, and "was" on none', () => {
    const fixture = tjorn()
    const draft = moveClipTo(fixture.draft, 'r0', 'r1', 's1710001.mp4', 1)
    const rows = rowsOf(fixture, draft, NO_TYPED, 's1710001.mp4')
    assert.equal(row(rows, 's1710001.mp4').moved, 'from Main')
    assert.equal(row(rows, 's1710001.mp4').place, 'Kvällen · 2 of 4')
    // The chapter it left, and the clips it landed among, are not moved.
    assert.deepEqual(rows.filter((r) => r.moved !== null).map((r) => r.identity), ['s1710001.mp4'])
  })

  it('names the chapter a clip came from as the chapters are headed now', () => {
    const fixture = tjorn()
    const draft = moveClipTo(fixture.draft, 'r1', 'r0', 'Kvällen/s1710002.mp4', 0)
    const rows = rowsOf(fixture, draft, NO_TYPED, 'Kvällen/s1710002.mp4')
    assert.equal(row(rows, 'Kvällen/s1710002.mp4').moved, 'from Kvällen')
    assert.equal(row(rows, 'Kvällen/s1710002.mp4').place, 'Main · 1 of 2')
  })

  it('is no longer moved once the clip is put back where it was', () => {
    const fixture = tjorn()
    const away = moveClipTo(fixture.draft, 'r0', 'r1', 's1710001.mp4', 0)
    const back = moveClipTo(away, 'r1', 'r0', 's1710001.mp4', 0)
    const rows = rowsOf(fixture, back, NO_TYPED, 's1710001.mp4')
    assert.ok(rows.every((r) => r.moved === null))
  })

  it('agrees with the top bar: the clips it counts as moved within chapters are the rows that say so', () => {
    const ids = Array.from({ length: 12 }, (_, n) => `c${n}`)
    const fixture = setup([{ name: '', clips: ids }])
    const next = moveClip(moveClip(ids, 2, 9), 10, 1)
    const draft = { ...fixture.draft, orders: new Map([['r0', next]]) }
    const bar = movedSet(keptOriginal(ids, next), next, 'c2')
    const rows = rowsOf(fixture, draft, NO_TYPED, 'c2')
    assert.ok(bar.size > 0)
    assert.deepEqual(new Set(rows.filter((r) => r.moved !== null).map((r) => r.identity)), bar)
  })
})

describe('names of clips from another folder', () => {
  it('names a chapter\'s clips by file while all lie in its own folder', () => {
    const fixture = tjorn()
    const rows = rowsOf(fixture, fixture.draft)
    assert.equal(row(rows, 'Kvällen/s1710002.mp4').name, 's1710002.mp4')
    assert.equal(row(rows, 's1710001.mp4').name, 's1710001.mp4')
  })

  it('names them all by their paths once a clip of another folder is in the chapter', () => {
    const fixture = tjorn()
    const draft = moveClipTo(fixture.draft, 'r0', 'r1', 's1710001.mp4', 0)
    const rows = rowsOf(fixture, draft)
    assert.equal(row(rows, 's1710001.mp4').name, 's1710001.mp4')
    assert.equal(row(rows, 'Kvällen/s1710002.mp4').name, 'Kvällen/s1710002.mp4')
    assert.equal(row(rows, 'Kvällen/s1710004.mp4').name, 'Kvällen/s1710004.mp4')
  })

  it('keeps the file names of the chapter a clip left, and names the one that arrived by its path', () => {
    const fixture = tjorn()
    const draft = moveClipTo(fixture.draft, 'r1', 'r0', 'Kvällen/s1710002.mp4', 0)
    const rows = rowsOf(fixture, draft)
    // Main now lists a clip of another folder: its rows are named by path.
    assert.equal(row(rows, 'Kvällen/s1710002.mp4').name, 'Kvällen/s1710002.mp4')
    assert.equal(row(rows, 's1710001.mp4').name, 's1710001.mp4')
    // Kvällen's clips all lie in its own folder, the one that left included: file names.
    assert.equal(row(rows, 'Kvällen/s1710003.mp4').name, 's1710003.mp4')
  })
})

describe('the typed flag', () => {
  it('is set on the clips whose Cuts panel holds a typed cut, and only on them', () => {
    const fixture = tjorn()
    const rows = rowsOf(fixture, fixture.draft, new Set(['Kvällen/s1710003.mp4', 's1710004.mp4']))
    assert.deepEqual(rows.filter((r) => r.typed).map((r) => r.identity), [
      'Kvällen/s1710003.mp4',
      's1710004.mp4',
    ])
  })

  it('does not depend on the cuts the draft holds', () => {
    const fixture = tjorn()
    const cut = addCut(fixture.baseline, fixture.draft, 'Kvällen/s1710002.mp4', { in: 1, out: 2 }, 'a1')
    assert.ok(rowsOf(fixture, cut).every((r) => !r.typed))
  })
})

describe('the kept length', () => {
  it('is the duration less the live cuts, once, and null for a length not known', () => {
    const fixture = setup([
      {
        name: '',
        clips: [{ id: 'a.mp4', duration: 10 }, { id: 'b.mp4', duration: null }, { id: 'c.mp4', duration: 0 }],
      },
    ])
    let draft = addCut(fixture.baseline, fixture.draft, 'a.mp4', { in: 1, out: 3 }, 'a1')
    draft = addCut(fixture.baseline, draft, 'a.mp4', { in: 2, out: 4 }, 'a2')
    const rows = rowsOf(fixture, draft)
    // 1–3 and 2–4 overlap: 3 s are cut out, not 4.
    assert.equal(row(rows, 'a.mp4').keptMs, 7000)
    assert.equal(row(rows, 'b.mp4').keptMs, null)
    assert.equal(row(rows, 'c.mp4').keptMs, null)
  })
})

describe('a 400-clip event', () => {
  const big = () => {
    const first = Array.from({ length: 150 }, (_, n) => `Dag1/c${String(n).padStart(3, '0')}.mp4`)
    const second = Array.from({ length: 250 }, (_, n) => `Dag2/c${String(n).padStart(3, '0')}.mp4`)
    return setup([
      { name: 'Dag1', clips: first },
      { name: 'Dag2', clips: second },
    ])
  }

  it('lists every clip once, in play order, with a place on each', () => {
    const fixture = big()
    const started = performance.now()
    const rows = rowsOf(fixture, fixture.draft)
    const took = performance.now() - started
    assert.equal(rows.length, 400)
    assert.equal(new Set(binOrder(rows)).size, 400)
    assert.equal(rows[0].place, 'Dag1 · 1 of 150')
    assert.equal(rows[399].place, 'Dag2 · 250 of 250')
    assert.ok(rows.every((r) => r.moved === null && r.group === 'listed'))
    assert.ok(took < 1000, `took ${took} ms`)
  })

  it('says "was 150" on the one clip moved from the end of a long chapter to its start', () => {
    const fixture = big()
    const first = fixture.draft.orders.get('r0') ?? []
    const orders = new Map(fixture.draft.orders)
    orders.set('r0', moveClip(first, 149, 0))
    const rows = rowsOf(fixture, { ...fixture.draft, orders }, NO_TYPED, 'Dag1/c149.mp4')
    assert.deepEqual(rows.filter((r) => r.moved !== null).map((r) => [r.identity, r.moved]), [
      ['Dag1/c149.mp4', 'was 150'],
    ])
  })
})
