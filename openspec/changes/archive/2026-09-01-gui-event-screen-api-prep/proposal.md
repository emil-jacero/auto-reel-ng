## Why

GUI v1 (HLD **§6 phase 8**, stack locked as **D-8**, §4.10) opens on one screen: an event's chapters, its
clips, drag to reorder, save. Designing that screen against the API as it stands surfaced two deficits, both
in `api/`, both cheap, and both better fixed before any TypeScript exists — the same de-risking order
`editorial-write-api` and `editorial-read-api` used.

**1. The write endpoint hands back no precondition.** `editorial-read-api` (archived 2026-09-01) gave the
editorial read an `ETag` and the write an optional `If-Match`, but `PUT /api/v1/events/{event_id}/reel`
returns only `EditorialWriteResult` — document plus staleness, no `ETag`. A client that just wrote therefore
holds the persisted document and **no valid precondition for its next write**. The spec's own remedy is
`Scenario: A round trip is enough to obtain a fresh precondition` — re-read `/reel`, which re-walks and
re-parses the event.

That is the wrong incentive at exactly the wrong place. A reorder screen writes once per save, so the
conditional path costs a second request per interaction while the *unconditional* path — drop `If-Match`,
never re-read — is both simpler to write and faster. The safe client is the expensive one, so clients will
stop being safe, and the lost update `Requirement: Conditional editorial write` exists to prevent
(`auto-reel analyze` writing trims under an open tab) comes straight back. The endpoint already knows the
answer: `editorial_hash` is applied to the document it is about to echo. Withholding it is the whole bug.

**2. A clip is an identity and a status, and nothing else.** `ClipOut` is `{identity, status}`, so the v1
reorder list can only render raw camera filenames:

```
⠿ P1000123.MP4  active      ⠿ P1000124.MP4  active      ⠿ P1000125.MP4  NEW
```

Reordering home video by opaque filename is guessing. Thumbnails are explicitly **v2** (§4.10) and scrub
proxies are unresolved research (**§8.11**), so v1 cannot reach for either — but it does not need to. The
cheapest human signal that requires **no decode** is the clip's own `stat`: byte size, and modification time
to sort by. The detail path already performs that syscall — `compute_fingerprint` reads each clip's
size+mtime signal for the probe-free fingerprint (Principle IV) — so the data is already crossing this code
path unexposed.

## What Changes

- **`PUT /api/v1/events/{event_id}/reel` SHALL return an `ETag`** on a successful write, identifying the
  editorial state it just persisted — the same `editorial_hash` value the GET emits, over the document the
  response body already carries. A client can then write, edit, and write again conditionally with no
  intervening read. No request shape changes; the response gains a header.
- **`ClipOut` gains `size` and `mtime`** on `GET /api/v1/events/{event_id}`: the clip file's byte size and
  modification time (timezone-aware UTC) from a plain `stat`. Both are `null` for a MISSING clip, which by
  definition has no file — the response stays loud about absence rather than fabricating a zero
  (Principle I).
- **No new endpoint, no new engine capability, no probe.**

## Capabilities

### Modified Capabilities
- `api-service`: `Requirement: Conditional editorial write` gains the write response's `ETag`, closing the
  read-after-write round trip. `Requirement: Events read model is scanned from disk per request` gains the
  per-clip `size`/`mtime` on the detail response.

## Impact

- **Packages:** `api/` only — `routes/events.py` (one header), `schemas.py` (two optional fields),
  `events_read.py` (stat the clips `_build_chapters` already enumerates). Nothing below `api/` is touched.
- **Principle VIII:** two response-shape changes in one package, one screen's worth of prerequisite, no
  engine change. Kept as one change deliberately: split, each half is a two-line commit with its own
  proposal, and the second would be pure ceremony. If either half grows a design question during apply, it
  splits then.
- **API / CLI (Principle V):** API only. Neither half adds engine capability — `editorial_hash` already
  exists (extracted by `editorial-read-api`) and `Path.stat` is not a capability. Nothing lands that the CLI
  cannot already reach (`ls -l`, `scan`).
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump.**
- **Staleness fingerprint inputs:** unchanged. Size and mtime are *already* fingerprint inputs; this change
  only surfaces them in a response. **No event becomes stale.**
- **Schemas:** no `reel.yaml`, `config.yaml`, or Postgres change. **No Alembic migration, no rescan.** The
  OpenAPI schema changes additively, which is what the GUI's generated types will consume.
- **Performance:** one extra `stat` per clip on the detail request — the same syscall `compute_fingerprint`
  performs for its clip signals a moment later. Measured context: the scan+parse work a detail request
  already does costs ~1.6 ms per event (300 events × 25 clips = ~490 ms for the full list walk); a `stat` is
  microseconds against that.
- **Dependencies:** none added (Principle VII).

## Non-goals

- **No `duration`.** It needs an `ffprobe` subprocess per clip, which would put decoding on a path
  Principle IV deliberately keeps probe-free and cost minutes on a large library. If it is wanted later it
  belongs behind the analysis cache, as its own change.
- **No thumbnails or poster frames.** §4.10 puts them in v2 and they need a cache location, an endpoint, and
  a CLI counterpart (Principle V) — a change of its own, and the right first v2 slice.
- **No change to `GET /api/v1/events`.** The list keeps `clip_count`/`new_count`/`missing_count`; per-clip
  detail belongs to the detail endpoint, and statting every clip in the library on a list request is exactly
  the cost this change is careful not to add.
- **No conditional GET.** `If-None-Match` on the read was settled against in **D-R4** and stays settled.
- **No mandatory `If-Match`.** The absent header stays unconditional, per the existing requirement.
- **No frontend code and no `web/dist` mount.** The scaffold is the next change; this one ships headlessly
  testable Python before the SPA exists.
