## 1. Gate

- [ ] 1.1 Confirm that the gate is archived on `main`: `ls openspec/changes/archive/ | grep -E -- '-media-endpoints$'` must
  print one directory. Stop and report to the supervisor if it does not. Then re-check what this change builds on
  (design, "Context") against the landed code. Stop and report on any mismatch that moves a name, a status or a
  mount point, and rename nothing here.
  - **The route in the schema:**
    - `web/src/api/schema.d.ts` has the path `/api/v1/events/{event_id}/movie`, whose `get` has an optional query
      parameter `v` and response keys `200`, `206`, `304`, `400`, `404`, `416`, `502` (plus FastAPI's own `422`,
      as on every route with parameters)
    - `grep -n '"video/\*": string' web/src/api/schema.d.ts` finds its 200 and 206
  - **The route's behavior** (after setup, below), with `curl -si -H 'Range: bytes=0-0'` on
    `/api/v1/events/2024/2024-07-14%20-%20Kalas/movie`:
    - 206, `Content-Range: bytes 0-0/<size>` and a strong `ETag: "<hex>-<hex>"`
    - `Cache-Control: private, no-cache`
    - `Content-Disposition: inline; filename*=utf-8''2024-07-14%20-%20Kalas.mp4`
    - on `2024-09-01 - Sommarlov`, 404 `application/json` with `event_id`
  - **The page:**
    - `EventDetail.tsx`'s `ReadyView` still opens with the missing-clips `Alert`, and `EventEditor` still replaces
      it in Edit mode
    - `load({ quiet: true })` still keeps `ReadyView` mounted
    - `thumbnailUrl`, `unansweredFailure`, `failureDetail`, `FAILURE_LABEL`, `formatBytes` and `Alert`'s `role`
      prop exist as the design cites them
  - **The other screen change:** if `clip-preview-screen` has landed, note whether `web/src/styles/tokens.css`
    already has `--media-bg` (task 2.2) and `web/src/ui/Icon.tsx` a `download` icon (used on "Download the
    movie"). If `api/clipMedia.ts` exists on `main`, reuse its status mapping rather than restating it; the
    response-to-kind table must stay identical.
  - **The docs:** read §4.10 and D-14 in `docs/high-level-design.md` on `main`, and note whether `media-endpoints`
    and `cross-chapter-drag` have edited them (task 3.2 builds on them).
  - **Set up** per the dev-env runbook §9 with `SLUG=movie-player-screen` and port **8130** (never 8080 or 5173,
    never the database `auto_reel_ng`, never `../auto-reel-dev`):
    - database `arel_movie_player_screen`, library `$AR/dev-movie-player-screen`
    - in that library copy only, the fixtures of design "Verification fixtures", by **symlinks** to
      `auto-reel-media/samples/`, never copies or moves. Render `2022/2022-05-19 - Provklipp` with
      `auto-reel render <library> -o <library-output> --years 2022`, and adopt `2016/2016-12-24 - Julafton - Tjörn`
      with `auto-reel adopt-renders <library> -o <library-output> --years 2016`
    - record `sha256sum` of every movie in `library-output`, `touch <verify>/marker`, then `serve` the library on
      8130 in the background with its PID recorded. Here `<verify>` is `<scratchpad>/verify/movie-player-screen`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass on the untouched tree (in `docker.io/library/node:22`)
  - `ffprobe -show_chapters` on Provklipp's movie lists two chapters, and `GET /api/v1/events` shows Julafton with
    no `no_manifest` and no `output` reason
  - `git diff --stat main -- openspec/specs` is empty

## 2. web/ — the address, the probe and the words

- [ ] 2.1 Add `web/src/api/headers.ts` (`contentRangeSize`, `dispositionName`, with no imports) and
  `web/src/api/movie.ts`, as design "One address per movie file" gives them:
  - `MOVIE_PATH` checked with `satisfies keyof paths`, and the `v` query typed from `paths`
  - `movieUrl(eventId, version)`
  - `MovieFile`, `MovieProbe` and `probeMovie(eventId, signal)`: `Range: bytes=0-0`, `cache: 'no-store'`, 200 or
    206 with `ETag` → `ok` with the body cancelled, 416 → `empty`, 404 or 502 problem → `problem`, rejected →
    `unreachable`, else `unpublishedAnswer('GET', …)`

  Verify:
  - `tsc --noEmit` passes, and temporarily changing `movie` to `movies` in `MOVIE_PATH`, or `v` to `version` in the
    query object, makes it fail; restore it
  - an ad hoc check in `<verify>/headers.check.ts`, run with `node --experimental-strip-types` in the node:22
    container against a copy of `headers.ts`, never committed, asserts:
    - `contentRangeSize`:
      - `'bytes 0-0/34207057'` → 34207057, and `'bytes */0'` → 0
      - `null`, `''`, `'bytes 0-0/*'` and `'items 0-0/5'` → `null`
    - `dispositionName`:
      - `"inline; filename*=utf-8''2024-06-27%20-%20Grillning%20med%20Grannar.mp4"` →
        `2024-06-27 - Grillning med Grannar.mp4`, and `"inline; filename*=utf-8''Tj%C3%B6rn.mp4"` → `Tjörn.mp4`
      - `'inline; filename="Blandat.mp4"'` → `Blandat.mp4`
      - `"inline; filename*=utf-8''%E0%A4%A.mp4"` (a malformed escape), `'inline'` and `null` → `null`
  - `grep -rn "/movie'" web/src --include=*.ts --include=*.tsx | grep -v schema.d.ts` prints only `movie.ts`

- [ ] 2.2 Add `web/src/movie/labels.ts`, `web/src/movie/MoviePanel.tsx` and `web/src/movie/movie.css`, and the
  `--media-bg` token in `web/src/styles/tokens.css`, per design:
  - **labels:** `MovieAge` with `MOVIE_AGE_LABEL` and `MOVIE_AGE_LOOK`, `OUTDATED_NOTE`, `MovieTrouble` with
    `MOVIE_TROUBLE` (title and tone), and `MEDIA_ERROR_WORDS`, with the exact words of the design's tables
  - **the panel:** `MoviePanel({ eventId, event })` (`hasMovie`, the poster clip, the probe effect on
    `[eventId, event]`, same-version keep, new-version replace with the focus handoff, the fetch-trouble note with
    its role and focusable wrapper)
  - **the player:** `MoviePlayer` keyed by version (`controls`, `preload="none"`, the poster, `aria-labelledby`,
    `no_picture` on `loadedmetadata`, the diagnosing re-probe on `error`, the playback-trouble notes and their
    actions)
  - **the stylesheet** and the token, as design "Layout and the design system" gives them

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -nE 'autoPlay|autoplay|loop|muted|\.play\(' web/src/movie` prints nothing
  - `grep -nE '#[0-9a-fA-F]{3}|oklch|rgb|black' web/src/movie/movie.css` prints nothing
  - the three motion grep commands of `web/README.md`, run over `web/src/movie`, print nothing at all
  - `git diff main -- web/src/styles/tokens.css` adds exactly the token, as one `light-dark()` value, and its
    comment, or is empty because the token is already there as specified (`clip-preview-screen` landed first)
  - removing a key from any of the four `Record`s makes `tsc` fail; restore it

## 3. web/ — mount point and docs

- [ ] 3.1 Mount `<MoviePanel eventId={eventId} event={event} />` as the first child of `ReadyView` in
  `web/src/events/EventDetail.tsx`, with its import.

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - in the running service (built client, port 8130), `2024-07-14 - Kalas` shows the "Movie" heading between the
    render region and the first chapter, and `2024-09-01 - Sommarlov` shows none
  - `git diff --stat main -- web/src` lists only the files of design "File ownership"

- [ ] 3.2 Update `web/README.md` and `docs/high-level-design.md`, as design "File ownership" and "HLD: D-15" list:
  - **`web/README.md`:**
    - the event page paragraph gains the Movie section: when it shows, Current or Outdated, the file and size,
      nothing loaded before Play, and failures by cause
    - the file tree gains `api/movie.ts`, `api/headers.ts` and the `movie/` directory
    - "Design system" gains `--media-bg`
    - "Checks" says that movie playback is checked in Chrome (channel `chrome`) or Firefox, never Playwright's
      bundled Chromium, which cannot decode H.264
  - **`docs/high-level-design.md`:** D-15 after D-14, §4.10's v1 bullet, and slice row C. Re-read §4.10 on `main`
    first, and keep `media-endpoints`' dated sentence and any `cross-chapter-drag` edit as they are.

  Verify:
  - `grep -n "D-15" docs/high-level-design.md` finds the entry, the v1 bullet and row C
  - `grep -n "movie/\|movie.ts\|headers.ts\|media-bg" web/README.md` finds the tree entries and the token
  - `git diff main -- docs/high-level-design.md` touches no other decision and no other section

## 4. Verification against the dev library

Run each check as an ad hoc Playwright script in `<verify>`, **never committed**:
- the container is `podman run --rm --network host --ipc host -v <verify>:/work:Z -w /work -e
  FONTCONFIG_FILE=/work/fonts/fonts.conf mcr.microsoft.com/playwright/python:v1.49.0-noble`, with `pip install
  playwright==1.49.0 && python -m playwright install chrome` before the script
- the browser is `p.chromium.launch(channel="chrome")` for every playback check. Playwright's bundled Chromium
  cannot decode H.264 (R0), so a check run with it would look like a player bug.
- Noto Sans and `fonts.conf` follow `web/README.md`
- locators are scoped to `main:not([hidden])`
- a request log comes from `page.on("request")`, alongside the serve access log
- screenshots are saved in `<verify>/shots/`; look at every one

- [ ] 4.1 Read view: layout, loading, keyboard and access (`check_read.py`).
  - **Widths and schemes:** `2024-07-14 - Kalas` (Current), `2024-06-27 - Grillning med grannar` (Outdated) and
    Provklipp, at 320, 390, 768 and 1280 px wide (800 tall), in light and dark (24 PNGs). For each:
    - `document.documentElement.scrollWidth <= innerWidth`
    - the frame's box is 16:9 within 1px
    - at 1280 it is 768 × 432, and after `scrollIntoView` it lies whole between the header's bottom and
      `innerHeight`
    - at 320 and 390 it spans the panel's inner width
    - the facts line's and the outdated sentence's text rectangles lie inside the panel
  - **Loading** (in a context that never routes):
    - opening Kalas makes exactly one `/movie` request, with `Range: bytes=0-0` and no `v`
    - the `<video>`'s `src` ends in `?v=<that answer's ETag without quotes>`
    - its `preload` is `none`, and it has no `autoplay`, `loop` or `muted` attribute
    - its `poster` attribute equals the `src` attribute of `s1710002.mp4`'s row image
    - after 5 s, `paused` is true and `readyState` is 0
    - the serve log shows no other `/movie` request
  - **Copy:** Kalas shows "Current" and names `2024-07-14 - Kalas.mp4` with its size as `formatBytes` writes the
    probe's `Content-Range` total. Grillning shows "Outdated", `OUTDATED_NOTE`, and the old name
    `2024-06-27 - Grillning med Grannar.mp4`, while its `.render-panel` contains no `.mp4` (the modified
    renamed-movie scenario), at 390 and 320 px in both schemes.
  - **No movie:** `2024-09-01 - Sommarlov`, `2024-10-05 - Trasig`, `2024/Blandat` and `2024-07-14 - kalas` show no
    "Movie" heading and make no `/movie` request.
  - **Keyboard only:**
    - from Kalas's Edit button, Tab until `document.activeElement` is the `<video>`, and record the count
    - the `<video>` matches `:focus-visible`, its computed outline is 2px solid, and no ancestor up to the panel has
      computed `overflow` other than `visible` (screenshot in both schemes)
    - Space plays (`currentTime` advances at least 1 s in 2 s), Space pauses, Home returns to 0, End reaches
      `duration`
    - Tab then leaves the player for the next control in the page
  - **Coarse pointer** (`has_touch`, 390 px): the native controls show, and the page scrolls no wider. The note
    actions' 44 × 44 checks are in task 4.3.
  - **axe-core** (injected ad hoc; `wcag2a`, `wcag2aa`): zero violations on Kalas and Grillning in both schemes.
    Record that `video-caption` is listed under `incomplete`.
  - **Motion:** under `reduced_motion='reduce'`, `document.querySelector('.movie-panel').getAnimations({ subtree:
    true })` is empty.
  - **Edit mode:** on Grillning, Edit removes the "Movie" heading. Stop editing brings it back with a paused
    `<video>` at `currentTime` 0.
  - **Changes nothing:** after these checks, `find $AR/dev-movie-player-screen -newer <verify>/marker` and `find
    ../auto-reel-media -newer <verify>/marker` print nothing, `auto-reel jobs list` is unchanged, and every request
    the pages made was a `GET`.
  - **Idle:** with Kalas shown and nothing played, 60 s of idling make no request.

  Verify: every item passes, and the PNGs and the script's output are in `<verify>`.

- [ ] 4.2 Playback and versions (`check_play.py`):
  - **It plays:** Provklipp's movie from the keyboard, then at least 1 s of advance in 2 s, and a seek to 50 % fires
    `seeked`. `duration` is within 0.1 s of `ffprobe -show_entries format=duration`.
  - **Refresh starts over.** Play Kalas's movie for 2 s and mark the element, then press Refresh. The page shows
    its placeholders, then an unmarked `<video>` that is paused at `currentTime` 0, whose `src` carries the same
    `v` as before.
  - **A finished render replaces the player.** First cancel the dev library's queued `2024/Blandat` job
    (`auto-reel jobs list <library> --status queued`, then `auto-reel jobs cancel <library> <id>`), so the worker
    renders nothing else. Then start `auto-reel worker <library> --device cpu` with the same `DATABASE_URL`. On
    Kalas:
    - play and pause from the keyboard, so that focus stays on the `<video>`
    - mark the element (`v.dataset.mark = 'old'`)
    - `POST /api/v1/jobs` `{"event_id": "2024/2024-07-14 - Kalas", "force": true}` with curl
    - wait until the render region shows the job as rendered and the page's probe after it is logged (no toast:
      the tab did not start this job)
    - check that the `<video>` has no mark, its `src` carries the new file's `ETag`, `document.activeElement` is
      the new `<video>`, and it plays

    Stop the worker afterwards.
  - **A re-read that finds the same file keeps playing.** With no worker running, play Kalas's movie and mark the
    element. Enqueue a forced job with curl, then cancel it with `POST /api/v1/jobs/{id}/cancel` while it is
    queued. After the page's re-read and its probe (request log), the marked element is still there, `paused` is
    false, and `currentTime` did not go back.
  - **No picture:** on Julafton, Play leads to `videoWidth === 0`, no `error`, and the `status` note "This browser
    cannot show this movie's picture. It plays the sound only." with the player still shown.
    `page.expect_download()` on "Download the movie" gives `suggested_filename` `2016-12-24 - Julafton - Tjörn.mp4`.
    Cancel the download.
  - **The file changes while it plays:**
    - play Provklipp's movie for 2 s
    - `os.replace` a copy of Grillning's old-name movie over it, after keeping the original as a hard link
    - seek to 60 s
    - the `alert` "The movie file changed while it played." appears with "Load the new movie"
    - Enter on it shows a paused `<video>` with focus, whose `src` carries the new `ETag`
    - it plays, and its `duration` is the replacement's
    - restore the original afterwards, in a `finally`
  - **Firefox pass** (`p.firefox.launch()`, the same container): Kalas plays with Space. Provklipp's movie has
    `mozHasAudio === true` after `loadedmetadata`: its PCM source was rendered to AAC. 390 px shows no horizontal
    scroll.

  Verify: every item passes, the script's output and screenshots are in `<verify>`, and Provklipp's movie has the
  `sha256sum` recorded in 1.1 again.

- [ ] 4.3 Failures by cause (`check_fail.py`), each fixture made and undone around its own check on Kalas:
  - **404:** move `2024/2024-07-14 - Kalas.mp4` aside in `library-output` and `mkdir` that name. The page's
    staleness still cites no reason. The section shows "The service has no movie file for this event." with the
    service's detail, no `<video>`, and no element with `role="alert"` in the section.
  - **502:** `chmod 000` the movie (skip as root). The section shows "The movie could not be read." with a detail
    that contains `2024-07-14 - Kalas.mp4` and `Permission denied` and not `$AR`, and no `<video>`.
  - **416:** replace the movie by an empty file. The section shows "The movie file is empty."
  - **Unanswered:** `page.route('**/movie*', lambda r: r.abort())`. The section shows "The service is not
    reachable." with the hint to press Refresh.
  - **The file goes after the page read it:** open Kalas (player shown, nothing loaded), then swap the movie for a
    folder on disk, then Tab to the `<video>` and press Space. The `error` leads to the note "The service has no
    movie file for this event." with `role="alert"` in place of the player, and focus is on the note's wrapper.
  - **The browser fails:** `page.route('**/movie?v=*', lambda r: r.abort())` (the probe, which has no `v`, still
    passes), then Play. The `alert` "This browser could not play the movie." appears under the frame with one of
    `MEDIA_ERROR_WORDS`' sentences and "Download the movie".
  - **Narrow:** each note at 320 px in both schemes has `scrollWidth <= innerWidth`, and its text rectangles lie
    inside the panel (PNGs).
  - **Coarse pointer** (`has_touch`, 390 px): a tap at each corner of a 44 × 44 area centered on "Download the
    movie" (Julafton) and on "Load the new movie" (the replacement fixture) reaches that control, using
    `document.elementFromPoint`.

  Before the first fixture, copy Kalas's movie to `<verify>/kalas.mp4` (task 4.2 rendered it anew).

  Verify: every item passes, each fixture is undone (the movie `cmp`-equal to that copy, its mode restored), and
  `git status` shows no Playwright, fixture or screenshot file in the repository.

## 5. Validation

- [ ] 5.1 Run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - the full `.venv/bin/python -m pytest`, which keeps the web-mount and OpenAPI drift tests green
  - no Python file changed, so these run only to confirm that nothing changed:
    - `.venv/bin/python -m black --check auto_reel_ng tests`
    - `.venv/bin/python -m isort --check auto_reel_ng tests`
    - `.venv/bin/python -m mypy auto_reel_ng`
    - `.venv/bin/python -m pylint auto_reel_ng`
  - then stop `serve`, drop `arel_movie_player_screen`, and remove `$AR/dev-movie-player-screen`

  Verify:
  - all of the above pass, apart from the known cairo `no-member` noise and the environmental title-card skips
  - the motion grep gate passes over `web/src`
  - `git diff main -- web/package.json web/package-lock.json web/openapi.json web/src/api/schema.d.ts web/src/ui
    auto_reel_ng alembic` is empty
  - `openspec validate movie-player-screen --strict` passes
