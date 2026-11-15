## Context

`reel.yaml` (HLD §4.6) lists each chapter's clips by identity with their `trims`; order is list order. The render
plays each listed clip's kept spans (`render/segments.py kept_spans`). The draft (`edit/draft.ts`) keys clips by
identity in `Orders`. One identity appearing twice is not modelled anywhere.

## Decisions

### D0. The model is decided first (open)
Task 0.3 runs `/opsx:explore clip-split` with the user and records the outcome below. Implementation tasks for
option B are not written until then.

### D1 (option A). A split is a boundary inside a clip
```ts
// draft: per clip, sorted split points in ms of the source
splits: ReadonlyMap<string, readonly Ms[]>
```
The boundary must survive a save: either as a zero-length cut (if `trims` allows `a..a`) or as a new optional
`splits:` list per clip (a schema change, which moves it towards option B's cost). Task 0.2 checks `reel/`. If
neither is acceptable, option A is display-only for the session, which is not worth building.

### D2 (option B). Clip uses
To be designed after 0.3.

## Research & Decisions

### Split model
**Context**: the goal lists Split; `reel.yaml` has one entry per clip identity.
**Explored**: explore session 2026-11-15 (split "may not fit `reel.yaml`"); `docs/editor-workspace.md` open question
"Is Split worth a `reel.yaml` change, or is 'cut a span' (already possible) enough?".
**Decision**: open — decided in task 0.3.
**Rationale**: the options differ by an order of magnitude in scope.

## Risks / Trade-offs

- **Option B touches the editorial source of truth** (Principle II) and the fingerprint (Principle IV).
- **Option A may not be worth it**: "cut a span" already removes the middle of a clip.

## Failure behaviour
Option A: display and draft only. Option B: to be designed.
