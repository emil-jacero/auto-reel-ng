## Context

See proposal.md, "Why". This section covers the code as it stands on `main` (`93721b3`).

**The render's adoption** is in `auto_reel_ng/cli/adoption.py`:

- `prepare_event` (lines 70–104) loads the authored document. With no `reel.yaml` it seeds one from the
  folders (`event/discovery.py` `seed_document`, lines 196–218: subfolders become chapters).
- It reconciles that document against `scan_event` (`event/discovery.py` lines 119–140). The scan groups
  clips by folder in `DiskListing.by_chapter`: the event root first, under `DEFAULT_CHAPTER_NAME = ""`,
  then each subfolder by name.
- When `adopt` is set, it does this (lines 91–95):

  ```python
  authored = _ensure_chapter(authored, adopt_chapter)          # adopt_chapter defaults to ""
  adopted = order_clips(result.new, event_dir, authored.sort or order)
  for identity in adopted:
      authored = add_clip(authored, identity, adopt_chapter)
  ```

  Every NEW clip goes to one chapter, whatever its folder. `_ensure_chapter` (lines 116–134) appends that
  chapter last when the document lacks it.

There is one call site with `adopt=True`: `cli/build.py` `prepare_and_persist` (lines 43–58). Both `render`
(`cli/commands.py` line 287) and the job-scheduler worker (`scheduler/worker.py` line 75, which serves the
GUI's Render) go through it. `persist` writes only when the document was seeded or adopted into (lines
60–62, 107–113).

**The read model** is in `auto_reel_ng/api/events_read.py` `_build_chapters` (lines 325–376), called by
`get_event` (line 442):

- With no `reel.yaml`, it returns the folder seed's chapters (lines 340–350). This is what a render seeds.
- With a `reel.yaml`, it lists the document's chapters first (lines 353–361). It then walks
  `listing.by_chapter` and places every clip the document does not list (lines 363–375):
  - A clip goes into the chapter named after its folder when the document names that chapter.
  - **Otherwise it goes into a new chapter with the folder's name, appended after the document's
    chapters** (lines 372–375).
  - Clips are ordered per folder group by `document.sort or order`.

**The web client** shows `detail.chapters` in the order the service returns them
(`web/src/events/EventDetail.tsx` line 454). It names the default chapter `Main` when there is a named
chapter, else `Clips` (`web/src/edit/EventEditor.tsx` lines 424–426). In Edit mode
(`web/src/edit/draft.ts`):

- `detailMatchesDocument` (lines 69–95) accepts any detail whose chapters begin with the document's
  chapters, each listing its own clips first. Later chapters may hold only NEW or ignored clips.
- `buildWriteBody` (lines 159–200) writes a reordered chapter in the order shown, and appends a reordered
  chapter that the document does not name (lines 181–183).
- When the document names no chapters, a first reorder writes every chapter shown (`writtenFromView`,
  lines 136–142). A metadata-only save writes none (web-app spec, "When `reel.yaml` names no chapters …").

**Documents that name no chapters are a designed state, not an edge case.** Three writers produce them:

- `import` (`reel/legacy.py` lines 9–10: "The resulting document has no chapters/clips: every clip enters it
  later through NEW-clip adoption"), and every load of a versionless legacy `reel.yaml` (README, "Legacy
  documents").
- A GUI metadata-only save on an event with no `reel.yaml`. `event/editorial.py` line 69 starts from an
  empty `ReelDocument`, and lines 181–184 keep it chapterless.
- The "Needs attention" metadata form (web-app, "Events that need attention…": it "SHALL write no chapters
  the event's `reel.yaml` does not already hold").

## Supervisor decisions (2026-10-01)

Recorded before implementation. Where they differ from a section below, they win, and that section says
so.

- **The rule (brief `plan/brief-decisions.md`, Z1).** The user agreed on 2026-10-01: a NEW clip in a
  subfolder joins the chapter named after its folder, and falls back to the default chapter when `reel.yaml`
  has no such chapter.
- **USER DECISION on the edge case (2026-10-01, "Seed like a new event").** When `reel.yaml` names **no
  chapters at all**, adoption builds the chapters exactly as first discovery seeds them: the event folder's
  clips into the default chapter, each subfolder's clips into a chapter of its own, the chapters in seeding
  order (default first, then subfolders by name), and each chapter's clips in the sort rule's order. Every
  other document follows the agreed rule unchanged: the folder's chapter if `reel.yaml` names it, else the
  default chapter. The first draft of this design offered this as option (a') of an open risk, which
  "Risks / Trade-offs" now replaces with the decision. The GUI keeps its folder-chapter view of a document
  that names no chapters, because the read model's view of it is the seed, and that is now what a render
  adopts.
- **Confirmed:**
  - The deltas stay MODIFIED headless-cli and ADDED api-service. event-reconcile is cited, not changed.
  - HLD records the amendment as a new §7 **D-12** plus one sentence in §4.6.
  - Ignored clips are placed by the same rule on the event page.
  - `prepare_event`'s unused `adopt_chapter` parameter is removed.
  - No migration of clips that earlier renders placed in the default chapter.
- **Follow-up, not here:** the web-app scenario "A clip from another folder is named by its path" describes
  its setup with the old adoption wording. Its outcome still holds.
- **Not this change:** `test_editorial_write_save_stale_render_cycle` can fail when run together with
  `test_api_events.py` only (pre-existing test order; "Spiked in review" below).

## Goals / Non-Goals

**Goals:**

- One placement rule for clips the document does not list. Adoption and the read model call the same
  function, so they cannot drift apart again.
- The rule the user agreed to: the folder's chapter when `reel.yaml` names it, else the default chapter.
  A `reel.yaml` that names no chapters is adopted into as a new event is seeded (user decision).
- Ordering stays the event-reconcile rule, applied per target chapter.

**Non-Goals:**

- Moving clips that earlier renders adopted into the default chapter (see "Risks / Trade-offs").
- Any change to the web client, the OpenAPI document, seeding, `scan`, `enqueue` or the editorial write.

## Research & Decisions

### Reproduction

**Context**: The brief requires the problem to be reproduced, and asks exactly how the detail shows a
clip whose folder's chapter `reel.yaml` does not name.

**Explored**: This used a scratch library in the session scratchpad: four 2-second stream-copied cuts of
the fixture's clips, symlinked, never the fixture itself. The script is `repro.py` there. It renders
through the real `auto-reel render` (AMD VAAPI profile) and reads the detail's chapters by calling
`_load_for_reconcile` and `_build_chapters`, which is the code path `get_event` runs (lines 441–442).

- Phase 1 rendered `Två kapitel` (root `s1710001.mp4`, `Kvällen/s1710002–3.mp4`) and `Ny mapp` (root
  `s1710001.mp4`), which seeded their `reel.yaml`.
- It then added `Kvällen/s1710004.mp4` and `Dag 2/s1710002–3.mp4`, plus a third event `Utan kapitel` whose
  `reel.yaml` is `version: 0` plus `metadata` only, with `s1710001.mp4` and `Kvällen/s1710002.mp4`.

Before the second render, the detail showed:

```
Två kapitel   '': s1710001[active]   'Kvällen': Kvällen/s1710002[active], Kvällen/s1710003[active], Kvällen/s1710004[new]
Ny mapp       '': s1710001[active]   'Dag 2': Dag 2/s1710002[new], Dag 2/s1710003[new]        <- 'Dag 2' is not in reel.yaml
Utan kapitel  '': s1710001[new]      'Kvällen': Kvällen/s1710002[new]                          <- reel.yaml names no chapters
```

After `auto-reel render` (`+ … adopted 1 / 2 / 2 new clip(s)`), `reel.yaml` and the detail agree with each
other, but not with the first read:

```
Två kapitel   '': s1710001, Kvällen/s1710004    Kvällen: Kvällen/s1710002, Kvällen/s1710003
Ny mapp       '': s1710001, Dag 2/s1710002, Dag 2/s1710003
Utan kapitel  '': s1710001, Kvällen/s1710002
```

`ffprobe -show_chapters` on `2024-08-20 - Två Kapitel - Tjörn.mp4` gives `'' 0.00→4.04` and
`Kvällen 4.04→8.08`. Two clips play in each chapter, so the movie plays `Kvällen/s1710004.mp4` in Main.

A fourth check covered the GUI's metadata-only first save (`repro_metadata_save.py`). It called
`apply_editorial_write` with `chapters: []` on an event with no `reel.yaml` that holds `s1710001.mp4` and
`Kvällen/s1710002.mp4`. The result was `reel.yaml` = `version: 0` plus `metadata`. The detail still showed
`''` and `Kvällen`, but `prepare_event` would write a single default chapter holding both clips.

**Decision**: Today, a NEW clip whose folder's chapter `reel.yaml` does not name is shown **in a chapter
named after its folder, which the detail invents and lists after the document's chapters**. The render
puts it in the default chapter. Under the agreed fallback, the render keeps doing that for a `reel.yaml`
that names any chapter, so the read model must change to show such a clip in the default chapter.

For a `reel.yaml` that names no chapters (`Utan kapitel`), the detail already shows the folder seed: one
chapter per folder group, in `listing.by_chapter` order. Under the user's decision ("Seed like a new
event"), that is what the render now adopts, so for this row the engine changes and the read model's view
stays as it is.

**Rationale**: The brief asks for the read model to be aligned only if that stays within two packages. It
does: `cli/` and `api/`. The web client needs no change (see "The web client needs no change").

### The rule (amended D-CLI3, recorded as HLD D-12)

**Context**: The user agreed (2026-10-01) to adopt a NEW clip "into the chapter named after its folder, and
fall back to the default chapter only when the document has no such chapter".

**Explored**: Three cases, from the reproduction:

- the chapter is named
- a folder's chapter is not named while others are
- the document names no chapters

There is also the default chapter itself being absent, for a root clip or a fallback clip.

**Decision**: A clip's *folder chapter* is the `DiskListing.by_chapter` group it was found in: `""` for the
event folder, the subfolder's name otherwise. Its *target* is the folder chapter when
`document.chapter(folder) is not None`, else `DEFAULT_CHAPTER_NAME`. The match is exact and case-sensitive,
as seeding names chapters exactly after folders. In a document that names any chapter, a target that the
document lacks can only be the default chapter. It is appended after the document's chapters, as
`_ensure_chapter` does today, and no other chapter is created.

The one exception is the user's decision: when the document names **no chapters at all**, every clip's
target is its folder chapter, and the targets come in `listing.by_chapter` order (the default chapter
first, then subfolders by name). Adoption then creates each of those chapters, in that order, and writes
exactly the chapters and clip order that `seed_document` would write for the same disk under the same sort
rule. The document's own `sort`, when it sets one, is that rule, as for every other adoption.

**Rationale**: This is the agreed rule taken literally, plus the edge case decided by the user. It keeps
the per-chapter sort rule (event-reconcile), the chapter order rules, and `_ensure_chapter`'s existing
placement unchanged. A document that names no chapters has never stated a structure, so it gets the
structure a new event gets: HLD §2's chapter-from-subdirectory convention reaches legacy imports and
metadata-only first saves, as it reaches every event without a `reel.yaml`. Once a document names any
chapter, it has stated its structure, and the folder rule with its default-chapter fallback applies.

event-reconcile says "Chapters SHALL keep their existing order: the default chapter first, then subfolders
by name". That sentence says the sort rule never re-orders chapters, and how seeding orders them. It does not
place a default chapter that adoption creates later. `_ensure_chapter` has appended that chapter last since
`project-cli`, and the read model lists a root clip's invented chapter last too (lines 372–375). The
headless-cli delta now states this placement explicitly ("added after the chapters `reel.yaml` names"), so
the chapter order rules are unchanged, as the brief requires.

### One placement function, in `cli/adoption.py`

**Context**: Adoption (`cli/`) and the read model (`api/`) must place clips identically, including order.
Two copies of the rule caused this defect: the folder rule was in `api/` and the default-chapter rule in
`cli/`.

**Explored**:

- Putting the function in `event/` (next to `reconcile`/`add_clip`) would make three packages, over the
  limit.
- `api/` already imports from `cli.adoption` (`events_read.py` line 24 `REEL_FILENAME`, `routes/jobs.py`
  line 23 `load_or_seed`).
- `cli/adoption.py`'s docstring already says "the policy lives here" (lines 3–4).

**Decision**: Add to `cli/adoption.py`:

```python
def place_disk_clips(
    document: ReelDocument,
    listing: DiskListing,
    identities: Iterable[str],
    *,
    event_dir: Path,
    order: ClipOrder,
) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
    """The chapter each disk clip the document does not list enters, and its order there (D-12).

    ``identities`` are clips ``listing`` holds that ``document`` does not list (NEW, or for the
    read model also IGNORED). Each enters the chapter named after its ``listing`` folder group
    (the event root is the default chapter) when ``document`` names that chapter, else the
    default chapter. Returns ``((chapter, clips), ...)`` with no empty groups: the document's
    chapters in its order, then the default chapter when the document does not name it. Each
    group's clips are in ``order_clips(..., document.sort or order)`` order.

    A document that names no chapters is placed as a new event is seeded: every clip enters
    its folder's chapter, in ``listing.by_chapter`` order (the default chapter first, then
    subfolders by name).

    Raises:
        ReconcileError: an identity ``listing`` does not hold (a caller bug; fail loud).
    """
```

The implementation builds `folder_of = {identity: name for name, clips in listing.by_chapter for identity in
clips}`. It buckets identities by target, then emits the buckets in
`[c.name for c in document.chapters] + ([""] if document.chapter("") is None else [])` order. For a
document that names no chapters, the target is always the folder chapter, and the emit order is
`[name for name, _ in listing.by_chapter]`. Each bucket is sorted with `order_clips`. It is pure apart from
the `stat` that `order_clips` already does for `datetime`, and it never probes.

`prepare_event` becomes:

```python
def prepare_event(event_dir: Path, *, order: ClipOrder, adopt: bool = True) -> PreparedEvent:
    ...
    adopted: Tuple[str, ...] = ()
    if adopt and result.new:
        placed = place_disk_clips(authored, listing, result.new, event_dir=event_dir, order=order)
        for chapter, clips in placed:
            authored = _ensure_chapter(authored, chapter)   # "" (appended last), or a seed chapter
            for identity in clips:
                authored = add_clip(authored, identity, chapter)
            adopted += clips
```

`_build_chapters`, in the branch where a document exists, replaces lines 363–375 with:

```python
by_name = {chapter.name: chapter for chapter in chapters}
disk_only = [identity for identity in listing.identities if identity not in seen]
for name, identities in place_disk_clips(
    document, listing, disk_only, event_dir=event_dir, order=order
):
    clips = [_clip_out(event_dir, i, result.classification.get(i, ClipStatus.NEW)) for i in identities]
    if name in by_name:
        by_name[name].clips.extend(clips)
    else:
        chapter_out = ChapterOut(name=name, clips=clips)
        chapters.append(chapter_out)
        by_name[name] = chapter_out
```

Line 352 (`order = document.sort or order`) goes, because the function applies the event's own rule. The
seed branch (no document) is unchanged.

**Rationale**: One function means one rule, used by both callers. It touches two packages and adds no new
import direction.

**Spiked in review** on a scratch export of `main` (`93721b3`), never the checkout: this function, the
`prepare_event` loop and the `_build_chapters` replacement above, as written before the user's decision on
documents that name no chapters. That branch came later, and tasks 2.1–2.3 and 3.1 test it.

- The `Två kapitel` case failed on unmodified `main` (the clip landed in `""`) and passed with the spike.
- The two-folder case gave `Kvällen` = `Kvällen/a.mp4`, `Kvällen/d.mp4` and a trailing `""` = `Dag 2/c.mp4`,
  `b.mp4`, and the detail before and after adoption equalled `reel.yaml`, ignored clips aside.
- The whole `-m "not requires_db"` suite passed unchanged, and so did the OpenAPI drift test.
- `tests/test_api_events.py`, `test_api_editorial_read.py` and `test_api_editorial_write.py` passed unchanged,
  and so did `test_editorial_write_e2e.py` when run on its own. When only those files run together,
  `test_editorial_write_save_stale_render_cycle` fails on unmodified `main` as well: its worker claims a
  job that `test_api_events.py` left queued (`… failed to build: File is empty …
  test_a_running_latest_job_lose0 …`). The `-m requires_db` suite in its default order passes on `main`.
  This is pre-existing test isolation, not this change; task 6.1 runs the full suite in its default order.
- Task 2.3's render test, written as specified, passed with a real CPU render.

### Ordering: one sort per target chapter

**Context**: event-reconcile says the rule is "applied per chapter, to the clips entering that chapter".
Today the read model sorts per *folder* group (lines 364–365). Under the fallback, one chapter can receive
clips from several folders.

**Decision**: Sort each target bucket as a whole, with `document.sort or order`, in the function. In
`prepare_event`, `adopted` is the concatenation of the buckets in chapter order. It is used only for
`len(...)` in the CLI line (`commands.py` line 289) and for `changed`.

**Rationale**: This follows the existing requirement literally. The positions the page numbers before a
render are then exactly the positions after it: the listed clips first, then the entering clips in rule
order. The existing order tests stay valid: they adopt root clips only, so there is a single bucket.

### Ignored clips follow the same placement in the read model

**Context**: An IGNORED clip is on disk and not listed, just like a NEW one. Today it is placed by folder too,
so a folder whose chapter is missing would otherwise still produce an invented chapter that holds only
ignored clips.

**Decision**: The read model passes every disk-only clip, NEW and IGNORED, through `place_disk_clips`.
Adoption passes only `result.new`, because ignored clips are never adopted.

**Rationale**: The detail then never lists a chapter that `reel.yaml` lacks, except the default chapter, or
the seed chapters of a `reel.yaml` that names none. Edit mode's `detailMatchesDocument` still holds: ignored clips appear only after a chapter's listed clips,
and every one is in `ignore`.

### The web client needs no change

**Context**: The aligned detail changes which chapter some clips appear in. Edit mode reads that detail.

**Explored**: `draft.ts`:

- `editableChapters` (lines 43–52)
- `detailMatchesDocument` (lines 69–95)
- `writtenFromView` and `buildWriteBody` (lines 136–200)
- `adoptedNewCount` (lines 203–214)

**Decision**: No web change.

- A NEW clip that falls back into the default chapter sits after that chapter's listed clips, which
  `detailMatchesDocument` accepts.
- Reordering the default chapter and saving writes it there, the same place a render would put it.
- For a document with no chapters, the page keeps showing the folder seed, as on `main`, and a first reorder
  writes every chapter shown (`writtenFromView`). That is now also what a render would adopt, so the GUI
  keeps its path to folder chapters, and the page and the render agree on it.

**Rationale**: The page and Edit mode follow the service's placement as they already do. The response
shape does not change, so `web/openapi.json` and `web/src/api/schema.d.ts` are not regenerated.

### The adoption target stops being a parameter

**Context**: D-CLI3 said "default chapter (configurable)". `prepare_event(..., adopt_chapter=…)` is that
hook. No caller passes it (grep: `cli/build.py` line 53 and all tests call `prepare_event` without it), and
`config.yaml` has no key for it.

**Decision**: Remove `adopt_chapter`. The target comes from the rule.

**Rationale**: Principle VII, "no option bag, no second code path for later". A single configurable target
cannot express "the folder's chapter".

### RENDER_GRAPH_VERSION and the fingerprint

**Context**: The proposal must say whether rendered output or fingerprint inputs change (Principle IV).

**Explored**: `staleness/fingerprint.py`:

- `RENDER_GRAPH_VERSION = 3` (line 35)
- `editorial_hash` = `_hash_json(document.to_dict())` (lines 63–72)
- the render gate at `commands.py` lines 287–305 computes the fingerprint *after* `prepare_and_persist`

**Decision**: **No bump**, and no new fingerprint input.

- The render graph and `render/` are untouched. A given `reel.yaml` with given clips renders the same bytes.
- Adoption changes which `reel.yaml` exists, and that is an editorial input the editorial component already
  covers.
- An event whose clips are all listed (every rendered event) adopts nothing, so its document and fingerprint
  are unchanged and it stays fresh.
- An event with a NEW clip is stale anyway (`clip_set`). Its manifest was never written under the old
  rule's post-adoption document for that clip, so nothing compares against it.
- The read model's verdict (`staleness_for`, lines 390–423) uses the unadopted document, as before.

**Rationale**: Principle IV demands a bump only when identical inputs change output. They do not.

### Spec ownership: headless-cli and api-service

**Context**: The brief names event-reconcile and headless-cli "as they own the rule". The house limit is ≤2
capability deltas.

**Explored**:

- headless-cli's "NEW-clip adoption policy" (spec lines 94–114) holds the default-chapter sentence and its
  scenario.
- event-reconcile's "Clips enter a document in the configured sort order" (lines 187–206) states only the
  order rule ("per chapter, to the clips entering that chapter"), which is unchanged and is cited.
- The read model's placement is observable API behavior. api-service says only that the detail "merges
  disk-only NEW clips into the document's chapters" (line 336).

**Decision**:

- MODIFIED headless-cli "NEW-clip adoption policy"
- ADDED api-service "The event detail places clips not in reel.yaml by the render's adoption rule"
- event-reconcile untouched

**Rationale**: The changed behavior lives in these two capabilities. Editing event-reconcile would restate
its rule without changing it, and would push the change to three deltas.

### HLD: D-12 records the amendment

**Context**: The brief asks to amend "HLD's D-CLI3 text". There is none. D-CLI3 exists only in
`openspec/changes/archive/2026-06-07-project-cli/design.md` (line 50), and archives are history. The
config rule says a decision that outlives a change is folded into the HLD as a D-n entry. §7 ends at D-11.

**Decision**: Add to HLD §7, after D-11:

> - **D-12 — NEW-clip adoption follows the clip's folder** (2026-10-01, change `adopt-into-folder-chapter`;
>   amends `project-cli`'s D-CLI3). A clip that appears in an event after its `reel.yaml` exists (NEW) is
>   adopted by the next render, from the CLI or the worker, into the chapter named after the folder it is
>   in: the event folder's clips into the default chapter, and a subfolder's into the chapter of that name.
>   It goes into the default chapter only when `reel.yaml` has no chapter of that name. A `reel.yaml` that
>   names no chapters at all (a legacy import, a metadata-only first save) is adopted into as a new event is
>   seeded: the event folder's clips into the default chapter and each subfolder's into a chapter of its
>   own, in seeding order. Otherwise adoption creates no chapter except the default one, appended last when
>   absent. It never moves a clip the document lists, and it appends a chapter's entering clips in the sort
>   rule's order. The events detail places every clip `reel.yaml` does not list (NEW or ignored) by this
>   same rule, so it shows each NEW clip where the render will adopt it.
>
>   *Amended 2026-10-01:* D-CLI3 adopted every NEW clip into the default chapter ("configurable", never
>   wired). The GUI v1 end-to-end pass found `Kvällen/s1710004.mp4` shown under `Kvällen` and played in
>   Main after Render, and the operator chose the folder rule, and seeding for a `reel.yaml` that names no
>   chapters. Adoption writes `reel.yaml`, which the editorial component already fingerprints, so this is no
>   render-graph change. (§4.6)

§4.6, after "Folder-name parsing **seeds** a `reel.yaml` on first scan; thereafter the file wins.", gains:
"A clip added later is adopted by the next render into its folder's chapter, or the default chapter when
the file names no such chapter; a file that names no chapters at all is adopted into as a first scan seeds
it (D-12)."

**Rationale**: This is where future readers look for locked decisions. The archived design is not edited.

### Alternative: create the folder's chapter

**Context**: Another rule would also make the render and the page agree.

**Explored**: Rule B: "the folder's chapter, *created* (appended after the document's chapters) when
`reel.yaml` does not name it".

- It matches today's read model exactly, so it needs no `api/` change.
- It matches seeding ("subdirectories become chapters"), legacy auto-reel (chapters from folders at every
  scan), and Edit mode's existing save of an invented chapter (`draft.ts` lines 181–183).
- It keeps folder chapters for documents that name no chapters.
- Its cost: a hand-renamed chapter (`Kvällen` → `Evening`) gets a new `Kvällen` chapter for clips added
  later. The page shows that before the render, as it does today.

**Decision**: Not taken. The user agreed to the default-chapter fallback, and decided the one case where
Rule B's benefit mattered most, a document that names no chapters, separately: it is seeded like a new
event ("Supervisor decisions"). Rule B is recorded here so the hand-renamed-chapter trade-off can be
revisited deliberately.

**Rationale**: A decision the user made is not reversed inside a spec.

## Failure behavior and idempotency

- **Raises:**
  - `place_disk_clips` raises `ReconcileError` for an identity the listing does not hold. This is a caller
    bug, never a user state: both callers pass identities taken from the same listing.
  - `add_clip` keeps raising `ReconcileError` for an already-listed or ignored clip. Adoption passes only NEW
    clips, and `_ensure_chapter` creates every target the document lacks (the default chapter, or the seed
    chapters of a document that names none), so neither path is reachable.
- **Where such an error would go** (unchanged paths, as for `add_clip`'s errors today):
  - `ReconcileError` is a `ReelError`, so in the read model it becomes `EventReadError` through `get_event`'s
    `except (ReelError, OSError)` (`events_read.py` line 444).
  - In the worker it fails the job.
  - In `render`, the gate loop calls `prepare_and_persist` (`commands.py` line 287) outside the per-event
    `try` that guards the build (lines 206–222). That is pre-existing, and this change does not widen it.
- **No partial file.** `persist` writes `reel.yaml` once, through `write_document`, after every clip is
  placed in memory. Nothing is written in `--dry-run` (`prepare_and_persist`, lines 53–57).
- **A re-run** finds no NEW clips (they are listed now), adopts nothing and writes nothing. The event is
  fresh after a successful render.
- **`--force`** bypasses only the staleness gate. Adoption runs before the gate either way, identically.
- **A worker restarted mid-render.** Adoption was persisted before the render started (worker.py line 75).
  The requeued job re-prepares, finds the clips listed, and adopts nothing twice.
- **The read model** stays read-only. `place_disk_clips` never writes, and `_build_chapters` never calls
  `persist`.

## Risks / Trade-offs

- **[Decided] Documents that name no chapters are seeded like a new event** (user decision 2026-10-01,
  "Seed like a new event"; this replaces the open risk and its three options).
  - These are legacy imports, versionless legacy `reel.yaml`s, GUI metadata-only first saves, and
    "Needs attention" fixes. On `main`, their next render put every clip in the default chapter, while the
    detail showed the folder chapters (invented, lines 372–375).
  - Now the render adopts them into the folder seed's chapters, which is what the detail already shows. The
    read model's view of such a document does not change, and Edit mode's first reorder still writes every
    chapter shown (`draft.ts` `writtenFromView` lines 136–142), now the same chapters a render would write.
    HLD §2's carried-over "chapter-from-subdirectory convention" reaches these events too.
  - → A behavior change on the next render of such an event: a `Kvällen/` clip that `main` would have put in
    Main now gets a `Kvällen` chapter. That is what the page has shown all along. Events that `main` already
    rendered have chapters now, so the rule for documents that name a chapter applies to them, and nothing
    is migrated.
  - → An operator who wants one chapter for such an event names the default chapter in `reel.yaml` (a
    `chapters` entry with `name: ""`). Every folder's clips then fall back to it. The GUI cannot express
    that, because Edit mode does not move clips between chapters (v3).
  - The real archive has 9 legacy `metadata.yaml` events and at least one legacy `reel.yaml` (`2025-01-13 -
    Resa till Gran Canaria`). Whether any of them have chapter subfolders was not checked: MOL was not
    mounted. Any that do get the chapters a new event would get.
- **[Risk] Clips adopted under the old rule stay in Main**, for example on any library rendered with
  `Kvällen/…` clips adopted before this change. → Intended: an existing order is never re-sorted. The page
  names such rows by path (web-app, "A clip from another folder is named by its path"), and Edit mode can
  move them only within their chapter. Moving them takes a hand edit of `reel.yaml`.
- **[Risk] The web-app scenario "A clip from another folder is named by its path"** (spec line 419) says
  "as a hand edit or a render's adoption of that NEW clip leaves it". After this change, only a hand edit
  (or an old-rule adoption) leaves `Kvällen/s1710004.mp4` in the root chapter of that event. The scenario's
  outcome still holds. Its precondition wording is stale, and a third capability delta to fix one clause
  would break the two-delta limit. → Left for a later web-app touch.
- **[Trade-off] Exact, case-sensitive chapter match.** A chapter renamed only in case (`kvällen`) does not
  match its folder, so new clips fall back to the default chapter. Seeding writes folder names verbatim, so
  this needs a hand edit to arise.
- **[Trade-off] An `api/` → `cli/` import.** It is an existing direction (lines cited above). Moving the
  policy to `event/` is a later refactor that this change does not need.

## Migration Plan

None. There is no schema, `reel.yaml` or database change, no rescan, and no rewrite of existing documents.
Events with NEW clips get the new placement on their next render. Rollback is a revert of the two call
sites and the function, with no data to undo: documents written under the new rule are valid documents.
