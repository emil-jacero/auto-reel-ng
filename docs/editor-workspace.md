# Editor workspace — goal for the next GUI work

Status: **goal, not yet designed in OpenSpec.** This file lists every feature in the editor-workspace mock and
is the target for the next set of changes. Each slice below goes through the normal OpenSpec flow
(`/opsx:explore` → `/opsx:ff` → `/opsx:apply` → `/opsx:archive`); this file does not replace a change's design.

- Mock: Claude Design canvas "auto-reel UI", board **Event page: Edit mode (editor workspace)**
  (https://claude.ai/artifact/Dr1qr9cg5qrb8uKZxy6n1P, private to the owner). The board has a `selection` tweak
  (clip / title card / suggestion / nothing) and a `theme` tweak (dark / light).
- Origin: user request on 2026-11-14 — "I click Edit and it resembles something like the simple iMovie".
- Relation to the design doc: §6 roadmap item 10 said GUI v3 had no planned scope; this is that scope.

## The idea in one paragraph

Edit mode stops being a long page of stacked panels and becomes a full-window workspace: a **clip bin** on the
left, a **viewer** in the centre, an **inspector** on the right and a full-width **timeline** at the bottom. The
timeline becomes the main editing surface: clips are reordered and moved between chapters on the track itself.
The read view (`#/event/<id>`) stays as it is; **Edit** opens the workspace and **Done** leaves it. There is no
separate List view: the bin is today's chapter lists in compact form, so keyboard and screen-reader reordering keep
working.

## Legend

| Tag | Meaning |
|---|---|
| **reuse** | Exists today; moves into the workspace with little or no logic change |
| **new-web** | New, but web only: no API, engine or `RENDER_GRAPH_VERSION` change |
| **model** | Needs a decision about `reel.yaml` / the API before it can be built (`/opsx:explore` first) |

## Features

### 1. Workspace shell

| # | Feature | Tag |
|---|---|---|
| 1.1 | Edit opens a full-window workspace (bin · viewer · inspector · timeline); Done returns to the read view | new-web |
| 1.2 | Workspace is dark by default (footage stands out); the read view keeps following the system theme | new-web |
| 1.3 | No List view: the bin *is* today's chapter lists (keyboard reorder kept); narrow windows stack the panes | new-web |
| 1.4 | Fixed panes: bin `clamp(240px, 22vw, 320px)` (282 px at 1280, 317 px at 1440; `compact-bin-tools`), inspector 340 px, timeline ~340 px tall, viewer takes the rest | new-web |

### 2. Top bar

| # | Feature | Tag |
|---|---|---|
| 2.1 | Back to Events; event title with date and location | reuse |
| 2.2 | **Undo / Redo** buttons (Ctrl+Z / Ctrl+Shift+Z) over every draft edit | new-web |
| 2.3 | Unsaved pill with a count ("Unsaved · 3 changes") and the change summary beside it (today's save-bar text) | reuse |
| 2.4 | Reset, Save (Ctrl+S), Done — the save bar moves up here | reuse |

### 3. Clip bin (left)

| # | Feature | Tag |
|---|---|---|
| 3.1 | "On timeline" list: filmstrip thumbnail, file name, kept length | new-web |
| 3.2 | Selection is shared with the track: selecting in the bin selects on the track and the reverse | new-web |
| 3.3 | "Not on timeline" section with **New** and **Ignored** clips (pills) — also the place for missing clips | reuse |
| 3.4 | Drag a clip from the bin onto the video track to include it; drag off the track to ignore it | new-web |

### 4. Viewer (centre)

| # | Feature | Tag |
|---|---|---|
| 4.1 | 16:9 player on the proxy (today's stage), with a chip for the source clip and clip-local time | reuse |
| 4.2 | Proxy chip (e.g. "Proxy · 540p") | new-web |
| 4.3 | Movie time readout `0:27.40 / 0:38.08` | reuse |
| 4.4 | Transport: previous clip, play/pause, next clip | new-web |
| 4.5 | Use as poster (today's button) and full screen | reuse / new-web |

### 5. Inspector (right) — follows the selection

Tabs **Clip · Title card · Suggestion · Event**; the active tab follows what is selected, and empty-track
selection shows Event. This replaces the stacked Details / Poster panels and the modal card dialog.

| # | Feature | Tag |
|---|---|---|
| 5.1 | **Clip:** file name; chapter and position ("Kvällen · clip 1 of 2"); length in the movie | new-web |
| 5.2 | **Clip:** Trim In / Out as numeric fields, plus the Q / W to-playhead shortcuts | new-web (fields) / reuse (Q/W) |
| 5.3 | **Clip:** Rotate left / right with the current angle | reuse |
| 5.4 | **Clip:** cut list (range, reason pill, remove) and "+ Cut at playhead" | reuse / new-web |
| 5.5 | **Clip:** Use frame as poster; ~~Ignore clip~~ (moved to `track-drag-edit`, which builds the draft ignore edit) | reuse |
| 5.6 | **Title card:** docked card editor — live preview, Name, Background Black / Video, Font, Length, Position, "Use event style" per field | reuse (moves out of the dialog) |
| 5.7 | **Title card:** link to the event-wide card style ("All title cards in this event") | reuse |
| 5.8 | **Suggestion:** state pill, kind, clip and range, frame preview, Approve as cut (A) / Dismiss (R), event totals | reuse |
| 5.9 | **Event:** Title, Date, Location (and Description); poster thumbnail with Changed state; Title cards On / Off; chapter list with + Add chapter | reuse |

### 6. Timeline (bottom)

| # | Feature | Tag |
|---|---|---|
| 6.1 | Tool row: Play, Split, Trim In (Q), Trim Out (W), Snap (S), Suggestions toggle with pending count, Zoom − / slider / +, Fit (`\`) | reuse, except Split |
| 6.2 | Movie stats in the tool row: length, chapters, clips, cuts and time removed | reuse |
| 6.3 | Labelled lanes: ruler · Chapters · Titles · Video · Analysis | new-web |
| 6.4 | **Chapter bands** over their clips; drop a clip on a band to move it to that chapter | new-web |
| 6.5 | **Titles track** above the video (iMovie style): a Black card also leaves a black block on the video track; a Video card overlaps the start of its chapter's first clip; the icon shows which | new-web |
| 6.6 | Drag a title card's edge to change its length | reuse |
| 6.7 | **Video track:** filmstrip clips labelled "name · length"; cut hatches by reason (manual, black, white, freeze); selected clip outlined with trim handles | reuse |
| 6.8 | **Reorder by dragging clips on the track**; the track shows the draft order, not the saved order | new-web, large (reverses part of D-20) |
| 6.9 | **Analysis lane:** dismissed ×, approved-as-cut ✓ spanning the cut, pending ?; the selected suggestion ringed | reuse |
| 6.10 | Playhead across all lanes; overview scroll bar under the track; gesture hints | reuse / new-web |
| 6.11 | Click on empty track selects the event (inspector shows Event) | new-web |
| 6.12 | **Split at playhead** — shown dashed in the mock as planned | model |

## Changes (OpenSpec, in order)

Each change starts with a **gate task** that stops it unless the change before it is archived on `main` and its
spec is merged. Proposed 2026-11-15 under `openspec/changes/`.

| # | Change | Covers | Depends on | Size |
|---|---|---|---|---|
| 0 | `track-draft-order` ✅ built 2026-11-15 | the track draws the draft's order and chapters; cards of added chapters built in the browser | — | 1–2 days |
| 1 | `editor-workspace-layout` ✅ built 2026-11-15 (HLD D-28) | 1.x, 2.1/2.3/2.4, 3.1–3.3, 4.x, inspector Event/Cut tabs, 6.1–6.3, 6.7, 6.9, 6.10 | 0 | 2–3 days |
| 2 | `editor-selection` ✅ built 2026-11-15 (HLD D-28) | one selection, 3.2, 5.x (Clip tab, docked card editor), 6.11 | 1 | 1–2 days |
| 3 | `track-drag-edit` ✅ built 2026-11-16 (HLD D-20) | 3.4, 6.4, 6.8, keyboard moves | 2 | 1–2 days |
| 4 | `editor-undo` ✅ built 2026-11-17 (HLD D-28) | 2.2 | 1 | 1 day |
| 5 | ~~`clip-split`~~ dropped 2026-11-18 (its change was removed on `main`; "cut a span" covers it) | 6.12 | 3 | — |
| 6 | `editor-shortcuts` ✅ built 2026-11-19 (HLD D-28) | the Timeline's keys answer anywhere in the workspace, Keyboard shortcuts list and single-key switch, Ctrl+wheel over the whole Timeline | 4 | 1–2 days |
| 7 | `clip-context-menu` ✅ built 2026-11-19 (HLD D-28) | a right-click or Shift+F10 on a clip block opens a menu of its edits (Rotate, Cut at playhead, poster, Move to, Ignore); reverses the context-menu half of `compact-bin-tools`' non-goal (every tool stays a direct button); the track only until `plain-clip-bin` | 6 | 1 day |

Slice 1 was tightened after the build by `compact-bin-tools` (web only, 2026-11-15): the bin follows the window's
width (`clamp(240px, 22vw, 320px)`) and its compact tools take less height. Clip rows are two lines with a fine
pointer, the marks line is two fixed sticky rows with icon-only Rotate and Help, the chapter's Move up, Move down and
Delete sit in its header bar as named icon buttons, an ignored clip is one line, and the new-clip line is gone (the
top bar's summary and the Clips help say it). On `Två kapitel - Tjörn`, with a fine pointer and nothing marked, the
bin shows 3 whole clip rows at 1280×720 and 4 at 1440×900 (played rows; from 960 px the ignored clips are listed after the chapters, and a clip's status is its icon alone with a fine pointer). Touch sizes are as
before.

Slice 1 as built (2026-11-15) left out four features of its "Covers" list, none of them in the change's tasks:
1.2 (the workspace follows the operator's theme rather than defaulting to dark, as the explore session decided),
4.2 (the proxy chip), 4.5's full screen (Use as poster is there) and 6.3's lane labels. They are open for a later
slice.

Slice 2 as built (2026-11-15) covers 3.2, 5.1–5.4, 5.6–5.9 and the poster of 5.5; "Ignore clip" (5.5) moved to slice 3. 6.11 as
built: a press on empty track selects nothing (the inspector then shows Event) rather than selecting the event.

Decisions from the explore session (2026-11-15): no List/Workspace switch (the bin replaces the lists); target
1280×720, not critical; light and dark both, following the existing theme setting; an added chapter's card is built
in the browser from the event's resolved cards.

## Open questions

- ~~Is Split worth a `reel.yaml` change, or is "cut a span" (already possible) enough?~~ Settled 2026-11-18: `clip-split` was dropped.
