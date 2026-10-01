## Why

GUI v1 (HLD **§6 phase 8**) is complete on `main` (`93721b3`). Its final end-to-end pass found a render that
moved a clip out of the chapter the page showed it in. The failing check was "after Render, each clip stays
in the chapter the page showed it in". On `2024-08-20 - Två kapitel - Tjörn`:

- The page listed the NEW clip `Kvällen/s1710004.mp4` under `Kvällen`.
- Edit mode would also have adopted it there ("A new clip joins reel.yaml once its chapter's order is saved").
- Pressing Render adopted it into the default chapter instead, so the movie plays it in `Main`, and
  `Kvällen` lost it.

The render follows locked decision **D-CLI3** (`project-cli`, design.md:50): `render` adopts each NEW clip
"into the default chapter (configurable)". `cli/adoption.py` `prepare_event` (lines 91–95) does exactly that.
The read model places the same clip by folder instead (`api/events_read.py` `_build_chapters`, lines
363–375). HLD §2 carries legacy's "chapter-from-subdirectory convention" forward, so the folder is the
operator's statement of where a clip belongs.

On 2026-10-01 the user agreed to amend D-CLI3: a NEW clip is adopted into the chapter named after its
folder, and falls back to the default chapter only when `reel.yaml` has no chapter of that name.

This was reproduced on a scratch library through the real `auto-reel render`, comparing the read model
before and after (design, "Reproduction"). The same split appears in two more cases:

| `reel.yaml` | Detail shows the NEW clip | Render adopts it into |
|---|---|---|
| names `Kvällen` | in `Kvällen` | the default chapter |
| names only the default chapter; NEW clips in `Dag 2/` | in a chapter `Dag 2` that `reel.yaml` lacks, listed last | the default chapter |
| names no chapters (legacy import, or a metadata-only first save); clips at the root and in `Kvällen/` | in `''` and in a chapter `Kvällen` that `reel.yaml` lacks | the default chapter, both |

The amended rule fixes the first row in the engine. For the other two rows the agreed fallback is the
default chapter, so the read model must show those clips there too. This change aligns it. That stays
within two packages: `cli/` and `api/`.

## What Changes

- **Adoption follows the folder (amends D-CLI3, recorded as HLD D-12).**
  - `render`, and the worker's render (a GUI Render), adopt each NEW clip into the chapter named after its
    folder: the event folder's clips into the default chapter, and a subfolder's clips into the chapter
    with that subfolder's name.
  - When `reel.yaml` has no chapter of that name, the clip goes into the default chapter. The default
    chapter is appended after the others if `reel.yaml` lacks it, as it is today.
  - Adoption creates no other chapter. It never moves or re-sorts a clip `reel.yaml` already lists.
  - The clips entering one chapter are appended after its existing clips, in the sort rule's order among
    themselves, whichever folder they came from. This is event-reconcile's per-chapter rule, unchanged.
- **The event detail shows each clip where a render will adopt it.**
  - `GET /api/v1/events/{event_id}` places every disk clip that `reel.yaml` does not list (NEW or IGNORED)
    by the same rule and in the same order. It therefore lists no chapter that `reel.yaml` lacks, except
    the default chapter.
  - An event without a `reel.yaml` still shows the folder seed, which is what a render seeds.
  - For a `reel.yaml` that names no chapters, the detail now shows one default chapter. Edit mode's first
    reorder then writes that one chapter, where on `main` it writes the folder chapters the detail invents.
    The GUI therefore loses its only way to give such an event folder chapters (design, Risks; open for a
    supervisor decision).
  - The response shape does not change, so `web/openapi.json` and `web/src/api/schema.d.ts` stay as they
    are.
- **The adoption target is no longer configurable.** `prepare_event`'s `adopt_chapter` parameter is removed.
  D-CLI3's "(configurable)" was never wired to `config.yaml` or a CLI flag, and no caller passes it.
- **Docs.**
  - HLD §7 gains **D-12**, which records the amendment of D-CLI3 with its date and reason. D-CLI3 itself
    lives only in the archived `project-cli` design, which stays as history. §4.6 gains one sentence.
  - The README's "Adoption policy" bullet is updated.

## Non-goals

- **No chapter creation from folders after seeding.** A folder whose chapter `reel.yaml` lacks does not
  become a chapter. This is the agreed fallback (design, "Alternative: create the folder's chapter").
- **No re-homing of clips adopted earlier.** A clip that an earlier render put in the default chapter stays
  there. An existing order is never re-sorted (event-reconcile).
- **No change to seeding**, to `scan`'s output, to the `adopted N new clip(s)` line, to `enqueue`, or to the
  editorial write API.
- **No web change.** The page renders the chapters the service returns (`web/src/events/EventDetail.tsx`
  line 454). Edit mode's model (`web/src/edit/draft.ts` `detailMatchesDocument`, `buildWriteBody`) accepts
  the aligned detail unchanged.
- **No change to how `MISSING` clips are handled.** They are reported and never removed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `headless-cli`: `Requirement: NEW-clip adoption policy`. NEW clips enter their folder's chapter, with the
  default chapter as the fallback. The requirement also covers the ordering of clips from several folders,
  clips adopted earlier, documents that name no chapters, and the worker's render.
- `api-service`: a new requirement, "The event detail places clips not in reel.yaml by the render's adoption
  rule". It covers placement, ordering, ignored clips, and agreement with `reel.yaml` after a render.

`event-reconcile` is not modified. Its "Clips enter a document in the configured sort order" already says
the rule "SHALL be applied per chapter, to the clips entering that chapter", which this change honors as
written.

## Impact

- **Packages (2):**
  - `cli/`: `adoption.py` gets the placement rule (`place_disk_clips`), and `prepare_event` adopts by it.
  - `api/`: `events_read.py` `_build_chapters` places disk-only clips with the same function.
    `events_read.py` already imports from `cli.adoption` (line 24).
- **Not touched:** `scheduler/worker.py` (line 75) and `cli/commands.py` (line 287) reach adoption through
  `cli/build.py` `prepare_and_persist`, so both CLI and GUI renders get the rule from the one call site.
- **Tests:**
  - `tests/test_cli_adoption.py` (unit)
  - a new `tests/test_cli_render_adoption.py`, a real-ffmpeg CLI render over a scratch library (`has_ffmpeg`)
  - `tests/test_api_events.py` (`requires_db`)
- **CLI vs API (Principle V):** both are touched. Adoption stays an engine/CLI behavior. The API only reports
  where it will place each clip, using the CLI's own function, so no endpoint logic exists that the CLI
  cannot reach.
- **Rendered output:** unchanged for identical inputs, so **no `RENDER_GRAPH_VERSION` bump** (it stays 3).
  The graph is untouched, and adoption only changes which `reel.yaml` a render reads. The same `reel.yaml`
  and clips render the same bytes.
- **Fingerprint:** its inputs are unchanged. The editorial component hashes the document. An event with
  pending NEW clips gets a different post-adoption document than before, but it is stale anyway (clip set).
  An already rendered event lists all its clips, so adoption does nothing and the event stays fresh.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. The wire shape is
  unchanged. Only chapter placement in the detail response changes.
- **Dependencies and gates:** no new library, no gate. It is independent of `output-renamed-reason` and
  `renamed-label-and-zoom-bar`.
- **Size (Principle VIII):** one function and two call sites in two packages, two capability deltas, and
  tests.
