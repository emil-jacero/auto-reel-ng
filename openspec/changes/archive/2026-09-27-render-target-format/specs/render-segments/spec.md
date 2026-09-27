## MODIFIED Requirements

### Requirement: Target spec derivation

The engine SHALL derive a **target spec**, the common canvas every segment conforms to, from:

- the resolved `look`
- the probe facts of **all** clips in the render plan
- the selected acceleration profile's usable encoders

The target spec SHALL include:

- **video resolution:** from `look.target_resolution`, a `[width, height]` pair, defaulting to 1920×1080
- **frame rate:** from `look.fps`, a positive number, defaulting to the highest probed fps among the plan's
  clips
- the chosen video codec and pixel format
- sample aspect ratio (1:1)
- common audio parameters (sample rate, channel count, codec)

No property of the canvas SHALL be taken from a clip because of its position in the plan. A clip whose
dimensions or orientation differ from the canvas SHALL be fitted into it (aspect preserved, padded), never
used to choose it.

A `look.target_resolution` that is not a pair of positive integers, or a `look.fps` that is not a positive
number, SHALL fail loud, naming the key and the offending value. When the look requests a codec the
selected profile cannot encode and CPU fallback is also unavailable, the engine SHALL fail loud rather than
substitute a different codec.

#### Scenario: Resolution and fps come from look and first clip
- **WHEN** the look sets `target_resolution: [1920, 1080]` and `fps: 30`, and the first clip is probed at
  25 fps
- **THEN** the target spec is 1920×1080 at 30 fps: the look decides, not the first clip

#### Scenario: A portrait first clip does not make a portrait movie
- **WHEN** the look sets no resolution, and the plan's first clip is a 720×1280 phone clip followed by
  1920×1080 camera clips
- **THEN** the target spec is 1920×1080, and the phone clip is pillarboxed into it

#### Scenario: A 4K clip does not make a 4K movie by default
- **WHEN** the look sets no resolution and the plan mixes 3840×2160 and 1920×1080 clips
- **THEN** the target spec is 1920×1080, and the 4K clips are downscaled

#### Scenario: The highest frame rate wins by default
- **WHEN** the look sets no fps and the plan's clips are probed at 25, 50 and 30 fps, with the 25 fps clip
  first
- **THEN** the target spec's frame rate is 50

#### Scenario: A uniform event keeps the stream-copy path
- **WHEN** the look sets neither key, and every clip is a 1920×1080 H.264 clip at 50 fps whose other stream
  parameters already match the target
- **THEN** the target spec is 1920×1080 at 50 fps, and the clips are copy-eligible exactly as before

#### Scenario: An event-level override wins over the library default
- **WHEN** `config.yaml` sets `target_resolution: [1920, 1080]` and one event's `reel.yaml` sets
  `target_resolution: [3840, 2160]`
- **THEN** that event's target spec is 3840×2160, and the others' are 1920×1080

#### Scenario: A malformed fps fails loud
- **WHEN** the look sets `fps: "fifty"` or `fps: 0`
- **THEN** the engine raises a typed error naming `look.fps` and the value, and no segment is rendered

#### Scenario: AV1 target honored when profile supports it
- **WHEN** the look requests AV1 and the selected profile reports a usable AV1 encoder
- **THEN** the target spec's codec is AV1 using that encoder (D-5)

#### Scenario: Unencodable codec fails loud
- **WHEN** the look requests a codec for which neither the selected profile nor the CPU fallback has a usable encoder
- **THEN** the engine raises a typed error rather than picking a different codec
