## Why

The user decided (2026-10-04, GUI v2): "Opening subtitle: show date and location" and "Shadow on text: yes" (white
text over bright footage is hard to read). Since `title-card-model` the opening card shows only the event title and
a free-text subtitle that is empty unless the author wrote one; the ISO date and the `Plats: <location>` line the
legacy tool drew (`format_date`, `format_location`, `LOCATION_LABEL` in `render/title/content.py` at commit
`7cbbdc4`) are gone. A card over video (`title-card-over-video`) is drawn with the same hard 3 px, 50 % shadow as a
black card, which does not lift white text off a bright frame.

## What Changes

- The opening card's subtitle defaults to the event's resolved date (ISO `YYYY-MM-DD`, the folder-name date counts)
  and, on the next line, `Plats: <location>`, each line only when the metadata has it. The description is not
  shown. The default applies only when the default chapter's `card` has no `subtitle` key. Any text replaces it;
  an explicit `subtitle: ""` means no subtitle. Absent and empty stay distinct through the loader, the writer,
  `PUT .../reel` (`""` is kept, `null` removes the key), the preview and the card resolver. Chapter cards are unchanged.
- A card whose background is `video` gets a soft drop shadow under the title and the subtitle (black, about 60 %
  alpha, offset about 0.004 x height, blur about 0.006 x height), drawn as a blurred text layer under the text,
  deterministic. It replaces the hard offset shadow for those cards. A `black` card is pixel-identical to before.
  The preview endpoint uses the same renderer and shows it with no further work.
- `RENDER_GRAPH_VERSION` +1 with a history line (opening card text and video-card pixels change).
- The event detail's resolved `card` reports the effective `subtitle` (already the field's meaning) and a new
  `default_subtitle`: what the card shows when the key is absent (the date/place text for the opening card, `""` for
  a chapter card), produced by the engine so the page invents nothing. OpenAPI and `web/src/api/schema.d.ts` regenerate.
- Web: the inspector's Subtitle field for the opening card shows `Default: 2024-08-20 / Plats: Tjörn` as its
  placeholder, has a **No subtitle** button that writes `""` and **Use default** that removes the key; the draft keeps
  `""` and unset apart (today `textOf` turns `""` into unset). Chapter rows show the effective subtitle.
- HLD: D-24 note, §4.10 and §6 lines (a task).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `title-card`: the card text rule (default subtitle for the opening card, absent vs empty) and a soft shadow for
  video cards. It also states precedence over the `reel-document` line "Absent or empty means the card has no
  subtitle line" and the matching `api-service` clause, so those older sentences are not rewritten here.
- `api-service`: the resolved card reports `default_subtitle`; the opening card's effective subtitle follows the rule.
- `web-app`: the subtitle field's default placeholder, No subtitle and Use default.

## Impact

- Code: `auto_reel_ng/render/title/content.py`, `render.py`, `staleness/fingerprint.py`, `api/schemas.py`,
  `api/card_read.py`, `web/src/edit/card/`, `web/src/edit/cardRows.ts`, `web/src/api/schema.d.ts`. Packages: `render`, `web`
  (the API field is the engine's value passed through).
- Existing outputs: every rendered event re-renders once (reason `engine`). Every event with a date or location
  and no explicit subtitle gains two text lines on its opening card; `subtitle: ""` is the opt-out.
- Three capability deltas, one over the usual two: the API field has to be a contract (the page may not show a default
  it was not told), and `web-app` owns the field. Flagged for the supervisor.
