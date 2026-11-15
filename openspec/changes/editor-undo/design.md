## Context

`EventEditor.tsx` keeps the draft in a reducer; Reset restores the opened snapshot; Save writes and the editor
continues from the saved state. There is no history.

## Decisions

### D1. History wraps the reducer
```ts
// edit/history.ts
export type History<S> = { past: S[]; present: S; future: S[]; labels: string[] }
export function record<S>(h: History<S>, next: S, label: string, coalesceKey?: string, now?: number): History<S>
export function undo<S>(h: History<S>): History<S>
export function redo<S>(h: History<S>): History<S>
export function cleared<S>(present: S): History<S>
```
Each reducer action carries a label and an optional coalesce key (field id); `record` merges into the last step while
the key matches and less than 1000 ms passed. Drags record once, on release (the live drag state is not in the draft).
At most 200 steps; the oldest is dropped.

### D2. Save clears, Reset records
Save → `cleared(savedDraft)`. Reset → `record(h, snapshot, 'Reset')`. A 412 conflict's Reload latest → `cleared`.

### D3. Keys
Handled at the workspace frame; ignored when focus is in an `input`, `textarea`, `select` or contenteditable (native
undo); ignored during a drag.

## Research & Decisions

### Save clears the history
**Context**: undoing past a save would reopen edits that are already on disk.
**Explored**: iMovie keeps history past a save; Edit mode's draft is rebuilt from the saved state after a save.
**Decision**: clear on Save.
**Rationale**: the draft after Save is a new baseline; keeping older states would mean re-applying them on top of it.

## Risks / Trade-offs

- **Memory**: drafts are immutable and share structure; 200 steps of a 400-clip event stays small. Measured in 3.1.

## Failure behaviour
Display and draft only.
