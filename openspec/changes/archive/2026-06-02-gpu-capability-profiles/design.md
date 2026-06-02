## Context

This change converts the raw ffmpeg capability text exposed by `ffmpeg-runtime` (change #1) into a usable
acceleration-profile API for the render pipeline (#4). It is the most research-backed change in the project:
the hardware spikes (`experiments/002–004`) and the literature note (`docs/research/cross-vendor-ffmpeg.md`)
established what is real per vendor. The guiding lesson is **assume nothing, verify everything** — capability
presence in ffmpeg's listings did not predict reality on AMD (`overlay_vaapi` unsupported, `tonemap_opencl`
faulted the GPU, yet `scale_vaapi,pad_vaapi` worked and was fastest). Relevant decisions: D-3 (auto-pick best,
override allowed) and D-4 (reserve per-job device targeting for future multi-GPU). The dev host is dual-GPU
(RX 9070 XT + Radeon 780M) so device enumeration is exercised for real.

## Goals / Non-Goals

**Goals:**
- A typed capability inventory + enumerated device list from ffmpeg + system probes.
- A **startup self-test** that empirically classifies each candidate op as working / unsupported / faulting.
- Per-vendor `AccelProfile`s (AMD/NVIDIA/Intel/CPU) that emit ffmpeg fragments per logical op, track frame
  location, and always have a CPU fallback.
- Best-accelerator selection with override; reserved per-request device selector.

**Non-Goals:**
- Assembling the render graph / concat (#4) — profiles only emit fragments.
- Implementing the tonemap/overlay *stages* (#4/#5) — only exposing their capability flags + CPU fallbacks.
- Postgres persistence and the scheduler (#7) — results are in-process with an optional file cache.

## Decisions

- **Self-test is mandatory, not optional.** Each op is verified by running it on a 1-frame synthetic clip
  (built with `ffmpeg lavfi`, no real media). Classification: *working* (exit 0, expected output), *unsupported*
  (clean ffmpeg/driver rejection), *faulting* (crash/non-clean failure — run in a child process so a GPU fault
  can't take down detection). Rationale: this is the literal lesson of exp 003/004. *Alternative:* trust
  `-filters`/`-encoders` listings — rejected; they were wrong on AMD.
- **Profiles emit fragments, they don't run ffmpeg.** An `AccelProfile` returns structured fragments
  (input flags, filter snippet, output/encoder flags) + a frame-location tag per op. The render change (#4)
  composes them. Rationale: keeps profiles pure and unit-testable via **golden fragment assertions** (no GPU
  needed to test the AMD/NVIDIA/Intel argument strings). *Alternative:* profiles own the whole pipeline —
  rejected; couples detection to rendering and is untestable without hardware.
- **Frame-location tracking on every op.** Each op declares `frames_in`/`frames_out` ∈ {hw(ctx), system}. The
  composer inserts `hwupload`/`hwdownload` only where locations disagree. Rationale: exp 002 showed silent
  CPU round-trips and broken interop; making transfers explicit prevents accidental sub-realtime fallbacks.
- **Guaranteed CPU fallback per op.** The CPU profile is always usable and complete; vendor profiles delegate
  any non-usable op to it (notably AMD tonemap → `zscale,tonemap`, AMD overlay → CPU `overlay` / title-as-segment).
- **Selection = capability rank, with override.** Rank usable accelerators (hw > cpu; prefer the op coverage a
  job needs); honor an explicit vendor/device override or fail clearly. Device selector defaults to `auto`;
  v1 uses the first usable device, the field exists for D-4.
- **Enumeration sources are additive and optional.** ffmpeg listings are the base; `nvidia-smi -L`, `vainfo`
  per render node, and OpenCL enumeration enrich it; each is best-effort and absence is non-fatal.
- **Caching.** The inventory+self-test result is cached in-process and optionally to a file keyed by a host
  fingerprint (ffmpeg version + device set), to avoid re-running the self-test every startup; a flag forces refresh.

## Risks / Trade-offs

- **Self-test latency at startup** (running N tiny encodes) → Mitigation: tiny 1-frame clips, run candidates in
  parallel, cache results keyed by host fingerprint; refresh only on change.
- **A GPU fault during self-test** (seen with `tonemap_opencl`) → Mitigation: run each probe in a child process
  with a timeout so a crash/hang is contained and recorded as *faulting*, not fatal to the app.
- **NVIDIA/Intel fragments are unverified on this host** → Mitigation: they are best-guess but **only used if the
  self-test passes**; golden tests pin the *strings*, the self-test gates *use*. Flagged for hardware validation.
- **Device-id stability across reboots** (render-node numbering can shift) → Mitigation: derive ids from a stable
  attribute (PCI address / driver+name) where available, not just `renderD12N`; document the limitation (research §8.13).
- **Over-trusting the file cache** after a driver/hardware change → Mitigation: fingerprint includes ffmpeg
  version + enumerated device set; mismatch invalidates the cache.

## Migration Plan

Additive: a new `auto_reel_ng/accel/` package consuming the existing `ffmpeg-runtime`. No changes to shipped
behavior yet (no renderer consumes it until #4). Rollback = revert; #1 is unaffected.

## Open Questions

- Exact rank function when a host has multiple usable hardware vendors (out of scope on the single-vendor dev host).
- Whether the file cache lives next to config or in a state dir — settle when the service/config change (#3/#7) lands.
- NVIDIA/Intel fragment details (e.g. NVENC needs `format=nv12` before encode; Intel pad needs libplacebo/CPU per
  research) — pin during hardware validation; the self-test protects correctness in the meantime.
