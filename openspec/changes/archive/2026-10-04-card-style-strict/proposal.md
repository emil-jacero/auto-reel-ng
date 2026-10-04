## Why

Supervisor follow-ups from the reviews of PRs #107, #116 and #117 (2026-10-04). The event-wide
`look.title_card` is parsed by `parse_title_card_config` more leniently than a chapter's own card:
an unknown key is silently ignored (a typo such as `titel_font_size` renders with the default and
nothing says so) and `title_font_size`, `subtitle_font_size` and `duration` are not range-checked,
while the same fields on a chapter's `card` are bounded by the loader (`CARD_MIN_DURATION` /
`CARD_MAX_DURATION`, `CARD_MIN_FONT_SIZE` / `CARD_MAX_FONT_SIZE` in `reel/card.py`). `check_card_styles`
documents this laxness as a follow-up. The editorial PUT and the event detail already route the
event-wide style through the parser, so tightening it there is enough for the API to answer 400 and
`title_card_error` naming the field. Separately,
`tests/test_proxies_ensure.py::test_an_editorial_edit_never_invalidates_a_proxy` greps every ffmpeg
argument for the substring `rotate`, so it fails whenever `TMPDIR` or the worktree path contains the
word (it bit three agents).

## What Changes

- `parse_title_card_config` rejects any key that is not a field of the title-card config, and applies
  the chapter card's bounds to `title_font_size`, `subtitle_font_size` and `duration` (the constants
  of `reel/card.py`, not copies). Each refusal is a `TitleCardError` that names `look.title_card.<field>`.
- `check_card_styles` and the `title-card` requirement stop describing the event-wide parse as lax.
- No rendered-output change for valid input: no `RENDER_GRAPH_VERSION` bump. An event whose
  `look.title_card` is now refused reports `title_card_error` in the detail (still 200) and fails its
  render loud, as a malformed value already does.
- The dev and sample libraries were checked: `scripts/make_dev_library.py` and
  `scripts/seed_compose_library.py` write no `title_card`, and no `reel.yaml` under `auto-reel-media/`
  or the compose seed carries one, so nothing in them is newly refused (re-checked at apply).
- The proxy-cache test matches ffmpeg filter-graph tokens (`transpose=`, the `rotate=` filter,
  `-noautorotate`) instead of a path-sensitive substring, and a test proves it under a `TMPDIR`
  containing `rotate`.

## Capabilities

### Modified Capabilities

- `title-card`: "Title-card config parsed from `look`" refuses unknown keys and out-of-range sizes
  and durations, naming the field.

## Impact

- Packages: `render/title` (config.py), tests.
- No API schema change, so no regenerated web types; the existing `api-service` text already says
  the engine's refusal is a 400 naming the field and `title_card_error` on the detail.
- Research evidence: none needed; the rule is the existing per-card bounds, reused.
