## 1. Module scaffold & types

- [x] 1.1 Create `auto_reel_ng/analysis/` package (`__init__.py` with public exports)
- [x] 1.2 Define `Segment` (immutable dataclass: `start`, `end`, `kind`, `confidence`) and a `kind` enum/literal (`black`/`white`/`freeze`); enforce `end > start`
- [x] 1.3 Add a typed `AnalysisError` to `errors.py` and export it from the package `__init__`
- [x] 1.4 Define an `AnalysisConfig` (thresholds) with exp-005 defaults: `pic_th=0.98`, `pix_th=0.10`, freeze `n=0.003`, min-duration `d=2.0`

## 2. Filter command building (pure)

- [x] 2.1 Build pass-1 filter args: `blackdetect` + `freezedetect` from `AnalysisConfig`
- [x] 2.2 Build pass-2 filter args: `negate,blackdetect` for white
- [x] 2.3 Unit-test emitted args against golden strings for defaults and for overridden thresholds

## 3. Log parsing (pure)

- [x] 3.1 Parse `black_start`/`black_end` and the negated-pass output into black/white raw spans
- [x] 3.2 Parse `freeze_start`/`freeze_end` into freeze raw spans
- [x] 3.3 Apply min-duration filtering; map raw spans to `Segment`s with coarse `confidence`
- [x] 3.4 Fixture tests from exp-005 recorded artifacts (`experiments/005-detection-thresholds/artifacts/`)

## 4. Overlap resolution (pure)

- [x] 4.1 Implement precedence `black`/`white` > `freeze`: subtract black/white regions from freeze spans
- [x] 4.2 Test: freeze fully inside a black span is dropped; freeze partially overlapping is clipped; non-overlapping freeze kept
- [x] 4.3 Test: black + white + freeze on the same region resolves to a single `kind`

## 5. Detection runner (impure, FfmpegRuntime)

- [x] 5.1 `analyze_clip(path, runtime, config) -> list[Segment]`: probe duration via `ClipMetadata`, run both passes through `FfmpegRuntime`, parse, resolve overlap
- [x] 5.2 Assert exactly two ffmpeg invocations per clip
- [x] 5.3 Fail loud: ffmpeg non-zero / undecodable clip raises `AnalysisError` naming the clip (no empty-result fallback)
- [x] 5.4 `has-ffmpeg`-marked integration test: run against a generated synthetic clip, assert detected spans

## 6. Sidecar cache (.auto-reel/cache/)

- [x] 6.1 Define on-disk entry format + path layout under `.auto-reel/cache/` (private to the module)
- [x] 6.2 Cache key = clip identity + content-change signal (size+mtime default; optional content hash); shape kept §8.14-compatible
- [x] 6.3 `write`/`read` segments; serialize/deserialize `Segment`s
- [x] 6.4 Invalidation: stale on signal mismatch; cold on missing/unreadable/unparseable entry → re-run + rewrite
- [x] 6.5 `analyze_event` (or cache wrapper): warm read returns cached segments with no ffmpeg pass; cold/stale runs detection then writes
- [x] 6.6 Tests: cold-write, warm-read (assert no ffmpeg call), modified-clip re-run, corrupt-entry recovery

## 7. Guardrails & integration boundaries

- [x] 7.1 Test: analysis does not modify `reel.yaml`
- [x] 7.2 Test: `scan_event` triggers no detection passes and writes no cache entries
- [x] 7.3 Export public API (`Segment`, `analyze_clip`, `analyze_event`, `AnalysisConfig`, `AnalysisError`) from `auto_reel_ng/__init__.py`

## 8. Quality gate

- [x] 8.1 `black`/`isort`/`mypy` clean over `auto_reel_ng/analysis/`
- [x] 8.2 Full `pytest` green; add `has-ffmpeg` marker registration if not already present
