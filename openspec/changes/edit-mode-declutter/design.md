## Context

Edit mode (`web/src/edit/EventEditor.tsx`, 3,000 lines) carries four generations of title-card UI: `InlineName` (the pencil
renames, #113), `TitleCard` (Main's second pencil line, D-13), `CardRow` (a card row per chapter, `title-card-blocks`),
`CardStylePanel` and `TitleCardsSwitch` (page sections, `title-card-event-style`, #123), and since #133 a card editor dialog
(`edit/card/Inspector`, opened from a row or a Timeline block) that already holds the card's fields and the live preview.
The Timeline section in Edit mode is a closed section with an Open/Close button. The operator's 2026-10-04 feedback (see the
proposal) asks to make the dialog the only place and to remove the rest. The marks line (`.mark-line`, `edit.css`) is a grid
whose second and third rows are flex rows of controls of different heights (`btn-compact` against a `field-input` select
against a text reason with `min-block-size: 2.5rem`).

Everything the dialog needs exists: `Inspector`/`Fields`/`Preview`/`usePreview` (D-24), the style draft (`cardStyle.ts`),
the decorators draft (`decorators.ts`), the name rules (`chapterNames.ts`: `checkName`, `laterClipNotes`, `nameDialogNote`;
`inlineName.ts`: `decideName`, `nameUnsent`, `titleLine`, `FILE_NAME_NOTE`), and the length rules of the drag
(`timeline/cardLength.ts`: `cardLimits`, `secondsToTenths`). Web only: the same keys are written as before.

## Goals / Non-Goals

**Goals**
- Every chapter name and every title-card setting is edited in one dialog, identically for Main and chapters.
- A chapter section is its header bar and its clips; the page has no card row, pencil, card-style or Title cards section.
- Edit mode opens with the Timeline open.
- The marks line is one aligned unit.

**Non-Goals**: see the proposal. In particular no new API, no `reel.yaml` change, no change to Save or the draft model.

## Research & Decisions

### Tabs, not stacked groups
**Context**: the dialog must hold the card's ten fields and the event's eight (plus the switch), with one live preview visible
for both.
**Explored**: two groups in one scroll (every field on one long sheet; at 390 px the sheet is a full-screen sheet with the preview
above, so the second group is two screens down and the preview is out of view while it is edited); tabs ("This title card" /
"All title cards in this event").
**Decision**: a two-tab `role="tablist"`, the preview outside the panels.
**Rationale**: the two groups answer two different questions ("this card" against "all cards") and the operator thinks of them
that way (their own words: "all title card related settings in the popup"); tabs keep the dialog one panel high, keep the preview in view
while either is edited, and leave the Name first without a scroll. The cost is a hidden panel; it is covered by labelling a tab that
holds a problem ("1 problem") and opening on that tab when the service's last answer named one. The dialog always opens on "This title
card", except for such a problem, so that the tab is predictable and no state is remembered.

### The Name in the dialog is a live draft edit with the old rules
**Context**: the inline rename kept the name on Enter or blur and dropped it on Escape, with an "unfinished" state that held Save. The
dialog's other fields write the draft as they are typed.
**Explored**: (a) copy the inline field's commit/drop model into the dialog; (b) write every accepted name to the draft as it is typed, hold a
refused one in the field.
**Decision**: (b). The decision (accept/refuse, the words, the Unicode case-fold and spaces rules, the clash with `Main` and a deleted
chapter) stays in `chapterNames.checkName` and `inlineName.decideName`, called by the field; nothing is re-implemented. A refused name stays in the
field with the refusal in a remounted `role="alert"`; Done with it keeps the dialog open; Escape and Close return the field to the draft's name and
announce "Name not changed" and why; Ctrl+S with a refused field saves nothing. The rename is announced once, when focus leaves the field or the
dialog closes (a pure "announce on settle" rule, tested).
**Rationale**: in a modal dialog there is no "elsewhere" for an unkept name to wait in, so the unfinished-field state shrinks to a refused name; the heading,
the preview, the header bar and the picker of Move marked to… follow the name as it is typed, as they follow every other dialog field. Typing back
the old name counts as no edit because the draft compares equal (the existing rule), so no spurious "renamed".
For Main the field edits `metadata.title` through the Details form's draft setter, so the two stay in step with no copy.

### Card title override: shown, clearable, never added
**Context**: a card in `reel.yaml` may carry its own `title`; the old inspector had a Title field that could set one.
**Decision**: when the draft's card has `title`, the first tab shows "Card title (overrides the name)" and "Use the name", which removes it;
no control adds one. The Name is the card's heading otherwise (the model already resolves `card.title` else the name).
**Rationale**: the operator asked for one name in one place; a second title field is the confusion the feedback removes, while a card
that has one must remain fixable.

### Length field mirrors the drag
**Context**: the inspector deliberately showed no length (#133: "the drag is the way"); the operator now wants every card setting in the popup.
**Decision**: a number field (seconds, step 0.1) validated by a pure `parseCardLength(text, range)` in `timeline/cardLength.ts` built on the existing
`secondsToTenths` and `cardLimits(...)`, with the same limits as the drag (0.5 to 60 s, a video card bounded by the anchor clip's kept span); not a
number or out of range is refused in words naming the limits, never clamped; a card whose `cardLimits` is not adjustable shows the reason and takes
no value. It writes the same draft `duration` the drag writes, so the two views follow each other; Use event style removes it.
**Rationale**: reuse the engine-mirroring constants (a test already fails when they differ from `reel/card.py`); refusing instead of clamping keeps
the "never a value the operator did not type" rule of the rest of the editor.

### The chapter bar button replaces the row as the card's page-level handle
**Decision**: `Edit Titlecard` sits in the header bar (name, button, clip count, tools). It uses the existing card selection
(`useCardSelection`) and the existing dialog open path, so the Timeline block and the button are two entrances to one selection; it shows
`aria-pressed` when selected. A chapter added in the draft gets the button too (its dialog says the card is drawn after Save); the old row's
"not selectable" rule goes, since the dialog edits the draft's card either way.
**Rationale**: the row's words (title, subtitle, length, background, font) are in the dialog and on the Timeline's block and readout; a second summary in the
page is what the feedback calls clutter. The header bar keeps `Main`/`Clips` and the chapter's name as plain text; the "later clips" notes
(`laterClipNotes`) keep their place beside the chapter.

### Edit mode's Timeline is open on entry, with no toggle
**Context**: `TimelineSection` owns `open` state and the button; D-20 says the Timeline needs the clips' facts and shows Prepare otherwise
(research `synthesis.md` §3, finding X6). The read view's rule "a closed timeline costs nothing" is the spec'd protection for a 400-clip page.
**Decision**: when `editing !== null` the section is open and renders no toggle; the read view is unchanged. Entering Edit mode with unprepared proxies
shows Prepare. No new request path: opening already is the existing read of proxies and filmstrips, windowed, and the proxy job stays an
explicit button.
**Rationale**: the operator chose Edit to edit; the read view keeps its toggle (supervisor decision). Cost on a very large event is the first
paint of the windowed track, which the Timeline already budgets; this is measured in the Playwright pass on the dev library, and recorded.

### The marks line: one token, one axis, hint below
**Context**: `btn-compact` buttons, a `field-input` select and a `min-block-size: 2.5rem` text sit in rows with `align-items: center` but different box heights
and a `row-gap` that differs by pointer type (1.5rem coarse), so the reason sits high.
**Decision**: one `--mark-control-h` custom property on `.mark-line` (36 px fine pointer, 44 px coarse) is the `block-size` of every button and the select inside it;
the rows are `display: flex; align-items: center` with one `gap` and one `row-gap` token; labels and the count are `line-height: var(--mark-control-h)` boxes or centred
flex items; the reason becomes a single muted hint line below the controls, `min-block-size` of one line, so it never floats. Narrow: wrap by whole groups (Move group on
a row, label above, `select { flex: 1 }` beside Move). No markup change beyond moving the reason element and wrapping groups.
**Rationale**: the defect is box height and per-row gaps, not structure; one token fixes all rows by construction, and a Playwright box measurement (heights equal, centre
lines within 1 px) is the acceptance test the feedback calls for. The coarse 44 px token also satisfies "every control is large enough to touch" without the old 1.5rem row gap.

### Deletions
`InlineName.tsx`, `TitleCard.tsx`, `CardRow.tsx`, `cardRows.ts`, `CardStylePanel.tsx`, `cardStyle.css` (the panel's; the style *model* `cardStyle.ts` stays), `TitleCardsSwitch.tsx`,
`titleCardsSwitch.css` and their tests/strings go; `inlineName.ts` keeps what the dialog's Name uses (`decideName`, `nameUnsent`, `titleLine`, `FILE_NAME_NOTE`) and loses
what only the pencil used (`acceptAnything`). A grep-and-`tsc --noUnusedLocals`-style check is part of the task, so no dead export remains.

## Behaviour under failure and repetition

- Nothing here touches the server; a failed Save keeps the draft as before, and a 400 naming `card.*`, `look.title_card.*` or `look.decorators` is shown at
  the dialog field, and on the tab label when its tab is hidden.
- A preview failure is told in words in the dialog, as in #133.
- Re-opening the dialog, switching tabs, pressing Done or Escape twice, and a Refresh while it is open are idempotent: the dialog reads the draft, writes nothing on open or close.
- A Refresh in Edit mode keeps the Timeline open (it re-renders the same section); the selection is kept above it as before.

## Risks / Trade-offs

- **A hidden tab can hold a mistake.** Mitigated by the tab label and the open-on-problem rule; the save bar still counts everything.
- **A long Edit-mode first paint on huge events.** Windowed track and filmstrip requests are already bounded; measured, and the supervisor's decision keeps the read view lazy.
- **Scenario names.** The validator keeps each replaced scenario by its old name, so a few titles keep stale words ("Edit mode has its own, closed timeline",
  "Opening from a row far down the page"); their bodies are new. They can be renamed in a follow-up.
- **Name field in a modal drops Enter-to-keep.** Enter in the field behaves as in any dialog field (no submit); Done closes. Documented in the spec.

## HLD

`docs/high-level-design.md` §4.10: replace the lines on the inline rename / Main title card (D-13), the card rows (`title-card-blocks`), "Card style for this event"
(`title-card-event-style`, D-24) and "Title cards: On / Off" (`title-card-toggle`, D-25) with one paragraph for this change: the dialog is the single place, with the tabs and the
Name and Length; the Edit-mode Timeline opens on entry (D-20); the marks line is one aligned unit. §6: phase 8 note. D-13, D-20, D-24 and D-25 each get a one-line
"superseded UI" pointer; no new D-number (no decision outlives the UI).
