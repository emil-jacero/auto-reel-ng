## Context

`parse_title_card_config` (render/title/config.py) is the single parser of the event-wide
`look.title_card`, of `resolve_card_config`'s layered result and, through `check_card_styles`, of the
editorial PUT and the event detail. A chapter `card` is range-checked earlier by the loader in `reel/`,
which owns the bounds (`CARD_MIN_DURATION` 0.5, `CARD_MAX_DURATION` 60, `CARD_MIN_FONT_SIZE` 8,
`CARD_MAX_FONT_SIZE` 400) because `reel/` sits below `render/`.

## Decisions

- **One parser, one rule.** The bounds and the known-key set are applied inside
  `parse_title_card_config`, importing the constants from `reel/card.py`. Per-chapter values reach the
  same parser through `resolve_card_config`, so they are checked twice with identical limits; that is
  harmless and means an event-wide value cannot sit outside what a card may set.
- **Known keys** are the fields of `TitleCardConfig` (derived from `dataclasses.fields`, not a second
  list), so adding a field cannot leave the check stale. The error names the key and lists the allowed
  ones: `look.title_card.<key> is not a title-card field; use one of: ...`.
- **Bound errors** name the field, the value and the range, e.g.
  `look.title_card.duration must be between 0.5 and 60.0 seconds, got 900.0`. Bounds are inclusive.
  `bool` is already refused before the range test. NaN is refused by the same comparison form
  (`not lo <= v <= hi`).
- **Fades.** Clamping is unchanged and runs after the duration check.
- **No graph bump.** Valid input parses to the same `TitleCardConfig`, so rendered bytes and the
  staleness fingerprint do not change. Previously accepted but out-of-range values now fail; that is a
  refusal, not an output change.
- **Libraries.** The dev-library and compose-seed scripts write no `title_card`; the audit at apply
  re-greps them and `auto-reel-media/` (read-only) and records the result in the PR.
- **Test fix.** The proxy test asserts on filter-graph tokens: an argument that is `-noautorotate`,
  or one whose `-vf`/`-filter_complex` value contains `transpose=` or `rotate=`. The test tmp path is
  never inspected. A second test sets `TMPDIR`-derived paths containing `rotate` (a clip directory named
  `rotate-me`) and shows the assertion still passes, while a hand-built graph with `transpose=1` still
  trips it.

## Risks

- A hand-edited `look.title_card` with an out-of-range value that rendered before now fails. Mitigated
  by the detail staying 200 with `title_card_error`, so the author can open and fix it.
