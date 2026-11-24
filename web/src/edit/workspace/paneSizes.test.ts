import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  commitPanes,
  defaultSizes,
  dragAction,
  edgeDistance,
  effectiveSizes,
  isPaneKey,
  keyAction,
  limits,
  MIN_BIN_PX,
  MIN_INSP_PX,
  middleMin,
  paneHidden,
  paneProperties,
  parsePanes,
  sameFrame,
  serializePanes,
  valueText,
} from './paneSizes.ts'
import type { Drawn, Frame, Limits, Mods, PaneId, PanePrefs } from './paneSizes.ts'

const frame = (width: number, height: number, rem = 16, top = 48): Frame => ({
  width,
  height,
  rem,
  top,
})
const prefs = (sizes: PanePrefs['sizes'] = {}, hidden: PaneId[] = []): PanePrefs => ({ sizes, hidden })
const none: Mods = { shift: false, ctrl: false, alt: false, meta: false, repeat: false }
const drawnOf = (bin: number, insp: number, tl: number): Drawn => ({ bin, insp, tl })

test('defaultSizes follows today s rules', () => {
  assert.equal(defaultSizes(frame(960, 720)).bin, 240)
  assert.equal(defaultSizes(frame(1280, 720)).bin, 282)
  assert.equal(defaultSizes(frame(1440, 900)).bin, 317)
  assert.equal(defaultSizes(frame(1600, 900)).bin, 320)
  assert.equal(defaultSizes(frame(1280, 720)).insp, 340)
  assert.equal(defaultSizes(frame(1280, 720)).tl, 280)
  assert.equal(defaultSizes(frame(1440, 900)).tl, 342)
})

test('middleMin is 20rem with the bin and 14rem without', () => {
  assert.equal(middleMin(true, frame(1280, 720)), 320)
  assert.equal(middleMin(false, frame(1280, 720)), 224)
  assert.equal(middleMin(true, frame(1280, 720, 24)), 480)
  assert.equal(middleMin(false, frame(1280, 720, 24)), 336)
})

test('limits at 1280x720', () => {
  const f = frame(1280, 720)
  const d = drawnOf(282, 340, 280)
  assert.deepEqual(limits('bin', d, f), { min: 240, max: 1280 - 340 - 320 })
  assert.deepEqual(limits('insp', d, f), { min: 320, max: 1280 - 282 - 320 })
  assert.deepEqual(limits('tl', d, f), { min: 200, max: 352 })
  assert.deepEqual(limits('tl', drawnOf(0, 340, 280), f), { min: 200, max: 448 })
})

test('the bin s max falls with a wider inspector and rises when it is hidden', () => {
  const f = frame(1280, 720)
  const narrow = limits('bin', drawnOf(282, 300, 280), f).max
  const wide = limits('bin', drawnOf(282, 500, 280), f).max
  assert.equal(narrow - wide, 200)
  assert.equal(limits('bin', drawnOf(282, 0, 280), f).max - limits('bin', drawnOf(282, 340, 280), f).max, 340)
})

test('max never falls below min', () => {
  for (const f of [frame(960, 500), frame(960, 900, 24), frame(960, 220)]) {
    for (const pane of ['bin', 'insp', 'tl'] as const) {
      const l = limits(pane, drawnOf(240, 300, 200), f)
      assert.ok(l.max >= l.min, `${pane} in ${JSON.stringify(f)}`)
    }
  }
})

test('effectiveSizes: empty prefs give the defaults', () => {
  for (const f of [frame(1280, 720), frame(1440, 900)]) {
    assert.deepEqual(effectiveSizes(prefs(), f), defaultSizes(f))
  }
})

test('effectiveSizes keeps a preference inside the limits', () => {
  assert.deepEqual(effectiveSizes(prefs({ bin: 417 }), frame(1440, 900)), {
    bin: 417,
    insp: 340,
    tl: 342,
  })
})

test('effectiveSizes shrinks both side panes by the same share of their excess', () => {
  const f = frame(1100, 900)
  const d = effectiveSizes(prefs({ bin: 600, insp: 500 }), f)
  assert.equal(d.bin, 386)
  assert.equal(d.insp, 393)
  assert.ok(d.bin + d.insp <= 1100 - 320)
  // the same preferences at 1440 come back unchanged
  const wide = effectiveSizes(prefs({ bin: 600, insp: 500 }), frame(1440, 900))
  assert.equal(wide.bin, 600)
  assert.equal(wide.insp, 500)
})

test('effectiveSizes: fractions never overshoot the room', () => {
  for (let width = 1000; width < 1200; width += 7) {
    const d = effectiveSizes(prefs({ bin: 613, insp: 577 }), frame(width, 900))
    assert.ok(d.bin + d.insp <= width - 320, `${width}`)
  }
})

test('effectiveSizes: no room for the minimums sits at the minimums', () => {
  const f = frame(960, 900, 24)
  const d = effectiveSizes(prefs({ bin: 500, insp: 500 }), f)
  assert.equal(d.bin, 240)
  assert.equal(d.insp, 320)
  const exact = effectiveSizes(prefs({ bin: 240, insp: 320 }), frame(960, 900))
  assert.equal(exact.bin, 240)
  assert.equal(exact.insp, 320)
  assert.ok(Object.values(d).every((v) => !Number.isNaN(v)))
})

test('effectiveSizes: a stored size under the minimum is drawn at the minimum', () => {
  const d = effectiveSizes(prefs({ bin: 100, insp: 100, tl: 50 }), frame(1440, 900))
  assert.equal(d.bin, 240)
  assert.equal(d.insp, 320)
  assert.equal(d.tl, 200)
})

test('effectiveSizes clamps the Timeline to the middle row s least height', () => {
  const f = frame(1280, 720)
  assert.equal(effectiveSizes(prefs({ tl: 600 }), f).tl, 720 - 48 - 320)
  assert.equal(effectiveSizes(prefs({ tl: 600 }, ['bin']), f).tl, 720 - 48 - 224)
})

test('effectiveSizes: short windows', () => {
  assert.equal(effectiveSizes(prefs(), frame(960, 600)).tl, 232)
  const tight = effectiveSizes(prefs(), frame(960, 500))
  assert.equal(tight.tl, 200)
  assert.ok(tight.bin > 0 && tight.insp > 0)
  assert.equal(effectiveSizes(prefs(), frame(960, 220)).tl, 172)
  assert.equal(effectiveSizes(prefs({ tl: 340 }), frame(1280, 600)).tl, 232)
  assert.equal(effectiveSizes(prefs({ tl: 340 }, ['bin']), frame(1280, 600)).tl, 328)
})

test('effectiveSizes: hidden panes are 0 and a hidden side pane gives the room to the other', () => {
  const f = frame(1280, 720)
  const d = effectiveSizes(prefs({ bin: 400, insp: 400 }, ['bin', 'tl']), f)
  assert.equal(d.bin, 0)
  assert.equal(d.tl, 0)
  assert.equal(d.insp, 400)
  const wide = effectiveSizes(prefs({ insp: 2000 }, ['bin']), f)
  assert.equal(wide.insp, 1280 - 320)
  assert.deepEqual(effectiveSizes(prefs({}, ['bin', 'insp', 'tl']), f), { bin: 0, insp: 0, tl: 0 })
})

const grid: Frame[] = []
for (const width of [960, 1100, 1280, 1440, 1920]) {
  for (const height of [400, 500, 600, 720, 900, 1200]) {
    for (const rem of [16, 24]) {
      grid.push(frame(width, height, rem))
    }
  }
}
const variants: PanePrefs[] = [
  prefs(),
  prefs({ bin: 900 }),
  prefs({ insp: 900 }),
  prefs({ bin: 900, insp: 900, tl: 900 }),
  prefs({ bin: 500, insp: 500 }, ['bin']),
  prefs({ bin: 500, insp: 500 }, ['insp']),
  prefs({ tl: 900 }, ['tl']),
]

test('the invariant: every shown pane is within its limits', () => {
  for (const f of grid) {
    for (const p of variants) {
      const d = effectiveSizes(p, f)
      for (const pane of ['bin', 'insp', 'tl'] as const) {
        if (d[pane] === 0) {
          assert.ok(p.hidden.includes(pane) || (pane === 'tl' && f.height - f.top <= 0))
          continue
        }
        const l = limits(pane, d, f)
        const upper = l.max
        const lower = pane === 'tl' ? Math.min(l.min, f.height - f.top) : l.min
        assert.ok(
          d[pane] >= lower && d[pane] <= upper,
          `${pane} ${d[pane]} in ${JSON.stringify(l)} for ${JSON.stringify(f)} ${JSON.stringify(p)}`,
        )
      }
    }
  }
})

test('dragAction: direction, off-axis movement and whole px', () => {
  const lim: Limits = { min: 240, max: 700 }
  assert.deepEqual(dragAction('bin', 300, 50, 999, lim), { kind: 'size', px: 350 })
  assert.deepEqual(dragAction('insp', 340, -60, 999, { min: 320, max: 700 }), { kind: 'size', px: 400 })
  assert.deepEqual(dragAction('tl', 300, 999, -40, { min: 200, max: 600 }), { kind: 'size', px: 340 })
  assert.deepEqual(dragAction('bin', 300, 10.4, 0, lim), { kind: 'size', px: 310 })
})

test('dragAction clamps at the largest size and stops at the minimum', () => {
  const lim: Limits = { min: 240, max: 500 }
  assert.deepEqual(dragAction('bin', 300, 900, 0, lim), { kind: 'size', px: 500 })
  assert.deepEqual(dragAction('bin', 300, -100, 0, lim), { kind: 'size', px: 240 })
})

test('dragAction snaps to hide under half the minimum', () => {
  const lim: Limits = { min: 240, max: 500 }
  assert.deepEqual(dragAction('bin', 240, -121, 0, lim), { kind: 'hide' })
  assert.deepEqual(dragAction('bin', 240, -120, 0, lim), { kind: 'size', px: 240 })
  assert.deepEqual(dragAction('bin', 119, 0, 0, lim), { kind: 'hide' })
  assert.deepEqual(dragAction('bin', 120, 0, 0, lim), { kind: 'size', px: 240 })
  const tl: Limits = { min: 200, max: 500 }
  assert.deepEqual(dragAction('tl', 99, 0, 0, tl), { kind: 'hide' })
  assert.deepEqual(dragAction('tl', 100, 0, 0, tl), { kind: 'size', px: 200 })
})

test('a hidden pane follows the pointer from its press inside the window edge', () => {
  const lim: Limits = { min: 240, max: 700 }
  // Bin strip at x 0-8, press at 4, release at 300: the bin is 300 (its edge under the pointer).
  const start = edgeDistance('bin', 4, 400, 1280, 720)
  assert.equal(start, 4)
  assert.deepEqual(dragAction('bin', start, 296, 0, lim), { kind: 'size', px: 300 })
  assert.equal(edgeDistance('insp', 1276, 400, 1280, 720), 4)
  assert.equal(edgeDistance('tl', 600, 712, 1280, 720), 8)
  assert.equal(edgeDistance('bin', -3, 0, 1280, 720), 0)
  // The pane shows once the pointer is half the minimum from the edge, wherever it was pressed.
  assert.deepEqual(dragAction('bin', 12, 107, 0, lim), { kind: 'hide' })
  assert.deepEqual(dragAction('bin', 12, 108, 0, lim), { kind: 'size', px: 240 })
})

test('dragAction from hidden', () => {
  const lim: Limits = { min: 240, max: 500 }
  assert.deepEqual(dragAction('bin', 0, 119, 0, lim), { kind: 'hide' })
  assert.deepEqual(dragAction('bin', 0, 120, 0, lim), { kind: 'size', px: 240 })
  assert.deepEqual(dragAction('bin', 0, 300, 0, lim), { kind: 'size', px: 300 })
})

const binLim: Limits = { min: 240, max: 700 }

test('keyAction: steps, directions and Shift', () => {
  assert.deepEqual(keyAction('bin', 'ArrowRight', none, 300, binLim), { kind: 'size', px: 316 })
  assert.deepEqual(keyAction('bin', 'ArrowLeft', none, 300, binLim), { kind: 'size', px: 284 })
  assert.deepEqual(
    keyAction('bin', 'ArrowRight', { ...none, shift: true }, 300, binLim),
    { kind: 'size', px: 364 },
  )
  assert.deepEqual(keyAction('insp', 'ArrowLeft', none, 340, { min: 320, max: 700 }), {
    kind: 'size',
    px: 356,
  })
  assert.deepEqual(keyAction('tl', 'ArrowUp', none, 300, { min: 200, max: 700 }), {
    kind: 'size',
    px: 316,
  })
  assert.deepEqual(keyAction('tl', 'ArrowDown', none, 300, { min: 200, max: 700 }), {
    kind: 'size',
    px: 284,
  })
})

test('keyAction: shrinking stops at the minimum, then hides', () => {
  assert.deepEqual(keyAction('bin', 'ArrowLeft', none, 250, binLim), { kind: 'size', px: 240 })
  assert.deepEqual(keyAction('bin', 'ArrowLeft', none, 240, binLim), { kind: 'hide' })
  assert.equal(keyAction('bin', 'ArrowLeft', none, 0, binLim), null)
  assert.deepEqual(keyAction('bin', 'ArrowRight', none, 0, binLim), { kind: 'size', px: 240 })
})

test('keyAction: Home, End and Enter', () => {
  assert.deepEqual(keyAction('bin', 'Home', none, 400, binLim), { kind: 'size', px: 240 })
  assert.deepEqual(keyAction('bin', 'End', none, 400, binLim), { kind: 'size', px: 700 })
  assert.deepEqual(keyAction('bin', 'Home', none, 0, binLim), { kind: 'size', px: 240 })
  assert.deepEqual(keyAction('bin', 'End', none, 0, binLim), { kind: 'size', px: 700 })
  assert.deepEqual(keyAction('bin', 'Enter', none, 400, binLim), { kind: 'hide' })
  assert.deepEqual(keyAction('bin', 'Enter', none, 0, binLim), { kind: 'show' })
  assert.deepEqual(keyAction('bin', 'Enter', { ...none, shift: true }, 400, binLim), { kind: 'hide' })
  assert.deepEqual(keyAction('bin', 'Enter', { ...none, shift: true }, 0, binLim), { kind: 'show' })
})

test('keyAction: other keys are null', () => {
  assert.equal(keyAction('bin', 'ArrowUp', none, 300, binLim), null)
  assert.equal(keyAction('bin', 'ArrowDown', none, 300, binLim), null)
  assert.equal(keyAction('tl', 'ArrowLeft', none, 300, binLim), null)
  assert.equal(keyAction('bin', ' ', none, 300, binLim), null)
})

test('keyAction: Ctrl, Alt and Meta leave every key to the browser', () => {
  for (const key of ['ArrowLeft', 'ArrowRight', 'Home', 'Enter']) {
    for (const mod of ['ctrl', 'alt', 'meta'] as const) {
      assert.equal(keyAction('bin', key, { ...none, [mod]: true }, 300, binLim), null, `${mod}+${key}`)
    }
  }
})

test('keyAction: a repeat never hides or shows', () => {
  const rep = { ...none, repeat: true }
  assert.equal(keyAction('bin', 'Enter', rep, 300, binLim), null)
  assert.equal(keyAction('bin', 'Enter', rep, 0, binLim), null)
  assert.equal(keyAction('bin', 'ArrowLeft', rep, 240, binLim), null)
  assert.deepEqual(keyAction('bin', 'ArrowLeft', none, 240, binLim), { kind: 'hide' })
  assert.equal(keyAction('bin', 'ArrowRight', rep, 0, binLim), null)
  assert.deepEqual(keyAction('bin', 'ArrowLeft', rep, 300, binLim), { kind: 'size', px: 284 })
})

test('keyAction clamps to the limits', () => {
  assert.deepEqual(keyAction('bin', 'ArrowRight', none, 695, binLim), { kind: 'size', px: 700 })
  })

test('isPaneKey names the keys a separator takes', () => {
  assert.ok(isPaneKey('bin', 'ArrowLeft') && isPaneKey('bin', 'Enter') && isPaneKey('tl', 'ArrowUp'))
  assert.ok(!isPaneKey('bin', 'ArrowUp') && !isPaneKey('bin', ' '))
})

test('commitPanes: size, hide and reset', () => {
  const f = frame(1440, 900)
  const d = effectiveSizes(prefs(), f)
  const sized = commitPanes('bin', { kind: 'size', px: 417 }, prefs({}, ['bin']), { ...d, bin: 0 }, f)
  assert.deepEqual(sized, { sizes: { bin: 417 }, hidden: [] })
  const hid = commitPanes('bin', { kind: 'hide' }, prefs({ bin: 417 }), d, f)
  assert.deepEqual(hid, { sizes: { bin: 417 }, hidden: ['bin'] })
  const reset = commitPanes('tl', { kind: 'reset' }, prefs({ tl: 400 }), d, f)
  assert.deepEqual(reset, { sizes: {}, hidden: [] })
})

test('commitPanes show: a hidden pane comes back without rewriting any kept size', () => {
  const f = frame(1100, 900)
  const p = prefs({ bin: 600, insp: 500 }, ['insp'])
  const d = effectiveSizes(p, f)
  assert.equal(d.insp, 0)
  const shown = commitPanes('insp', { kind: 'show' }, p, d, f)
  assert.deepEqual(shown, { sizes: { bin: 600, insp: 500 }, hidden: [] })
  const wide = effectiveSizes(shown, frame(1440, 900))
  assert.equal(wide.bin, 600)
  assert.equal(wide.insp, 500)
  // nothing kept: nothing is invented
  assert.deepEqual(commitPanes('bin', { kind: 'show' }, prefs({}, ['bin']), d, f), {
    sizes: {},
    hidden: [],
  })
})

test('showing a hidden side pane in a window without room draws the other pane narrower, storing nothing', () => {
  const f = frame(1100, 900)
  const p = prefs({ bin: 600 }, ['insp'])
  const d = effectiveSizes(p, f)
  assert.deepEqual([d.bin, d.insp], [600, 0])
  const shown = commitPanes('insp', { kind: 'show' }, p, d, f)
  assert.deepEqual(shown, { sizes: { bin: 600 }, hidden: [] })
  const after = effectiveSizes(shown, f)
  assert.deepEqual([after.bin, after.insp], [448, 331])
  assert.ok(after.bin >= MIN_BIN_PX && after.insp >= MIN_INSP_PX)
  assert.ok(after.bin + after.insp <= f.width - 20 * f.rem)
  const wide = effectiveSizes(shown, frame(1440, 900))
  assert.deepEqual([wide.bin, wide.insp], [600, 340])
})

test('commitPanes inside the shrink stores the other pane as drawn', () => {
  const f = frame(1100, 900)
  const p = prefs({ bin: 600, insp: 500 })
  const d = effectiveSizes(p, f)
  const bin = commitPanes('bin', { kind: 'size', px: 380 }, p, d, f)
  assert.deepEqual(bin.sizes, { bin: 380, insp: 393 })
  assert.deepEqual(effectiveSizes(bin, f), { ...d, bin: 380, insp: 393 })
  const insp = commitPanes('insp', { kind: 'size', px: 380 }, p, d, f)
  const after = effectiveSizes(insp, f)
  assert.equal(after.insp, 380)
  assert.equal(after.bin, 386)
  const hid = commitPanes('bin', { kind: 'hide' }, p, d, f)
  const gone = effectiveSizes(hid, f)
  assert.equal(gone.bin, 0)
  // a hide rewrites no kept size: the inspector takes its kept size in the freed room
  assert.deepEqual(hid.sizes, { bin: 600, insp: 500 })
  assert.equal(gone.insp, 500)
  const tl = commitPanes('tl', { kind: 'size', px: 250 }, p, d, f)
  assert.deepEqual(tl.sizes, { bin: 600, insp: 500, tl: 250 })
})

test('commitPanes hide and show cycles in a shrinking window change no kept size', () => {
  const f = frame(1100, 900)
  let p = prefs({ bin: 600, insp: 500 })
  const before = effectiveSizes(p, f)
  for (let i = 0; i < 6; i += 1) {
    p = commitPanes('bin', { kind: 'hide' }, p, effectiveSizes(p, f), f)
    assert.deepEqual(p.sizes, { bin: 600, insp: 500 })
    // a pointer wiggle on the hidden strip that ends in hide is no change
    assert.deepEqual(commitPanes('bin', { kind: 'hide' }, p, effectiveSizes(p, f), f), p)
    p = commitPanes('bin', { kind: 'show' }, p, effectiveSizes(p, f), f)
    assert.deepEqual(p.sizes, { bin: 600, insp: 500 })
    assert.deepEqual(effectiveSizes(p, f), before)
  }
  assert.equal(effectiveSizes(p, frame(1440, 900)).insp, 500)
})

test('commitPanes reset holds the other side pane where it is drawn', () => {
  const f = frame(1100, 900)
  const p = prefs({ bin: 240, insp: 540 })
  const d = effectiveSizes(p, f)
  const after = effectiveSizes(commitPanes('bin', { kind: 'reset' }, p, d, f), f)
  assert.equal(after.insp, d.insp)
})

test('commitPanes property: the committed pane is drawn as asked and no other moves', () => {
  for (const f of grid) {
    for (const p of variants) {
      const d = effectiveSizes(p, f)
      for (const pane of ['bin', 'insp', 'tl'] as const) {
        if (d[pane] === 0 && !p.hidden.includes(pane)) {
          continue
        }
        const lim = limits(pane, d, f)
        // No room for the pane's minimum beside the other side pane: the minimums win (design D1).
        const other = pane === 'bin' ? d.insp : d.bin
        if (pane !== 'tl' && f.width - other - 20 * f.rem < lim.min) {
          continue
        }
        const asks = [
          { kind: 'size' as const, px: lim.min },
          { kind: 'size' as const, px: lim.max },
          { kind: 'size' as const, px: Math.floor((lim.min + lim.max) / 2) },
          { kind: 'hide' as const },
        ]
        for (const action of asks) {
          const after = effectiveSizes(commitPanes(pane, action, p, d, f), f)
          const asked = action.kind === 'hide' ? 0 : action.px
          assert.equal(after[pane], asked, `${pane} ${JSON.stringify(action)} ${JSON.stringify(f)}`)
          for (const other of ['bin', 'insp', 'tl'] as const) {
            if (other === pane) {
              continue
            }
            if (other === 'tl' && pane !== 'tl') {
              // A side pane's commit may move the Timeline (the middle row's minimum): within its limits.
              if (after.tl > 0) {
                const tlLim = limits('tl', after, f)
                assert.ok(
                  after.tl >= Math.min(tlLim.min, f.height - f.top) && after.tl <= tlLim.max,
                  `tl ${after.tl} outside ${JSON.stringify(tlLim)} after ${pane} ${JSON.stringify(f)}`,
                )
              }
              continue
            }
            if (action.kind === 'hide') {
              // A hide keeps every kept size, so the other side pane may take the freed room.
              continue
            }
            assert.equal(after[other], d[other], `${other} moved by ${pane} ${JSON.stringify(f)}`)
          }
        }
      }
    }
  }
})

test('paneHidden and paneProperties', () => {
  const p = prefs({}, ['bin'])
  assert.equal(paneHidden('bin', p, false), true)
  assert.equal(paneHidden('insp', p, false), false)
  assert.equal(paneHidden('bin', p, true), false)
  assert.deepEqual(paneProperties(drawnOf(394, 385, 0), false), {
    '--ws-bin-w': '394px',
    '--ws-insp-w': '385px',
    '--ws-tl-h': '0px',
  })
  assert.deepEqual(paneProperties(drawnOf(394, 385, 0), true), {
    '--ws-bin-w': null,
    '--ws-insp-w': null,
    '--ws-tl-h': null,
  })
})

test('sameFrame', () => {
  assert.ok(sameFrame(frame(1, 2, 3, 4), frame(1, 2, 3, 4)))
  assert.ok(!sameFrame(frame(1, 2, 3, 4), frame(9, 2, 3, 4)))
  assert.ok(!sameFrame(frame(1, 2, 3, 4), frame(1, 9, 3, 4)))
  assert.ok(!sameFrame(frame(1, 2, 3, 4), frame(1, 2, 9, 4)))
  assert.ok(!sameFrame(frame(1, 2, 3, 4), frame(1, 2, 3, 9)))
})

test('parsePanes accepts the format', () => {
  assert.deepEqual(parsePanes('{}'), { sizes: {}, hidden: [] })
  assert.deepEqual(parsePanes('{"bin":317}'), { sizes: { bin: 317 }, hidden: [] })
  assert.deepEqual(parsePanes('{"bin":1,"insp":2,"tl":3,"hidden":["tl","bin"]}'), {
    sizes: { bin: 1, insp: 2, tl: 3 },
    hidden: ['bin', 'tl'],
  })
  assert.deepEqual(parsePanes('{"insp":420,"hidden":[]}'), { sizes: { insp: 420 }, hidden: [] })
})

test('parsePanes refuses everything else', () => {
  for (const raw of [
    null,
    'null',
    'nope',
    '[]',
    '{"x":1}',
    '{"bin":NaN}',
    '{"bin":-1}',
    '{"bin":0}',
    '{"bin":"3"}',
    '{"bin":1e999}',
    '{"hidden":"bin"}',
    '{"hidden":["x"]}',
    '{"hidden":["bin","bin"]}',
  ]) {
    assert.equal(parsePanes(raw), null, String(raw))
  }
})

test('serializePanes', () => {
  assert.equal(serializePanes(prefs()), null)
  assert.equal(serializePanes(prefs({ bin: 417 })), '{"bin":417}')
  assert.equal(serializePanes(prefs({}, ['bin'])), '{"hidden":["bin"]}')
  const full = prefs({ tl: 300, bin: 417 }, ['tl'])
  assert.equal(serializePanes(full), '{"bin":417,"tl":300,"hidden":["tl"]}')
  assert.deepEqual(parsePanes(serializePanes(full)), full)
})

test('valueText', () => {
  assert.equal(valueText('bin', 282), 'Clip bin 282 pixels wide')
  assert.equal(valueText('insp', 340), 'Inspector 340 pixels wide')
  assert.equal(valueText('tl', 342), 'Timeline 342 pixels tall')
  assert.equal(valueText('bin', 0), 'Clip bin hidden')
  assert.equal(valueText('insp', 0), 'Inspector hidden')
  assert.equal(valueText('tl', 0), 'Timeline hidden')
})
