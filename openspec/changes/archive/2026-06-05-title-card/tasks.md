## 1. Dependencies & packaging

- [x] 1.1 Add `pycairo` and `PyGObject` to project dependencies; add `gi.*` to the mypy `ignore_missing_imports` overrides (alongside moviepy/exifread).
- [x] 1.2 Add the runtime system libs and default font to the D-1 container image (`libcairo2`, `libpango-1.0-0`, `libpangocairo-1.0-0`, `gir1.2-pango-1.0`, `fonts-dejavu`) plus an `fc-cache` step; document the same libs as a dev-host prerequisite for the renderer tests.
- [x] 1.3 Add a "has-fonts" pytest marker (skip image/render tests when Cairo/Pango/the bundled font are unavailable), mirroring the existing "has GPU" marker.

## 2. Title-card config (parsed from `look.title_card`)

- [x] 2.1 Add a typed `TitleCardConfig` dataclass (font family/size(s), color, outline, shadow, background color+opacity, fade-in/out, total duration, position) with `to_dict()` for debug/golden logging.
- [x] 2.2 Implement parsing from the opaque `look.title_card` sub-map at render time, with documented defaults (carry auto-reel's 7s duration / 2s fade unless overridden) and fail-loud typed errors on malformed values.
- [x] 2.3 Clamp combined fade durations to the total card duration during parse.
- [x] 2.4 Tests: defaults applied when fields absent; fades clamped when their sum exceeds duration; malformed value raises a typed error naming the field.

## 3. Cairo + Pango title-card renderer (the seam)

- [x] 3.1 Implement `render_title_card(config, target) -> Path` writing an RGBA PNG at `target.width × target.height` via an ARGB32 Cairo surface; keep all `gi`/Cairo calls behind this one function.
- [x] 3.2 Lay out title/date/location/description as centered Pango layouts that wrap within a max-width column (Pango column-wrapping, NOT auto-reel's relative-offset hand-positioning); compose text from event `metadata` for the default card and from the chapter name for a non-default chapter card (carry the Swedish "Plats:"-style location formatting). Validate spacing against sample media.
- [x] 3.3 Render outline (`pango_cairo_layout_path` + stroke) and an offset drop-shadow; fill the configured background (color/opacity).
- [x] 3.4 Implement fail-loud font resolution: resolve the configured family through fontconfig and raise a typed error (naming family + bundled default) if it does not resolve; ensure the bundled default renders with no config.
- [x] 3.5 Tests: image is the target resolution and RGBA; default-card text includes title and formatted date/location; non-default chapter card heading is the chapter name; unresolved family raises; bundled default renders without config. Layout assertions are structural (computed boxes / wrap points / resolved family); gate a single tolerance-based pixel snapshot behind the has-fonts marker.

## 4. Segment-producer seam

- [x] 4.1 Add a name-keyed producer registry (parallel to `render/decorators.py`) with `register_producer` / `get_producer`; unknown name raises a typed error naming the unknown producer and the registered names.
- [x] 4.2 Define the `ProducedSegment` result type (rendered image/source path, duration, fade-in/out timings) and the producer signature; producers materialize only their asset and never invoke encoding.
- [x] 4.3 Implement and register the `title` producer: calls `render_title_card` and returns the `ProducedSegment` for a synthetic title segment.
- [x] 4.4 Tests: producer resolved by name; unknown producer fails loud; title producer returns image+duration+fades sufficient for a target-conforming encode.

## 5. Title decorator (inserter)

- [x] 5.1 Implement and register the `title` decorator: insert one synthetic title segment immediately before each chapter's title clip (`is_title` / `ResolvedChapter.title_clip`), carrying the producer reference, resolved duration, look-derived config, and the chapter membership of the clip it precedes.
- [x] 5.2 Tests: title segment inserted before the default chapter's title clip with that chapter's name; per-chapter insertion for a two-chapter plan; `look.decorators` without `title` yields no synthetic segment (behavior unchanged).

## 6. Synthetic normalize path (replace the `raise`)

- [x] 6.1 In `render/normalize.py`, replace the synthetic-segment `RenderError` with materialization via the producer seam: build a command that `-loop 1 -t <duration>` the rendered image, applies `fade=t=in`/`fade=t=out` over the producer fade timings, synthesizes silent audio at the target params (reuse the video-only silence path), and encodes to the target codec/pix_fmt/fps/resolution.
- [x] 6.2 Keep the synthetic path overlay-free (no `overlay`/`overlay_vaapi`/CPU overlay bridge); confirm synthetic segments stay never copy-eligible.
- [x] 6.3 Tests (golden ffmpeg-arg strings, no GPU): synthetic command loops the image + encodes to target + has silent audio; fade-in/out present for configured fades; no overlay op even when `can_overlay_hw` is false; AV1 target encodes the card with the target's AV1 encoder (chosen codec honored).

## 7. End-to-end & docs

- [x] 7.1 Orchestrator-level test: a plan with `look.decorators: [title]` renders a movie whose first segment is the title card and whose chapter durations (measured post-encode) account for the inserted card segment(s).
- [x] 7.2 Update HLD: resolve §8.5 to "Cairo+Pango, fail-loud font resolution, structural+tolerance tests" and update §4.4 to "card-as-segment (overlay-free), renderer behind a swappable seam" instead of overlay-in-normalize-pass.
- [x] 7.3 Run `task lint:check` and the full test suite; ensure has-fonts/has-GPU-gated tests skip cleanly on a host lacking those, and the default-config path renders on the container image.
