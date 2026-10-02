## 1. Gate

- [x] 1.1 Confirm the gates are archived on `main`, re-check what this change builds on, and set up:
  `ls openspec/changes/archive/ | grep -E -- '-(title-card-whole-clip-cut|thumbs-sidecar-metadata|api-excluded-clips-read-model|api-job-summary-and-renamed-fields)$'`
  must print four directories. Stop and report to the supervisor if any is missing.
  - **Re-read** `web/src/events/EventDetail.tsx`: this change edits `LoadState`, `load()`, the Refresh `onClick`,
    the top level of `<main>` and the first child of `ReadyView`. If the two `EventDetail.tsx` gates moved any of
    them, adapt the task text (names only), and stop and report if one is gone.
  - **Re-base the MODIFIED blocks** of `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`
    text of the four requirements, keeping any edit another change made.
  - **Set up** with `DB=arel_web_playback_and_notices`, library `dev-web-playback-and-notices`, port 8242, the
    env file and `TMPDIR` from the brief; `serve` with `XDG_CACHE_HOME=$SCRATCH/xdg`. Render
    `2024-07-14 - Kalas` once in that library copy only, so it has a movie. Never port 8080, `../auto-reel-dev`
    or `auto-reel-media/`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass on the untouched tree (node:22 container)
  - `curl -si` on the thumbnail of `2024-10-05 - Trasig`'s `trasig.mp4`, twice within 60 s, answers 502 with
    `thumbnail_failure: thumbnail_failed` both times (the marker replays the kind); stop and report otherwise
  - `git diff --stat main -- openspec/specs` is empty

## 2. web/ — a Refresh keeps the movie

- [x] 2.1 In `events/EventDetail.tsx` and `movie/MoviePanel.tsx` (design, "State: `loading` carries the event
  whose Movie section stays"):
  - `LoadState.loading` gains `movie?: EventDetailData`; `LoadOptions` gains `keepMovie`; `load()` fills `movie`
    from a `ready` (or an already `loading`) state only when `keepMovie` is set
  - only the Refresh button passes `keepMovie` (`requestLeave(editing ? leaveEditMode : () => load({ keepMovie: true }))`);
    the mount read and `leaveEditMode` do not
  - `MoviePanel` moves from `ReadyView` to `<main>`, straight after `<header>`, rendered when the page has an
    event to show it for and is not editing
  - `MoviePanel` takes `reading`; the section gets `aria-busy` and `data-reading`; `movie.css` hides the age pill
    and every `.movie-facts` with `visibility: hidden` under `[data-reading]`, adding no color literal

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -n "MoviePanel" web/src/events/EventDetail.tsx` shows the import and one use, outside `ReadyView`
  - `grep -nE '#[0-9a-fA-F]{3}|oklch|rgb' web/src/movie/movie.css` prints nothing new
  - the motion grep commands in `web/README.md` pass over `web/src/movie`

## 3. web/ — the cut editor's hints

- [x] 3.1 In `cuts/times.ts`, end the whole-clip sentence of `CUT_HINT` and of `lengthHint` with "If it is its
  chapter’s title clip, the chapter’s title card moves to the next clip that plays." (design, "The cut
  editor's words"), and check that no spec or test text quotes the old ending.

  Verify:
  - `tsc --noEmit` passes
  - `grep -rn "leaves the clip out of the movie" web/src` prints only the two hints
  - in the running client, the Cuts panel of `s1710001.mp4` of Grillning says the sentence before and after its
    preview has read the clip's length (task 7.1 records it)

## 4. web/ — the thumbnail note

- [x] 4.1 Add the reader and the counter (design, "How a failed thumbnail's cause is read", "Counting"):
  - `api/thumbnail.ts`: `FailedThumbnail` and `readFailedThumbnail(url, signal)`, using `isProblem` and
    `readJson` from `api/http.ts`; the three kinds `clip`, `service` and `unknown`; only `AbortError` is
    rethrown; a 200 or any body that is not a problem reads as `unknown`, its body cancelled
  - `events/thumbHealth.ts`: `THUMB_NOTE_AT = 3`, the context with `report` and `clear`, `useThumbHealth()`
    returning the context value and `unavailable`, `useThumbReporter()` for a thumbnail, `isUnavailable()` as the
    pure counting rule, and a no-op default for a thumbnail outside a provider
  - unit tests (`api/thumbnail.test.ts`, `events/thumbHealth.test.ts`, `events/loadState.test.ts`,
    `cuts/times.test.ts`, node runner): the reader's three kinds against a stubbed `fetch` (a 502 with an event
    `failure` is the third), what a Refresh carries into the reading state (`readingState`, `movieOf`), the counting rule (three of one key, mixed keys, `clear`), and
    both hints' title-card sentence; each fails without its code

  Verify:
  - `tsc --noEmit` passes
  - temporarily changing `'thumbnail_failed'` in the reader to another string, or the problem field it reads,
    makes `tsc` fail or the check of 7.2 fail; restore it
  - `grep -rn "thumbnail_failure" web/src` prints only `api/thumbnail.ts`
- [x] 4.2 Wire it in:
  - `events/ClipThumb.tsx`: a failed `LoadingThumb` runs the effect of the design (read; `report` a `service`
    answer under `SERVICE_CAUSE`; on cleanup abort and `clear`), keeps showing "No preview" throughout, and the header
    comment says what changed ("no alert and no retry" stays true of the image)
  - `events/EventDetail.tsx`: create the hook, provide the context around the main's content, render the note
    (`Alert tone="warn" role="note"`, words `PREVIEWS_UNAVAILABLE` in `events/labels.ts`, with `auto-reel thumbs`
    in a `<code>`) straight after the Movie slot, in both modes
  - `events/thumbs.css` only if the note needs a rule; no color literal

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -rn "role=\"alert\"\|toast" web/src/events/ClipThumb.tsx web/src/events/thumbHealth.ts` prints nothing
  - `git diff --stat` for this task lists only the files named here

## 5. Docs

- [x] 5.1 Bring the docs in line, and verify that each edit is the only change to its section:
  - `docs/high-level-design.md`: D-15's "A Refresh stops playback in v1" becomes "A Refresh keeps the player;
    Edit mode shows no movie, and entering it ends playback"; D-11 gains a bullet for the page-level note
    (three failures of one non-clip cause, a quiet note, `auto-reel thumbs`); D-14's "a whole-clip cut leaves
    the clip out" gains "and moves its chapter's title card to the next clip that plays"
  - `web/README.md`: the screens paragraph (a Refresh keeps the movie player; the note), and the file tree
    entries for `events/thumbHealth.ts`, with `api/thumbnail.ts` described as also reading a failed address

  Verify: `git diff docs/high-level-design.md web/README.md` touches only those places, and `grep -n "stops playback" docs/high-level-design.md web/README.md openspec/specs` prints nothing.

## 6. Browser verification

- [x] 6.1 Run an ad-hoc Playwright pass for playback from `$SCRATCH`, **never committed**:
  - script: `$SCRATCH/check_playback.py`, container `localhost/playback-research:chrome`, `--network host --ipc host`,
    target the built client on port 8242, locators scoped to `main:not([hidden])`, waits with
    `page.wait_for_timeout`
  - the event-detail GET is delayed by `page.route` on `**/api/v1/events/**` for GET requests of the detail
    only (the handler continues the thumbnail, movie and reel requests); no other route

  Check on `2024-07-14 - Kalas`, in a context where the movie can be played:
  - **Same element:** play the movie, wait until `currentTime > 2`, store `window.__v = <video>` and
    `t0 = currentTime`; press Refresh with the detail GET held 2 s. During those seconds `document.contains(__v)`,
    `!__v.paused`, `__v.currentTime >= t0`, the heading and rows are placeholders, "Reading event…" is announced,
    and the section shows no "Current", no file name, no size (`visibility: hidden`: `getByText` is not visible).
  - **After the answer:** the same element, still playing, `currentTime` never went back; "Current" and the
    file facts are back; the log holds exactly one movie request with `Range: bytes=0-0` after the Refresh
    and none while the read was held.
  - **Paused stays paused:** pause at 3 s, press Refresh: the same element, paused at 3 s (± 0.1).
  - **Other starts unchanged:** open the page in a new load: placeholders then a player paused at its start;
    play, enter Edit mode and leave it: a new element, paused at its start (the spec for those is unchanged).
  - **A new render:** render the event again in the library copy, press Refresh: a new element, paused at its
    start, whose `src` carries the new entity-tag.
  - **No movie, and failure:** remove the render manifest in the library copy and press Refresh: the section is
    gone and focus stays on Refresh; stop `serve`, press Refresh: the failure alert and no section.
  - **Layout:** the vertical distance between the Movie section and the first chapter panel is the same before,
    during and after a Refresh (± 1 px), and the section sits where it sat before this change (compare with a
    screenshot from the untouched tree).
  - **Screenshots** (look at each): Kalas read view, Refresh held, in light and dark at 1280 and 390 (8 PNGs);
    `scrollWidth <= innerWidth` at 390 and 320.

  Verify: every item passes; the PNGs and the script's output are in `$SCRATCH`; `git status` shows no
  Playwright, fixture or screenshot file in the repository.
- [x] 6.2 Run the notice and hint checks with the same setup, script `$SCRATCH/check_notices.py`:
  - **A real cache fault:** start a second `serve` on the same library with `XDG_CACHE_HOME` pointing to an
    unwritable directory (`chmod 0500`; restore it afterwards). Open `2024-06-27 - Grillning med grannar`: the four
    boxes read "No preview", exactly one `role="note"` "Previews are unavailable…" is shown above the clips,
    there is no `role="alert"` and no toast; enter Edit mode: the same single note in the same place; leave
    it, make the directory writable, press Refresh: four images and no note.
  - **Clips' own failures:** open `2024-10-05 - Trasig` (one broken clip): "No preview", no note, at most two
    thumbnail requests for `trasig.mp4`. With `page.route` on `**/thumbnail*` answering every thumbnail of
    Grillning 502 with `thumbnail_failure: thumbnail_failed`: four boxes, no note.
  - **Two are not a pattern:** `page.route` answering two of Grillning's four thumbnails 502 with no kind and
    letting the others through: two boxes, no note. Three: the note. Four answers that carry an event
    `failure` (`unusable_metadata`): four boxes, no note.
  - **Other answers count nowhere:** four thumbnails answered 404, then four with the route aborted: no note.
  - **Rows are untouched:** with the note shown, every row's box has the size and place it has without the
    fault (bounding boxes compared), and Tab order through the clips is unchanged.
  - **Cut hints:** in Edit mode on Grillning, the Cuts panel of `s1710001.mp4` says the title-card sentence
    before its preview is opened and after it has read the clip's length (read the panel text).
  - **Screenshots** (look at each): Grillning with the note in read view and in Edit mode, light and dark, at 1280
    and 390 (8 PNGs); `scrollWidth <= innerWidth` at 390 and 320; axe-core (wcag2a, wcag2aa, injected ad hoc)
    reports zero violations on the page with the note, in both schemes.

  Verify: every item passes, and the PNGs and the output are in `$SCRATCH`.

## 7. Validation

- [x] 7.1 Run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `npm test` in the node:22 container
  - the full `.venv/bin/python -m pytest` (the web-mount and OpenAPI drift tests must stay green); no Python
    file changed, so black, isort, mypy and pylint run only to confirm that nothing changed:
    `.venv/bin/python -m black --check auto_reel_ng tests`, `.venv/bin/python -m isort --check auto_reel_ng tests`,
    `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`
  - the motion grep gate of `web/README.md` over `web/src`

  Verify:
  - all of the above pass
  - `git diff main -- web/package.json web/package-lock.json web/openapi.json web/src/api/schema.d.ts web/src/ui web/src/styles` is empty
  - `RENDER_GRAPH_VERSION` is unchanged by this change (`git diff main -- auto_reel_ng` is empty)
  - `openspec validate web-playback-and-notices --strict` passes
