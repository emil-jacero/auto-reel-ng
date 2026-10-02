# auto-reel-ng — High-Level Design

> Status: **draft for discussion**. This document is the basis for slicing work into OpenSpec changes.
> It captures the learnings from `auto-reel`, the target architecture, the key decisions already made,
> and an explicit list of things that still need research before they can be specced in detail.

## 1. Goal & scope

`auto-reel-ng` is a rewrite of `auto-reel` (the `movie-merge` Python tool). It keeps the core idea —
**merge per-event video clips into one polished movie per event, with a title card and chapters** — but
takes the learnings from the old project and adds:

1. **Cross-vendor GPU acceleration from day one** — NVIDIA (NVENC/NVDEC/CUDA), Intel (QSV/VAAPI), AMD
   (VAAPI/AMF), with graceful CPU fallback. Solve as much of the video/image work on the GPU as possible.
2. **Optional analysis/AI** — detect long black/white/frozen sections in clips; start with ffmpeg
   filters, leave room for ML (scene-cut, quality scoring) behind the same interface.
3. **A web GUI** — manage ingest, edit metadata, **reorder clips**, configure the look, schedule and
   watch renders. The GUI *aims* to become a full timeline editor, but ships **extremely small** first.

### Decisions locked in (from design discussion)

| Area | Decision |
|---|---|
| Backend / engine stack | **Python + FastAPI** (reuse learnings; best AI/ML ecosystem) |
| GPU render strategy | **Normalize on GPU + stream-copy concat** (re-encode only when needed) |
| Analysis scope | **ffmpeg filters now, ML later; surface detections in the GUI for approval** |
| GUI ambition | **Full timeline editor is the north star, but v1 is tiny**: ingest + reorder + metadata + schedule |
| Editorial source of truth | **`reel.yaml` per event dir** — metadata, clip order, trims, look. GUI reads/writes it. |

### Non-goals (for now)

- Multi-user / multi-tenant cloud service (assume single operator, one host).
- Cloud transcode farms; assume one host with 0–N local GPUs.
- A general-purpose NLE. The timeline editor is scoped to *this* merge workflow.

---

## 2. Learnings carried over from auto-reel

Full source was reviewed end-to-end. The mechanics worth **keeping**:

- Folder-name metadata seeding (`YYYY-MM-DD - Title [- Location]`) + `reel.yaml` override.
- Chapter-from-subdirectory convention; root clips = default chapter; `original/` skipped; `.reelignore`.
  Carried by the specs `event-reconcile` ("Legacy folder conventions exclude clips from
  discovery") and `ingest-layout` ("An event marked with .reelignore is not an event").
- Sort strategies (datetime / filename / custom order). Carried by the specs `event-reconcile`
  ("Clips enter a document in the configured sort order") and `project-config` (the `sort` rule);
  `custom` is the `reel.yaml` clip list itself, and a per-event rule is the follow-up
  `clip-order-legacy-sort`.
- Dataclass configs with `to_dict()` debug logging; thread/movie/clip logging context.
- The `gpu:info` Taskfile idea (it already parses `ffmpeg -hwaccels/-encoders/-decoders`).

The problems we are **explicitly fixing**:

| # | auto-reel problem | NG fix |
|---|---|---|
| 1 | GPU = NVENC **encode only**; decode/scale/pad/overlay on CPU; frames bounce CPU↔GPU | Capability-driven **acceleration profiles**; keep frames GPU-resident |
| 2 | **2–3 full re-encodes** per clip (convert → scale-pad → concat) | Normalize-once on GPU + **stream-copy concat** fast path |
| 3 | **Chapters are illusory** — never written to the container | Write real `ffmetadata` chapter markers |
| 4 | moviepy title cards spawn their own `libx264`/`aac` ffmpeg, ignore chosen codec, hardcoded fonts | Render card to image, encode it as **its own segment** (overlay-free) with the chosen codec |
| 5 | Fragile probe: `time.sleep(1)`/clip, per-clip exiftool+ffprobe, **silent fake-metadata fallback** | One robust probe layer; **fail loud**, never fabricate dimensions/fps |
| 6 | **No rotation / SAR / HDR handling** (`is_hdr` computed, never used) | Normalize rotation/SAR; HDR→SDR tonemap |
| 7 | **GPU-unaware concurrency** — N movies each launch NVENC, oversubscribe | GPU-aware **job scheduler** |
| 8 | No persistence/GUI; `ffmepg` typo; `--cov` bug; **zero tests** | Project model + GUI + real test suite |

---

## 3. Architecture overview

Four layers. The **core engine is a library**; both the FastAPI service and a headless CLI drive it.

```
┌─────────────────────────────────────────────────────────────┐
│  Web GUI (browser SPA)                                       │
│  ingest · reorder · metadata · look · analysis review · jobs │
└───────────────▲──────────────────────────────────────────────┘
                │ REST + WebSocket (live progress)
┌───────────────┴──────────────────────────────────────────────┐
│  Service / API  (FastAPI)                                     │
│  GPU-aware job scheduler · project index (Postgres, derived)    │
│  reel.yaml read/write (source of truth)                       │
└───────────────▲──────────────────────────────────────────────┘
                │ same engine called by headless CLI
┌───────────────┴──────────────────────────────────────────────┐
│  Core Engine (library, pure-ish, testable)                   │
│  ┌────────────────┐ ┌───────────┐ ┌────────────────────────┐ │
│  │ Capability     │ │ Probe /   │ │ Analysis pass          │ │
│  │ detect + accel │ │ metadata  │ │ black/white/freeze →ML │ │
│  │ profile select │ └───────────┘ └────────────────────────┘ │
│  └──────┬─────────┘                                          │
│         │ emits per-vendor ffmpeg arg fragments              │
│  ┌──────▼──────────────────────────────────────────────────┐ │
│  │ Filter-graph / job builder → ffmpeg runner (progress)    │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Design principle: **the engine never hardcodes a vendor**. It asks the capability layer for an
*acceleration profile* and builds ffmpeg arg fragments from it. Adding a vendor = adding a profile.

---

## 4. Component designs

### 4.1 Capability detection & acceleration profiles  *(the centerpiece)*

At startup (and cacheable), probe the host:

- GPUs present: `nvidia-smi -L`; `/dev/dri/renderD*` render nodes; `vainfo` (VAAPI entrypoints); QSV via VAAPI/`libmfx`.
- ffmpeg build: parse `-hwaccels`, `-encoders`, `-decoders`, `-filters` for what's actually compiled in.

Build a **capability matrix**, then select an **AccelProfile** that emits the right fragments per logical op:

Legend: ✅ verified on dev host, ⚠️ verified-broken on dev host, ❓ untested (no such hardware here).

| Logical op | NVIDIA (CUDA/NVENC) ❓ | Intel (QSV/VAAPI) ❓ | AMD (VAAPI) — tested | CPU |
|---|---|---|---|---|
| decode | `-hwaccel cuda -hwaccel_output_format cuda` | `-hwaccel qsv` / `vaapi` | ✅ `-init_hw_device vaapi=va:<node> -filter_hw_device va -hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi` (one named device shared with filters, exp 006) **for the codecs in the profile's `hw_decode` set** (h264 8-bit, hevc/vp9/av1 10-bit; 4:2:0 only); any other clip (MPEG-4 Part 2, MJPEG, 10-bit H.264, 4:2:2) is decoded in software and goes through `format=nv12,hwupload` (D-18) | software |
| scale + pad | `scale_cuda`/`scale_npp` (+`pad`?) | `vpp_qsv` scale **only** (no pad) → libplacebo or CPU pad | `scale_vaapi` ✅; `pad_vaapi` ⚠️ geometry correct, **fill colour ignored on Mesa** (exp 006) — the self-test's `pad_fill_ok` decides; clips needing bars fall back to CPU `scale,pad` | `scale,pad` |
| overlay (title) | `overlay_cuda` | `overlay_qsv` | ⚠️ `overlay_vaapi` **unsupported on Mesa** → CPU bridge / title-as-segment | `overlay` |
| tonemap HDR→SDR | `libplacebo` / CUDA | `tonemap_vaapi` / QSV | ⚠️ **all GPU paths fail** → CPU only | `zscale,tonemap` |
| encode | `h264_nvenc`/`hevc_nvenc`/`av1_nvenc` | `*_qsv` | ✅ `h264_vaapi`/`hevc_vaapi`/`av1_vaapi` | `libx264`/`libx265`/`svtav1` |

This replaces `VideoCodec.is_gpu_codec`. The profile also tracks **where frames live** (hw frame context)
so the graph builder knows when an explicit `hwupload`/`hwdownload` is unavoidable. The AMD column is now
empirically grounded (`experiments/002–004`); the libplacebo/Vulkan unification idea was **refuted on AMD/radv**
(interop broken) and **not needed** — native `scale_vaapi` is the better AMD path, with `pad_vaapi` only where
the self-test measured a correct fill (exp 006). NVIDIA/Intel cells
remain best-guess until tested on real hardware, and **every cell must be confirmed by the startup self-test**
rather than assumed.

**Strong shortcut:** depend on a **known cross-vendor ffmpeg build** (jellyfin-ffmpeg or BtbN) instead of
distro ffmpeg — those ship NVENC + QSV + VAAPI + AMF + libplacebo compiled in, removing most "is it even
available" pain. See research notes §8.

> ⚠️ **Research before speccing:** see §8.1 (filter equivalence & libplacebo), §8.2 (VAAPI pad), §8.3 (mixed hw contexts).

### 4.2 Probe / metadata

One probe module. Single `ffprobe -show_format -show_streams -print_format json` per file (no `sleep`,
no per-clip exiftool unless needed for creation date). Extract: dimensions, SAR/DAR, **rotation/display
matrix**, pix_fmt, color transfer (HDR), fps (avg then r_frame_rate), codec, duration, audio params,
creation time. **On probe failure: error and skip the clip — never fabricate metadata.**

### 4.3 Render pipeline — "normalize on GPU + stream-copy concat"

Per movie:

1. **Plan.** Inspect all clips. If they already share codec + resolution + SAR + pix_fmt + timebase →
   **fast path: concat demuxer with stream copy, zero re-encode**.
2. **Normalize (only the clips that need it).** One GPU-resident pass per nonconforming clip:
   decode → fix rotation/SAR → scale+pad to target → tonemap if HDR → encode to the common intermediate.
   Title clips get the card **overlaid in this same pass** (no separate moviepy encode).
3. **Concat.** Stream-copy concat of the (now uniform) set.
4. **Chapters.** Generate an `ffmetadata` file with `[CHAPTER]` entries from chapter boundaries and mux it in.

Audio is normalized in the same normalize pass (sample rate / channels / codec) so concat can stream-copy.

The target canvas defaults to 1920×1080 at the highest probed clip fps, overridable via `look.target_resolution` /
`look.fps` (config.yaml or reel.yaml); clip order never decides it (render-target-format).

Each movie is finalized to `<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`. Colliding output
paths are refused (**D-9**).

> ⚠️ **Research:** §8.4 stream-copy concat constraints (timebase, B-frames, SPS/PPS, audio priming).

### 4.4 Title / overlay generation

Replace moviepy. Render the title card to an **RGBA PNG at the target resolution** (Cairo + Pango: text,
optional background, outline/shadow) behind a **single swappable renderer seam** (`render_title_card`), then
ship it as **its own synthetic segment** — looped, faded with the `fade` filter, given a synthesized silent
audio track, and encoded to the **target spec with the chosen codec** like any other segment. This is
**card-as-segment, overlay-free** (decision **D-A**): no `overlay`/`overlay_vaapi` and no CPU overlay bridge,
so it is fully on-GPU on every vendor — sidestepping the AMD `overlay_vaapi` gap (exp 003) the original
"overlay in the main graph" wording would have hit. A generic, name-keyed **producer registry** materializes a
synthetic segment's content by its `producer` key (the title card is the first registration; intro/outro/
transition bumpers reuse the seam). Fonts are resolved **by family name through fontconfig** with a bundled
default (DejaVu Sans), and an unresolved family **fails loud** rather than silently substituting. The same
`render_title_card` seam produces the future GUI look-editor preview, so preview is byte-identical to the
render. The title-over-footage *overlay* look stays a future addition via the decorator seam's `attacher`
(non-goal here).

> ✅ **Resolved (§8.5):** Cairo + Pango, fail-loud font resolution, structural + tolerance-gated tests. The
> title-over-footage overlay variant remains future work.

### 4.5 Analysis pass (black / white / freeze → ML later)

Stage 1 (now): run ffmpeg detection filters and parse timestamped segments:
`blackdetect`, `freezedetect`, and a luma-mean threshold via `signalstats`/`blackframe` for **white**.
Output = list of `{start, end, kind, confidence}` per clip.

Stage 2 (later): ML behind the same interface — PySceneDetect for scene cuts, a small ONNX model
(GPU via onnxruntime) for blur/quality. Same `Segment` output type, so the GUI and render don't change.

Detections are **suggestions**: they appear in the GUI as proposed trims; the operator approves/edits;
approved trims are written to `reel.yaml` and applied at render time as in/out points. Raw detection
output is cached in a sidecar (e.g. `.auto-reel/cache/`), **not** in `reel.yaml`.

> ⚠️ **Research:** §8.6 white/freeze thresholds ✅ **RESOLVED** (exp 005); §8.7 ML model choices.

### 4.6 `reel.yaml` — editorial source of truth

`reel.yaml` (per event dir) is the **canonical, git-friendly store of every editorial decision**. The GUI
and CLI both read and write it; Postgres is only a derived index/cache for fast GUI listing. Folder-name
parsing **seeds** a `reel.yaml` on first scan; thereafter the file wins. A clip added later is adopted by
the next render into its folder's chapter, or the default chapter when the file names no such chapter; a
file that names no chapters at all is adopted into as a first scan seeds it (D-12).

Proposed schema (superset of the old format — backward compatible with auto-reel's `metadata`/`title`/
`description`/`sort`/`title_card`):

```yaml
version: 2
metadata:
  title: Midsummer
  date: 2024-06-21
  location: Dalarna
  description: ...
look:                      # was title_card; extended with render/look settings
  target_resolution: [1920, 1080]
  codec: { video: hevc, audio: aac, quality: 22 }
  title_card: { ... }      # font/size/color/position/bg/fade
chapters:
  - name: default
    is_default: true
    clips:                 # explicit, reorderable order — overrides sort
      - file: 00400.mp4
        order: 0
        title: true        # gets the title card
        trims:             # approved cut ranges (from analysis or manual)
          - { in: 0.0, out: 3.2, reason: black }
        rotate: auto       # or 0/90/180/270 override
        include: true
      - { file: 00401.mp4, order: 1 }
  - name: Reception
    clips: [ ... ]
sort:                      # optional: this event's rule for clips ENTERING the document (seed +
  method: custom           #   NEW-clip adoption); overrides config.yaml. datetime | filename | custom
  reverse: false
  custom_order: { 00401.mp4: 1 }   # custom only: file name -> position; unlisted clips follow by filename
```

Open question: how much render/look config lives per-event in `reel.yaml` vs a **project-level**
`config.yaml` (defaults inherited by all events) — **decided: both, event overrides project (D-2).**

### 4.7 Project / config model & GUI ⇄ reel.yaml sync

- **Project** = an input root containing `<year>/<event>/` dirs. Scanning populates a Postgres index
  (event list, clip list, analysis cache pointers) for fast GUI loads.
- Every editorial mutation in the GUI (reorder, trim, metadata edit) is **persisted to `reel.yaml`**,
  with Postgres updated as a cache. `reel.yaml` is authoritative on conflict / re-scan.
- Layered config resolution: layout/folder seed → project `config.yaml` → event `reel.yaml` → render-time overrides (D-2).
  The folder seed is a **per-field fallback**: an event's date, title and location each take the
  `reel.yaml` value when set, else the folder name's (`[<date> - ]<title>[ - <location>]`, parsed leniently,
  with a stated problem for an impossible, year-only or absent date). Resolution happens at load, for every
  consumer (output naming, title card, fingerprint, scan, worker, events reads), and is **never persisted**;
  the editorial read/write stays "as authored". A project event must resolve to a real, non-future date and
  a title, else it fails on its own with the reason and the fix (nothing is derived from media).
- **Ingest layouts are pluggable (D-6):** a layout parser maps a folder structure → events/clips. Built-ins:
  `<year>/<event>/` and `flat`; users can define more in `config.yaml` for different sources/purposes.

### 4.8 GPU-aware job scheduler

Renders and analysis are **jobs**. A scheduler with a small queue that is **GPU-resource-aware**: limit
concurrent encode sessions per GPU (NVENC session caps, VRAM), allow CPU-only jobs to run alongside.
Before enqueuing a render the scheduler runs the **§4.13 staleness check** — an unchanged event produces
no job (unless the operator forces it).
Job state (queued/running/done/failed, progress, logs) in Postgres; progress parsed from `ffmpeg -progress`
and pushed over WebSocket.

**Multi-GPU scheduling (future, but design for it now).** The host may have more than one GPU. The
eventual goal is to **target a specific GPU per job** — either auto-balanced across available devices or
operator-pinned. To keep this cheap to add later, model GPUs as **named, enumerated resources** from the
start: the capability layer (§4.1) discovers a list of devices `[{id, vendor, name, render_node, ...}]`,
each accel profile is parameterized by a **device selector** (e.g. CUDA `-hwaccel_device N` / NVENC
`-gpu N`; VAAPI/QSV `-init_hw_device ...:/dev/dri/renderD12N`), and the scheduler tracks capacity
**per device** rather than globally. v1 can simply use device 0; nothing in the data model assumes a
single GPU. A `device` (or `auto`) field on the render job carries the selection.

> ⚠️ **Research:** §8.9 NVENC session limits & per-vendor concurrency; ffmpeg `-progress` parsing;
> §8.13 per-device selection flags across NVENC/QSV/VAAPI and multi-render-node hosts.

### 4.9 API (FastAPI)

REST for CRUD (projects, events, clips, look, jobs) + WebSocket channel for live job progress/logs.
Thin layer over the engine; no business logic that the CLI can't also reach.
The service serves one project; its jobs views are scoped to it; the queue is shared (change
`jobs-project-guards`: `auto-reel jobs` and the worker stay database-wide).

**The events read model is probe-free.** File facts (byte size, mtime) come from the clip's own directory
entry — a `stat` — and may be served per request. Media facts (duration, dimensions, codec) require decoding
and therefore belong to the analysis cache; no events read may probe a clip to fill a response field. This is
D-A3 (scanned per request) plus Principle IV (the staleness path never decodes) applied to the read model,
not a new decision, and it is the rule to quote when a response field would need an `ffprobe`. The thumbnail
route (`GET /api/v1/events/{event_id}/thumbnail?clip=`, change `clip-thumbnail-endpoint`, **D-11**) is a
per-clip media read on request, not a field of the events read model, so the list and detail stay probe-free
and gain no field: the client builds each thumbnail's URL from the event id and clip identity it already has.
The media routes (`GET /api/v1/events/{event_id}/media?clip=` and `/movie`, change `media-endpoints`) are,
like the thumbnail, per-request media reads, not fields of the events read model. They stream the file on disk
unchanged with byte ranges: no transcode, no probe. They answer `GET` and `HEAD` with `If-None-Match` and
`If-Modified-Since` validators (change `api-media-head-conditional`). The movie is the file the staleness gate
counts as the event's movie (`staleness.rendered_output`), so a legacy movie with no render record is not served until
`auto-reel adopt-renders` records it. `<img>` and `<video>` send no `Authorization` header, so a future token
is a cookie or a query parameter (D-A8).

**The same rule bounds content hashing.** The staleness fingerprint's clip-set component has a content-hash
opt-in (`compute_fingerprint(use_hash=True)`) that sha256s every clip's bytes; on a per-event read that is a
deliberate, bounded cost, but a whole-library read must never take it — an events **list** would turn one
request into a read of every byte in the library. The list computes its verdicts from the clips' size and
mtime, the same content-free signal a `stat` already gives it. Read endpoints that fan out over the whole
project MUST NOT read clip content to fill a response field, by hash any more than by probe.

### 4.10 Web GUI — phased

The north star is a **full timeline editor**, but we ship in thin slices:

- **v1 (tiny, ship first):** scan/ingest view (events + clips), **drag-reorder clips** (persist to
  `reel.yaml`), **chapter edits, Move clips and dragging clips between chapters** (**D-13**), **typed cuts** (**D-14**), **a clip's preview with Set From / Set To** (**D-16**), edit basic metadata (title/date/location/description), **schedule a render and watch
  live progress**, **clip thumbnails** (one frame per clip, **D-11**), and **the rendered movie on the event
  page** (**D-15**). The resolved `look` is shown
  **read-only**; editing it is v2. No timeline, no per-frame editing.
- **v2:** look/style editor (**the look picker deferred from v1**; title card live-ish preview); **the full
  timeline editor, moved from v3** — a per-clip track with proxies, filmstrip, drag-trim in/out and scrub
  preview; **analysis review built as overlays on that timeline** (approve black/white/freeze trims in place,
  not a separate screen); event poster frames; and, beside the proxy work, chapter times in the render
  manifest (a chapter list for the movie player) and a movie version in the event detail. v2 starts with a
  research step: §8.11 (proxies, the PCM-audio path) and the timeline library against D-8's dependency budget.
- **v3:** nothing is planned for the GUI: the timeline editor moved to v2 on 2026-10-01, and dragging
  across chapters landed in v1 (D-13, `cross-chapter-drag`).

**Roadmap edit (2026-10-01, user decision):** "A and B in this version, but i want C a full editor in v2".
v1 gains the movie player (A, change `movie-player-screen`) and the clip preview with Set From / Set To at
the playhead (B, change `clip-preview-screen`); their one `api/` prerequisite is `media-endpoints` (the media
routes of §4.9), as `clip-thumbnail-endpoint` is for D-11. The full timeline editor (C) moves from v3 to v2,
and v2's analysis review is built as overlays on that timeline rather than as a screen of its own.

The v1 screens share one visual system in plain CSS — tokens, an app shell, and the primitives slices
D and E build on — pulled forward from the v2 look-and-feel pass (**D-10**, change `web-design-system`).

Clip thumbnails are pulled forward from v2 as **D-11**, in three changes (`clip-thumbnails` →
`clip-thumbnail-endpoint` → `clip-thumbnails-screen`); `clip-thumbnail-endpoint` is the one extra `api/`
prerequisite this adds to v1.

**v1's slices** (planned 2026-09-01; one OpenSpec change each, in order). v1 is four features and a
scaffold, which is several changes under Principle VIII, so the plan lives here rather than as five open
change directories:

| # | Slice | What it lands |
|---|---|---|
| 0 | `events-list-staleness` | `api/` prerequisite: the events **list** carries the staleness verdict, so the scan view can answer "what needs rendering?" in one request |
| A | `web-app-scaffold` | `web/` + the static mount + schema→types pipeline; no screen |
| B | event list screen | the scan/ingest view, over slice 0's verdicts |
| C | event detail screen | chapters/clips read-only, using the per-clip `size`/`mtime` file facts. `movie-player-screen` plays the event's rendered movie (D-15) |
| D | reorder + metadata save | the first write: `ETag`/`If-Match`, 412 conflict handling, the one drag-and-drop dependency — landed in `event-edit-screen` (the event page's Edit mode). `missing-clips-screen` adds the explicit removal of a MISSING clip's entry (never automatic) and holds Render back while an event lists one. `chapter-management-screen` adds the chapter edits (add, rename, move, delete when empty) and Move clips between chapters (D-13). `clip-cuts-screen` adds a clip's cuts, listed, added from typed times and removed in Edit mode, and shown on the event page (D-14). `cross-chapter-drag` lets a clip be dragged into another chapter (D-13). `clip-preview-screen` plays a clip in its Cuts panel, sets a cut at the playhead, skips cuts as the movie will, and refuses a cut past the length the browser reads (D-16) |
| E | render + live progress | `POST /jobs` (201 / 200-fresh / 409), the WS hook, cancel — landed in `render-progress-screen` |

C, D and E were designed only after A and B had been used against a real library; all three have
landed. `editorial-write-api`, `editorial-read-api` and `gui-event-screen-api-prep` closed the
write precondition and the per-clip file facts. Slice E then needed two more `api/` prerequisites, found
while designing it: `jobs-client-contract` (the published jobs answers, cancel outcomes and WebSocket
frames) and `jobs-project-guards` (the output-collision refusal and project-scoped jobs). Its follow-up
`job-summary-times` gave the events reads' latest job its start and finish times, so a screen dates a
job it knows only from a read by its state. **The
resolved `look`, shown read-only in the v1 sketch above, is not exposed by any endpoint**; it is
deferred to v2 with the look editor rather than adding a read surface for a field v1 only displays.

#### Decision D-8 — Frontend stack (LOCKED, 2026-08-31)

**React 19 + Vite + TypeScript, built to static assets and served by the FastAPI process, under a hard
dependency budget.** Rationale and rules:

- **The runtime stays one Python process.** `auto-reel serve` is the whole deployment, so the frontend may
  depend on Node at **build time only**; any framework requiring a Node process at runtime (SvelteKit, Next,
  Nuxt) is disqualified. The build output is static files the API mounts.
- **Why React.** The widest ecosystem and the deepest library/documentation coverage for the v2 timeline
  editor (drag-trim, scrub preview; moved from v3 on 2026-10-01) — the slice most likely to need something
  off the shelf. Chosen over Svelte on support breadth, and over htmx/Jinja because the timeline editor is
  not reachable from there without a rewrite.
- **API types are generated, never hand-written.** Every endpoint carries a pydantic `response_model`, so
  FastAPI's OpenAPI schema → `openapi-typescript` → TS types. A backend schema change becomes a frontend
  **build error** instead of a silent runtime bug. Hand-maintaining a template ⇄ schema mapping (the htmx
  path) was the deciding maintenance cost.
- **The dependency budget is the real maintenance lever, not the framework** (Principle VII). GUI v1 ships
  `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`, and one drag-and-drop library, plus
  `openapi-typescript` as a dev dependency. The drag-and-drop library is the legacy `@dnd-kit` line
  (`@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`; `event-edit-screen`): keyboard sorting and
  screen-reader announcements built in, and it works under React's StrictMode. Its successor
  `@dnd-kit/react` replaces it once that reaches 1.0 or its StrictMode issue #2116 is fixed. **No
  component library, no CSS framework, no router, and no state-management or data-fetching library at v1**
  — each is added only when a slice demonstrably needs it, justified in that change's proposal.
  Component-library majors are the usual source of frontend bit rot; plain CSS has none.
- **Layout.** `web/` at the repo root; the Vite dev server proxies `/api` to the running service.
  `create_app` mounts the built `web/dist` at `/` **when that directory exists** and serves nothing
  otherwise, so dev and test runs never need a build. Same origin → no CORS, and the WS shares the host.
- **Live progress needs no library.** The hub already fans out `JobOut` deltas and re-sends a full snapshot
  on reconnect (D-A4), so the client is one WebSocket hook holding a `Map<job_id, JobOut>` with reconnect
  backoff. The service closes the socket with 1012 when it stops and 1013 when it drops a subscriber, and
  the client reconnects after any close. A snapshot carries only active jobs, so a job the client knew as
  active that a reconnect snapshot lacks is read once with `GET /jobs/{id}`: it ended while the socket was
  down. A browser cannot see transport pings, so an idle connection is sent a `heartbeat` frame (empty job
  list) after 15 s of silence, and a client that has seen no frame for 40 s drops the socket itself and takes
  the same reconnect path: a half-open connection reads "reconnecting", not "live".
- **The Node toolchain runs in podman** (`node:22`), mirroring the containerized-Postgres test fixture —
  nothing is layered onto the immutable host.
- **`web/dist` in the image.** The local image (`Containerfile`, **D-17**) builds `web/dist` in a `node:22`
  stage and serves it through an editable install in `/app`, so `web_dist_dir()` needs no change. A wheel or
  a published image that carries the client is still §6 phase 11 packaging.

#### The schema → types pipeline, and what checks it (slice A, 2026-09-01)

D-8 promises that a backend schema change becomes a **frontend build error**. The mechanism is two
committed artifacts and two checks standing on either side of them:

```
auto_reel_ng/api response models
        │  app.openapi()                     ← auto_reel_ng/api/openapi.py, offline:
        ▼                                      no service, no reachable database (the engine is lazy)
   web/openapi.json          (committed)  ◄── pytest: regenerate and compare, naming the disagreement
        │  openapi-typescript
        ▼
   web/src/api/schema.d.ts   (committed)
        │
        ▼
      client code                          ◄── tsc --noEmit: fails where client code reads a field
                                               the regenerated types no longer describe
```

The Python check is the load-bearing one: a developer who changes a response model and never opens
`web/` still gets a failure, with no Node involved. Neither check can be satisfied by hand-editing a
generated file, because regenerating overwrites it. Both artifacts are committed so `tsc` runs from a
clean checkout and the client's API surface is visible in review.

**A closed vocabulary must be typed as an enumeration, or the pipeline cannot see it.** The two checks
compare and compile *what the schema says*; they cannot notice a field whose schema says less than the
code means. A closed set published as a bare `list[str]` — `StalenessOut.reasons` was one — generates
`string[]`, so every client re-states the vocabulary in a hand-maintained map, and renaming a value in
the engine leaves `pytest`, the drift check and `tsc --noEmit` all green while the UI degrades to raw
slugs: exactly the hand-maintained schema ⇄ view mapping D-8 rejected htmx to avoid. The rule that
follows: a field drawn from a closed set is typed with an enumeration owned by the layer that owns the
vocabulary (`StalenessReason` lives in `staleness/`, not in `api/`), so the schema publishes the set and
the generated types become an exhaustive union. `events-list-client-contract` is the worked example. A
model sent only over the WebSocket has no HTTP route to carry it into the schema, so the application's
schema hook publishes it into the schema's components (`WsMessage` and its `WsMessageType`,
`jobs-client-contract`), never through a fake HTTP route.

**`tsc --noEmit` is the frontend gate for GUI v1** — the whole frontend check. There is deliberately
**no test runner and no browser automation**: types are generated from the schema, so drift is a compile
error, and endpoint behavior is already covered by `pytest`. A later slice with logic worth unit-testing
proposes a runner then, with its justification.

> ⚠️ **Research:** §8.11 proxies and scrubbing for the timeline (v2, the research that opens GUI v2);
> browser playback of the archive is measured in `docs/research/browser-playback.md`; single-frame clip thumbnails are
> **resolved** (Decision D-11). The frontend framework is now **resolved** (Decision D-8).

### 4.11 Headless CLI

Same engine, same `reel.yaml`. Supports batch processing by year (the old workflow) plus `reel.yaml`
import from auto-reel. Keeps automation/CI working without the GUI.

### 4.12 Packaging / deployment

#### Decision D-1 — ffmpeg distribution (LOCKED, 2026-06-01)

**The container bundles `jellyfin-ffmpeg` as the default ffmpeg/ffprobe, but the engine stays
binary-agnostic.** Rationale and rules:

- **Default = jellyfin-ffmpeg.** It is the only single build shipping NVENC/NVDEC + QSV + VAAPI + AMF + libplacebo,
  is actively maintained, and is current enough for the filters the spikes require. (See `docs/research/cross-vendor-ffmpeg.md`.)
- **Engine is binary-agnostic, not hardcoded.** `ffmpeg`/`ffprobe` paths are configurable (env/CLI); the default
  resolves to the bundled jellyfin-ffmpeg. The §4.1 capability layer **probes + self-tests** whatever binary it's
  given, so a dev host can use system ffmpeg and a power user can drop in **BtbN `gpl`** or a custom build without
  code changes.
- **Minimum version asserted at startup: ffmpeg ≥ 7.1** (required for `pad_vaapi` and other tested filters). Pin
  the bundled jellyfin-ffmpeg version; jellyfin-ffmpeg also carries Jellyfin-specific patches, so pinning avoids surprises.
- **Licensing:** jellyfin-ffmpeg (and BtbN `gpl`) is **GPL**. Bundling it in our image is mere aggregation — our
  Python app keeps its own (MIT) license — but the **published image must carry the GPL source offer + the exact
  configure line**. **Never** bundle the `nonfree`/fdk-aac variant in a published image. (Note: this Fedora dev
  host's system ffmpeg 7.1.3 is an `--enable-nonfree` build → dev-only, must not be redistributed.)
- **How the image gets it** (2026-10-02, change `compose-stack`). No `jellyfin/jellyfin-ffmpeg` image exists
  on any registry: Jellyfin ships jellyfin-ffmpeg only as `.deb` packages. The `Containerfile` installs
  `jellyfin-ffmpeg8` from the Jellyfin apt repo on `debian:trixie-slim`, pinned by
  `ARG JELLYFIN_FFMPEG_VERSION` (default `8.1.3-1-trixie`, `ffmpeg version 8.1.3-Jellyfin`). The package
  bundles its own libva and the `radeonsi`, `iHD` and `i965` VA drivers under `/usr/lib/jellyfin-ffmpeg`, so
  the image installs no host VA driver or Mesa package.
- ⚠️ **Pre-publish blocker.** `jellyfin-ffmpeg8` 8.1.3 is built with `--enable-libfdk-aac` (and without
  `--enable-nonfree`; `ffmpeg -L` prints GPLv3), and `-encoders` lists `libfdk_aac`. That conflicts with the
  rule above. The local compose image (D-17) is a dev-only build that is never pushed; **no image may be
  published** until this is settled (a jellyfin build without fdk-aac, or a different binary).

#### Deployment

- NVIDIA needs `nvidia-container-toolkit` + `--gpus`; Intel/AMD need `/dev/dri` passthrough + drivers
  (intel-media-driver / Mesa). One image can support all three if it ships the userspace drivers and the
  host passes the right devices.
- **Local compose stack (D-17).** `compose.yaml` at the repo root runs Postgres, the migration, a seed of a
  scratch library, `serve` and one `worker` from the local image. The worker gets `/dev/dri`; with
  jellyfin-ffmpeg's bundled VA drivers that is all VAAPI needs (measured on a Radeon 860M, radeonsi, rootless
  podman with SELinux enforcing, no `group_add` for a `0666` render node). `compose.cpu.yaml` runs the worker
  with `--device cpu` for a host without `/dev/dri`. Usage: README, "Run the stack with compose".

> ⚠️ **Research:** §8.12 one-image-all-vendors feasibility (ship CUDA + intel-media-driver + Mesa/VAAPI userspace,
> select at runtime). The jellyfin-ffmpeg choice and its licensing are now **resolved** (Decision D-1),
> but publishing an image waits for the fdk-aac pre-publish blocker in D-1 above (`jellyfin-ffmpeg8`
> 8.1.3 ships `libfdk_aac`).

### 4.13 Change detection — don't render unless something changed

**Requirement:** the system **must not schedule (or run) a render for an event unless a relevant change
has been detected** since that event's last successful render. A no-op re-scan, a GUI open, or a batch CLI
run over an unchanged project must enqueue **zero** render jobs. The operator can always force a render
explicitly (e.g. `--force` / a "Re-render" button), which bypasses the check.

This is deliberately **left open** — the *what*, the *how*, and especially the *where* are research items
(§8.14). The shape of the problem, to be resolved before speccing:

- **What counts as a change?** Candidate inputs to a staleness decision (non-exhaustive): the set of source
  clips in the event dir (added / removed / renamed), each clip's content (size + mtime, or a content
  hash), the editorial decisions in `reel.yaml` (order, trims, metadata, look), the resolved project-level
  defaults (`config.yaml`, per D-2), the chosen codec / target resolution, the approved analysis trims, and
  the engine / ffmpeg version (a render-graph change can alter output even with identical inputs — relevant
  given the pinned jellyfin-ffmpeg of D-1). Open question: hash file *contents* (robust, slower) vs trust
  `size + mtime` (cheap, misses in-place edits) vs a hybrid.
- **How to detect it?** Likely a **render fingerprint** — a hash over the normalized set of inputs above —
  compared against the fingerprint recorded for the last successful render. Equal → skip; differ or absent
  → stale → eligible to schedule. A **missing or partial output file** is always treated as stale,
  regardless of fingerprint.
- **Where to store the "last rendered" state?** The crux, and explicitly undecided. Per D-7 the Postgres DB
  is **rebuildable from disk**, so authoritative render state probably shouldn't live *only* in it. Options:
  - **Sidecar in the event dir** (e.g. a `render-manifest.json` under the `.auto-reel/cache/` already used
    for analysis output in §4.5) — travels with the media, backup-friendly, survives a DB rebuild.
  - **Postgres** (§4.8/D-7) — convenient for the scheduler to query, but it's declared a *derived*,
    disk-rebuildable index/cache (§4.7), so it can't be the sole home for render state.
  - **Inside `reel.yaml`** — rejected as the default: `reel.yaml` is the *editorial* source of truth and
    should stay human-authored; machine-written render bookkeeping would muddy diffs and fight the GUI.
  - **The output container metadata** — stamp the fingerprint into the rendered file and read it back; no
    extra files, but couples state to a mutable artifact and is awkward to query in bulk.

  Current lean: a **sidecar manifest as the source of truth, mirrored into Postgres for fast GUI/scheduler
  queries** (consistent with D-7's "DB rebuildable from disk") — but §8.14 settles this.

This gates the scheduler in §4.8: scanning yields *candidate* events; a **staleness check** filters them to
the set that actually needs work before any job is enqueued.

> ⚠️ **Research:** §8.14 change-detection signals, fingerprint composition, and where last-render state lives.

---

## 5. Cross-cutting concerns

- **Error handling:** fail loud on probe/render errors; never fabricate metadata; per-event isolation so
  one bad event doesn't kill the batch (carry over auto-reel's per-dir try/except, but log + report).
- **Logging:** keep the thread/movie/clip context logger; structured logs for the GUI.
- **Testing:** real suite from the start (fix the `--cov` package bug). Unit-test the capability layer and
  graph builder with **recorded `ffmpeg -*` outputs** and **golden ffmpeg command strings** (assert the
  emitted args per profile without needing the GPU). Integration tests behind a "has GPU" marker.
- **Naming:** fix `ffmepg` → `ffmpeg`.

---

## 6. Phasing → maps to OpenSpec changes (proposed slices)

Rough dependency order; each becomes one or more OpenSpec changes:

1. **Engine skeleton + probe/metadata** (robust ffprobe, data model, no fake fallback).
2. **Capability detection + acceleration profiles** (matrix, profile selection, golden-arg tests).
3. **`reel.yaml` v2 schema + loader/writer** (+ auto-reel import, folder-name seeding).
4. **Render pipeline** (normalize-on-GPU + stream-copy concat, real chapters).
5. **Title/overlay** (image render + in-graph overlay, replace moviepy).
6. **Analysis pass v1** (black/white/freeze → segments → reel.yaml trims).
7. **Job scheduler + FastAPI service** (jobs, progress over WS, Postgres index).
8. **GUI v1** (ingest + reorder + metadata + schedule + progress).
9. **GUI v2** (look editor + the full timeline editor, with analysis review as timeline overlays; starts
   with the §8.11 research).
10. **ML analysis** (parallel, behind existing interfaces); GUI v3 has no planned scope: the timeline editor
    moved to v2, and dragging across chapters landed in v1 (D-13).
11. **Packaging** (cross-vendor image, deployment docs). Slice 1: local compose stack (`compose-stack`,
    D-17): a local image and a test stack, nothing published; the published image waits for the D-1
    fdk-aac blocker (§4.12).

---

## 7. Product decisions (resolved 2026-06-01)

- **D-2 — Config layering.** Project-level **`config.yaml`** holds shared defaults (look/codec/resolution/
  ingest layouts); per-event **`reel.yaml`** overrides. Resolution order: folder/layout seed → project
  `config.yaml` → event `reel.yaml` → render-time overrides. (§4.6/§4.7)
- **D-3 — Vendor pick.** **Auto-pick the best accelerator by capability**, with a config/job field to force a
  specific device. (§4.1/§4.8)
- **D-4 — Multi-GPU targeting** (future behavior): per-job device selection field reserved now (auto vs pinned);
  auto-balancing/pinning logic lands later. (§4.8)
- **D-5 — AV1 is a first-class v1 target.** Ship AV1 hardware encode alongside H.264/HEVC (verified on the AMD
  test card; the profile self-test + CPU `svtav1` fallback cover hosts without AV1 hw). (§4.1)
- **D-6 — Configurable ingest layouts.** Ingest is **not** hardcoded to `<year>/<event>/`. A **pluggable layout
  system** lets users define folder-structure parsers for different purposes; **ship `<year>/<event>/` and
  `flat` as built-ins**. (§4.2/§4.7 — see Open question O-1 on persistence.)

- **D-7 — Persistence: Postgres.** The service uses **Postgres** for derived state — **index + job/scheduler
  state + analysis cache + ingest-layout definitions**. `reel.yaml` remains the editorial source of truth; the
  DB is rebuildable from disk. Access goes through an ORM (SQLAlchemy) and migrations (Alembic). Ship Postgres in
  the compose/deployment stack; a dev fallback (containerized PG) keeps local setup simple. (§4.7/§4.8)

- **D-8 — Frontend stack: React + Vite + TypeScript** (locked 2026-08-31). A static build served by the
  FastAPI process — **no Node at runtime**; API types generated from the OpenAPI schema; a hard dependency
  budget with **no component library, router, or state library at GUI v1**. (§4.10)

- **D-9 — Output layout** (2026-09-26, changes `output-path-year-folder` and `output-name-date-prefix`).
  Movies go to `<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`, with the year folder and the
  name's ISO date both taken from the event's `metadata.date`. An undated event goes directly under
  `<output>/` as `<title>[ - <location>].mp4`, and the date is never guessed. This is the legacy auto-reel
  layout, so `adopt-renders` finds the existing archive. *Corrected 2026-09-26:* the first version omitted
  the date prefix legacy put in every movie name (`directory.py:220`); on the real archive that found
  0 of 138 legacy outputs, the prefixed rule finds 129. `render`, `enqueue`, `adopt-renders` and
  `POST /api/v1/jobs` (change `jobs-project-guards`) refuse every event whose output path collides
  with another's (compared case-insensitively, never auto-suffixed). The default output directory is
  the sibling `<parent>/<root-name>-output`, outside the walked root, so rendered year folders are
  never scanned as events. *Amended 2026-10-01 (change `output-renamed-reason`):* after a render, a new
  title, date or location changes the movie's path. The engine never deletes, moves, renames or
  overwrites the previous movie: the next render writes the new path beside it and records the new
  name in the render manifest. Until then the staleness verdict cites `output_renamed` instead of
  `output` (which keeps meaning the movie is really gone). Removing the old file is the operator's
  call. A render still replaces the file at its own path, so a case-only rename on a
  case-insensitive filesystem replaces the old movie, as before, and so does the render of another
  event that now has the renamed event's old name (the collision check compares only current paths);
  the renamed event's verdict then still cites `output_renamed`, for a file that is now the other
  event's movie.
  *Amended 2026-10-02, change `engine-output-claims`:* which events claim an output path, and who else
  claims it, is decided by one engine rule (`event/claims.py` `checked_claim`, `render/claims.py`
  `output_collision`), not by caller-private copies. An event claims a path only when it loads and is
  processable; one that fails to load (an unparseable `reel.yaml`, a folder or file the process cannot
  list or read) claims nothing and is reported on its own. The CLI, `POST /api/v1/jobs` and the worker
  adopt it in the changes `cli-batch-isolation-and-claims`, `api-jobs-create-validation` (landed: the API's
  copy is gone, and an enqueue names an event by exactly the id the list shows and answers the events
  reads' 502 for one it cannot process) and `worker-claim-guards`; the worker's claim-time recheck
  fails a colliding job rather than requeueing it. *Amended 2026-10-02, change `worker-claim-guards`:*
  the worker applies that rule at claim time, before the plan is rebuilt or anything is written, and
  also refuses a job whose output path another `running` job writes (another project sharing the output
  directory, an event the layout walk does not reach); a refused job fails with the reason and is
  enqueued again once the cause is gone. A clip the event lists but the folder lacks fails the event by
  identity, all of them at once, on `render` and in the worker alike.
  *Amended 2026-10-02, change `staleness-output-lookup`:* the event's movie is a regular file, for the
  verdict, the movie route and `adopt-renders` alike: a folder at the movie's path is a missing movie (`output`),
  is not adopted, and makes a render fail typed instead of replacing it. The previous movie is looked for only
  in the output directory in use, so a render into another `-o` directory reads `output`. A case-only rename on
  a case-insensitive mount is unchanged and unverified here (no such mount on the dev host); an undated title
  that starts with a date prefix is unreachable, since every surface refuses an event without a real date.
  (§4.3/§4.11)

- **D-10 — GUI v1 visual system** (2026-09-30, change `web-design-system`). GUI v1 ships a modern visual
  design, overriding event-list-screen's deferral of look and feel to v2, and does it inside D-8's budget:
  plain CSS in cascade layers (`reset, tokens, base, components, screens`); one token set whose colors
  are OKLCH `light-dark()` values (a cool neutral ramp, one indigo accent, five status tones measured
  to WCAG AA in both schemes); system fonts, no web font; inline-SVG icons (Lucide paths, copied as
  source); native `<dialog>` for confirmations. Status is never shown by color alone: every status
  pairs its words with an icon. The color scheme follows the OS unless the operator picks Light or
  Dark, a per-browser preference, not project state. Later slices add their own stylesheets and
  reuse the shared primitives (`web/README.md`, "Design system"). (§4.10)

- **D-11 — Clip thumbnails in GUI v1** (2026-09-30, change `clip-thumbnails`). Every clip on disk gets one
  JPEG thumbnail, pulled forward from v2 at the operator's request.
  - **The frame** is the one at `thumbnails.position` × the clip's ffprobe duration (default 0.25,
    0 < p < 1). It is never the first frame and never at a guessed time. There is one attempt: a clip
    with no frame there has no thumbnail.
  - **Extraction** uses CPU decode through the engine's ffmpeg runtime: input seek, one frame,
    SAR-corrected, the display rotation applied and the editorial `rotate` not, fitted inside 320×180.
    A clip the probe flags HDR (PQ or HLG) is tone-mapped to SDR first, on the CPU, with the render's own
    chain (`CPU_TONEMAP_FILTER`).
  - **The cache** is derived state in a file cache outside the library:
    `$XDG_CACHE_HOME/auto-reel/thumbnails/` (else `~/.cache/…`), or `thumbnails.cache_dir`. It is keyed
    by the resolved file's name (not its path), size, mtime, position, box and `THUMBNAIL_VERSION`,
    so a move, copy or remount of the library keeps the cache; written atomically, never in Postgres
    (D-7), and never evicted in v1 (≈15 KB per clip). A full cache disk is one cache error, not a
    failure of the clip; hidden temporaries a killed extraction left behind, older than a day, are swept
    once per process.
    - *2026-10-02, change `thumbs-cache-key-and-count`:* the key used to hold the absolute resolved
      path, so every remount regenerated every thumbnail. `THUMBNAIL_VERSION` is now 2; the files
      written under version 1 are orphaned and stay (never evicted), and every clip regenerates once.
      Two different files with the same name, size and mtime would share a thumbnail (accepted;
      deleting the cache directory repairs it). `auto-reel thumbs` extracts one file once per event.
    A host CLI and a container service share one cache when they see the same directory (the compose
    stack's `XDG_CACHE_HOME=/data/cache` bind mount, or `thumbnails.cache_dir` in `config.yaml`); the
    library may sit at different paths on each side, since the key no longer hashes the path.
    - *2026-10-02, change `thumbs-hdr-and-cache-hygiene`:* an HDR clip's thumbnail used to be
      range-clipped; it is tone-mapped now. The key is computed before any probe (a cache hit runs no
      ffprobe), so it cannot carry an HDR flag: `THUMBNAIL_VERSION` is now 3, the files written under
      earlier versions are orphaned and stay (never evicted), and every clip regenerates once. An HDR
      clip that declares only a transfer function (no primaries or matrix) has no thumbnail, as its
      render fails the same way; nothing is guessed.
    - *2026-10-02, change `thumbs-sidecar-metadata`:* beside `<key>.jpg` the cache holds two small files
      with the same key, written atomically like it. `<key>.json` is the duration the thumbnail's probe
      reported, read with no ffprobe (`recorded_duration`; absent for a thumbnail made earlier, and
      unknown until one is made, never guessed). `<key>.fail` is the reason a clip failed, remembered
      for 60 s from the failed attempt (a module constant, not a setting) so a broken clip is not
      re-probed on every request, by the CLI and the service alike; a read does not renew it, a success
      removes it, and a cache or config fault is never remembered. No `THUMBNAIL_VERSION` bump.
  - **Filling it:** `auto-reel thumbs` fills it in batch. The service's thumbnail route fills it on
    request (change `clip-thumbnail-endpoint`).
  - **Still open:** proxies and scrubbing are v2, with the timeline editor (§8.11; moved from v3 on
    2026-10-01). (§4.10)

- **D-12 — NEW-clip adoption follows the clip's folder** (2026-10-01, change `adopt-into-folder-chapter`;
  amends `project-cli`'s D-CLI3). A clip that appears in an event after its `reel.yaml` exists (NEW) is
  adopted by the next render, from the CLI or the worker, into the chapter named after the folder it is
  in: the event folder's clips into the default chapter, and a subfolder's into the chapter of that name.
  It goes into the default chapter only when `reel.yaml` has no chapter of that name. A `reel.yaml` that
  names no chapters at all (a legacy import, a metadata-only first save) is adopted into as a new event is
  seeded: the event folder's clips into the default chapter and each subfolder's into a chapter of its
  own, in seeding order. Otherwise adoption creates no chapter except the default one, appended last when
  absent. It never moves a clip the document lists, and it appends a chapter's entering clips in the sort
  rule's order. The events detail places every clip `reel.yaml` does not list (NEW or ignored) by this
  same rule, so it shows each NEW clip where the render will adopt it.

  *Amended 2026-10-01:* D-CLI3 adopted every NEW clip into the default chapter ("configurable", never
  wired). The GUI v1 end-to-end pass found `Kvällen/s1710004.mp4` shown under `Kvällen` and played in
  Main after Render, and the operator chose the folder rule, and seeding for a `reel.yaml` that names no
  chapters. Adoption writes `reel.yaml`, which the editorial component already fingerprints, so this is no
  render-graph change. (§4.6)

- **D-13 — Chapters are edited in GUI v1** (2026-10-01, change `chapter-management-screen`). Edit mode adds,
  renames, reorders and deletes chapters, and moves clips between them with a per-chapter Move clips
  dialog, pulled forward from v3 at the operator's request. Dragging a clip into another chapter
  followed in `cross-chapter-drag` (2026-10-01), at the operator's request, beside Move clips: any position,
  an empty chapter too, by pointer and keyboard. A missing clip stays in its chapter. A save that
  changes the chapter list writes every chapter as shown, so every NEW clip is adopted where the page shows
  it; a chapter's name then only decides where later clips go (D-12). The event's own chapter keeps no name,
  and a chapter is deleted only once empty. (§4.10)

- **D-14 — Cuts are edited by typed times in GUI v1** (2026-10-01, change `clip-cuts-screen`). Edit mode
  lists, adds and removes a clip's cuts (D-D), with times typed as seconds, m:ss or h:mm:ss, pulled forward
  from v3 at the operator's request. A clip's preview followed in GUI v1 (D-16). Scrubbing and drag-trim
  are the v2 timeline editor's (§4.10, 2026-10-01). The page refuses what the engine refuses (`out <= in`, negative), and
  refuses an overlap with another cut. It cannot refuse a cut past
  the clip's end, because no probe-free read gives a duration, unless the clip was previewed in that Edit
  mode (D-16); otherwise it states the render's rule instead (cut short at the end; a whole-clip cut leaves the
  clip out). A cut made in the GUI has the reason `manual`. The event page shows each clip's cuts.
  The refusal of a new overlapping cut is an editing aid, not an engine rule: `reel.yaml` and the engine accept
  overlap and join overlapping or touching cuts as one removal, and cuts already overlapping show as their
  union. (§4.10)

- **D-15 — The event page plays its rendered movie in GUI v1** (2026-10-01, change `movie-player-screen`). The
  event page's read view shows the movie the staleness gate counts (`GET …/movie`, `media-endpoints`) in the
  browser's native player, says whether it is current or outdated, and names its file and size. It loads none of
  the movie until Play (`preload="none"`; the poster is the first played clip's thumbnail). Its address carries
  the file's entity-tag as `v`, read with a one-byte range request on each read of the event, because Chrome
  fails to play a replaced file at an address that served the old one. Failures are said by cause, including a
  picture the browser cannot show (a legacy MPEG-4 movie plays its sound only). There are no custom controls or
  shortcuts, no captions and no chapter list: the manifest records no chapter times and browsers expose none.
  Chapter times in the render manifest and a movie version in the event detail are v2 items beside the proxy
  work. A Refresh stops playback in v1. Edit mode shows no movie. (§4.10)

- **D-16 — A clip is previewed in Edit mode in GUI v1** (2026-10-01, change `clip-preview-screen`).
  - **What.** A clip's Cuts panel plays the clip itself, its file streamed unchanged by the media route
    (`media-endpoints`, §4.9). Its Watch control, or one press on the clip's thumbnail in Edit mode, opens it.
    It has a cut bar, Set From and Set To at the playhead (to the millisecond, written as typed times, D-14),
    and Skip cuts, which plays the clip as the movie will (the render's merge, D-D), showing no frame that lies
    wholly inside a cut; a cut within 0.1 s of the clip's end stops playback at its start.
  - **Loading.** A `<video>` exists only while a preview is open, one at a time: Edit mode holds at most one
    video, and shows no movie player (D-15).
  - **Notes, not alerts.** What the browser cannot do is said by cause in a note, announced through Edit mode's
    one live region (polite) rather than as an alert, unlike D-15's playback failures, because Edit mode already
    speaks every edit there.
  - **The length.** The length the browser reads from the file refuses a cut that ends past the clip's end,
    for that clip, while Edit mode stays open. The API still carries no duration, so a clip never previewed
    keeps D-14's rule. Measured on five files: Chrome's length equals ffprobe's, and Firefox's runs up to 60 ms
    longer, never shorter, so the check never refused a cut the render keeps in full.
  - **What stays v2.** Firefox plays PCM audio silently (52 % of the archive), and the preview says so. Proxies,
    the PCM audio path, scrubbing and drag-trim stay the v2 timeline editor's (§4.10, §8.11).
- **D-17 — A local compose stack for testing** (2026-10-02, change `compose-stack`; the first, local-only
  slice of §6 phase 11). `podman compose up -d` at the repo root brings up Postgres, the migration, a seed,
  `serve` and one `worker`.
  - **The fixture is read, never written.** `auto-reel-media` is mounted read-only, and a one-shot seed builds
    a writable scratch library over it: absolute symlinks to the clips, real copies of `reel.yaml`, no
    `.auto-reel/` cache. Re-seeding never overwrites an edit, and `seed --reset` starts over. The services that
    mount the fixture run with `label=disable`, never `:z`/`:Z`, because relabeling would rewrite the
    context of the user's directory tree, and a confined container cannot read `user_home_t`.
  - **The client** is served from the image through an editable install in `/app` (§4.10), with no
    settings key for `web_dist_dir()`.
  - **Exposure.** Postgres is not published, and the GUI binds `127.0.0.1` only, because the API has no
    authentication and the GUI writes `reel.yaml`.
  - **Always the checked-out code.** Every `up` rebuilds the image from the checkout (`pull_policy: build`,
    cached), and `.dockerignore` keeps the scratch data and the non-runtime trees out of the build context.
  - **Local only.** The image is never pushed while D-1's fdk-aac blocker stands (§4.12).
- **D-18 — Decode is chosen per clip, with one software retry** (2026-10-02, change
  `render-vaapi-software-decode-fallback`). The startup self-test proves hardware decode with one h264 clip, which
  says nothing about the other codecs the archive holds; an MPEG-4 Part 2 `.avi` failed the whole event on the
  AMD Radeon 860M (`Failed setup for format vaapi`, -38) while `--device cpu` rendered it.
  - **A capability, not a render rule.** `AcceleratorCapabilities.hw_decode` maps a source codec to the highest
    bit depth the hardware decoder handles, from a static per-vendor table kept only when the decode probe
    passed. `AccelProfile.can_hw_decode(codec, pix_fmt)` answers per clip: the codec must be listed, the format
    4:2:0 and within the depth; an absent `pix_fmt` is decided by the codec alone and an unrecognised one is
    software. `render/` stays vendor-free and asks the profile. A missing table entry costs speed, never
    correctness.
  - **No new graph shape.** A clip the hardware cannot decode takes the CPU DECODE fragment, and the existing
    frame-location composition adds `format=nv12,hwupload` plus the one named upload device. **NVIDIA and Intel are
    unchanged:** they have no verified upload device, so the choice is not made for them; a profile with an empty
    `upload_device_flags` keeps attempting its own hardware decode for every clip, exactly as before. Their
    `hw_decode` tables are recorded but take effect only once an upload recipe is verified on their hardware.
    A forced software build for such a profile (the retry) fails loud naming `--device cpu`, with the segment and
    the first ffmpeg failure in the message.
  - **One retry for a wrong table.** If a hardware-decode normalize fails with `hwaccel initialisation returned
    error` or `Failed setup for format`, that segment is rebuilt with software decode and run once; the recovered
    failure is logged and returned in `RenderResult.warnings`. Nothing else is retried (not `-38` alone, not a
    synthetic or already-software segment), and a failed retry is raised with both attempts' detail.
  - **`RENDER_GRAPH_VERSION` is not bumped.** Only inputs that failed before change behaviour; every input that
    rendered still produces the same command. The capability cache schema is bumped so `hw_decode` is detected
    once on upgrade.

---

## 8. Research backlog — resolve before the corresponding spec

These are the items that need real investigation (docs, experiments, or vendor testing) before they can be
turned into confident OpenSpec changes. Numbered to match the ⚠️ markers above.

> **Spike results so far** (see `experiments/`):
>
> - **§8.4 — Confirmed** (exp 001). Stream-copy concat is clean only when `codec/profile/width/height/SAR/
>   pix_fmt/time_base` all match (fps drives timebase). Resolution/SAR mismatches **mux with exit 0 but break
>   players** → the pre-flight equivalence check must come from `ffprobe`, never the exit code. AAC priming
>   injects a ~256-sample gap at each join → prefer normalizing audio. **Normalize is the default path; copy is
>   a narrow fast path.**
> - **§8.1/§8.2 — Resolved for AMD** (exp 002+003, AMD RX 9070 XT). The clean AMD normalize is **native,
>   single-API `scale_vaapi,pad_vaapi → {h264,hevc,av1}_vaapi`** — fully on-GPU and the **fastest** path tested
>   (1.98 s vs bridge 2.83 s vs CPU 3.18 s for 30 s). `pad_vaapi` **exists** in ffmpeg 7.1+ (the "VAAPI can't
>   pad" claim is outdated). The libplacebo↔VAAPI (Vulkan) route is **broken on radv** and not needed for AMD.
>   **Corrected by exp 006:** `pad_vaapi` ignores its fill colour on Mesa (paints green); bars pad on the CPU
>   unless the self-test's `pad_fill_ok` is true.
> - **AMD driver gaps found** (exp 003+004): `overlay_vaapi` is **unsupported** (→ title can't be composited
>   on-GPU via VAAPI; prefer **title-as-separate-segment** over overlay), and **every GPU HDR tonemap path
>   fails** (`tonemap_vaapi` "doesn't support HDR", libplacebo interop broken, `tonemap_opencl` **crashes the
>   GPU**) — only **CPU `zscale,tonemap`** works on AMD, at ~0.35× realtime.
> - **Lessons baked into the design:** the profile must (a) provide a **native single-API normalize per vendor**,
>   (b) carry **capability flags** (`pad_filter`, `can_overlay_hw`, `can_tonemap_hw`) discovered by a **startup
>   self-test** that runs a 1-frame clip through each candidate filter and excludes any that error/fault, and
>   (c) keep a **guaranteed CPU fallback** for overlay and tonemap. NVIDIA/Intel paths **untested here** and must
>   be validated per vendor before §4.1 is finalized.
> - **Literature (source-verified, `docs/research/cross-vendor-ffmpeg.md`)** corroborates the spikes and adds:
>   distribution = **jellyfin-ffmpeg** (treat as GPL — publish source/config); **`vpp_qsv` does NOT pad** (Intel
>   needs libplacebo or CPU bridge — corrects an earlier assumption); libplacebo pad = `normalize_sar`+
>   `pad_crop_ratio`+`fillcolor`; AMD libplacebo/Vulkan may need `RADV_PERFTEST=video_decode` (one retry worth
>   trying before declaring it dead); and concat copy-safety can't be fully proven from `ffprobe` (GOP open/closed,
>   edit lists, AAC priming are invisible) → **normalize is the safe default**.
> - **Dual-GPU confirmed** on the dev host (RX 9070 XT dGPU `renderD128` + Radeon 780M iGPU `renderD129`) —
>   validates modeling GPUs as enumerated, per-render-node devices (§4.8).

1. **Cross-vendor GPU filter equivalence + libplacebo.** *(AMD done; NVIDIA/Intel open.)* Map every logical
   filter to NVENC/QSV/VAAPI/AMF names. AMD: native `scale_vaapi,pad_vaapi`; libplacebo refuted on radv.
   **Still need:** validate NVIDIA (CUDA/libplacebo) and Intel (`vpp_qsv` scale-only) on real hardware; retry
   AMD libplacebo with `RADV_PERFTEST=video_decode`.
2. **VAAPI padding.** ⚠️ **RESOLVED WITH A DEFECT** — `pad_vaapi` exists (FFmpeg ≥ 7.1) and produces the right
   geometry on AMD (exp 003), but **ignores its `color` on Mesa radeonsi**: every syntax paints all-zero YUV
   (green bars; exp 006). The self-test now reads the padded pixels back (`amd.pad_fill` → `pad_fill_ok`);
   clips that need bars pad on the CPU where the fill is wrong, 16:9 clips stay on `scale_vaapi`. The same
   experiment found the VAAPI decode must share one named device with the filter graph, or no CPU stage can
   `hwupload` back. Intel QSV still needs libplacebo/CPU bridge (`vpp_qsv` can't pad).
3. **Mixed hardware frame contexts** in one ffmpeg graph (different decoders/inputs) — what's allowed,
   when an explicit `hwupload`/`hwdownload` round-trip is forced. *(Partially seen in exp 002: Vulkan↔VAAPI
   reverse map fails on radv; device-derivation order matters.)*
4. **Stream-copy concat constraints.** ✅ **RESOLVED** (exp 001 + literature) — match `codec/profile/level/W/H/
   SAR/pix_fmt/time_base/fps` + audio params; **GOP open/closed, edit lists, AAC priming are NOT probe-visible**
   → normalize is the safe default; copy only for same-source clips (or add a keyframe packet check).
5. **Title text rendering replacement** for moviepy. ✅ **RESOLVED** (title-card change) — **Cairo + Pango**
   (real shaping/wrapping/kerning, fontconfig name-based fonts, headroom for non-Latin/RTL), behind a single
   swappable `render_title_card` seam. **Fail-loud font resolution** (an unresolved family raises, naming the
   bundled DejaVu Sans default; Pango's silent substitution is refused). Outline + crisp offset drop-shadow in
   v1 (blurred shadow is a follow-up). The card ships **as its own overlay-free segment**, not an in-graph
   overlay (decision **D-A**), so the AMD `overlay_vaapi` gap never applies. Tests are **structural** (computed
   text boxes / wrap points / resolved family + golden ffmpeg-arg strings) with a single tolerance-based pixel
   snapshot gated behind a "has-fonts" marker — no fragile exact-PNG goldens.
6. **White/freeze detection thresholds.** ✅ **RESOLVED** (exp 005). Black/white via `blackdetect`
   (`pic_th=0.98`, `pix_th=0.10`); **white = `negate,blackdetect`** (reuses the same machinery, range-robust —
   chosen over a bespoke `signalstats` YAVG cutoff); `freezedetect=n=0.003`; **min-duration `d=2.0s`** default,
   all configurable. Validated on a synthetic ground-truth clip (exact spans) with **zero false positives** on
   real daytime footage (brightest frame `YAVG=124.6` vs white `235`). **Freeze overlaps black/white** → the
   analysis layer must apply precedence (black/white > freeze) so a span isn't double-reported. Caveat:
   re-check black on dark night footage. Defaults are suggestions the operator approves, never auto-applied.
7. **ML analysis stack (later)** — PySceneDetect detectors (content vs adaptive), a blur/quality model,
   onnxruntime GPU execution providers per vendor.
8. **ffmpeg distribution.** ✅ **RESOLVED → Decision D-1 (§4.12, LOCKED).** Default = **jellyfin-ffmpeg**
   (bundled), engine binary-agnostic, **≥ 7.1** asserted at startup, treated as **GPL** (publish source +
   configure line), `nonfree`/fdk-aac never shipped. Details in `docs/research/cross-vendor-ffmpeg.md`.
   ⚠️ Reopened for publishing only (2026-10-02, `compose-stack`): `jellyfin-ffmpeg8` 8.1.3 ships
   `libfdk_aac`, so no image may be published until the D-1 pre-publish blocker (§4.12) is settled.
9. **GPU concurrency limits** — NVENC simultaneous-session caps per GPU class, VRAM budgeting, and the
   QSV/VAAPI equivalents, to size the scheduler. Plus `ffmpeg -progress` parsing for accurate %.
10. **Frontend framework.** ✅ **RESOLVED → Decision D-8 (§4.10, LOCKED).** **React 19 + Vite +
    TypeScript**, static build served by FastAPI (no runtime Node), API types generated from OpenAPI, and a
    hard dependency budget (no component library, router, or state library at GUI v1). WS state handling is
    a hand-written hook over the existing D-A4 progress hub.
11. **Proxy & thumbnail generation** for the timeline editor. Clip thumbnails ✅ **RESOLVED → Decision
    D-11** (§4.10): one JPEG per clip at a fraction of its duration, in a file cache outside the library.
    Still open (v2, the research that opens GUI v2): low-res proxies (and/or HLS) for scrubbing without
    touching originals; where to cache them. The PCM audio path: 52 % of the archive's clips (every Sony
    XAVC clip) carry PCM audio that Firefox does not play; the v1 media routes serve files unchanged. Facts
    that size the proxy work: about 76 % of the archive's files keep `moov` at the end (every seek is a
    range, the first open a tail fetch), and HEVC exists only under `original/`. See
    `docs/research/browser-playback.md`.
12. **Single image, all vendors** — can one container ship CUDA + intel-media-driver + Mesa/VAAPI
    userspace and select at runtime from host-passed devices; document the `--gpus` vs `/dev/dri` matrix.
    Data point (2026-10-02, `compose-stack`): the VAAPI userspace comes bundled with jellyfin-ffmpeg8 (libva +
    radeonsi/iHD/i965, Mesa 26.0.8), so AMD/Intel need only `/dev/dri`; VAAPI rendered on a Radeon 860M in
    rootless podman. RDNA4 and Intel were not run. NVIDIA (`--gpus`, CUDA userspace) is still open.
13. **Per-device targeting** — exact flags to pin a job to a chosen GPU across NVENC (`-gpu`/
    `-hwaccel_device`), QSV, and VAAPI (`-init_hw_device` per render node); behavior on hosts with
    multiple render nodes / mixed vendors; how to enumerate stable device IDs that survive reboots.
14. **Change detection / render staleness** (gates §4.13). Decide: (a) **which signals** define a relevant
    change — clip set + content (hash vs `size+mtime` vs hybrid), `reel.yaml` editorial state, resolved
    `config.yaml` defaults (D-2), codec/look, approved trims, engine/ffmpeg version (D-1); (b) **fingerprint
    composition** — what's hashed and how it's normalized so cosmetic reorders don't false-positive while
    real edits always do; (c) **where the last-render state lives** — sidecar manifest in `.auto-reel/cache/`
    vs Postgres (D-7, but it's rebuildable from disk) vs output-container metadata, and how the two stay in
    sync; (d) **edge cases** — missing/partial output, clock skew / mtime-only filesystems, force-render
    override, and detecting that the *previous* render failed. Prototype as a `fingerprint(event) → hash`
    - `is_stale(event)` pair the scheduler calls before enqueuing.

```
