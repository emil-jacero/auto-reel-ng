## MODIFIED Requirements

### Requirement: Overlay compositing with CPU bridge fallback

For a segment carrying one or more `OverlaySpec` entries, the engine SHALL composite them during the normalize
pass. It SHALL use the profile's hardware overlay only when `can_overlay_hw` is true; otherwise it SHALL
composite via a CPU overlay bridge (downloading frames, overlaying, and re-uploading only as needed for that
segment), leaving overlay-free segments fully on the hardware path. The CPU bridge SHALL run only over frames
that can show an overlay: a source segment carrying a timed overlay is split at the end of the overlay's window
(see `render-segments`, "A timed-overlay segment is split at its window"), so the bridge covers the head and the
tail is an ordinary overlay-free segment on the hardware path.

An `OverlaySpec` MAY name a registered `segment-producer` instead of an image, with the producer's opaque
payload. The engine SHALL materialize such an overlay before it builds the segment's command, whether the
command is to be run or only planned: it SHALL ask the producer for the rendered image, its duration and its
fade timings, and composite that image for that duration. An overlay naming a producer that is not registered
SHALL fail loud, naming the producer and the registered ones.

An overlay that carries a fade-in or fade-out is a **timed overlay**: a still image shown over the first
`duration` seconds of the segment (its start at the segment's start), faded in and out on its alpha channel so
that the segment's own picture shows through the fading text, not a faded black or white frame. A timed overlay
SHALL be composited with the CPU overlay on every profile, including one whose `can_overlay_hw` is true, and
SHALL NOT change the segment's duration, audio or frame rate. Its window SHALL NOT exceed the segment's length:
when the requested duration is longer than the segment the engine SHALL clamp the window to the segment's
length, scale the fades down together so their sum does not exceed the window, and report a warning on the
normalize result naming the segment, the requested duration and the shown duration. An overlay without fades
SHALL be composited exactly as before this requirement was extended.

#### Scenario: Overlay on AMD uses the CPU bridge
- **WHEN** a segment with an overlay is normalized on a host where `can_overlay_hw` is false
- **THEN** the overlay is composited via the CPU bridge for that segment and overlay-free segments are unaffected

#### Scenario: Segment without overlays stays on the hardware path
- **WHEN** a segment has no overlays on a hardware-capable host
- **THEN** its normalize command contains no overlay operation and no overlay-driven transfer

#### Scenario: Overlay without fades is unchanged
- **WHEN** a segment carries an overlay with no fade-in and no fade-out
- **THEN** its normalize command is the same as it was before timed overlays existed

#### Scenario: Timed overlay on AMD
- **WHEN** a segment carries a 7 s overlay with a 2 s fade-in and a 2 s fade-out and is normalized on a host where
  `can_overlay_hw` is false
- **THEN** the command loops the overlay image for 7 s as a second input, fades its alpha in over 0-2 s and out
  over 5-7 s, composites it with the CPU overlay between the CPU download and the upload to the hardware encoder,
  and encodes a segment whose duration is the segment's own

#### Scenario: Timed overlay on the CPU profile
- **WHEN** the same segment is normalized with the CPU profile
- **THEN** the command has the same overlay input, fades and overlay filter, with no download or upload

#### Scenario: Timed overlay avoids a hardware overlay filter
- **WHEN** a segment carries a timed overlay and the selected profile reports `can_overlay_hw` true
- **THEN** the overlay is composited with the CPU `overlay` filter, not the profile's hardware overlay filter

#### Scenario: Overlay window longer than the segment
- **WHEN** a 7 s timed overlay with 2 s fades is attached to a segment that is 3 s long
- **THEN** the overlay is shown for the segment's 3 s, its fades are scaled so they total no more than 3 s, the
  normalize result carries a warning naming the segment, 7 s and 3 s, and the segment is still 3 s long

#### Scenario: Producer-backed overlay is materialized
- **WHEN** a segment's overlay names the `title` producer and its payload
- **THEN** the producer is asked for the image before the command is built, and the command's overlay input is
  that image, in a planned (dry-run) command as well as a run one

#### Scenario: Unknown overlay producer fails loud
- **WHEN** a segment's overlay names a producer that is not registered
- **THEN** building its command raises a render error naming the producer and the registered producers, and no
  command is produced without the overlay

#### Scenario: The bridge does not cover footage after the card
- **WHEN** a 7 s timed overlay is attached to a 180 s first clip on a host where `can_overlay_hw` is false
- **THEN** the head's command has the download, overlay and upload for its 7 s, and the tail's command (173 s)
  contains no overlay, no card input, no `-filter_complex`, and no `hwdownload` or `hwupload`
