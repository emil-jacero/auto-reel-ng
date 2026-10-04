## Context

- `compose_content` (`render/title/content.py`) returns `subtitle = card.subtitle if set and non-empty else ""`; the
  loader already accepts `subtitle: ""` (`reel/schema.py`, `blank_ok`), `ChapterCard.to_dict()` drops only `None`, and
  `CardBody` passes `""` through `PUT`, `GET` and the preview (`_draft_card` filters `is not None`). So absent and empty
  are already distinct on disk and over HTTP; only the renderer and the web draft collapse them.
- `plan.metadata` holds the resolved date and location (reel.yaml value, else the folder-name seed, D-12).
- `_draw_layout` draws a hard offset shadow (`shadow_offset` 3 px, `shadow_opacity` 0.5) then outline then fill, for
  both backgrounds. `render_card_png` is the one seam for preview and render (`title-card` spec), and the video card
  is drawn on a transparent canvas, so a blurred layer needs no compositing elsewhere.
- Web: `web/src/edit/card/model.ts` `textOf` maps `""` to `null`; `Inspector.tsx` sends `null` for an empty field;
  `specs.ts` `draftSpec` uses `own.subtitle ?? ''`. The page is forbidden a default of its own (web-app spec).
- Evidence: the legacy format is `git show 7cbbdc4:auto_reel_ng/render/title/content.py` (`format_date` = ISO,
  `format_location` = `Plats: <value>`, lines in the order date, location, description). No research file in
  `research/v2/` covers this change; the sizes below are the user-facing brief's, checked by eye in the task 2 frames.

## Goals / Non-Goals

**Goals:** the opening card says when and where by default; white text stays legible over bright footage; the
author can say "nothing" (`""`) and "the default" (key removed) and the page shows which is which.

**Non-Goals:** the description is not drawn; no new card key, schema version or migration; no shadow controls (the
existing `shadow_*` keys stay; `shadow_offset: 0` or `shadow_opacity: 0` still turns the shadow off); no change
to chapter cards; the preview uses the saved date and location (editing the date in the same draft does not move
the previewed default until saved; a follow-up if it matters).

## Decisions

1. **Default text lives in `compose_content`, not in the page or the loader.** For the default chapter with
   `card is None` or `card.subtitle is None`: lines `date.isoformat()` then `Plats: <location>`, each only when
   present, joined with `\n`. `subtitle == ""` yields no line. Anything else is used as written. Alternative: have
   the writer fill the key on first save; rejected, it would freeze a default and make a later date edit stale.
   Locale of the label stays Swedish, as the legacy tool did (`LOCATION_LABEL`, kept as a constant of `content.py`).
2. **The same function yields `default_subtitle`.** A pure helper `default_subtitle(plan, chapter)` returns the
   default text (`""` for a chapter card or when the metadata has neither), `compose_content` uses it, and `card_read`
   passes it out. Alternative: the page formats `metadata.date`/`location`; rejected, it would duplicate the label and
   the format (and the page may show no default it was not told).
3. **Soft shadow = a blurred copy of the glyph path, drawn first, only for `background == "video"` and when
   `has_shadow`.** Render the text layout to a separate A8/ARGB surface, blur with a deterministic separable box
   blur (three passes approximating a Gaussian, integer radius from `0.006 x height`, no random or locale input),
   tint with `shadow_color` at 0.6 alpha, composite at `(+0.004 x height, +0.004 x height)`, then draw outline and fill
   as today. The blur is ours (numpy-free, plain Python over the one surface or `cairo` filters if the install has
   none); the choice is made in task 2 by whichever is deterministic bit for bit across two runs. Alternative:
   a larger hard offset; rejected, it reads as a double image on footage. Alternative: a dark scrim behind the
   text; rejected, it changes the look more than asked.
4. **Black cards keep the old path.** The hard shadow stays for `black` (pixel-identical, tested by a stored hash), so
   the change touches only the new branch.
5. **`RENDER_GRAPH_VERSION` 8 to 9** (re-check at apply) with history line `9: title-card-date-place-shadow (the
   opening card's default subtitle and the video card's soft shadow)`. Nothing else enters the fingerprint; the
   editorial hash is unchanged because an absent subtitle still hashes as absent.
6. **Web keeps `""` and `null` apart** in the card draft (`CardDraft.subtitle: string | null`, `null` = unset);
   only the subtitle field changes (`textOf` stays for the others). `cardBody` sends `""`. The opening card's
   unset subtitle shows `default_subtitle` as its placeholder and in the row/preview text; chapter cards keep
   "No subtitle". `draftSpec` uses the detail's `default_subtitle` when unset, the saved effective subtitle when the
   card is unchanged, and never invents text.

## Risks / Trade-offs

- A blur written in Python is slow at 4K; the card is one image per card and is cached by the render, so the cost
  is per render, not per frame. Measured in task 2 (budget: under 100 ms at 1920x1080).
- Every event with a date re-renders and its opening card grows two lines; the opt-out is `subtitle: ""`.
- Existing explicit `subtitle` values are untouched.
