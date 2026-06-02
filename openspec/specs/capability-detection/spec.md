# capability-detection Specification

## Purpose

Probe the host into a typed capability inventory and a list of enumerated devices, combining ffmpeg-reported capabilities with system discovery (render nodes, `nvidia-smi`, VAAPI, OpenCL), and empirically self-test each candidate operation so that only operations verified to work — never assumed from mere presence — are exposed as usable capability flags to downstream stages.

## Requirements

### Requirement: Accelerator and device enumeration

The engine SHALL build a typed capability inventory of the host by combining ffmpeg's reported capabilities
(`-hwaccels`, `-encoders`, `-decoders`, `-filters` via `ffmpeg-runtime`) with system discovery of
`/dev/dri/renderD*` nodes and, when present, `nvidia-smi -L`, VAAPI (`vainfo` per render node), and OpenCL
devices. The result SHALL include a list of **enumerated devices**, each with a stable id, vendor, human name,
and render node (where applicable). Missing optional tools SHALL degrade gracefully rather than fail.

#### Scenario: Inventory reflects ffmpeg-reported capabilities
- **WHEN** capability detection runs on a host whose ffmpeg lists `hevc_vaapi` among its encoders
- **THEN** the inventory reports `hevc_vaapi` as an available encoder

#### Scenario: Multiple GPUs are enumerated as distinct devices
- **WHEN** the host exposes two render nodes backed by different GPUs
- **THEN** the inventory lists two distinct devices, each with its own id, vendor, name, and render node

#### Scenario: Optional tool absence degrades gracefully
- **WHEN** `nvidia-smi` is not installed
- **THEN** detection completes without error and simply reports no NVIDIA devices from that source

### Requirement: Empirical self-test of candidate operations

The engine SHALL verify each candidate operation (hardware decode, normalize=scale+pad, overlay, tonemap, and
each encoder) by executing it on a tiny synthetic clip, and SHALL classify each as **working**, **unsupported**,
or **faulting**. Operations that error or crash SHALL be excluded from the usable capability set. Detection
SHALL NOT mark an operation usable on the basis of its mere presence in ffmpeg's filter/encoder listing.

#### Scenario: Unsupported hardware filter is excluded
- **WHEN** the self-test runs an overlay operation that the driver rejects (e.g. `overlay_vaapi` "not supported")
- **THEN** that operation is classified unsupported and excluded from the usable capability set

#### Scenario: Faulting operation is excluded, detection survives
- **WHEN** a self-tested operation crashes the GPU process (e.g. `tonemap_opencl` page fault)
- **THEN** detection records that operation as faulting, excludes it, and still returns an inventory

#### Scenario: Presence alone is insufficient
- **WHEN** an encoder is listed by ffmpeg but fails the self-test encode
- **THEN** it is not reported as a usable encoder

### Requirement: Capability flags for downstream stages

The inventory SHALL expose, per usable accelerator, explicit capability flags consumed by later stages: the
pad filter to use (if any), `can_overlay_hw`, `can_tonemap_hw`, the set of usable hardware encoders by codec,
and the hardware decode method. Each flag's value SHALL reflect the self-test result, not assumption.

#### Scenario: AMD flags reflect verified reality
- **WHEN** detection runs on an AMD VAAPI host like the dev machine
- **THEN** the flags report a usable pad filter (`pad_vaapi`), `can_overlay_hw=false`, `can_tonemap_hw=false`, and h264/hevc/av1 VAAPI encoders usable

#### Scenario: Flags drive fallback decisions
- **WHEN** `can_tonemap_hw` is false for the selected accelerator
- **THEN** the flag value is available for the caller to choose the CPU tonemap fallback
