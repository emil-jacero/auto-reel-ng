## ADDED Requirements

### Requirement: Clips are padded where the fill is correct

When normalizing a clip to the canvas, the caller SHALL tell the profile whether the clip needs padding. A
clip needs padding when its pixel aspect or its display aspect differs exactly from the canvas aspect. Both
are taken after rotation; display aspect also has the sample aspect ratio applied. Pixel aspect counts
because the scale fits by pixels and ignores the sample aspect ratio. Exactness means compared as a ratio,
not a rounded decimal.

The profile SHALL emit a hardware pad only when the pad-fill capability flag is true. When the clip needs
padding and the flag is false, the profile SHALL fall back to the CPU scale-and-pad for that clip, with the
frame transfers the chain requires. A clip that needs no padding SHALL keep the hardware scale path whatever
the flag says. No clip SHALL be rendered with a padded region of any colour other than the requested fill.

#### Scenario: A portrait clip gets black bars on a host with a faulty hardware pad
- **WHEN** a 1440×1920 phone clip is normalized to a 1920×1080 canvas on a host whose pad-fill flag is false
- **THEN** its bars are black: the clip is scaled and padded on the CPU between the hardware decode and the
  hardware encode

#### Scenario: A 16:9 clip stays on the GPU
- **WHEN** a 3840×2160 or 1280×720 clip is normalized to a 1920×1080 canvas on the same host
- **THEN** it is scaled on the GPU, with no CPU scale-or-pad stage and no frame transfer

#### Scenario: A nearly-16:9 clip is still padded correctly
- **WHEN** a 1920×1088 clip is normalized to a 1920×1080 canvas on the same host
- **THEN** it is treated as needing padding, and any padded rows are black

#### Scenario: A correct hardware pad is used for every clip
- **WHEN** the pad-fill flag is true
- **THEN** clips that need padding are padded on the GPU

### Requirement: A hardware decode shares its device with the filter graph

When a profile decodes on a hardware device, the decode SHALL use a named device that the filter graph also
uses. A CPU stage placed between the hardware decode and a hardware encode can then upload its frames back
to the device. The CPU stages concerned are padding, rotation, tonemap and an overlay bridge. The same
single device SHALL serve decode, filters and upload, so no second device is opened for one command.

#### Scenario: A rotated clip renders on the GPU path
- **WHEN** a clip with a 90° rotation is normalized with hardware decode and a hardware encoder, so a CPU
  `transpose` sits between them
- **THEN** the command succeeds and the output is upright, rather than failing because the upload has no
  device

#### Scenario: One device per command
- **WHEN** a hardware-decoded clip's normalize command is built
- **THEN** it initializes exactly one named hardware device, and uses it for decode and for the filter graph
