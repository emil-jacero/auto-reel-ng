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
| 4 | moviepy title cards spawn their own `libx264`/`aac` ffmpeg, ignore chosen codec, hardcoded fonts | Render card to image, encode it as **its own segment** (overlay-free) with the chosen codec; a `video`-background card is instead an alpha-faded overlay on the chapter's first segment (`title-card-over-video`) |
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
   The rotation is the clip's **display rotation plus the editorial `rotate`** (an extra clockwise turn,
   **D-23**), applied by the engine as one CPU transpose chain on every profile with ffmpeg's own autorotate off;
   a clip with a display rotation or a `rotate` is never stream-copied.
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
**card-as-segment, overlay-free** (decision **D-A**) for a card on a `black` background: no `overlay`/`overlay_vaapi`
and no CPU overlay bridge, so it is fully on-GPU on every vendor — sidestepping the AMD `overlay_vaapi` gap
(exp 003) the original "overlay in the main graph" wording would have hit. A generic, name-keyed **producer registry** materializes a
synthetic segment's content by its `producer` key (the title card is the first registration; intro/outro/
transition bumpers reuse the seam). Fonts are resolved **by family name through fontconfig**, from a **bundled set of nine
families** (DejaVu Sans, the default, plus eight OFL families, `fonts/`, one registry `render/title/fonts.py`) under a
fontconfig the engine points at itself, so no system font is involved and the image and a dev host draw the same
glyphs (**D-22**); an unresolved family or weight **fails loud** rather than silently substituting. The same
`render_title_card` seam produces the future GUI look-editor preview, so preview is byte-identical to the
render.

A card with the background `video` is the other look (`title-card-over-video`, **D-24**): text over the start of the
chapter's first clip while it plays, no time added. The `title` decorator inserts no segment for it; it attaches the
card, rendered on a transparent canvas by the same `render_title_card`, to the chapter's anchor segment as a
**timed overlay** (an `OverlaySpec` naming the `title` producer, materialized when the segment's command is built),
over the segment's first `duration` seconds, faded in and out on its alpha channel. The normalize step loops the
still, fades its alpha and composites it with the CPU `overlay` on every profile (on AMD between the CPU download and
the upload, as the bridge always did). Only the card's window goes through that bridge: the anchor segment is split
at the first target-frame boundary at or after the window's end (`video-card-bridge-window`), the head carries the
card through the CPU bridge and the tail, the rest of the clip, takes the profile's ordinary hardware path. Experiment
003's advice was that "only the title segment pays CPU cost"; an over-video card gives it up for the card's seconds of
one segment per chapter. A card longer than its segment is clamped to the segment's length, its fades shrunk
together, and the render reports a warning.

A card has its own text, length and style (**D-24**, `title-card-model`). Its heading is the card's `title`, else
the chapter's name, else (the opening card of the default chapter) the event title; its subtitle is free text,
empty by default on a chapter card. **The opening card's default subtitle is the event's date and place again**
(`title-card-date-place-shadow`): the ISO date, then `Plats: <location>`, each only when known, never the
description; any `subtitle` text replaces it and an explicit `subtitle: ""` means none. A card over video
draws a soft drop shadow under its text (`RENDER_GRAPH_VERSION` 9). Each card's length and style are the engine defaults, then the event-wide `look.title_card`, then
the chapter's own `card:` in `reel.yaml`, parsed once so the fades clamp to the card's own length.

> ✅ **Resolved (§8.5):** Cairo + Pango, fail-loud font resolution, structural + tolerance-gated tests. The
> title-over-footage overlay variant is built (`title-card-over-video`, D-24).

### 4.5 Analysis pass (black / white / freeze → ML later)

Stage 1 (now): run ffmpeg detection filters and parse timestamped segments:
`blackdetect`, `freezedetect`, and a luma-mean threshold via `signalstats`/`blackframe` for **white**.
Output = list of `{start, end, kind, confidence}` per clip.

Stage 2 (later): ML behind the same interface — PySceneDetect for scene cuts, a small ONNX model
(GPU via onnxruntime) for blur/quality. Same `Segment` output type, so the GUI and render don't change.

Detections are **suggestions**: they appear in the GUI as proposed trims; the operator approves/edits;
approved trims are written to `reel.yaml` and applied at render time as in/out points. Raw detection
output is cached in a sidecar (e.g. `.auto-reel/cache/`), **not** in `reel.yaml`. The GUI writes an approved
suggestion as a trim whose `reason` is its kind (`black`, `white`, `freeze`; D-20, "Analysis overlays"), by the
Timeline on Edit mode's draft (`timeline-overlay-decisions`).

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
  decorators: [title]      # absent = [title], the cards are on; [] or [none] = no cards (D-25)
  title_card: { ... }      # font/size/color/position/bg/fade
poster:                    # optional: the frame that stands for the movie (D-26)
  clip: 00400.mp4          #   a clip of the event (its identity)
  at: 12.5                 #   seconds into the ORIGINAL clip, before trims; absent = the default frame
chapters:
  - name: default
    is_default: true
    card:                  # optional: this chapter's title card (the default chapter's is the opening card; D-24)
      title: Midsummer 2024
      subtitle: At grandma's
      duration: 5
    clips:                 # explicit, reorderable order — overrides sort
      - file: 00400.mp4
        order: 0
        title: true        # gets the title card
        trims:             # approved cut ranges (from analysis or manual)
          - { in: 0.0, out: 3.2, reason: black }
        rotate: 90         # an extra clockwise turn on top of the display rotation (0/90/180/270; D-23)
        include: true
      - { file: 00401.mp4, order: 1 }
  - name: Reception
    clips: [ ... ]
sort:                      # optional: this event's rule for clips ENTERING the document (seed +
  method: custom           #   NEW-clip adoption); overrides config.yaml. datetime | filename | custom
  reverse: false
  custom_order: { 00401.mp4: 1 }   # custom only: file name -> position; unlisted clips follow by filename
```

Chapter names other than `""` (the default chapter) are unpadded and non-blank, and unique under
`str.casefold()` (user decision 2026-10-02, "Enforce in engine", change `chapter-name-rules-engine`). Loading
a `reel.yaml` that breaks this fails loud, naming both chapters; so does writing one. A `reel.yaml` that
today holds case-variant or padded chapter names stops loading until one chapter is renamed in the file.

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
and therefore belong to the analysis cache; no events read may probe a clip to fill a response field. The first
exception is the detail's per-clip `duration` (change `api-clip-duration`): not a probe but a read of the
number the thumbnail operation already measured, kept in the sidecar beside the clip's cached thumbnail
(D-11), `null` (unknown, never zero) until a thumbnail of the file as it is now has been made. The second is the
detail's per-clip `proxy` (change `proxy-state-read`, D-21): the state of the clip's proxy (`absent`, `ready`,
`stale` or `failed`) and, when `ready`, the facts the proxy job recorded (duration, frame rate as a fraction,
dimensions as displayed, rotation, audio codec, the filmstrip's tile geometry) with the proxy's entity tag as
`version`, read from the cache entry by `stat` and one JSON read per clip, with no process, no write and no
listing of the cache; `null` (unknown, never `absent`) for a missing clip, an unresolvable `proxies`
configuration or a cache that cannot be read. The list keeps its clip counts and carries no `proxy`. This is
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
`auto-reel adopt-renders` records it. The proxy routes (`GET`/`HEAD /api/v1/events/{event_id}/proxy?clip=` and `/filmstrip?clip=`, change
`proxy-media-endpoints`, **D-21**) are the same kind of per-request read, of the proxy cache (per-request reads of the
cache, not fields of the events read model): the clip is looked up as the thumbnail's and the clip route's is, the file
is the cache entry's `proxy.mp4` or `filmstrip.jpg` computed from the clip's stat (nothing created, no ffmpeg, no
database), and a clip with no finished file is a 404 problem body. `<img>` and `<video>` send no `Authorization` header, so a future token
is a cookie or a query parameter (D-A8).

The jobs shapes carry a job's **`kind`** (`render | proxy`, change `proxy-enqueue-endpoint`): in `JobOut`, in the
events reads' `latest_job` (which is always the latest *render* job) and in every WebSocket frame, and `GET
/api/v1/jobs` lists every kind. `POST /api/v1/events/{event_id}/proxies` enqueues an event's proxy job with the render
enqueue's 201 / 200 fresh / 409 semantics (D-21 "Enqueue over REST"); it is a job-lifecycle route, so Principle V holds:
the work is `auto-reel proxies`'s, and the API only owns enqueue, follow and cancel. Proxy jobs share the one WebSocket.

**The same rule bounds content hashing.** The staleness fingerprint's clip-set component has a content-hash
opt-in (`compute_fingerprint(use_hash=True)`) that sha256s every clip's bytes; on a per-event read that is a
deliberate, bounded cost, but a whole-library read must never take it — an events **list** would turn one
request into a read of every byte in the library. The list computes its verdicts from the clips' size and
mtime, the same content-free signal a `stat` already gives it. Read endpoints that fan out over the whole
project MUST NOT read clip content to fill a response field, by hash any more than by probe.

### 4.10 Web GUI — phased

The north star is a **full timeline editor**, but we ship in thin slices:

- **v1 (tiny, ship first):** scan/ingest view (events + clips), **drag-reorder clips** (persist to
  `reel.yaml`), **chapter edits, Move clips and dragging clips (singly or as a marked group) between chapters** (**D-13**), **typed cuts** (**D-14**), **a clip's preview with Set From / Set To** (**D-16**), edit basic metadata (title/date/location/description), **schedule a render and watch
  live progress**, **clip thumbnails** (one frame per clip, **D-11**), and **the rendered movie on the event
  page** (**D-15**). The resolved `look` is shown
  **read-only**; editing it is v2. No timeline, no per-frame editing.
- **v2 title-card inspector** (`title-card-inspector`, D-24): selecting a card (Timeline block or chapter row) opens its
  inspector in Edit mode (`web/src/edit/card/`): title, subtitle, Black/Video, font (`GET /fonts`, by display name),
  sizes, colour, position, each a per-card override with **Use event style** (the unset value is the event's resolved
  `title_card`). Cards are a draft slice by chapter key; a save sends `card` only for changed cards (`{}` removes) and
  the save bar counts them. The preview is `POST …/title-card/preview` (250 ms debounce, stale requests aborted,
  previous image kept, failures in words, one retry after `Retry-After`); a Video card is laid over the **thumbnail
  frame** of the clip it sits over (not the exact start: the preview has no frame-at-time option). Follow-ups: serve
  the bundled font files so the picker can show each family in its own face, and a frame-at-time route.
- **v2 opening subtitle and shadow** (`title-card-date-place-shadow`, D-24): the opening card's Subtitle shows the
  engine's `default_subtitle` (from the event detail) as its placeholder, **No subtitle** writes `""`, **Use default**
  removes the key; rows show the effective subtitle. The page composes no default.
- **v2 event card style** (`title-card-event-style`, D-24): **Card style for this event** (Edit mode, closed by default,
  `web/src/edit/CardStylePanel.tsx`, pure model `cardStyle.ts`) edits the event-wide `look.title_card` (font, title and
  subtitle size, colour, position, default length, default background) in the same draft as everything else. A card
  says which style fields it overrides (`Overrides font, color` / `Uses the event style`; read from the draft card, so a
  value equal to the event's still counts), **Use event style** falls back to the *draft* style, and every preview sends
  that draft as the body's `style`. A save writes `look` as read with only `look.title_card`'s edited fields changed
  (`fade_in`, outline and every other key kept; the sub-map is removed when its last key is cleared; an unchanged style
  sends `look` itself). An unset field shows the project default (the detail's resolved value) as a placeholder; a
  field cleared although the saved style set it says "Project default" with no number, because the lower layer is not
  known to the page and is never guessed. No API, engine or `RENDER_GRAPH_VERSION` change.
- **v2 Title cards switch** (`title-card-toggle`, D-20, D-25): Edit mode's **Title cards: On / Off**
  (`web/src/edit/TitleCardsSwitch.tsx`, pure model `decorators.ts`) edits the event's own `look.decorators` in the same
  draft (Off removes `title` and keeps the other names; with no list it writes `[]`; On puts `title` first). The state the
  page shows is the detail's `title_cards.enabled` (resolved by the engine from the event and the project), never a guess
  from `reel.yaml`: the Timeline's card lane, the chapter list's rows and the movie's length follow it, and the draft's
  switch before any save. Selecting a card opens the inspector below the track, so the track never moves. A choice with
  no value of its own shows the value it inherits as pressed in a muted style with "(event style)" / "(project default)".
  The event's own chapter shows one opening-card row whose heading is the "Main title card" control. Web only.
- **v2:** look/style editor (**the look picker deferred from v1, now built as the event card style and the card inspector: one draft, one save**; title card live-ish preview; `title-card-fonts`
  is the foundation of the card editor: the bundled font set and its registry, **D-22**; **the title card model
  has landed** as `title-card-model`, **D-24**: the per-chapter `card:` in `reel.yaml`; **its API is built** as
  `title-card-write-api`: `PUT`/`GET …/reel` carry each chapter's `card` (the overrides; `{}` removes, absent or `null`
  keeps; a refusal is a 400 naming the chapter and the field, and a `look.title_card` or font the engine refuses is
  refused the same way; the event-wide `look.title_card` is parsed as strictly as a chapter's card, so an unknown key or a
  `title_font_size`, `subtitle_font_size` or `duration` outside the card bounds is refused, naming the field), the event detail reports every chapter's resolved `card` and the event's `title_card` (the
  read exposure of the title-card part of `look`; the engine's `resolve_card`, probe-free, with `title_card_error`
  and a per-chapter `card_error` instead of a 502 when a hand edit cannot be resolved), `GET /api/v1/fonts` lists the
  registry (D-22), and `POST …/title-card/preview` draws one draft card as an `image/png` with the renderer's own
  `render_card_png` at the event's target resolution (a `video` card as text on transparency; no cache, no ffmpeg, no
  database; at most two at once, 503 with `Retry-After` after 10 s; free text bounded to 200/400 characters on the
  preview only). There is deliberately no CLI subcommand: the engine surface is `auto-reel render` of a `card:` in
  `reel.yaml`. **the card over the clip's start has landed** as `title-card-over-video`, with the editor to
  follow); **the full
  timeline editor, moved from v3** — a per-clip track with proxies, filmstrip, drag-trim in/out and scrub
  preview (built: scrub in `timeline-view`, trim handles in `timeline-trim`, D-20); **analysis review built as overlays on that timeline** (built: approve black/white/freeze trims in place on Edit mode's draft, `timeline-overlay-decisions`;
  not a separate screen); event poster frames (the engine half built, `event-poster-engine`, D-26: the optional `poster:` in `reel.yaml`, a `-poster.jpg` beside the movie and an embedded cover; the picker in the page follows); and, beside the proxy work, chapter times in the render
  manifest (built, change `render-chapter-times`) and a movie version in the event detail (built: the detail's
  `movie` carries the version and the chapter list, change `movie-facts-read`); the chapter jump list of the
  movie player that shows them is built too (change `movie-chapter-list`, D-15). v2 starts with a
  research step: §8.11 (proxies, the PCM-audio path) and the timeline library against D-8's dependency budget.
  Proxy generation is a job of its own kind (`proxy`) in the durable queue: the `jobs` table carries a `kind`
  (default `render`), the one-active-job guarantee is per (project, event, kind) so a render and a proxy job for
  one event may be active together, the store's render-facing reads default to `render` (the API, the WebSocket and
  the CLI answer exactly as before), and the worker dispatches by kind and fails a kind it has no handler for loud.
  The proxy engine has landed as `proxy-encode` (**D-21**): `auto-reel proxies <root>` fills a rebuildable cache of one
  verified 540p H.264 + AAC proxy per clip (plus its `facts.json`) outside the library; the job, the read model, the
  media routes and the timeline screens that use it follow as their own changes (D-18 and D-19 are taken).
  The proxy and filmstrip routes have landed (`proxy-media-endpoints`, §4.9, D-21 "Serving").
  The filmstrip sprites have landed (`filmstrip-sprites`): `auto-reel proxies` also cuts one JPEG sprite per proxied
  clip from the finished proxy's keyframes (`filmstrip.jpg` in the cache entry, its tile geometry in `facts.json`).
  The event detail reports each clip's proxy (`proxy-state-read`, D-21): a `proxy` of state `absent | ready |
  stale | failed` and, when `ready`, its facts and `version`, from the cache entry, never a probe; the list stays
  without it. The timeline opens only for an event whose clips are all `ready`.
  The proxy job has landed (`proxy-job`, D-21): the worker prepares one event's proxies and sprites as a `proxy` job,
  behind renders, so **the timeline opens only for prepared events and preparation is a `proxy` job**.
  The timeline is built in the repo (**D-20**); its pure model has landed (`timeline-model`) and **the read-only
  Timeline has landed on the event page** (`timeline-view`): its own section, closed until opened, a Prepare state
  when a clip has no ready proxy, then one track (ruler, chapter band, clips laid out from the proxy facts, cuts as
  hatched spans, filmstrip, zoom, a scrubbing playhead and Play on one `<video>`). **The analysis overlays have
  landed** (`timeline-overlays`): an analysis lane of suggestion marks under the clips, their state derived from the
  cuts, shown in the read view (D-20, "Analysis overlays"). **Trim handles have landed in Edit mode** (`timeline-trim`,
  D-20): the same section on the editor's draft, a slider at each edge of a cut, saved by the existing Save; the lane
  is mounted there too and shows state from the draft's cuts. **Approving, dismissing and restoring a suggestion have
  landed in Edit mode** (`timeline-overlay-decisions`): Approve adds the suggestion to the draft as a cut with its kind
  as the reason, Dismiss and Restore are the page's set; the read view offers no decision.
  **Title cards are visible on the Timeline and in Edit mode's chapter list** (`title-card-blocks`, D-20): a card lane above
  the clips (a black card is a span of its own before the chapter and adds time; a video card is a block over the start of the
  chapter's first footage and adds none), a card row at the head of each chapter, and one selection shared by both; read
  and select only, the editor of a card is the next changes.
  **A card's length is dragged on the Timeline** (`title-card-duration-drag`, D-20): the end edge of a card block is a slider
  (0.1 s steps, whole-second snap within 8 px, 0.5 s to 60 s, arrows/Shift/Home/End), a black card moves everything after it
  while it is dragged, a video card is held to its footage; one edit of the draft, Reset and Save as for a cut. The typed
  alternative is `title-card-inspector`.
  **Running times are legible and hold still** (`time-readouts-legible`, D-20 and D-16): the Timeline's readout, the clip player's
  header, the trim tip and the movie line are written by one fixed-width clock and say what each number is (`Clip 0:00.96 of
  0:39.84 · Event 1:02.40 of 2:29.76`); web-only.
  `proxy-enqueue-endpoint` has landed (D-21 "Enqueue over REST"): `POST /api/v1/events/{event_id}/proxies` enqueues the
  event's proxy job (201 / 200 `fresh` / 409), and a job reports its `kind` while `latest_job` stays the latest render;
  the timeline's Prepare state is its first web caller.
  **The clip preview plays the preview copy** when the detail says one is ready (`clip-preview-proxy`, D-16 and
  D-21): the first user-visible Firefox fix, since the copy's AAC gives the Sony PCM clips sound there, with an
  explicit Play original for the full file.
  **The clip's player works outside Edit mode** (`clip-play-read-view`, D-16): the event page's read view has a
  Watch control on every clip on disk that opens the same player, read-only.
  **That control is the play button on the clip's thumbnail** (`clip-play-overlay-one-player`, D-16), and one coordinator
  pauses every other playing video when one starts (D-15, D-16, D-20).
  **A clip can be turned** (**D-23**): `clips.<identity>.rotate` is an extra clockwise turn on top of how the clip
  plays, so the engine half (`clip-rotate-engine`) makes the render honour it on every profile; the proxies, thumbnails
  and filmstrips stay the file's (D-21) and are not rotated by the editorial value. **The GUI half has landed**
  (`clip-rotate-ui`): Edit mode has Rotate left and Rotate right on every clip on disk and Rotate marked left / right
  for a marked group, the turn is part of the draft (Reset, Save, "1 clip rotated", a turn of 0 removes the key), the
  read view tags a turned clip ("Rotated 90 degrees" with an icon), and every picture of a clip (thumbnail, clip player,
  Timeline video and filmstrip tiles) shows the turn by a CSS rotation of the picture the service already serves, with
  no cache, endpoint or contract change.
- **v3:** nothing is planned for the GUI: the timeline editor moved to v2 on 2026-10-01, and dragging
  across chapters landed in v1 (D-13, `cross-chapter-drag`; marked groups in v2, `clip-group-select-drag`).

An event's `latest_job` carries the job's `cancel_requested` and `requeue_count`, and a staleness verdict names the
two movie files behind `output_renamed` (`renamed_from`, `output_name`), so the GUI follows a requeue and a pending
cancel from a read alone and says which files a rename concerns.

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
| D | reorder + metadata save | the first write: `ETag`/`If-Match`, 412 conflict handling, the one drag-and-drop dependency — landed in `event-edit-screen` (the event page's Edit mode). `missing-clips-screen` adds the explicit removal of a MISSING clip's entry (never automatic) and holds Render back while an event lists one. `chapter-management-screen` adds the chapter edits (add, rename, move, delete when empty; `chapter-inline-rename` makes a chapter's title the rename control and the event's own chapter's main title card the event title's) and Move clips between chapters (D-13). `clip-cuts-screen` adds a clip's cuts, listed, added from typed times and removed in Edit mode, and shown on the event page (D-14). `cross-chapter-drag` lets a clip be dragged into another chapter (D-13). `clip-preview-screen` plays a clip in its Cuts panel, sets a cut at the playhead, skips cuts as the movie will, and refuses a cut past the length the browser reads (D-16) |
| E | render + live progress | `POST /jobs` (201 / 200-fresh / 409), the WS hook, cancel — landed in `render-progress-screen` |

C, D and E were designed only after A and B had been used against a real library; all three have
landed. `editorial-write-api`, `editorial-read-api` and `gui-event-screen-api-prep` closed the
write precondition and the per-clip file facts. Slice E then needed two more `api/` prerequisites, found
while designing it: `jobs-client-contract` (the published jobs answers, cancel outcomes and WebSocket
frames) and `jobs-project-guards` (the output-collision refusal and project-scoped jobs). Its follow-up
`job-summary-times` gave the events reads' latest job its start and finish times, so a screen dates a
job it knows only from a read by its state. **The
resolved `look`, shown read-only in the v1 sketch above, is not exposed by any endpoint** (v2 exposes its
title-card part only, as the detail's `title_card`, with `title-card-write-api`); it is
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

**`tsc --noEmit` is the frontend gate for GUI v1** — the whole frontend check; GUI v2 adds `npm test`.
Types are generated from the schema, so drift is a compile error, and endpoint behavior is already covered
by `pytest`. There is deliberately **no browser automation in the repo**. `npm test` runs Node's built-in
runner (`node:test`, no added package; `tsconfig.test.json` type-checks the tests) over the pure modules that
hold logic worth unit-testing (for example the jobs store, the dialog's focus rule and the cut times) and the timeline's
model (D-20).

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
   with the §8.11 research). The trim half has landed: `timeline-trim` puts trim handles on the Timeline in Edit mode
   (D-20).
   `job-kind` has landed as the first slice: a `kind` on jobs and a worker that dispatches by it, with no render,
   fingerprint, API or WebSocket change (so no `RENDER_GRAPH_VERSION` bump). Next slice: the timeline's pure model
   (`timeline-model`, D-20), then the read-only view (`timeline-view`, below): GUI v2's first user-visible timeline.
   Then the proxy cache: `proxy-encode` builds it with `auto-reel proxies` (D-21), again with no render,
   fingerprint, API or WebSocket change. `filmstrip-sprites` has landed next: the same command also cuts each
   proxy's filmstrip sprite (D-21), on the same terms. `proxy-media-endpoints` lands the serving half of D-21: two read-only
   routes stream a clip's proxy and filmstrip from the cache (an `api/` change; no render, fingerprint, schema or job change).
   `proxy-state-read` follows: the detail's per-clip `proxy` state and facts (D-21), a cache read with no render,
   fingerprint or WebSocket change.
   `movie-facts-read` follows: the detail's `movie` (version and chapter times from the render manifest), a
   manifest read with no render, fingerprint or WebSocket change.
   `clip-preview-proxy` is the first change that plays a copy: the clip preview
   (D-16) plays the proxy when it is ready, a web-only change with no render, fingerprint, schema or job change.
   `proxy-job` has landed after them: the worker runs the `proxy` kind (D-21), render-first, with `worker.proxy_slots`.
   `movie-chapter-list` is the first user of `movie-facts-read`: the movie player's chapter jump list and the
   movie's version in the facts, a `web/` change only (D-15).
   `proxy-enqueue-endpoint` has landed next: `POST /api/v1/events/{event_id}/proxies`, `kind` on the jobs shapes and the
   WebSocket frames, and per-kind independence over REST (an `api/` change; no render, fingerprint or schema change,
   and no `RENDER_GRAPH_VERSION` bump).
   `clip-play-read-view` follows: the same player opens from the event page's read view, read-only, with
   Watch on each clip (D-16), also web-only and with no render, fingerprint, schema or job change.
   `clip-group-select-drag` (GUI v2) follows: Edit mode marks clips and a drag of a marked clip moves the whole
   marked group (D-13); web-only, no render, fingerprint, schema or job change.
   `title-card-fonts` is the foundation of the card editor (the look editor's title-card half): a bundled set of nine
   title fonts, one registry and an engine-owned fontconfig (**D-22**), with `RENDER_GRAPH_VERSION` 5 and no schema,
   API or web change; the card style, per-card fields, preview endpoint and editor read it.
   `clip-rotate-engine` has landed: `rotate` is an extra clockwise turn on top of the display rotation, applied by the
   engine on every profile (D-23; `RENDER_GRAPH_VERSION` 6). `clip-rotate-ui` has landed (D-23, D-20): the Edit-mode controls, the
   draft and the group turn, the read view's tag, and the turn shown on every thumbnail, player, Timeline video and filmstrip tile
   by a CSS rotation; web-only, no render, fingerprint, schema, cache or job change.
   `time-readouts-legible` follows on user feedback: every running time on the Timeline and in the clip player is written to a
   fixed width by one clock and labelled in words (D-20, D-16), web-only, with no render, fingerprint, schema or job change.
   `title-card-model` has landed (D-24): the optional per-chapter `card:` and the engine that draws it; the write API
   and the editor follow. `title-card-over-video` has landed (the engine half of "text on video"; no version bump):
   a `video` card is attached over the chapter's first segment instead of failing the render. It raised `RENDER_GRAPH_VERSION` to 7, so every rendered event reports
   stale once (reason `engine`).
   `title-card-event-style` (GUI v2) follows `title-card-inspector`: the event-wide card style is edited in the page; web-only, same.
   `chapter-inline-rename` (GUI v2) follows: a chapter is renamed by pressing its title, and the event's own
   chapter shows the main title card, whose title is the event's (D-13); web-only, same.
   `clip-play-overlay-one-player` follows on user feedback: the read view's Play is a button on the clip's thumbnail, and
   one page-wide coordinator pauses any other playing video when one starts (D-15, D-16, D-20), web-only, with no render,
   fingerprint, schema or job change.
   `title-card-write-api` has landed (the API half of the card editor): the editorial `card`, the detail's resolved
   cards and `title_card`, `GET /fonts` and the PNG preview (§4.10); no render, fingerprint, schema-version or job
   change.
   `title-cards-default-on` follows the user's "the opening card and each chapter's card should be created automatically":
   cards are on unless `look.decorators` says otherwise, and the event detail reports `title_cards` (D-25;
   `RENDER_GRAPH_VERSION` 8; `title-card-date-place-shadow` then restored the opening card's date and place and added the
   video-card shadow, `RENDER_GRAPH_VERSION` 9); the Timeline's `unset` guess still has to be replaced by reading it.
   `title-card-blocks` has landed (the web half begins): every chapter's card is a block on the Timeline and a row in Edit
   mode's chapter list, selectable, web-only and read only; editing a card comes next.
   `title-card-duration-drag` has landed (web only): a card's length is dragged on the Timeline's card block, written as
   `card.duration` by the existing `PUT .../reel`; `title-card-inspector` is the typed alternative.
   `title-card-toggle` follows (web only): Edit mode's Title cards On / Off switch writes `look.decorators`, the Timeline and
   the chapter rows read the API's `title_cards` instead of guessing, the opening card is one row, an inherited choice shows
   pressed in a muted style, and the card inspector opens below the track; no API, engine or `RENDER_GRAPH_VERSION` change.
   `event-poster-engine` has landed (the engine half of "event poster frames"; D-26): the optional `poster: {clip, at}` in
   `reel.yaml`, the poster written as `<movie stem>-poster.jpg` beside the movie and embedded as its cover, claimed in the
   render manifest and pruned with its movie; `RENDER_GRAPH_VERSION` 11. No API or web change: the picker follows.
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
  case-insensitive filesystem replaces the old movie, as before.
  *Amended 2026-10-02 (change `render-refuses-claimed-movie`):* the render of another event that now
  has the renamed event's old name no longer replaces the kept movie silently. The collision check
  compares only current paths, so a second rule (`render/claims.py` `claimed_movie`) asks whether
  another event's render manifest records the very file a render would replace; if so the render
  (CLI `render` and the worker, so jobs from the API too) fails that event with a typed error naming
  the file and the claiming event, unless forced (`--force`, a job's `force`). The engine still never
  deletes a movie; removing superseded old-named movies is the operator's call (the command below). A forced render still replaces the file, and the
  renamed event's verdict then cites `output_renamed` for a file that is now the other event's movie.
  *Amended 2026-10-02 (change `prune-renamed-command`):* the engine still never deletes a movie on its
  own. The operator command `auto-reel prune-renamed <root> [--yes]` removes superseded old-named
  movies: dry run by default, and only after the event's new movie exists. The render manifest
  records the names a rename superseded (`superseded`, optional, schema version 1), and the command
  never deletes a file another event's manifest or expected path claims.
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
  *Amended 2026-10-03 (change `render-chapter-times`):* the manifest also holds the last render's chapter
  times (`chapters`: per chapter its name, start and end in milliseconds in the movie, and its title-card
  span or `null`), computed from the measured segment durations by the rule that writes the `[CHAPTER]`
  markers. It is additive at schema version 1, `null` for a movie rendered before the field or adopted
  without a render, and never a fingerprint input.
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
  - **A page-level note** (2026-10-02, change `web-playback-and-notices`). A thumbnail that fails to show makes
    one further request for its address, to read why. When three or more on the page fail with the same
    cause that is the service's and not the clip's (a 502 with neither `thumbnail_failure` nor an event
    `failure`: its cache or `config.yaml`), the page shows one quiet note, "Previews are unavailable",
    pointing to `auto-reel thumbs`.
    A clip's own failure never raises it; the rows keep their "No preview" box. (§4.10)

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

  *Amended 2026-10-02, change `chapter-name-rules-engine`:* the folder matches a chapter by its exact name
  first, then by `str.casefold()`, and the clip is listed under the chapter's own name, so a folder `party/`
  reaches the chapter `Party`. Chapter names are casefold-unique (§4.6), so at most one chapter matches. A
  folder name with leading or trailing whitespace is never trimmed to find a chapter: it falls to the default
  chapter. Seeding or adopting folders that differ only by case, or a folder with padding, fails loud
  instead of writing a `reel.yaml` that no longer loads. (§4.6)

- **D-13 — Chapters are edited in GUI v1** (2026-10-01, change `chapter-management-screen`). Edit mode adds,
  renames, reorders and deletes chapters, and moves clips between them with a per-chapter Move clips
  dialog, pulled forward from v3 at the operator's request. Dragging a clip into another chapter
  followed in `cross-chapter-drag` (2026-10-01), at the operator's request, beside Move clips: any position,
  an empty chapter too, by pointer and keyboard. In `clip-group-select-drag` (2026-10-03), at the operator's
  request, a drag of a marked clip takes every marked clip, to the drop position, in one edit, and Move clips
  has a Pick marked button. A missing clip stays in its chapter. A save that
  changes the chapter list writes every chapter as shown, so every NEW clip is adopted where the page shows
  it; a chapter's name then only decides where later clips go (D-12). The event's own chapter keeps no name,
  and a chapter is deleted only once empty. The page follows the engine's chapter-name rules
  (2026-10-02, change `chapter-name-rules-web`, after the user's answer "Enforce in engine" and
  `chapter-name-rules-engine`): it strips a typed name as Python's `str.strip()` does, refuses an empty one,
  compares names and folders under `str.casefold()` (a generated full-case-folding table, no dependency), and
  keeps only `Main` as its own reservation. Amended 2026-10-03 (change `chapter-inline-rename`, at the
  operator's request): a chapter is renamed at its title, a button with a pencil that turns into a text field
  (Enter or leaving it keeps the name, Escape drops it); there is no Rename button or dialog. The event's own
  chapter keeps its name `Main` (or `Clips`) and shows the main title card under its heading: renaming it
  edits `metadata.title` in the same draft as the metadata form's Title field, so the two stay in step, and a
  changed title says that saving changes the movie's file name (D-9). Add chapter keeps its dialog.
  (§4.10)

- **D-14 — Cuts are edited by typed times in GUI v1** (2026-10-01, change `clip-cuts-screen`). Edit mode
  lists, adds and removes a clip's cuts (D-D), with times typed as seconds, m:ss or h:mm:ss, pulled forward
  from v3 at the operator's request. A clip's preview followed in GUI v1 (D-16). Scrubbing (`timeline-view`) and
  drag-trim (`timeline-trim`) are the v2 Timeline's (§4.10, D-20, built 2026-10-03). The page refuses what the engine refuses (`out <= in`, negative), and
  refuses an overlap with another cut. It refuses a cut past the clip's end when it knows the length: from
  the clip's preview in that Edit mode (D-16), else from the duration the event detail gives the clip (§4.9,
  `api-clip-duration`); otherwise it states the render's rule instead (cut short at the end; a whole-clip cut
  leaves the clip out and moves its chapter's title card to the next clip that plays). A cut made in the GUI has the reason `manual`. The event page shows each clip's cuts.
  The refusal of a new overlapping cut is an editing aid, not an engine rule: `reel.yaml` and the engine accept
  overlap and join overlapping or touching cuts as one removal, and cuts already overlapping show as their
  union. (§4.10)

- **D-15 — The event page plays its rendered movie in GUI v1** (2026-10-01, change `movie-player-screen`). The
  event page's read view shows the movie the staleness gate counts (`GET …/movie`, `media-endpoints`) in the
  browser's native player, says whether it is current or outdated, and names its file and size. It loads none of
  the movie until Play (`preload="none"`; the poster is the first played clip's thumbnail). Its address carries
  the file's entity-tag as `v`, read with a one-byte range request on each read of the event, because Chrome
  fails to play a replaced file at an address that served the old one (the proxy routes of D-21 follow the same
  rule: their `ETag`, read with a `HEAD`, is the `v`). Failures are said by cause, including a
  picture the browser cannot show (a legacy MPEG-4 movie plays its sound only). There are no custom controls or
  shortcuts and no captions: browsers expose no chapter times. Amended 2026-10-03 (change
  `movie-chapter-list`): the section lists the movie's chapters under the player as a jump list when the event
  detail's `movie.chapters` gives two or more it can rely on (the times `render-chapter-times` records, read by
  `movie-facts-read`; none computed on the client, and none for a movie whose manifest predates them). A button
  seeks to the chapter's start and plays, also before the first Play (the seek waits for `loadedmetadata`
  under `preload="none"`); the current chapter is marked in words and an icon, following `timeupdate` and
  `seeked`, never announced; an outdated movie's list says "As rendered". The facts also say "Recorded {time}
  · version {fingerprint}" from `movie` (the record's time, not the render's finish: an adopted movie's is its
  adoption). A Refresh
  keeps the player (the same element, playing or paused, while the rest of the page reads; 2026-10-02,
  change `web-playback-and-notices`); Edit mode shows no movie, and entering it ends
  playback. Amended 2026-10-03 (change `timeline-view`): the read view's Timeline section (D-20) holds a second
  `<video>` once opened, so the page may hold two; **one plays at a time** (`playback/exclusive.ts`: each
  claims playback on `play` and the other is paused), and the movie still loads nothing before Play. Amended
  2026-10-03 (change `clip-play-overlay-one-player`): the movie player is paused by any other video's start, through
  the page's one coordinator (`playback/coordinator.ts`), which replaced `exclusive.ts`. (§4.10)

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
    for that clip, while Edit mode stays open, and wins over the detail's duration (the probe's number, from
    the thumbnail sidecar) because Set From and Set To write times in it. A clip with neither (no preview,
    no thumbnail yet) keeps D-14's rule. Measured on five files: Chrome's length equals ffprobe's, and Firefox's runs up to 60 ms
    longer, never shorter, so the check never refused a cut the render keeps in full.
  - **What stays v2.** Firefox plays PCM audio silently (52 % of the archive), and the preview says so. Proxies
    and the PCM audio path landed as D-21; **scrubbing landed with the Timeline** (`timeline-view`, D-20) and **drag-trim
    with its trim handles** (`timeline-trim`, D-20), which play the proxy, so they have sound in Firefox, while the
    original in this preview stays silent there with the note above.
  - **Amended 2026-10-03, change `clip-preview-proxy`: the preview plays the preview copy.** When the event
    detail gives a clip's proxy as `ready` with a duration above zero in its facts, the preview plays the copy
    (the proxy contract, D-21: 540p H.264 + AAC at the original's media time) from `…/proxy?clip=&v=<tag>`, the
    tag read by one `Range: bytes=0-0` request when the preview opens (D-15); otherwise it plays the original
    exactly as above, with a line under the picture saying which plays and why. **Play original** / **Play preview
    copy**, a last control after Set To, swaps the file under the playhead (time kept, playing or paused kept,
    announced); the choice follows the clip to another chapter and is forgotten when the preview closes.
    Set From, Set To and Skip cuts act on the playhead of whichever file plays, since proxy time is source time.
    **The length** while the copy plays is `facts.duration` (the original's, as the engine probed it), not the
    browser's reading of the copy, which differs by about 20 ms and can be shorter (a 1080p50 copy read 24.981 s
    for a 25.003 s source): the "never shorter" guarantee above holds for the copy too. The no-sound note belongs
    to the original and, with a ready copy, points at Play preview copy. A copy that cannot play is told by cause
    (gone, unreadable, empty, refused, no answer) and never as "changed on disk" (the copy's `Last-Modified` is the
    copy's file), with Play original beside Try again; the page never switches by itself. **So "What stays v2"
    no longer lists Firefox's silent preview for a clip with a ready copy:** the original still plays silently in
    Firefox, which is why the copy is offered first. The preview itself builds no copy: the Timeline's Prepare state (`timeline-view`, D-20) is the page's one caller of `proxy-enqueue-endpoint`.
  - **Amended 2026-10-03, change `clip-play-read-view`: the read view plays a clip too.** On the event page
    outside Edit mode, every clip on disk has Watch / Hide player, which opens the same component in a row under
    the clip's row, read-only: no Set From / Set To, the clip's cuts drawn on the bar as the page reads them,
    Skip cuts as a view option, and "Press Refresh" in place of "stop editing" after a clip that is gone or
    changed. One player is open at a time, and nothing is loaded before a press, on a 400-clip event too. Unlike
    Edit mode, the read view also shows the Movie player (D-15), so a video that starts pauses another that plays
    (`events/onePlayer.ts`; nothing is closed). A quiet re-read leaves an open player playing; a replaced clip
    continues paused at the same time; a copy built meanwhile is used by the next open, not by the open player.
    The thumbnail is not a Watch button here. The bare `<video>` is no longer a tab stop (Firefox made it one).
  - **Amended 2026-10-03, change `clip-play-overlay-one-player`: the read view's Play is a control on the thumbnail.**
    On the operator's request ("Watching a clip should be a play button on the clip"), the read view's Watch button
    is gone from the file cell: the clip's thumbnail carries the control, a button over the whole frame with a play
    glyph in a disc, named "Play <name>" and, while the player is open, "Hide player of <name>" (so it never shares a
    name with the player's own "Play <name>" / "Pause <name>"). The glyph is seen on hover, focus, while open and
    always without a fine hovering pointer; opening, one player at a time and focus on Close are as above. Edit
    mode's thumbnail stays its "Watch <name>" button. One coordinator, `playback/coordinator.ts`, installed once in
    `main.tsx`, replaces `exclusive.ts` and `events/onePlayer.ts`: it pauses every other playing `<video>` when one
    starts, with no player named and no player closed or seeked, so a thumbnail's start, the Movie section, Edit mode's
    preview and the Timeline are covered alike. A player does not play by itself when it opens; the coordinator sees
    its Play.
  - **Amended 2026-10-03, change `time-readouts-legible`: the header says what its numbers are and holds still.** The
    player's time reads `Clip 0:20.48 of 0:20.64` (the clock of D-20: two decimals, written to the scale of the clip's
    length), where it read `0:20.476 / 0:20.64` in a `15ch` box that was shorter than its text; before the browser has
    read the length it reads `Clip 0:00.00 of -:--.--`, and the first cell does not change width when the length
    arrives. The slider's value text, "Set From" and every announcement keep the Cuts panel's form (`0:01.234`): a cut
    is typed and spoken to the millisecond, and the header is a where-am-I, so the header shows `0:02.60` where Set From
    writes `0:02.607`.
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
- **D-19 — A stalled render fails and a cancel kills ffmpeg** (2026-10-02, change `render-stall-watchdog`).
  A render whose ffmpeg is alive but not progressing used to hold its job `running` forever, and `cancel`
  was read only between segments (D-S5/D-S6).
  - **In-process, no heartbeat.** `FfmpegRuntime.run_with_progress` kills ffmpeg when its reported output time
    has not strictly advanced for `SEGMENT_STALL_TIMEOUT_S` (10 minutes, a constant in `render/orchestrator.py`,
    counted from launch) and raises `FfmpegStalledError`; the job ends `failed` through the ordinary path, with
    no output and no manifest. A slow but advancing encode is never killed. The same loop polls `should_cancel`
    about once a second and raises `FfmpegCancelledError`, which the render layer turns into
    `RenderCancelledError` (`canceled`).
  - **The kill is bounded.** After it the runtime waits `KILL_GRACE_SECONDS` and then abandons a process the
    kernel will not release, logging its pid, so the failure is not itself a hang.
  - **Never retried.** A stall is not retried in software (a retry would double the wait), whatever its stderr said.
  - **Deferred.** A `jobs.heartbeat_at` column, a reaper and a worker registry wait for multi-worker support;
    the final concat and the ffprobe calls are not watched (the opt-in `timeout` of `run`/`run_ffprobe` is the
    route); reconcile still assumes one worker. No `RENDER_GRAPH_VERSION` bump: nothing that finished changes.
- **D-20 — The timeline is built in the repo, on a pure model in whole milliseconds** (2026-10-03, change
  `timeline-model`, the first slice of GUI v2; the research calls this decision D-18, a number the bug round
  took, and the proxy contract it calls D-19 is **D-21**, recorded by the proxy changes). (§4.10) A chapter's title
  card (**D-24**) is the timeline's later block: the card model is in `reel.yaml` before the timeline shows it.
  - **The chapter band reuses the chapter list's rule.** `usableChapters` (`web/src/movie/chapters.ts`,
    `movie-chapter-list`) decides whether the detail's chapter times may be relied on; the timeline's chapter
    band calls it rather than a second check.
  - **No timeline library.** The timeline lives in `web/src/timeline/`, on React and plain CSS, generalising
    D-16's cut bar. `@dnd-kit` stays for reordering only (it has no value semantics and re-renders every
    consumer per move). D-8's dependency list is unchanged. Evidence (`research/v2/timeline-library.md`): none
    of nine libraries models source-clip cuts, the three run in a browser exposed no keyboard path, and the
    nearest, `@xzdarcy/react-timeline-editor`, costs +68.5 KB gz; the in-repo prototype is +5.6 KB gz JS and held
    60 fps drag and scrub up to 400 clips at 4x CPU throttle, with 22 of 22 functional checks in Chrome 154,
    Firefox and WebKit. The pointer maths a library saves is about 110 lines; the keyboard and touch layer is
    the costly half and no library has it.
  - **The model is pure, in whole milliseconds, and takes its facts as arguments.** `model.ts` has time and
    pixel conversion, frame rounding at a clip's own rate (the time of frame *n* is `round(n * 1000 / fps)`),
    layout, zoom (4 to 240 px/s), windowing by binary search (the cost does not grow with the clip count), a
    clip's cut spans (reusing `skipSpans`, the client twin of the render's `kept_spans`), trim limits and
    snapping (8 px). A clip's duration and frame rate have no default and throw `ModelError` when missing: the
    events read is probe-free (§4.9), so they come from a proxy's `facts.json` (D-21), which is why the timeline
    opens only for an event whose proxies are prepared. A cut stays three frames long, measured so that its
    limits are frame times (the prototype's `MIN_CUT = 0.1` was not, and Home on a handle returned 0.12 s); a
    cut's number is its place in the list plus one, the Cuts panel's and `playheadWords`' number (the model has
    no second numbering by start; the prototype named two handles "cut 1 start"). Variable frame rate is not
    modelled.
  - **The filmstrip's geometry is read, never recomputed** (`filmstrip-sprites`, 2026-10-03). A clip's tiles come
    from the proxy entry's `facts.json` `filmstrip` object (D-21): tile size, columns, rows, tile count, interval
    and the sprite's size; tile `k` sits at column `k % columns`, row `k // columns`.
  - **Tests are the existing runner.** `npm test` (Node's `node:test`, type-checked by `tsconfig.test.json`),
    not vitest: no package is added. This is the proposal §4.10 asked for when it said a slice with logic worth
    unit-testing would propose a runner; the runner was already there.
  - **First slice (planned; the view in `timeline-view`, trim in `timeline-trim`, the overlays to come).** Trim of existing cuts and the analysis overlays on one timeline; one `<video>` whose `src`
    is swapped at clip boundaries (a short flash is accepted); reorder and cross-chapter moves stay list-based;
    no waveform lane.
  - **First slice, built (change `timeline-view`, 2026-10-03): the read-only Timeline.** Its own section of the
    event page's read view, between the Movie section and the chapters, with an Open / Close button; **not an entry
    to Edit mode**, which owns the draft, the Save bar and the unsaved-edits guard, while this slice writes nothing
    (`timeline-trim` mounts the same component there, below; it takes the cuts as a prop for that reason). It is
    closed until opened (no `<video>`, no media request, whatever the clip count), and closed again after a Refresh. **The layout comes from the proxy facts** (`duration`, `fps_num / fps_den`), never from
    the browser's length or a default rate; a clip is *ready* only with a `ready` state, usable facts and a tag
    (`version`) for its addresses. Until every shown clip is ready the section shows a **Prepare state** in the
    track's place: the counts by state, "Prepare proxies" (`POST …/proxies`, one request per press, the only way the
    page starts the job) and the `proxy` job's progress from the jobs socket the page already holds. Opening never
    starts it. A `stale` proxy is a damaged cache entry; **a source that changed on disk moves the cache key and
    reads as `absent`**. The track has a ruler, a chapter band drawn from the event's chapters (the movie's recorded
    chapter times, `usableChapters`, are a different list and are not used), the clips end to end with their
    filmstrips, `reel.yaml`'s cuts as read-only hatched spans (a pattern per reason, so no state is by color alone),
    zoom (4 to 240 px/s, Fit, keys), and windowing by the model's binary search: 400 clips of 25 s hold 23 clip
    elements at the lowest zoom. **One `<video>`** swaps `src` at clip boundaries; a **seek coalescer** keeps one
    load or seek in flight and always ends at the last target; a seek goes a quarter frame into the wanted frame.
    The playhead is a slider (a frame, a second, five seconds, Home, End, Space) and its grip is dragged like the
    ruler. Play follows the presented frames (`requestVideoFrameCallback`) and reuses D-16's cut rules, then goes on
    into the next clip; a clip all cut is skipped and a leading cut is passed. The Timeline plays the proxy, so it has
    sound in Firefox (a decoded peak above zero on the Sony PCM clip). **One video plays on the page**
    (`playback/exclusive.ts`). A `proxy` job is never shown as a render: `jobs/kinds.ts` (`job-kind`) keeps the
    render region, list rows and header count to renders, and the Prepare state shows the proxy job in its own words
    ("Preparing proxies", "Proxy progress"). What stays: the approval and dismissal of suggestions on Edit mode's draft
    (the lane's `decide`), a second preloaded `<video>` for seamless boundaries, undo.
  - **Measured on the shipped proxy** (Chrome 154.0.8037.92 and Firefox 155.0, ten real clips, one from each archive
    class, proxies made by the Prepare button and a real worker). **Quiet host** (the review's re-run, load average
    0.5 to 2.1 on 16 cores, two runs each): scrub, median frames per second over 50 sweeps of 2 s (gate: 30): Chrome
    57.4 and 57.4; Firefox 49.5 and 50.0. Frame step, p90 of 160 key presses to the presented frame (gate: 60 ms):
    Chrome 39.1 and 39.5 ms; Firefox 33.1 and 33.1 ms. Every number is inside its gate. The first frame after a clip
    change takes a median 45 and 37 ms (Chrome) and 33 ms (Firefox). **Busy host** (the first runs, three each, the
    shared host never idle: load average 2 to 13, swap full): scrub Chrome 38.6, 42.4 and 54.7, Firefox 46.7, 36.5
    and 46.7; step Chrome 46.2, 49.2 and 40.3 ms, Firefox 61.9, 40.0 and 34.1 ms, so Firefox's first busy run missed
    the step gate by 1.9 ms at a load average of 4 to 13. The hard sources are the expected ones: 4K50 and 1080p50
    steps reach a single-run p90 of 81 ms (Chrome) and 93 ms (Firefox) when the host is busy. A decoded audio stream
    in Firefox's test container needs about 1.9 s to start after Play or a seek (a bare `<video>` with no page code
    does the same, and a muted one does not), so the timing checks of Play ran muted and the sound check ran
    unmuted.
  - **Bundle (`timeline-view`).** `npm run build` on `origin/main` and on this change: JS 452,810 to 485,274 bytes
    (144,579 to 155,026 gzip -9, +10.4 KB) and CSS 56,929 to 62,914 bytes (11,221 to 12,205 gzip -9, +1.0 KB); no
    package added. The research prototype's whole interaction layer was +5.6 KB gz; this slice also holds the Prepare
    state, the jobs-by-kind words and the video controller. `npm test` runs 343 tests (252 before).
  - **Bundle (`timeline-overlays`).** `npm run build` before and after: JS 489.10 to 502.98 kB (157.64 to 162.39 kB gzip,
    +4.8 KB) and CSS 63.42 to 67.16 kB (12.47 to 13.06 kB gzip, +0.6 KB); no package added. `npm test` runs 438 tests (365 before).
  - **Bundle (`timeline-model`).** The model is not imported yet, so it is not built: `npm run build` on `origin/main` and on this
    change gives the same two files (same hashes), JS 444,745 bytes (142,313 gzip -9) and CSS 55,606 bytes
    (11,051 gzip -9) in both, a delta of 0 bytes.
  - **Analysis overlays** (`timeline-overlays`, 2026-10-03). The read view's Timeline shows the event's cached analysis
    (`GET …/analysis`, read once when the track is shown, never while the section is closed or preparing) as an
    **analysis lane**: a row of the canvas under the clips, a group per clip in the window holding one button
    per suggestion, placed by the model's time-to-pixel mapping, at least 44 px wide, close marks stacked on rows
    (stacked over the whole track, so the end of one clip's mark and the start of the next never hide each other, and the lane's height holds as the track scrolls), one tab stop per clip with the
    arrows, Home and End. **A suggestion's state is derived from the clip's cuts, never stored:** `cut` when the
    cuts not removed, joined as the render joins them, cover its span to the millisecond, `partly-cut` when they
    share more than an instant with it, `dismissed` when this page visit dismissed it and no cut touches it, else
    `pending`. The prototype stored the state and read "approved" for footage the movie still plays; here removing
    a cut (a handle, the Cuts panel, Undo) returns the mark to pending with no bookkeeping, and a cut saved
    earlier shows its suggestion as cut on the first read. **Approval (designed here, mounted on Edit mode's draft by `timeline-overlay-decisions`) is `cut-add` with the suggestion's kind as
    the reason**, through the Cuts panel's `checkCut` (an overlap is refused naming the cut, a span past the
    clip's end is refused, nothing is silently merged), in Edit mode's draft: one Save, one `If-Match` write, one
    undo model. **Dismissal is for this page visit only:** `reel.yaml` has no field for a rejection and a
    browser-side memory would differ per device and go stale when the cache is rebuilt, so the set lives in
    `EventDetail` (above the read view and Edit mode, because the section is closed by every Refresh and switch)
    and is gone on reload; the lane says so. **A and R act only on a focused mark**, never from a document
    listener (so "a" in the title field decides nothing), and not with Ctrl, Meta or Alt, on a repeat or during
    an IME composition; every decision is also a labelled button in the detail under the track (the route on
    touch). Kind is an icon and a word, state a glyph (`?` `✓` `◐` `×`) and a word, never colour alone. The three
    kinds of "no suggestions" are told apart, from the entries and not the service's `analyzed` flag (which is true
    for any event whose cache directory exists, and a render's manifest creates it): no clip has an entry (never analysed,
    with the command), entries and nothing found, and a clip with no entry among others that have. Analysis is never
    started from the page. A legend under the lane spells out the icons and glyphs. Deciding needs the Timeline on
    Edit mode's draft, so the lane takes an `analysis` value whose `decide` is null in the read view, where it offers
    no decision and no note about one; the decision rules (`decideApprove`, `decideDismiss`) are pure and tested.
    The requirements for them are in `event-timeline`, written by `timeline-overlay-decisions` (below).
  - **Prepare enqueues the proxy job** (`proxy-job`): the timeline's Prepare state enqueues the D-21 `proxy` job for the event; a render does not wait for it. It calls `POST /api/v1/events/{event_id}/proxies` (`proxy-enqueue-endpoint`) and follows the job on the WebSocket, whose jobs carry `kind`.
  - **Trim handles (change `timeline-trim`, 2026-10-03): the same Timeline in Edit mode, on the draft.** Edit mode mounts
    the one `TimelineSection` after the metadata form, closed until opened, with `editing` set: its cuts are the draft's
    (`liveTrims`), so a cut added, removed or restored in a Cuts panel is on the track at once and Play skips a trim before
    it is saved; its clips, chapters and proxies are the page's last read (a Prepare job that ends in Edit mode reads the
    event again, `withVerdict` keeps that read as `live`, and the draft is not touched) in the **saved order**, with a note
    while the draft has moved or renamed anything (reorders stay list-based). Each cut of a clip drawn with its cuts gets
    **two handles that are sliders, not draggables** (`role="slider"`, `aria-valuenow/min/max` from the model's limits, a
    value text in the Cuts panel's time format; `@dnd-kit` stays for reordering only): drag by the distance moved, snapping
    within 8 px to the clip's ends, the other cuts' edges and the playhead (a line and words, "Snapped to cut 2 start"),
    Left/Right a frame, Shift a second, Page Up/Down five, Home/End to the limits, Enter at the playhead; 24 px areas, 44 px
    under a coarse pointer, extending outward from the cut, and where two overlap the press goes to the nearer edge. While an
    edge is in the air it lives in a small external store and only its handle, the live span and the selected cut's fields
    read it; **the draft gets one edit on release** (`trimCut`), a key press is its own edit. The selected cut's Start and
    End fields (typed, through the Cuts panel's own `checkCut` with the cut itself taken out) are the non-dragging
    alternative and stay in step. **`draft.ts` had no operation that edits a cut**, and its "back to what was read" test
    compared keys only, so a trim would have been dropped as unchanged: `trimCut` keeps the key, place and reason, marks a
    read cut `edited` while its times differ (an Undo over it is refused as over an added cut), `settled` compares times,
    and the save bar counts "1 cut trimmed". Save is the existing whole-document `PUT` under `If-Match`; the service edits
    only the span that differs and keeps its comment. **One video in Edit mode**: a clip preview and the Timeline's video
    release each other through the editor's preview store (a preview open: the Timeline renders no `<video>`, keeps its
    playhead and handles; a scrub or Play closes the preview and creates the video at the playhead).
  - **The frame grid decides the numbers.** The model's limits are frame times, so on a 50 fps proxy (the dev library's
    clips) three frames are 60 ms and the cut 1.0 to 2.5 s has a start range of 0 to 2.44; on a 25 fps proxy it is 2.36,
    and "+1 s" from 2.5 s lands on 3.52. A typed time is not rounded.
  - **Measured with handles on the track** (Chrome 154.0.8037.92 and Firefox 155.0, the four-sample event of the timeline
    gates, 16 handles, in Edit mode; the host was busy, load average 2.5 to 15). Scrub median: Chrome 43.5, Firefox 35.7 fps
    (gate 30; the 4K50 sample alone 42.4 and 26.0). Frame step p90 of 160 presses: Chrome 37.8, Firefox 34.1 ms (gate 60).
    First frame after a clip change: median 40.5 and 33.7 ms. **Drag** (the research's measure: 180 moves, a handle at 40 px
    per second, frames longer than 25 ms; the page settled, since the editor's thumbnails shimmer for about ten seconds
    after a load and cost every frame meanwhile): 80 clips, 4x CPU throttle, Chrome, five runs: 0.37, 0.56, 0.75, 1.12 and
    1.12 % of frames (gate 2 %); no throttle: 0 of 360 frames in three Chrome runs and three Firefox runs. **400 clips at
    4x is outside the gate here: 6 to 25 % (median 16 %)**, and the playhead's existing scrub on the same page shows 14 to 16 %.
    The cost is the page, not the handle: the editor's 400 list rows (about 19,000 elements) are repainted per move; with
    the lists hidden the drag is 0.3 %, with `content-visibility: auto` on `.clip-item` 0.4 and 0.9 %, and at no throttle it
    is 0 % in both browsers. That rule is the lists' to adopt (their drag-and-drop measures rows), so it is a follow-up,
    not part of this change. Windowing: at the lowest zoom of 400 clips the section holds 93 clip elements and 186 handles,
    scrolled to the middle 140 and 280 (a view each side), 1,474 elements in all. **The clip's length at a cut's end** is the
    proxy's `facts.duration`, which is the source's: the Sony, the rotated HEVC (14.633333 s; the proxy's container says
    14.651995 because its audio runs 18 ms longer) and the legacy MPEG-4 (756.5 s) match ffprobe to the microsecond, so End
    does not leave a sliver of footage.
  - **Title card blocks (`title-card-blocks`, 2026-10-04).** The Timeline gains a card lane directly above the clips, from the
    detail's resolved cards and `look.decorators` (read from `reel.yaml`; in Edit mode the baseline's). `cards.ts` is the pure
    model: `cardPlacements` follows the render (anchor = the chapter's first shown clip, or the next with footage when the
    first is wholly cut; a video card starts at the end of a cut that begins at zero and is clamped to the first kept span; a
    black card adds its length), `cardMap`/`trackX`/`clipTimeAt` are the track map, **clip time stays the one time of the
    playhead, cuts, handles and marks** and only drawing is shifted, and the selection is a reducer by the chapter's saved
    name. Honest limits: the Timeline plays footage only (the playhead crosses a black card without time passing and a press
    in its span selects the card), the anchor is the first shown clip (an explicit `title: true` elsewhere in the chapter is
    not in the detail), and the readout's "Event" time counts black cards. **Bundle:** JS 539,223 to 551,338 bytes (173,912 to
    177,719 gzip -9, +3.8 KB), CSS 76,068 to 79,203 (14,391 to 14,913 gzip -9, +0.5 KB); no package added.
  - **Title card length by drag (`title-card-duration-drag`, 2026-10-04).** The card handle reuses the trim handle's parts:
    the same drag store (one drag at a time across both, with a second slot for the card edge), the slider role, the
    delta-from-where-the-edge-was rule, the 8 px snap (to whole seconds here), Escape, the lock while a save or Move is pending
    and the clock's fixed-width cell (`tenthsCell`). The unit is an integer number of tenths (`cardLength.ts`, pure,
    `node:test`), so no float reaches the draft or `reel.yaml`. **Mirrored bounds:** the web has two constants for the engine's
    `CARD_MIN_DURATION` and `CARD_MAX_DURATION` (0.5 s, 60 s) and a test reads `reel/card.py` and fails when they differ; the
    server stays the authority (a refused value is a 400 on Save). A video card is bounded by the first kept span of its
    anchor clip, the footage the engine attaches it to, from the draft's cuts, so a trim edited a moment ago already counts; a
    card longer than its footage keeps its value and can only be dragged down. A release is one edit of the
    card's `duration` in `Draft.cards` (`setCardLength`; a length equal to the one read is no override), so Save, Reset and
    the save bar are the inspector's own; the live drag lays its length over the specs (`withDurations`); a
    black card's drag keeps the committed layout, moves the layers behind the card by a `translate` (`data-after`) and draws
    the real layout once, on release. The handle lies in the card lane, a row of its own,
    so it never competes with a trim handle's area.
  - **The card lane reads `title_cards.enabled` (`title-card-toggle`, 2026-10-04).** The page no longer infers whether the
    render draws cards from the event's `look.decorators` (the project's `config.yaml` look is invisible to it): `cardsEnabled`
    takes the detail's `title_cards` and the draft's Title cards switch while it differs; the model's `unset` state and the
    "not counted" caveat are gone, and `title_cards: null` draws no block and says the service's `title_cards_error`.
    The card inspector is rendered after the Timeline's body, so selecting a card (from a block, a row or a duration
    handle, which selects again) never moves the track.
    **Drag cost, measured** (80 clips, 8 cards, 180 pointer moves at about 46 px/s, frames over 25 ms): the first build re-laid
    out the later content on each move and measured 9 to 24 % in Chrome at 4x (a loaded host), so the translate-and-commit-on-
    release build above replaced it. Now: unthrottled, Chrome 154 0 to 0.27 % and Firefox 155 0 to 3.2 % (median 0.8 %, nine
    runs); at the 4x throttle Chrome 1.3 to 12.4 % over eleven runs, median 3.1 %, on a shared host where the same page idle
    measures 0.5 to 3.7 % (load 2 to 6); a video card's drag, which also changes one block, 4.7 %. Gate: median 5 % (Chrome
    4x) and 2 % (Firefox), against the idle figure of the session.
    **Bundle:** JS 557,109 to 568,205 bytes (179,516 to 183,002 gzip -9, +3.5 KB), CSS 80,426 to 82,278 (15,165 to 15,330
    gzip -9, +0.2 KB); no package added.
  - **Bundle (`timeline-trim`).** `npm run build` on `origin/main` (with `timeline-overlays`) and on this change: JS 502,976 to
    521,304 bytes (160,932 to 167,683 gzip -9, +6.6 KB) and CSS 67,163 to 70,886 bytes (12,883 to 13,539 gzip -9, +0.6 KB); no
    package added. The research prototype's whole interaction layer was +5.6 KB gz. `npm test` runs 495 tests (438 before).
  - **Decisions on Edit mode's draft (change `timeline-overlay-decisions`, 2026-10-03).** The lane's `decide`, null in both
    modes until now, is built in Edit mode from the editor's binding by the pure `decideControl` (`EditBinding.onAdd` is
    `cutHandlers.onAdd`, the Cuts panel's own add); the read view's binding is null, so it still decides nothing. **Approve**
    (button, or **A** on a focused mark) adds the suggestion to the draft as a cut with its kind as the reason, through
    `checkCut`: the save bar counts one cut added, Save writes the trim `{in, out, reason}` by the existing `If-Match` write,
    and removing the cut or Reset returns the suggestion to pending (state is derived, not stored). An overlap (a partly cut
    suggestion included) or a span past the proxy's end is refused in the panel's words with nothing added. **Dismiss** and
    **Restore** (**R** toggles) are the page's set, no edit, no Save, no unsaved-changes guard, and survive leaving Edit
    mode, Refresh and Save, not a reload. While a save or a Move clips is pending the buttons are `aria-disabled` and the
    detail says so in words, and the keys are left to the browser. Verified in Chrome 154.0.8037.92 and Firefox 155.0: 86
    of 86 checks each, light and dark at 1280 and 390 (and 320), the detail buttons' tap area 44 px under a coarse pointer,
    button text contrast at least 5.65:1 (light) and 7.03:1 (dark), no horizontal page scroll. **Measured with decisions
    mounted** (Edit mode, four 6 s real clips, 8 marks, 3 approved cuts and 2 read ones, 10 handles; host load average 0.6 to
    1.7): scrub median Chrome 55.2, Firefox 51.2 fps (gate 30); frame step p90 of 160 presses Chrome 20.7, Firefox 22.9 ms
    (gate 60); first frame after a clip change median 31.0 and 33.4 ms.
  - **A mouse press without pointer events is handed over too (fix, `timeline-overlay-decisions`).** The one failure of
    `timeline-trim`'s browser run (Firefox, "a mouse press handed to the focused winner selects the winner", 39 of 40) was
    reproduced by logging the event order: with a normal context Firefox 155 fires `pointerdown` and behaves like Chrome,
    but under touch emulation (`has_touch`, `is_mobile`) it delivers a mouse press as `mousedown`, `mouseup` and `click`
    only, so the press never reached the hand-over by position and the browser's own focus move selected the handle on top.
    A `mousedown` that no pointer sequence accompanies (`bareMousePress`, pure) is now prevented and handed to the nearer
    edge as a pointer press is, selecting and focusing the handle that took it; it starts no drag. The `two_neighbours`
    case that failed (6 of 7 before) passes (7 of 7), and the rest of that file passes in both browsers (34 of 34 in Firefox,
    38 of 38 in Chrome; its 400-clip windowing group was not re-run, the windowing being untouched).
  - **Bundle (`timeline-overlay-decisions`).** `npm run build` on `origin/main` and on this change: JS 521,304 to 522,394
    bytes (167,683 to 168,013 gzip -9, +0.3 KB), CSS unchanged (70,886; 13,539 gzip -9); no package added. `npm test` runs
    516 tests (495 before).

  - **Running times are written by the clock, not by `formatTime`** (change `time-readouts-legible`, 2026-10-03). The user
    watched the Timeline play and said the numbers "jump", "get shorter" at a single digit, and that they did not say what
    they were. Cause: every readout was written by `formatTime`, the Cuts panel's form for a cut's time (typed back and
    parsed, so it drops a trailing zero: `1:02.4`, `0:01`), which is right for a cut and wrong for a time that changes
    several times a second. `web/src/clock.ts` (pure, no imports) is the second formatter, next to it and not a flag on it:
    a **scale** from the longest value a readout can show (hours only if the longest has them, minutes padded to the
    longest's digits, seconds two digits), then every value written to that scale with a fixed fraction, floored never
    rounded (a position never reads past its total), a value above the longest shown as the longest, an unknown length as
    dashes in the same places (`-:--.--`), and a negative or non-numeric time a `RangeError`, never a made-up number.
    **Two decimals** for playback readouts (a frame at 25 or 30 fps is 40 or 33 ms; a third digit changes every frame), **three**
    for the trim tip, which shows the time the edge will hold. The Timeline's readout reads `Clip 0:00.96 of 0:39.84 · Event
    1:02.40 of 2:29.76`: the clip pair is at the scale of the event's longest clip and the event pair at the whole timeline's,
    so crossing a clip changes no width; the summary line reads `Movie 3:12.00 of 3:45.00 of footage`; the slider's value
    text stays in the Cuts panel's form but says "clip" and "event" (`Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12`;
    padding is for eyes and "00:09" is read badly). **The layout is half of it**: each time is an inline cell of
    `calc(var(--ch) * 1ch)` in the mono face with tabular figures (`ui/Clock.tsx`, the inline style only sets the property),
    the clip's name is the one flexible part (one line, an ellipsis, the whole name as its tooltip), and the readout is a
    container: below 40rem the name takes its own line and the `·` that separates the pairs is not drawn. The trim tip is only as wide as its
    time; the snap words hang above it and cannot move it. `formatTime` still writes cut times, typed fields, ruler ticks,
    chapter starts and every spoken string.
  - **Measured** (Chrome 154.0.8037.92 and Firefox 155.0; the four-clip event of 149.76 s; the Timeline played across the first clip's end,
    140 samples at 100 ms over 14 s, light and dark, at 1280 and 390 px). Every element of the readout (name, both pairs, all four
    cells) kept its width and left edge to within 0.5 px in all eight runs; `origin/main` run through the same script moves the
    numbers by up to 13 px at 1280 and 6.5 px at 390 (4 of 4 runs fail), so the script sees the jump. Widths at 13 px: a time cell
    is 45.5 px (7 ch), a pair 134.9 px, the player's header the same; the trim tip's time is 48 px in a 64 px tip with and
    without snap words. Also constant: the player's header over a read view and an Edit-mode playthrough (the first cell does
    not move when the length is read), the numbers across a 41-character clip name turning into a short one at 390 and 320 px
    (no horizontal page scroll, the name cut by an ellipsis), and a 10:05 clip played through `09:59.99` to `10:00.00`. Contrast
    of the muted cell on its surface: 6.85 (light) and 7.38 (dark); the key and the name 17.65 and 15.86. The trim tip steps in frames
    (`0:01.240`, `0:01.260`, `0:01.280`, `0:01.300`: the proxy is 50 fps), so a drag across 1.25 s reads those.
  - **Bundle (`time-readouts-legible`).** `npm run build` on `origin/main` and on this change: JS 522,394 to 524,175 bytes
    (168,013 to 168,683 gzip -9, +0.7 KB), CSS 70,886 to 71,492 bytes (13,539 to 13,669 gzip -9, +0.1 KB); no package added.
    `npm test` runs 540 tests (516 before).
  - **Amended 2026-10-03, change `clip-play-overlay-one-player`: the Timeline's video joins the page's coordinator.**
    The Timeline no longer claims playback itself; the page's one coordinator (`playback/coordinator.ts`) pauses it
    like any other video. It does not take playback back across a clip boundary: when another video starts while its
    file is changing, its own resume yields and it stays paused (`resumeOrYield`, `timeline/follow.ts`). `npm run build` on `origin/main` and on this change: JS 533,160 to 533,333
    bytes (171,764 to 171,882 gzip -9), CSS 73,517 to 74,242 bytes (13,938 to 14,092 gzip -9); no package added.
  - **Amended 2026-10-04, change `clip-rotate-ui`: the Timeline shows a clip's turn.** The one `<video>` carries the turn
    of the clip it holds (set with its `src` at a swap, and again when the draft's turn changes, with no request), and
    each filmstrip tile of a turned clip shows its frame rotated inside the same tile box. The lane's geometry (widths
    by duration, tile height, trim handles, playhead, suggestions) does not depend on a turn.
- **D-21 — The proxy contract** (2026-10-03, change `proxy-encode`; the v2 research calls it D-19). The timeline
  must scrub, step and trim inside a clip, which the originals cannot do (a random seek takes a median 78 to
  1457 ms, a held scrub shows 1 to 12 frames per second, and Firefox plays none of the Sony PCM audio). Every
  clip on disk can therefore have a **proxy**: a small derived MP4, made by the engine, checked, and kept in a
  rebuildable file cache. The engine half is `auto_reel_ng/proxies/` and `auto-reel proxies <root>`.
  - **The contract** (all constants of the code, none a setting; changing one is a code change plus a
    `PROXY_VERSION` bump): MP4 with `+faststart`; one H.264 High `yuv420p` stream by libx264 `veryfast`, CRF 26;
    square pixels with the display rotation applied; short side 540, never upscaled, both sides even; **no
    B-frames (`-bf 0`) and a keyframe every `round(fps / 2)` frames (half a second), `-sc_threshold 0`**; `-fps_mode
    passthrough`, so a variable-frame-rate clip keeps its timestamps; one audio stream, **AAC-LC 128 kb/s
    stereo from ffmpeg's native `aac` encoder** (never `libfdk_aac`, the D-1 blocker; a test fails if it is ever
    named), from PCM, MP3, AC-3 5.1 or mono; a clip with no audio gets none. The editorial `rotate` is not baked
    in.
  - **E1 (experiment `proxy-shape-recheck`) measured the two values the research left open; the supervisor locked
    the shape.** On Chrome 154 and Firefox 155, gate G1 (median scrub of 30 frames per second, frame step, 60/60 exact
    seeks, A/V offset) passes for all three shapes E1 measured, and the cheapest, `-bf 2` with a one-second GOP
    (0.826 of the `-bf 0` file size over four real sources), was first implemented. It was rejected in review: it clears
    the scrub gate by about 1 fps (31.0 Chrome, 31.1 Firefox) and Panasonic 1080p50 (about 24 % of the archive's
    footage) stays below 30 on both one-second shapes (`-bf 0`: 28.2 / 28.9; `-bf 2`: 26.1 / 27.0). The only measured
    shape that clears every source in both browsers is **`-bf 0` with a half-second GOP**: scrub 40.8 Chrome and 44.1
    Firefox (minimum per source 37.0 and 39.4), frame step p90 about 30 ms, A/V offset 0 ms, at about +19 % disk over
    `-bf 2` and one second, so about 46 GB for the archive. `-bf 2` with a half-second GOP was never measured and is
    not used. Moving to another shape is one constant, a `PROXY_VERSION` bump and a regeneration.
  - **The encode ladder.** *Hybrid*: hardware decode, a verified hardware scale to the exact display size,
    `hwdownload`, then libx264 on the CPU, only for an unrotated, SDR, 8-bit H.264 or HEVC clip the selected
    profile decodes in hardware, on a frame context that has a row in the module's scale-filter table (one row,
    VAAPI; a vendor is added only after it is measured on that hardware). *CPU*: everything else, and every clip
    on a host with no usable accelerator; software decode applies the display rotation, an HDR clip is tone-mapped
    first. **Any hybrid failure, or a hybrid output that fails the check below, is redone once on the CPU**; a
    stall and a cancel are never retried. The proxy is never encoded by a hardware encoder (1.9 times bigger, and it
    fails on legacy MPEG-4). The profile's decode flags are used as they are, so the VAAPI device recipe stays in
    one place.
  - **Never a wrong proxy, silently.** GPU rotation of an HEVC clip gave a picture with SSIM 0.47 and no error.
    The ladder keeps rotated and non-H.264/HEVC clips off the GPU, and every proxy is probed before it is
    published: one video stream (H.264, `yuv420p`, the planned size, square pixels), one stereo AAC stream exactly
    when the source has audio, a video-stream duration within 50 ms of the source's video-stream duration (the container's is longer when audio outruns the video or the video starts late), and the
    source's declared frame count (skipped, and logged, only when the container declares none). A failed check
    names the check, the value found, the value expected and the path, and publishes nothing. A picture-similarity
    (SSIM) check is not made: the research's lowest CPU-path score (0.744, a rotated 720p phone clip) is
    unexplained, so no threshold could be set honestly.
  - **The cache** is `$XDG_CACHE_HOME/auto-reel/proxies/` (else `~/.cache/auto-reel/proxies/`), or
    `proxies.cache_dir`; absolute, and refused inside the project root or the `input` directory. An entry is a
    directory `<key>/` holding `proxy.mp4`, `facts.json` and, once `filmstrip-sprites` has made it,
    `filmstrip.jpg`. `<key>` is the SHA-256 of the clip's file name (symlinks followed, directory left out),
    size, `mtime_ns`, `PROXY_VERSION` and a digest of the contract's values, so a changed clip or contract gets a
    new entry by itself while a moved or remounted library keeps its proxies; the encode path is not in the key.
    An entry is built in a hidden `.<key>.<unique>.part` directory, verified, flushed and renamed whole, so a
    killed or cancelled encode never leaves anything that looks complete; a build that loses the rename to
    another process is discarded; `.part` directories older than 24 hours are swept once per process. Never
    Postgres (D-7), nothing evicted, an unwritable or full cache is a `ProxyCacheError` apart from a clip's
    `ProxyError`.
  - **`facts.json`** holds what the run learned, so a reader needs no probe: the source's probed duration (never
    the proxy's: a proxy container is up to 21 ms longer), its frame rate as `num`/`den`, `vfr`, the proxy's frame
    count and size, the source's coded size, its rotation (as the probe reports it, 0 to 359), its audio codec,
    and the encode path with the one-line cause of a fallback. A value the probe cannot give is `null`.
  - **Not a render input.** The proxy is a second artifact made beside the render: `staleness/`, `render/` and
    `persistence/` do not import `proxies/` (a test fails if they do), no proxy file, key or fact enters the
    fingerprint, an editorial edit never invalidates a proxy, and **`RENDER_GRAPH_VERSION` is not bumped**
    (rendered output is unchanged).
  - **Cost** (measured on the ten sample clips, 959 s of footage, 16 cores, AMD VAAPI, with the first shape, `-bf 2` and
    a one-second GOP; the locked shape took 54 s on the hybrid path and 57 s on the CPU path for the set, and its files
    are 1.31 times as large, 171.3 MB against 130.7 MB hybrid): 20.6 times real time on the
    hybrid path and 17.7 on the CPU path for the whole set, and about 11 to 14 times for a Sony 1080p25 clip; the
    cache grew 0.47 to 0.49 GB per footage hour on that set (the 12.6-minute legacy MPEG-4 clip is 79 % of its
    seconds and small per second; the nine camera clips alone are about 1 GB per hour, and they are the heavy
    ones). The archive at the locked shape is about 0.9 GB per footage hour, about 46 GB (the research measured 0.75 GB per hour, about 40 GB, at `-bf 0` with a one-second GOP), planned at 50 GB;
    **no cap and no eviction in v2**. The hybrid path is not always smaller: the 4K50 clip's hybrid proxy is 11.8 MB
    against 7.2 MB on the CPU path (the GPU scaler keeps more noise), the other samples are within 12 % of each other.
  - **The filmstrip sprite** (2026-10-03, change `filmstrip-sprites`). Each proxied clip gets one JPEG sprite,
    `filmstrip.jpg` in its entry, cut from the finished proxy and from nothing else, so the timeline draws a clip's
    picture without decoding video: tiles 90 px high (160 x 90 for 16:9, 50 x 90 for 540 x 960), at most 10
    columns, one tile per `interval = max(1, ceil(duration / 120))` seconds, so at most 120 tiles, JPEG `-q:v 5`;
    about 2.7 kB per footage second on the nine camera samples (0.85 kB on all ten), about 0.65 GB for the
    archive. Tile `k` is the latest keyframe at or before `k x interval` seconds and there are
    `ceil(duration / interval)` tiles, never fewer than 1, where `duration` is the proxy's **video-stream**
    duration (the container's is up to 21 ms longer and would add a tile). The tile geometry is recorded in
    `facts.json` under a `filmstrip` object (`version`, `tiles`, `interval`, `columns`, `rows`, `tile_width`,
    `tile_height`, `width`, `height`, `bytes`), written after the JPEG and renamed over the old file, so a record
    never lacks its image; **D-20's timeline reads that geometry and never recomputes it**.
    `FILMSTRIP_VERSION` is outside the proxy key: a bump rebuilds sprites (about 0.3 s each) and re-encodes no
    proxy. A sprite is built in the cache's hidden `.part` directory (swept like a killed encode's), checked
    (JPEG frame header of the planned size) and renamed in; a failure leaves the proxy valid, is not remembered,
    and is a `FilmstripError` of the clip (a cache or disk fault is a `ProxyCacheError`).
  - **The sub-second rule** (the research lost clip C0047, 0.48 s, 12 frames, one keyframe: 24 of 25 clips
    passed). A clip of one second or less gets a **one-tile sprite of its first frame**; it is not skipped (that
    would add a "no filmstrip" state to every consumer for 35 clips of about 3,000). Reproduced against the locked
    shape (`-bf 0`, half-second GOP) on ffmpeg 8.1.2: the research's `fps=1` filter hands mjpeg **no frame** for a
    single-keyframe clip (ffmpeg exits 234, "Nothing was written into output file"), and its `eof_action=pass`
    variant fixes that but still loses the **last tile** of clips whose tail after the last keyframe is short
    (1.04 s gave 1 tile, 25.025 s at 29.97 fps 25 instead of 26) without a word. So the `fps` filter does not sample the tiles:
    the proxy's keyframe times come from one `ffprobe` of its packets, and `select` takes exactly the chosen
    keyframes (`-skip_frame nokey`), which makes the tile count exact and testable (the tests' clips carry their
    own time in their luma). Two keyframes further apart than the interval (a variable-frame-rate clip with a
    static stretch: the proxy's GOP is a frame count) mean one frame is on screen for several tiles: it is selected
    once and repeated (`setpts` stamps + `fps=1`, `tpad` for the last), never padded with black (stamps are integers, so `fps` only copies there). ffmpeg's expression parser fails
    ("Cannot allocate memory") past about a hundred nested terms, so the `select` sums at most 16 terms a level;
    a 109-tile sample clip found it after 25-tile tests had passed. The sprite step takes the same cancel check as
    the proxy encode (`should_cancel`, polled about once a second): an interrupt kills the running sprite's ffmpeg,
    raises `FfmpegCancelledError` and publishes nothing.
  - **Serving** (2026-10-03, change `proxy-media-endpoints`). `GET` and `HEAD /api/v1/events/{event_id}/proxy?clip=`
    stream the clip's `proxy.mp4` as `video/mp4`, and `…/filmstrip?clip=` its `filmstrip.jpg` as `image/jpeg`, through
    the same `media_response` as the clip route: `Range`, `If-Range`, a strong `ETag` (the cache file's size and
    mtime, so a re-encode changes it and a client sends it as `v`), `Last-Modified`, `Cache-Control: private,
    no-cache` (never `immutable`), `If-None-Match`, `If-Modified-Since` and `HEAD`. The clip is the thumbnail route's
    (`listed_clip`: a clip discovery lists in an event the list shows, IGNORED included, exact identity, `reel.yaml`
    never read); the entry is the one `proxies.entry_dir` names for the clip **as it is now** (a symlink is
    followed), so a replaced clip, another `PROXY_VERSION` or other contract values are simply absent until
    `auto-reel proxies` runs again. **Absent is a 404 problem body, never a 200, a 202, a placeholder or the original:**
    a media element cannot use a 202, and bytes of the original would be silently wrong in exactly the case the proxy
    exists for; whether a clip is prepared is the event detail's business (`proxy-state-read`), and the filmstrip is
    independent of the proxy file (an entry with a proxy and no sprite is 200 and 404). The routes only `stat` and
    open: no database (they answer while Postgres is down), no ffmpeg, nothing created, not even the cache directory;
    a cache file that exists but cannot be read is a 502 before a status line, path-free. Cost: one lookup
    (listing, config read, two stats) per range request.
  - **The state in the read model** (2026-10-03, change `proxy-state-read`). The event detail's clips carry
    `proxy`, read with `read_proxy_state` (`stat` and one JSON read, no process, no write, no listing; it is not
    `lookup_proxy`, which cannot tell never-made from damaged). Four states, precedence `ready > failed > stale >
    absent`. **`ready`**: a non-empty `proxy.mp4` and `filmstrip.jpg` and a complete `facts.json` of the current
    `PROXY_VERSION` with a `filmstrip` record of the current format whose `bytes` is the image's size. **`failed`**:
    not ready, the proxy and its facts not both usable, and the clip's marker `<cache_dir>/<key>.fail`
    (`{"reason": "<one line>"}`, written atomically by `ensure_proxy` for any `ProxyError` of the clip: probe,
    encode, verification) records a cause. It has no TTL (D-11's expires after a minute because a thumbnail is
    retried on every page view; a proxy is made only when asked), a ready entry outranks it so success needs no
    cleanup, a published proxy supersedes it while the sprite is pending, and the key scopes it to the file and
    the version. A failed sprite is not recorded (`clip-filmstrips`). **`stale`**: not ready, no marker, and an
    entry at the current key that cannot be used (unusable `facts.json`, an empty file, a malformed or foreign
    `filmstrip` record, an image of another size than recorded). **`absent`**: everything else, including an
    incomplete entry (the proxy is published before its sprite). **A replaced file or a `PROXY_VERSION` bump moves
    the key and reads `absent`**; an entry made for the previous key is never looked for (that would mean listing
    the cache), and is an orphan for a later prune. `facts` are copied from `facts.json` as recorded: `fps` as
    two integers, `vfr` and `rotation` `null` where the probe could not say, never defaulted. `version` is the
    proxy file's entity tag (D-15, `"{size:x}-{mtime_ns:x}"` without quotes), for the media URL's `v`. The state
    is not a staleness input. `null` means unknown, never `absent`: a missing clip, an unresolvable `proxies`
    configuration (one warning per request) or an unreadable cache (`ProxyCacheError`).
  - **The proxy job** (2026-10-03, change `proxy-job`). The worker runs jobs of kind `proxy`, one event each: for
    every clip discovery lists (the clips on disk, IGNORED ones included; `reel.yaml` is never read or written, so
    editorial state neither adds nor invalidates work) it makes the proxy and then the filmstrip
    (`prepare_clip`), skipping what the cache holds, in the proxy cache of the job's own project. No render-only
    claim check applies (it writes none of the paths they guard), no fingerprint is recorded, a finished job
    never changes a staleness verdict and **`RENDER_GRAPH_VERSION` is not bumped**. It holds **one CPU token** for
    while it prepares clips and no GPU token (its libx264 encode is CPU work even on the hybrid path), and at most
    **`worker.proxy_slots` (default 1)** run at once: two workers gained only 20 to 35 % on one disk
    (research `proxies.md` §3.9). **A queued render is claimed before any proxy job** whatever its age or priority
    (`claim_next` orders render first, and the worker excludes `proxy` while its slots are full; the claim loop's
    in-flight bound does not count `proxy` jobs, so neither a waiting nor a running one uses up the capacity a render
    needs, and a CPU render waiting for the CPU token behind a proxy job does not keep a GPU render queued). A
    running proxy job is not preempted, but it **yields**: it starts no clip while a `render` job is `running` and
    gives its CPU token back while it waits (a render that waits for that token would otherwise wait for the job
    that waits for it). Progress is **weighted by source size** (a `stat`, not a probe; the clip in flight
    contributes its own fraction, the sprite is the last 3 % of its clip), never decreases, and is `1.0` only at
    `done`. A clip that fails does not stop the others and the job ends `failed` naming them ("1 of 3 clips
    failed: ..."); a cache fault (full or unwritable directory) ends it at once. Cancel kills the encode within about
    two seconds and leaves no `.part` directory; a worker stop does the same through a stop event the handler
    shares with the worker (`run` waits up to 10 s for its cleanup after requeueing the row); a crash is recovered
    by startup reconciliation and the rerun costs one `stat` per finished clip. **Measured (experiment 007, an AMD
    APU, shared host):** before the yield a GPU render beside a running proxy job took **about 1.3 to 1.6 times**
    as long (median 1.52 as built, pairs 1.22 to 1.53; a thread cap and taking the proxies off the GPU did not
    remove it); with the yield the warm median was **1.12** against the 1.15 bound and a cold pair 1.29, on a quieter
    host than the control (1.17), so the runs are not a clean A/B. The clip in flight still overlaps the render.
  - **Enqueue over REST** (2026-10-03, change `proxy-enqueue-endpoint`). Preparing an event's proxies is a job of kind
    `proxy` enqueued by `POST /api/v1/events/{event_id}/proxies`: no body (a proxy is a function of the clip file and
    the settings, so there is nothing to force), **201** with the queued job, **200 `fresh`** (`clip_count`, no job)
    when every clip the event folder lists already has a `ready` proxy, **409 `active_job`** with the job's id while
    one is queued or running (also when a concurrent request inserted first), 404 / 502 / 503 as the render enqueue.
    Freshness is read from the clips' `proxy` state (`stat` and JSON, no process, no write), never from a staleness
    verdict: the cache is not a staleness input. The 200 and the job count **the same clips**, the folder's listing
    (`reel.yaml` is never read, so an unparseable one or a missing title does not refuse proxies); an unreadable
    folder or cache is a 502, never read as `absent` or `ready`. A job reports its **`kind`** (`render | proxy`, a
    closed published enumeration) in `JobOut`, the events reads' `latest_job` and every WebSocket frame, while
    **`latest_job` stays the event's latest render job**: a proxy job never stands in it, and the proxy side of an
    event is read from the clips' `proxy` state and the socket. The one-active-job rule holds per kind, so neither
    a render nor a proxy job refuses the other; cancel works on both. The WebSocket and `GET /api/v1/jobs` carry
    jobs of every kind (the store's reads default to `render`, so both ask for all), and a stored row of a kind this
    build does not name is left out and logged, never a 500 of the list or a silent end of the feed; the poller logs
    and survives a failed poll. The web's job store keeps every kind but its event rows, event page, render control
    and header count read renders only. `auto-reel jobs list` shows every kind, with its `kind`. **The proxy enqueue
    is deliberately API-only** (Principle V): `auto-reel proxies <root>` is the CLI's way to prepare proxies, inline;
    a CLI `enqueue --proxies` is not needed until something wants a queued proxy job without the service.
  - **Deliberately not here:** a prune of
    orphan entries (`proxy-prune`); a virtual remux to give the original sound in Firefox. The cache-location
    helpers are copies of `thumbs/`'s; unifying them is a follow-up.
- **D-22 — The title-card fonts are bundled and the renderer owns fontconfig** (2026-10-03, change
  `title-card-fonts`). A card is drawn from a curated set of fonts that lives in the repository, so the GUI's font
  picker, the preview and the render agree on every host and in the image.
  - **The set** (`fonts/`, registry `auto_reel_ng/render/title/fonts.py`, which imports neither `gi` nor `cairo`):
    nine families, one per role, static files (no variable font is re-instanced, because that would ship a modified
    font), each with its license text beside the files. DejaVu Sans (default; Bitstream Vera / DejaVu license), Inter
    (clean sans), Poppins (geometric sans), Source Sans 3 (humanist sans), Source Serif 4 (serif), DM Serif Display
    (display serif), Barlow Condensed (condensed), Pacifico (handwritten script), IBM Plex Mono (monospace); the
    others are SIL OFL 1.1. Playfair Display, the first pick for the display serif, ships only as a variable font
    upstream, so the role went to DM Serif Display. The registry records per family the name fontconfig knows, a
    display name, the role, the **weights** (Pacifico and DM Serif Display have one: a later weight control must not
    offer a bold that Pango would synthesize), and per file a SHA-256. About 4.8 MB; a test caps `fonts/` at 8 MB.
  - **A standalone fontconfig.** `fonts/fonts.conf` lists only its own directory and includes no system
    configuration, so no host font can be a fallback or shadow a bundled name and no host rule changes the glyphs. The
    cost is that a character outside the bundled coverage draws a missing-glyph box rather than a host fallback:
    visible, never a silent other face. The engine sets `FONTCONFIG_FILE` itself (`configure_fontconfig`, idempotent,
    overriding an inherited value) in `render._load_backend`, before Pango makes its first font map, because the map
    is cached for the process and fontconfig reads the variable once. `AUTO_REEL_FONTS_DIR` moves the directory; a
    directory or `fonts.conf` that is not there is a typed error naming the path.
  - **The fail-loud check stays, and checks the weight.** The probe made for this change (fontconfig 2.17, PyGObject
    3.56) showed Pango **silently substituting a family a one-font fontconfig did not hold** (asked for DejaVu Sans,
    got Liberation Sans), and loading the Regular face when a Bold file is missing. `_resolve_font_or_raise` therefore
    compares the family and the weight of the face that loaded; `verify_bundled_fonts()` loads every family at every
    declared weight, and the image build runs it, so a build with a missing or unresolvable font fails.
  - **`look.title_card.font_family` must be registered**, checked (ignoring case, stored in the registry's spelling)
    when the config is parsed, with the field, the value and the list in the error. No migration: only DejaVu Sans
    was ever installed in the image.
  - **The image installs `fonts/`** (copied to `/app/fonts`, read in place, no second copy under `/usr/share/fonts`)
    and drops `fonts-dejavu`; `fontconfig` stays for `fc-list` and the cache tooling. License texts are `.txt`
    because `.dockerignore` drops `**/*.md`.
  - **`RENDER_GRAPH_VERSION` 5.** A font file is a render input the fingerprint cannot see, and this change swaps the
    file DejaVu Sans is drawn from and drops the host's rules; every rendered event is stale once. A test fails with a
    message saying so when a bundled file's hash no longer matches the registry: changing a font is deliberately an
    edit of three things (file, hash, version).
  - **Deliberately not here:** the card style, per-card fields, background-on-video, durations, the preview
    endpoint, the GUI, a weight setting, italics, user-supplied fonts, web fonts in the browser (D-10; the GUI previews
    with the engine's PNG).
- **D-26 — An event has a poster frame** (2026-10-04, change `event-poster-engine`, the engine half of the last open v2
  item). A media server (Jellyfin, Plex, Kodi) that scans the output folder saw a bare `.mp4` and a black tile, and the
  operator could not choose the frame.
  - **The key.** An optional top-level `poster: {clip, at}` in `reel.yaml` (schema stays `version: 0`, additive): `clip` is
    a clip identity, `at` a number of seconds `>= 0` into the ORIGINAL clip, before any trim. Both keys are required; the
    loader fails loud naming `poster.<key>` on an unknown key, a missing key, a non-number (a boolean is none), a negative
    or non-finite `at`, or a clip that is not an event-relative identity. Whether the clip exists and `at` lies inside it is
    not checked at load (a load makes no probe); the render does. `null` or no key is the default frame.
  - **Writers keep it.** The round-trip writer keeps its comments and key order; a document built from fields writes it
    after `look` and before `chapters`. The editorial write treats it as `card:` (D-24): no key or `null` leaves it as
    written, `{}` removes it, a mapping is merged key by key; the merged document is validated before anything is written.
  - **Which frame.** With a `poster` whose clip the movie plays: that clip at `at`. Otherwise the first played clip at the
    thumbnail position (D-11, `DEFAULT_POSITION` of the probed duration). A `poster.clip` that is missing, ignored or
    excluded falls back to the default with one render warning naming the clip and the reason; it never fails the render.
    A played clip whose `at` is not less than its probed duration is a typed `PosterFrameError` naming the clip, the time
    and the duration, raised before anything is encoded: the operator asked for a frame that does not exist, and picking
    another would fabricate one (Principle I). No frame at that time raises the same error; there is no placeholder.
  - **The extraction.** One CPU ffmpeg run on the original clip (a single frame, so every profile shares it): input seek,
    autorotate off, the renderer's own turn (display rotation plus `rotate`, D-23), the HDR tone-map when the probe says
    PQ/HLG, square pixels, then fitted and padded to the movie's size, JPEG `-q:v 2`.
  - **Atomic with the movie.** The poster is extracted to `<stem>-poster.jpg.part` and verified (a JPEG of the target
    size) before the encode. After the movie is assembled and verified, the cover is embedded by a stream copy into
    `<movie>.cover.part` (`attached_pic`, `mjpeg`; streams, chapters and metadata unchanged; `+faststart` again), which is
    verified again and replaces the movie `.part`. The poster is renamed into place, the movie last, then the manifest. A
    kill before the renames leaves only `.part` files and no manifest. A kill between the two renames leaves a new poster
    beside the previous movie and no new manifest, so the event reads stale and the next render replaces both.
  - **Verification ignores the cover.** A video stream with the `attached_pic` disposition is not the movie's video stream:
    `verify_output` requires exactly one other video stream and, when a cover is expected, exactly one `mjpeg` cover.
  - **Claims.** The manifest gains `poster`, the bare name of the sidecar that render wrote, or `null` (schema version 1;
    absent or malformed reads as `null`, fail-open as `superseded` does). The sidecar is a claim on a file: a render
    refuses, unforced, to replace a regular file another event's manifest records as its `poster` (the claimed-movie
    error). `prune-renamed` lists and deletes a superseded movie's sidecar with it, never a sidecar another event records,
    and never lists a sidecar alone. A scan cites the existing `output` reason, with no probe, when the manifest records a
    `poster` and no such file lies beside the movie.
  - **Staleness.** `poster` joins the editorial hash only when present, so a `reel.yaml` without one hashes as before and
    its ETag stays valid. The render now writes a second file and a cover for identical inputs, so
    `RENDER_GRAPH_VERSION` is raised from 10 to 11: **every rendered event reports stale once, reason `engine`**
    (D-C8). No Alembic migration, no new dependency.
  - **Deliberately not here:** the picker and any API field (the page reads `poster` through a later change), chapter
    posters, animated art, NFO files, writing the sidecar for a movie that is not re-rendered, and the web player's poster
    (it keeps the first played clip's thumbnail until the picker lands). An event whose plan has no clip cannot be rendered
    at all, so "no poster" is only the resolver's answer there.
- **D-25 — Title cards are on unless `look.decorators` says otherwise** (2026-10-04, change
  `title-cards-default-on`). The user asked for "a title card in the beginning" and "each chapter should generate a title
  card"; until now a render drew none unless a project listed `title` in `look.decorators` (D-24 left that opt-in).
  - **The rule.** `look.decorators` absent (or null) from the merged look, that is from both the event's `reel.yaml` and
    the project's `config.yaml` (D-2: the event wins, a key at a time), means `[title]`. An explicit list keeps its
    meaning: `[]`, `[none]` and any list without `title` draw no card; a non-list fails loud. The default lives in the
    engine's one `resolve_decorator_names`, not in a template written to disk, so existing projects and hand-made
    events get it and nothing is duplicated into files. `[]` is the way to say "no cards": it cannot be mistaken for unset.
  - **The report.** `title_cards_state(event_look, project_look)` sits beside it and returns `enabled` and `source`
    (`event`, `project` or `default`, by the same merge the render performs, so a null event value reads `default` in both).
    The event detail carries it as `title_cards: {enabled, source}` (and `title_cards_error` with `title_cards: null`
    for a non-list value: 200, nothing guessed), probe-free, so the web no longer has to infer an "unset" state.
  - **Staleness.** `RENDER_GRAPH_VERSION` is raised from 7 to 8: every rendered event with no decorators now renders
    cards, and the fingerprint cannot tell which events those are without a second path. **Every event with a manifest
    from the previous engine reports stale once, reason `engine`** (D-C8 accepts one archive re-render). A project that
    does not want cards writes `decorators: []` in its `config.yaml`.
  - **Callers.** Neither the legacy importer nor `scripts/make_dev_library.py` writes `decorators` (tests assert it).
  - **The web reads it (`title-card-toggle`).** The Timeline and Edit mode read `title_cards` instead of guessing from the
    event's `look`; the Title cards switch writes only the event's own `look.decorators` (Off: the list without `title`, or
    `[]`; On: `title` first; back to the state read is no override). The web never infers the project's list, so it never
    removes the key to "restore the default": a removed key would inherit a project opt-out the page cannot see.
- **D-24 — A title card belongs to its chapter** (2026-10-03, change `title-card-model`, the engine half of the
  title-card work of GUI v2). The user asked for cards that are configured and edited, not only rendered: "text on
  black or text on a piece of video", the title and a subtitle editable again, the font and the length too.
  - **Where it lives.** An optional `card:` mapping on a chapter of `reel.yaml` (schema stays `version: 0`,
    additive). The default chapter `""` holds the opening card. A chapter is renamed, reordered and deleted with its
    card by the machinery that already pairs chapters; a card is not a clip property and not a map keyed by a name
    the editor changes.
  - **Opening subtitle and shadow** (`title-card-date-place-shadow`, user: "Opening subtitle: show date and location",
    "Shadow on text: yes"). With no `subtitle` key the default chapter's card shows the ISO date and `Plats: <location>`
    (`default_subtitle`, also reported by the event detail); `subtitle: ""` is the opt-out. A `video` card is drawn with a
    blurred shadow (60 % alpha, offset 0.004 and blur 0.006 of the height); a `black` card is unchanged.
  - **The keys and their bounds** (named constants in `reel/card.py`, pinned by tests): `title` (not blank),
    `subtitle` (any text, empty allowed), `duration` (finite, 0.5 to 60 s), `background` (`black` | `video`),
    `font_family` (not blank in `reel/`, which cannot see fonts; the render layer checks it against the bundled registry (D-22) when the card's style is parsed),
    `title_font_size` and `subtitle_font_size` (integers 8 to 400), `text_color` (`#RRGGBB`), `position` (`center` |
    `top` | `bottom`). The loader fails loud naming `chapters[i].card.<key>` on an unknown key (listing the allowed
    ones), a wrong type (a boolean is never a number), a value out of range, and a `null` value: an unquoted
    `text_color: #FFD700` is a YAML comment, so `null` is refused rather than read as unset.
  - **Text.** The heading is `card.title`, else the chapter name, else the event title; the subtitle is `card.subtitle`
    and empty by default. The date, location and description are no longer drawn by the engine (user decision); an
    author who wants them writes them as the subtitle. A card with no heading fails loud.
  - **Style.** Defaults, then the event-wide `look.title_card` (which gains `background: black | video`), then the
    chapter's `card`, overlaid as raw mappings and parsed **once**, so the fades clamp to the final duration.
    `resolve_card(plan, chapter)` is the one function that returns a card's effective config and text; the decorator
    uses it now and the API's resolved-card read will use it later (Principle V).
  - **`background: video` is stored but not rendered here.** An event that reaches it fails loud with a typed error
    naming the chapter; it is never drawn as black. `title-card-over-video` replaced the error (below).
  - **The event layer is editable in the page** (`title-card-event-style`): Edit mode writes `look.title_card` through the
    editorial `PUT`. An unset field shows the resolved project default; a cleared field the saved style set shows
    "Project default" with no number, as the layer below it is not known to the client.
  - **Writers keep the card.** The round-trip writer keeps a card's comments and key order. The editorial write
    treats a chapter's `card` as: **no key or `null` leaves the card as written**, `{}` removes it, and a mapping is
    merged key by key (a key left out is removed, an equal value stays as written, a fresh card goes after `name`).
    Absent must not mean "remove": a client that predates cards, or an API model whose omitted fields dump as `None`,
    would otherwise erase every card on every save.
  - **Staleness.** `RENDER_GRAPH_VERSION` is raised from 6 to 7: the opening card's text and every card's length and
    style are output changes for identical inputs, and nothing in an unchanged `reel.yaml` would otherwise notice.
    Exactly: **every event with a render manifest from the previous engine reports stale once, reason `engine`**
    (the fingerprint cannot tell which looks use the `title` decorator without a second path; D-C8 accepts the cost
    of one re-render). A `reel.yaml` with no `card` hashes exactly as before, so the editorial ETag a client holds
    stays valid; adding a card moves the editorial component like any edit; an unrendered event is unaffected.
  - **Deliberately not here:** an event with no default chapter has no opening card; no API, editor, preview or card
    over video (the font registry is D-22). The cards were still opt-in here (`look.decorators: [title]`); that ended
    with `title-cards-default-on` (**D-25**).
  - **The card over video (change `title-card-over-video`, 2026-10-03).** The user's reading of "text on a piece of
    video": the text sits over the start of the chapter's first clip while it plays, no time added. A `video` card
    gets no inserted segment: the decorator attaches it, as a producer-backed timed `OverlaySpec`, to the same anchor
    a black card precedes (the title clip's first kept span, else the chapter's first surviving segment), so segment,
    chapter and movie lengths and the chapter times are untouched by construction (the chapter's recorded title-card
    span is `null`, as for a chapter with no card segment). The card is rendered on a transparent canvas by the one
    renderer (only the fill is skipped); normalize loops the still for the window, fades its alpha, and composites
    with the CPU `overlay` (`format=auto`, without which Mesa fails the following `hwupload`) on every profile, never
    a hardware overlay filter, because only the AMD bridge and the CPU are exercised on our hosts. A window longer
    than its segment is clamped with a render warning rather than refused: a short opening clip is a legitimate edit.
    Staleness: no `RENDER_GRAPH_VERSION` bump (stays 7). An event that carried `video` failed loud before, so no output
    exists to be wrong; black cards are byte-identical; switching a card to `video` moves the editorial component.
    Cost: the anchor segment went through the CPU bridge for its whole length; `video-card-bridge-window` (below)
    limits it to the card's window (see §4.4).
  - **The card window is split off the anchor (change `video-card-bridge-window`, 2026-10-04).** A long first clip
    encoded about twice as slowly as it needed to on VAAPI, because every frame of it was downloaded, overlaid with
    nothing (`enable=between(t,0,7)` is false after the card) and uploaded again. The segment's normalize step now
    materializes the card, then splits the segment into a **head** (from the segment's start for `N / fps` seconds,
    `N = ceil(window * fps)`, a whole number of *target* frames) that keeps the overlay and the CPU bridge, and a
    **tail** (the rest) with no overlay and no `filter_complex`. Both are re-encoded, so the boundary needs no keyframe,
    and because the head is a whole number of frame periods the tail's output tick `k` lands on the source instant the
    unsplit segment's tick `N + k` did: no frame is dropped or repeated. A tail under 1 s is not split off (the saving
    is below the cost of another ffmpeg start), nor a window that covers the segment. The pieces are video-only; the
    tail's command also writes the audio of the **whole** segment, encoded once, as a second output, and a third
    command stream-copies video and audio together into the segment's one intermediate. Two AAC streams joined by a
    copy do not work: the second stream's encoder delay is a gap of near-silence (about 1000 samples, 2048 more than
    the unsplit render) in the middle of continuous footage, which the tone test caught. The segment stays one entry
    for progress (the head and tail report their share of its weight), chapter times, copy eligibility and the
    segment list; a dry run lists the three commands a run executes. `RENDER_GRAPH_VERSION` goes 9 to 10: an anchor
    under a video card gets another encoder start, so its bytes change for the same inputs (D-C8: every manifest is
    stale once, reason `engine`). Measured (180 s 1080p30 H.264 first clip, 7 s video card, median of 3, before and after interleaved on a shared host at load average 15 to 27, so wall time is noisy and
    ffmpeg CPU seconds is the steadier figure): **VAAPI** (AMD Radeon 860M, integrated) wall 40.9 s to 30.2 s (-26%), ffmpeg CPU seconds
    113 to 19 (about 6x less: the 173 s of download, overlay and upload are gone); **CPU profile** wall 40.4 s to 39.1 s
    (within noise), CPU seconds 400 to 350 (-12%, the overlay filter no longer runs over the tail). The PR #115
    estimate of about 2x did not materialize in wall time: the hardware encode of the tail and the head's start-up are
    still serial, and the host was never idle; the CPU cost of the bridge is what fell by a factor of six.

- **D-23 — A clip's `rotate` is an extra clockwise turn on top of its display rotation** (2026-10-03, change
  `clip-rotate-engine`; D-20 keeps the timeline and D-21 the proxy contract). User request: "Some videos are rotated 90
  degrees. I want a feature to rotate them so they are correct. We need to remember this in the config as well."
  (§4.3, §4.6)
  - **The meaning.** `clips.<identity>.rotate` (0, 90, 180, 270, also -90 and 360; any other integer fails the load
    naming the clip and the key) is "turn this clip this many degrees **clockwise** from how it plays now", where "how
    it plays now" is the picture a player shows after the container's display rotation. It is remembered in the
    event's `reel.yaml`, the only home of the value (Principle II). What you see is what you fix.
  - **The compose.** The engine applies `(display rotation + rotate) mod 360` clockwise as one CPU `transpose` chain
    (between `hwdownload` and `hwupload` on a hardware path; no hardware rotation filter, D-21 "Never a wrong proxy,
    silently"). The probe's `rotation` is the display matrix's angle, **counter-clockwise** (matrix -90 probes as 270),
    so the clockwise display turn is `(360 - rotation) mod 360`; `display_turn` and `total_turn` in
    `render/normalize.py` are the only readers of it. A clip with a display rotation is opened with **`-noautorotate`**,
    so the turn happens exactly once and the output carries no display matrix. Padding is decided from the total turn;
    a clip with a display rotation, or a `rotate` that is not a multiple of 360, is never stream-copied.
  - **Why the engine had to change.** Measured on `main` 143f0fc with the rotated samples (SSIM, 24 renders): on the
    CPU profile ffmpeg's autorotate ran first and `rotate` already added; on the AMD VAAPI profile the hardware decode
    delivered frames ffmpeg does not autorotate, so a phone clip with `rotate` unset rendered sideways and `rotate: 90`
    "fixed" it. A display-rotated clip that matched the target was stream-copied with its matrix, and the movie reported
    `rotation=90`. Both profiles now agree.
  - **Fingerprint and migration.** Output changes for identical inputs (a display-rotated clip on a hardware profile;
    a display-rotated clip with `rotate` on a hardware profile; a display-rotated clip of the target's stored size), so
    **`RENDER_GRAPH_VERSION` goes 5 to 6** and every manifest is stale once (D-C8). No fingerprint input is added: the
    editorial `rotate` was one and the display rotation belongs to the file. A `reel.yaml` that already set `rotate`
    on a display-rotated clip renders as before on the CPU profile; on a hardware profile it now adds (a file that set
    `rotate: 90` to fix a phone clip that rendered sideways there now renders upside down: delete the key). The GUI
    never wrote `rotate` and the legacy import does not produce it, so such a file is expected to be rare; the first
    render logs the clip, both values and the total.
  - **Not here.** No GUI, no new key, no API or schema change. Proxies, thumbnails and filmstrips stay keyed by the
    file and are not rotated by the editorial value (D-20, D-21).
  - **Amended 2026-10-04, change `clip-rotate-ui`: the GUI turns what it shows.** The pictures the service serves are
    upright by the display rotation (measured on the rotated samples: the 720p phone clip's proxy is 540x960 with
    facts `rotation` 270 and its thumbnail 101x180), so the client adds only the editorial `rotate`, as a CSS `rotate`
    of the picture inside its own box. A box holding a turned picture is a size container, and a quarter turn swaps the
    picture's box (its width is the box's height, in `cqb`/`cqi`) before turning it, so `object-fit: contain` fits any
    picture shape whole inside an unchanged box; overlays are siblings and stay upright. The turn lives in the draft
    (`rotations`, only clips whose turn differs from the saved one), is written as `clips.<identity>.rotate` and a turn
    of 0 removes the key; a saved value that is not a quarter turn is shown as no turn.
    `npm run build` on `origin/main` and on this change: JS 539,223 to 544,668 bytes (173,912 to 175,578 gzip -9, +1.7 KB), CSS
    76,068 to 77,252 bytes (14,391 to 14,620 gzip -9); no package added; `npm test` runs 618 tests (599 before).

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
   bundled DejaVu Sans default; Pango's silent substitution is refused; the fonts are the bundled set of D-22, not
   the host's). Outline + crisp offset drop-shadow in
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
    Low-res proxies ✅ **RESOLVED → Decision D-21** (§7): progressive 540p H.264 + AAC MP4s in a file cache
    outside the library, no HLS and no live transcode; the engine half is built (`proxy-encode`, `auto-reel
    proxies`). The PCM audio path is answered the same way: 52 % of the archive's clips (every Sony XAVC clip)
    carry PCM audio that Firefox does not play, a proxy carries AAC made from it, so the proxy plays with sound
    in Firefox while the original stays silent there (the v1 media routes still serve files unchanged). Still
    open: the job and the read model that use the proxies (the sprites are built: `filmstrip-sprites`; the
    routes that serve both are built: `proxy-media-endpoints`, the Sony PCM proxy plays with sound in Chrome and
    Firefox), a prune of orphan entries (`proxy-prune`), and the virtual remux that would give the
    original sound in Firefox. Facts that sized the work: about 76 % of the archive's files keep `moov` at the
    end (every seek is a range, the first open a tail fetch), and HEVC exists only under `original/`. See
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
