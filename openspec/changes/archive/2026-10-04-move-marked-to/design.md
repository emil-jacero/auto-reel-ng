## Context

Edit mode moves clips between chapters in three ways on main: a drag of one clip, a drag of the marked group (#104), and
the per-chapter Move clips dialog (pick clips, pick one other chapter, move to the end). The dialog became a second,
heavier way to do what marking plus one action does. The marks line already hosts the group actions (Clear marks,
Rotate marked left / right), so a group move belongs there.

## Goals / Non-Goals

**Goals:**
- One non-drag move: mark, choose a chapter, press Move; usable by keyboard, screen reader and touch.
- One implementation of the group move: the drag's `groupOf` + `moveGroup`.
- Chapter rows lose a control; nothing else in them shifts meaningfully.

**Non-Goals:**
- No change to the drag, to marks, to cuts, to Save or to the server.
- No "move before clip N" control: the end of the chosen chapter only (the drag places precisely).
- No undo stack: Reset, as for every edit.

## Decisions

1. **Remove, don't hide.** The Move dialog, Pick all / Pick marked and `ChapterToolsModel.moveClips` are deleted, with
   their strings and tests; the REMOVED requirement carries a migration note. Reason: the user asked for removal, and a
   hidden dialog is dead code the spec would still have to describe.
2. **Control in the marks line, native `select`.** A native `select` is keyboard, screen-reader and touch operable
   with no new dependency (D-8) and no popup to focus-manage; the app's menu component would add focus handling for no
   gain. It lists every chapter the page lists (deleted ones aside) by heading name; it starts on "Choose a chapter"
   so a press never moves to a chapter the operator did not pick. Alternative considered: preselect the only other
   chapter as the old dialog did; rejected because the group may come from several chapters and the picker is
   persistent, so a stale preselection would be a silent wrong default.
3. **Offered with two or more chapters only**, as the old button was. A single-chapter event has no destination.
4. **Disabled with a reason, not hidden.** `aria-disabled` plus visible words, described by `aria-describedby`, for
   no mark, no chapter, and save/move pending (the app's busy-control rule: never `disabled`). The reason line keeps the
   group's height so marking the first clip moves no row.
5. **The edit is `moveGroup(draft, groupOf(orders, listed, marked), to, targetLength)`.** A thin pure wrapper
   (`moveMarkedToEnd`) returns the new draft and the identities that moved, null when the draft did not change; the
   component only wires announcement, marks (`afterMove`), the pending state and the save bar. Because `moveGroup`
   is the drag's edit, saving, counting, Reset and the cut/preview preservation come for free. It does not restore a
   returning clip after its old predecessors (the old `moveClips` did, the drag does not); "move there and back" can
   therefore leave a reorder to save, as a drag back to the end would. Accepted: the group move is the single
   implementation, and Reset undoes it.
6. **No-op is announced, not silent.** A group already last in the chosen chapter changes nothing: "Nothing moved.",
   marks kept, no save bar.
7. **Terminology elsewhere.** Requirements that said "a Move clips is pending" now say "a move of marked clips is
   pending"; the `ChapterEdit` pending/transition state is reused for the new action so Save, drag, Set From / Set To,
   trim handles and the card handle stay unavailable exactly as before.

## Risks / Trade-offs

- A returning clip no longer lands in its original place (decision 5): mitigated by Reset and by the drag's identical
  behaviour; a test pins it.
- Fewer affordances for operators who never mark: the marks line hint names Move marked to…, and the empty-chapter
  sentence points at it ("move them here with Move marked to…").
- Large spec delta (MODIFIED blocks copy whole requirements). Mitigation: each was changed by text substitution only,
  and a task greps the shipped web code and the specs for any remaining "Move clips".
