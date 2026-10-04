## Context

See proposal.md — Why. Evidence:

- Debug report `/var/home/emil/dev/larnet/auto-reel-project/dbg-provklipp/REPORT.md` (reproduced on `e5d3041`,
  `--device amd`; CPU passes). Differing field: `sample_aspect_ratio` (`None` vs `1:1`).
- `auto-reel-media/samples/hevc-mov-rotate90-aac.mov` probes `1920x1080`, `sample_aspect_ratio=N/A`, display matrix
  `-90`. Same shape: `h264-720p-rotate90-aac.mp4`.
- Host check (2026-10-04, ffmpeg 8.1.3, AMD Radeon 860M (integrated), `renderD128`, PCI `1002:1114`): the sample
  through `-noautorotate … -hwaccel vaapi -hwaccel_output_format vaapi -vf scale_vaapi=w=1920:h=1080:
  force_original_aspect_ratio=decrease -c:v h264_vaapi` probes SAR `N/A`; with `,setsar=1` appended it probes
  `1:1`. `setsar` runs on VAAPI frames without a transfer.
- Code: `accel/profiles/vaapi.py` `vaapi_scale_filter` / `vaapi_normalize_filter` (no `setsar`);
  `accel/profiles/cpu.py`, `qsv.py`, `nvenc.py` end in `setsar=1`; `render/concat.py` `probe_copy_fields` holds the
  raw ffprobe SAR; `render/normalize.py` `_normalize_sar` already maps `None`/`""`/`N/A`/`0:1` → `1:1` for copy
  eligibility; `render/orchestrator.py` raises after the re-encode retry when `is_copy_uniform` stays false.

Why only the net-zero case: with a turn, the CPU transpose sits between `hwdownload` and `hwupload`; with a pad on
Mesa (`pad_fill_ok` false) the CPU pad fragment ends in `setsar=1`. With neither, the chain is pure `scale_vaapi`
(and, for the 1920x1080 sample, no pad), so nothing sets SAR.

## Goals / Non-Goals

**Goals:** a VAAPI render of the Provklipp event succeeds; every normalized segment carries SAR 1:1 on every
profile; an unset SAR is equivalent to 1:1 in the pre-flight.

**Non-Goals:** relaxing any other copy-critical field; changing how a non-square SAR source is scaled (no scale
honours SAR today — unchanged); the proxy chain (`proxies/command.py` already appends `setsar=1`); the self-test.

## Decisions

1. **`setsar=1` inside the VAAPI normalize fragment, not appended by `normalize.py`.** Both
   `vaapi_scale_filter`'s use in `_normalize` and `vaapi_normalize_filter` end in `,setsar=1`, matching how the
   CPU/QSV/NVENC fragments already own it. Every chain that uses the VAAPI normalize — the overlay-free `-vf`
   chain, the video-card head (normalize → `hwdownload` → CPU `overlay` → `hwupload`; `overlay` takes the main
   input's SAR) and the tail — inherits it. Alternative: append `setsar=1` in `_canvas_stages` for every profile —
   rejected: duplicates the filter on three profiles and churns their goldens for no output change.
   `vaapi_scale_filter` itself stays SAR-free (the self-test builds its own strings; keep the helper a pure scale)
   — the `setsar` is added where the fragment is built.
2. **Normalize SAR in `probe_copy_fields`** using the same rule as `_normalize_sar` (move it to one shared helper
   so the two cannot drift). Safe: an unset SAR is displayed as square by players, so `N/A` and `1:1` segments
   play identically after a copy concat; exp 001's breakage was a *real* SAR difference, which still fails. This
   also covers a copy-eligible source clip with unset SAR (eligible today because eligibility normalizes, but its
   raw `N/A` would fail the pre-flight and trigger a needless re-encode).
3. **Both fixes, not either.** (1) makes the output correct metadata (the movie's SAR is 1:1, as the target spec
   says); (2) stops a metadata-only difference from failing a render on any future path.
4. **`RENDER_GRAPH_VERSION` 12.** VAAPI segment bytes change (the SPS carries VUI aspect 1:1). CPU output can
   change too, in one narrow case: a copy-eligible clip with an unset SAR used to fail the raw pre-flight and be
   re-encoded with `setsar=1`; it now stays stream-copied (Decision 2). The bump is engine-wide by design (D-C8).

## Risks / Trade-offs

- [`setsar` on hardware frames misbehaves on another driver] → it is a metadata-only filter with no format
  restriction; the VAAPI golden test pins it and the real-render VAAPI test proves it on this host.
- [Normalizing SAR hides a real mismatch] → only the four "unset" spellings map to 1:1; any concrete non-1:1 SAR
  still compares unequal (unit test).
- [Whole archive reports stale] → accepted, same as every prior bump; renders are gated, not forced.

## Migration Plan

None beyond the version bump: the next scan reports rendered events stale (engine component), and a render
produces the fixed output. Rollback = revert the commit (version returns to 11).
