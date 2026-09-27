## ADDED Requirements

### Requirement: Hardware padding is verified by its output

When the self-test verifies a hardware pad operation, it SHALL check the padded pixels, not only that the
operation exits cleanly. The probe SHALL:

- pad a synthetic frame whose aspect ratio differs from the output, so that a padded region exists
- request a black fill
- read the padded region back

Detection SHALL report a capability flag stating whether the hardware pad fills with the requested colour.
The flag SHALL be true only when the padded region measures as black. A pad that runs but paints any other
colour SHALL leave the flag false, while the operation itself MAY remain usable for clips that need no
padding.

A capability inventory cached before this flag existed SHALL NOT be reused: the cache SHALL carry a schema
version, and a mismatch SHALL cause re-detection.

#### Scenario: A pad that ignores its fill colour is caught
- **WHEN** the self-test runs `pad_vaapi` with `color=black` on a host whose driver fills the padded region
  with zero-valued YUV, which shows as green
- **THEN** the pad-fill flag is false, and the scale-and-pad operation is still recorded as working

#### Scenario: A pad that fills correctly is trusted
- **WHEN** the self-test's padded region measures as black
- **THEN** the pad-fill flag is true

#### Scenario: An old cache is not reused
- **WHEN** a capability cache written before the pad-fill flag existed is found at startup
- **THEN** detection runs again instead of loading it, and writes a cache that includes the flag
