## 1. Strict event-wide card style

- [x] 1.1 In `render/title/config.py`, make `parse_title_card_config` refuse unknown keys (allowed set derived from the `TitleCardConfig` fields) with a `TitleCardError` naming `look.title_card.<key>` and listing the allowed fields. Test (`tests/test_title_card_config.py` or the existing config test module): a typo key is refused naming it; every real field still parses; `resolve_card_config` with a chapter card still passes.
- [x] 1.2 In the same parser, bound `title_font_size`, `subtitle_font_size` (`CARD_MIN_FONT_SIZE`..`CARD_MAX_FONT_SIZE`) and `duration` (`CARD_MIN_DURATION`..`CARD_MAX_DURATION`) using the constants from `reel/card.py`, inclusive, NaN refused, error naming field, value and range. Test: parametrized below/at/above each bound for the three fields; fades clamp unchanged at the bounds.
- [x] 1.3 Test no rendered-output change: a fully valid `look.title_card` (all sixteen fields) parses to the same `TitleCardConfig` (checked by a `to_dict` round-trip); `RENDER_GRAPH_VERSION` is not edited, and the existing fingerprint/version pins pass untouched (no dedicated fingerprint test).
- [x] 1.4 Update the `check_card_styles` docstring (the laxness paragraph) to say the event-wide style is strict; keep the font-registry check for chapters. Test: `check_card_styles` refuses an unknown event-wide key and an out-of-range duration, naming `look.title_card.<field>`.

## 2. API

- [x] 2.1 API tests: an editorial PUT (`tests/test_api_editorial*`) with `look.title_card` carrying an unknown key, `duration: 900`, `title_font_size: 4000` and `subtitle_font_size: 2` answers 400 naming `look.title_card.<field>` and leaves `reel.yaml` byte-identical; the same value hand-written into `reel.yaml` gives a 200 event detail with `title_card` and every `card` null and `title_card_error` naming the field.
- [x] 2.2 Library audit: grep `scripts/make_dev_library.py`, `scripts/seed_compose_library.py`, the legacy importer and the read-only `auto-reel-media/` for `title_card`; assert by test that a built dev library and an imported legacy event write no `look.title_card` key that the strict parser refuses, and record what was found in the PR body.

## 3. Proxy test robustness

- [x] 3.1 In `tests/test_proxies_ensure.py::test_an_editorial_edit_never_invalidates_a_proxy`, replace the `"rotate" in " ".join(run)` check with a helper that matches ffmpeg filter-graph tokens only (`-noautorotate`, and `transpose=` / `rotate=` inside the `-vf` / `-filter_complex` value). Test: the helper is true for graphs with `transpose=1`, `rotate=PI/2` and `-noautorotate`, and false for a command whose clip and cache paths contain `rotate`.
- [x] 3.2 Prove the original test passes under a path containing the word: run it with `TMPDIR` set to a directory containing `rotate` (a parametrized variant using `tmp_path_factory` with a `rotate-` basename, so it runs on every machine, not only when the environment happens to).

## 4. Docs

- [x] 4.1 HLD: in the title-card notes of `docs/high-level-design.md` (§4.10 / §6, near the card-model entry) record that the event-wide `look.title_card` is parsed as strictly as a chapter card (unknown keys and size/duration bounds refused, naming the field); no new D-number is needed (D-20/D-21 are the timeline and proxy contract and are untouched). No test (docs-only edit).
