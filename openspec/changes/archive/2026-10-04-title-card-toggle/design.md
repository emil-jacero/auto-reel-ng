## Context

See proposal.md. `GET …/events/{id}` carries `title_cards: {enabled, source: event|project|default} | null` (null with
`title_cards_error` when `look.decorators` is not a list). The engine decides it with the function the render uses
(`title_cards_state`), so the page cannot disagree with a render. Edit mode keeps one draft whose `look` goes back as
read except for `look.title_card` (`applyStyle`). The inspector is a sibling of the Timeline body in `TimelineSection`
and renders above the track (the defect of task 3).

## Goals / Non-Goals

**Goals:** one switch for one fact; no web-side guess of the effective decorators; the inspector never moves the track.

**Non-Goals:** editing other decorators (`chapter`, `none`), per-chapter on/off, a project-level setting, any API or
engine change, deleting a card's text when the switch is Off (the card edits stay in the draft).

## Decisions

1. **The draft holds a decorators override, not a boolean.** `draft.decorators` is absent (as read) or a replacement
   list. Effective state = the draft's list includes `title`, else the detail's `title_cards.enabled`. Putting the switch
   back to the read state deletes the override, so "edited and put back" is no change (the rule `cardStyle` uses).
   Alternative: a boolean plus a derived write; rejected because the other names and the absent-key case need the list.
2. **What a switch writes.** Off writes the event's own list without `title` (other names, order and non-string items
   kept); with no list on the event it writes `[]` (D-25: `[]` = no cards, and an event key replaces the project one:
   D-J). On writes the event's list with `title` put first (a list as read, minus `title`, plus `title`). The key
   is removed only when the draft returns to the state read (it had no key and the switch is back). The brief offered
   removing the key when the result "equals the default"; that is unsafe, since the page does not know the project's list
   and a removed key would then inherit a project opt-out, so the page never infers it. When the detail says
   `title_cards: null` (not a list) the switch is disabled and the detail's `title_cards_error` shown.
3. **One fact for the Timeline.** `TimelineSection` passes `enabled` (from the draft, else the detail) and the
   source, replacing `decoratorsRead`/`titleCardsOn`. The placement function takes `enabled: boolean`; the
   model's `unset` is gone, so `Decorators` shrinks to `on | off | invalid`, and `invalid` becomes `title_cards: null`.
   Off still draws dashed blocks with "not enabled" and no time added; the lane says once "Title cards are off for this
   event" and, when the source is `project`, "set by the project's config.yaml" so the operator knows why. The movie
   length is final in every state with a `title_cards` answer.
4. **One opening-card row.** `ClipOrderList` renders `CardRow` with `TitleCard` as a child; the row's heading line is the
   "Main title card" control (a button as `chapter-inline-rename` made it), the card's words follow in the same row.
   The web-app "Main title card" requirement's observable text (label, draft title, folder-name mark, rename warning)
   is unchanged, so it needs no delta.
5. **Inherited value pressed.** `Choice` takes `inherited` as a value as well as text; with no own value it renders that
   option's radio `checked` in a distinct `data-inherited` style (muted, dashed outline, never colour alone, and the
   words "(event style)") and an own value renders as now. Because a radio checked by the page would look set, the
   state is drawn by CSS from `data-inherited`, and the group stays without a chosen value in the draft; pressing the
   inherited option sets it explicitly (an override equal to the inherited value, as the overrides requirement already
   counts it).
6. **Layout.** The inspector moves from before `.timeline-body` to after it: the track, ruler and playhead are
   upstream in the DOM, so selecting changes nothing above them. No scroll is done on selection (`preventScroll`
   focus). Beside-the-track on wide screens is not built: a column would narrow the track and change its zoom. The
   duration handle selects on pointer-down again, which is harmless once the inspector is below the track.
   The `timeline` spec's parenthetical about `unset` is a stale clause once the model loses that state: it is fixed in
   task 1.4 as part of this change's archive sync (a one-clause edit, not a behaviour delta), keeping the delta count at 2.

## Risks / Trade-offs

- [The project's `decorators` list has other names and Off writes `[]`] → the switch says, when the source is
  `project`, that saving writes this event's own list; the event overrides, as D-J says. Known limit: the event key wins
  wholesale, so a project decorator other than `title` is dropped for that event on the first toggle. Only `none` and
  `title` are registered today, so no output changes; the save bar does not name it and the service does not yet expose
  the effective names, so a future registered decorator needs that exposure first.
- [A hand-written radio style looks like a chosen value] → `data-inherited` is announced ("event style, not set") and
  scenario-tested by role and name.
- [Pointer-down on the handle selects and the inspector now sits below] → asserted by Playwright: the track's bounding box
  is identical before and after a block is selected and after a handle press.

## Migration Plan

None: `reel.yaml` is untouched until the operator saves; no data format changes.
