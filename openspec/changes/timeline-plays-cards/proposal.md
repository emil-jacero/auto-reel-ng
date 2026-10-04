## Why

`title-card-blocks` (D-20, #118) put the title cards on the Timeline but chose to play footage only: the playhead
crosses a black card's span "without time passing" and a press there selects the card. The operator's first use
of it (2026-10-04, a screenshot of the Timeline zoomed out showing two textless black blocks and the note "The Timeline
plays footage only") said: "It appears I cannot actually see the title cards, or even play them. The timeline selector
just skips past them." That repeats the original requirement of 2026-10-03, "I want the title cards to be visible in the
editor", and reverses the limit that change recorded in the HLD (§4.10, "Honest limits"): the Timeline must show and
play the cards as the movie will, or the editor does not show the movie.

Everything it needs is built: the card lane and the track map (`cards.ts`), the one `<video>` with a src swap at clip
boundaries (`useTimelineVideo.ts`), the one-player coordinator, and `POST /api/v1/events/{id}/title-card/preview`,
which draws a draft card with the real renderer (black cards as the card, video cards as text on transparency). It is
the Timeline that does not use them. HLD §6 phase 8, GUI v2 (D-20).

## What Changes

- **Playback:** playing into a black card shows the card's image in the player area, letterboxed like the video, with
  its fades as opacity; the playhead advances in real time for the card's duration; then play goes on into the
  chapter's first clip, which was loaded and sought during the card. A video card's image is laid over the playing video
  for its window. Pause, Space, seeking and the one-player rule all work inside a card.
- **Scrub and click:** the playhead can be put in a card; the card shows there. The Event readout counts card time; the
  Clip readout reads "Card 0:01.20 of 0:07.00" inside a card.
- **Blocks:** each card block shows a miniature of its card, its title when it fits, a name always, a 24 px minimum
  width.
- **Images:** every card's preview is fetched once when the Timeline opens, one at a time, honouring `503 Retry-After`,
  kept as object URLs, and only the edited card is fetched again (debounced).
- The "plays footage only" note and requirement text go. Specs: `event-timeline` (MODIFIED: the card block, Play;
  ADDED: card playback, put-in-card and readouts, card images) and `timeline` (ADDED: the pure play clock, stages,
  opacity and hand-over).

## Capabilities

### New Capabilities

### Modified Capabilities
- `event-timeline`: the card block shows its card and the "footage only" limit is removed; Play goes through cards; new
  requirements for playing cards, putting the playhead in one, and fetching the images.
- `timeline`: new pure requirement for the stages, the card clock and the fades' opacity.

## Impact

- Packages: **web** only (`web/src/timeline/`, a small fetcher beside `web/src/api/titleCard.ts`'s use). Docs: HLD.
- CLI/API: none touched; the existing preview endpoint is used as it is (it allows two at once and answers 503 with
  `Retry-After`; the Timeline asks one at a time).
- Rendered output: unchanged; `RENDER_GRAPH_VERSION` and the staleness fingerprint are untouched. `reel.yaml`,
  `config.yaml`, Alembic and rescans: none.
- Dependencies: none new (D-8, D-20); dnd-kit stays for reorder only. Bundle growth is measured and recorded.
- Honest limit carried forward: the event detail does not carry the cards' fade durations, so the Timeline uses the
  engine's defaults (2 s in, 2 s out, clamped); a `look.title_card` that changes them is not shown (see design).

## Non-goals

- No title-card sound, no waveform, no change to how the card is drawn, faded or composited by the render.
- No new endpoint and no new field on the event detail (carrying the fades there is the follow-up that removes the
  limit above).
- No reorder or cross-chapter move on the Timeline; no card editing on the Timeline beyond the length drag that exists.
- No second `<video>`, no canvas compositor, no pre-rendered card clip.
