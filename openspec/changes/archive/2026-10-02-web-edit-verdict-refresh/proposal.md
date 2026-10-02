## Why

The event page's render region says whether the movie is rendered or stale, and shows the latest job.
When a render ends in the background while the operator is in **Edit mode**, the page keeps the words of
its last read until Edit mode ends: the region can keep saying "Stale" with a job "running" after the
render finished and the movie is up to date. The deferral is written into the `web-app` spec ("An event
page in Edit mode defers that re-read until Edit mode ends"), so it is specified, not accidental. Its
reason is real but narrow: the page's `state.event` feeds the editor, so a full re-read must not run
under it (the draft and the order shown are never re-initialised from a newer detail). The render region
needs only two fields of that read, `staleness` and `latest_job`, and in Edit mode it is read-only
(Render is blocked with "Save or leave Edit mode to render"), so words that are out of date there mislead
the operator without protecting anything. Supervisor decision: a render that ends during Edit mode
refreshes **only the verdict and the latest job** in the render region, never the clips, the chapters or
the draft baseline.

This is a web-only GUI v1 polish item (HLD **§6 phase 8**, §4.10; **D-8**'s budget). It follows
**Principle I** (a stale verdict shown as current is a quiet lie) and keeps **Principle II** (`reel.yaml`
is read by Edit mode itself; this change writes nothing).

Triage item: `edit-mode-verdict-stale-after-live-render-ends` (`web/src/events/EventDetail.tsx`, its
`reread` is a no-op while `editingRef.current` is true).

## What Changes

- While Edit mode is open, when the job the render region shows reaches a finished state, the page makes
  one **verdict-only read** of the event and applies only its `staleness` and `latest_job` to the render
  region. Chapters, clips, counts, the "Read <time>" stamp and the editor's baseline and draft are not
  touched, and the read does not mark the page as updating.
- A verdict read that gets no usable answer leaves the region as it is and adds a short note in it saying
  that the verdict may be out of date. It never replaces the page or the editor.
- A verdict read that is in flight when Edit mode ends is dropped; the read that leaving Edit mode makes
  (unchanged) replaces everything.
- A re-read that was already on its way when the operator pressed Edit (today it is dropped, and nothing
  replaces it) is replaced by a verdict-only read, so the render that ended just before Edit was opened
  is not lost.
- The `web-app` requirement "A shown screen re-reads in place when events change" changes one sentence
  and one scenario ("Edit mode defers the page's re-read") and gains two scenarios.

**Non-goals**

- No change to what Edit mode reads or saves, to the draft, to the save bar, or to the editor's own
  "This event changed on disk since the page was read" handling.
- No polling and no new server push: the trigger is the same one the page already has (the shown job
  ended), so a render started and finished elsewhere, which the page never showed, is not noticed until
  the next read, as today.
- No change to Render being blocked in Edit mode, to the list, or to the API.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: "A shown screen re-reads in place when events change": an event page in Edit mode refreshes
  the render region's verdict and latest job when its job ends, and still defers every other part of the
  re-read until Edit mode ends.

## Impact

- **Package:** `web/` only (`src/events/EventDetail.tsx`; `src/events/loadState.ts` and its test hold the
  pure part, the verdict slice; the doc comments of `edit/EventEditor.tsx`'s "read once" paragraph stay true
  and need no edit). Not touched: `auto_reel_ng/`, `web/src/api/`, the OpenAPI document, `RenderControl`.
- **API / CLI:** neither is touched. The verdict read is the existing `GET /api/v1/events/{id}` route,
  already used by the page; no new endpoint or field (Principle V).
- **Rendered output:** unchanged for identical inputs; no `RENDER_GRAPH_VERSION` bump and no change to
  the staleness fingerprint inputs.
- **Schemas:** no `reel.yaml` or `config.yaml` change, no Alembic migration, no rescan.
- **Dependencies:** none. `web/` has the `node --test` runner (`npm test`) for its pure modules; the slice
  is tested there, and the page's behaviour is checked in a real browser with Playwright scripts kept
  outside the repo.
- **Gate:** `web-save-shortcut` (merged first) edited `edit/EventEditor.tsx` and `events/EventDetail.tsx`;
  the design below was re-checked against `EventDetail.tsx` as it is after that merge.
