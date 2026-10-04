## Why

A user render failed on the VAAPI profile with "segments could not be made copy-uniform; refusing a silent-broken
concat" (2026-10-04, job 462f2547, event `2025/2025-01-15 - Provklipp`). Root cause (debug report
`dbg-provklipp/REPORT.md`, reproduced on `e5d3041`): a clip with no SAR (`N/A`) and a display rotation of 90 that
has `rotate: 270` has a net turn of 0, so since `clip-rotate-engine` its VAAPI normalize is a bare `scale_vaapi`
with no `setsar`; the unset SAR passes through, the segment probes `sample_aspect_ratio=N/A` while every other
segment is `1:1`, and the raw-string equivalence pre-flight rejects a set that would in fact play correctly. The
CPU, QSV and NVENC chains already end in `setsar=1`, so only VAAPI renders fail.

## What Changes

- Every normalize path forces square pixels explicitly: the VAAPI normalize (scale-only and scale+pad) ends in
  `setsar=1`, so an overlay-free VAAPI segment, a video-card head (bridge with the CPU overlay) and its tail on the
  GPU all carry SAR 1:1. `setsar` is metadata-only and was proven to run on VAAPI hardware frames on this host.
  The CPU/QSV/NVENC chains already end in `setsar=1` and are pinned by tests so they stay that way.
- The equivalence pre-flight compares SAR **normalized** the way copy eligibility already does (unset, `N/A`,
  `0:1` and empty mean `1:1`), so an unset SAR never blocks a concat that is uniform in fact (this also covers a
  stream-copied source clip whose SAR is unset).
- `RENDER_GRAPH_VERSION` 11 → 12 (VAAPI output now carries SAR 1:1 for identical inputs); fingerprint goldens
  re-pinned.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `clip-normalize`: "Rotation and aspect normalization" — every normalized segment, on every profile and for
  every turn including a net turn of 0, carries an explicit SAR 1:1.
- `movie-assembly`: "Equivalence pre-flight before stream-copy concat" — SAR is compared normalized (unset ≡ 1:1).

## Impact

- Code (package `render`, plus the VAAPI profile fragment it composes): `auto_reel_ng/accel/profiles/vaapi.py`
  (normalize filters), `auto_reel_ng/render/concat.py` (`probe_copy_fields` SAR), `auto_reel_ng/render/normalize.py`
  (SAR normalizer shared with concat), `auto_reel_ng/staleness/fingerprint.py` (version + history line).
- Every rendered event reports stale once (engine fingerprint changes); `--force` not needed.
- No API, schema, web, proxy-cache or config change. The VAAPI self-test probe is unchanged.
