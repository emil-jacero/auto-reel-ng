## 1. Gate and set-up

- [x] 1.1 Confirm the gates are archived on `main` and bind the field names: `ls openspec/changes/archive/ | grep -E
  -- '-(render-chapter-times|movie-facts-read)$'` must print two directories (stop and report if not). Read their
  archived specs and `web/src/api/schema.d.ts`: `EventDetailOut` must carry the movie's chapters (name, start
  seconds, nullable) and a movie version (record time, short fingerprint, nullable). The real field is `movie`
  (`recorded_at`, `fingerprint`, `chapters`); bound in this change's `design.md` D1, and
  stop and report if the detail lacks either (do not derive chapter starts on the client). Set up with the
  brief's values (`DB=arel_movie_chapter_list`, `PORT=8311`, `$DEV`, `$ENVF`, `$TMPDIR`); `npm ci` in the node:22
  container; render `2024-06-21 - Midsommar - Dalarna` once in `$DEV` only so it has a movie with chapter times.

  Verify:
  - `npx tsc --noEmit` and `npm test` pass on the untouched tree (node:22 container)
  - `curl -s localhost:8311/api/v1/events/<Midsommar id>` shows its chapter list and version; the same for an
    event rendered before the gate (or `adopt-renders`) shows them null
  - `git diff --stat main -- openspec/specs` is empty

## 2. web/ — the pure model

- [x] 2.1 Add `web/src/movie/chapters.ts`: `ChapterMark`, `usableChapters(raw)` (D2), `listedChapters(raw)` (D2), `currentChapterIndex(chapters,
  position, slack = 0.06)` (D3), `jumpLabel(index, title, start)` (D6), `chapterHeading(name, hasNamed)` in `web/src/events/labels.ts` (used by `EventDetail`
  too, D6), and `web/src/movie/facts.ts`: `movieFacts(event)`
  (D1) and `movieVersionWords(version)` (D7), reusing `formatTime` and `formatInstant`.

  Verify (`chapters.test.ts`, `facts.test.ts`, `node:test`; `npm test` and `tsc --noEmit -p tsconfig.test.json` pass):
  - `usableChapters`: `null` for `null`, `[]`, a non-increasing pair, equal starts, a negative, `NaN`,
    `Infinity`, a whitespace-only name and a non-string name; the empty name is usable; the same array back for a valid one, including a
    first start above 0; it never reorders or drops a row
  - `listedChapters`: `null` for one usable chapter, the array for two
  - `currentChapterIndex`: `null` before the first start less the slack; index 0 at exactly 0 and at 0.5; the
    boundary at `start`, `start - 0.06` (next chapter) and `start - 0.061` (previous); the last chapter past the
    end of the movie; a single chapter
  - `jumpLabel(1, 'Majstången', 74)` is `Jump to chapter 2, Majstången, at 1:14`; an hour-long
    start reads `1:01:15`; a name with a comma is left as it is
  - `movieVersionWords`: instant and fingerprint both present; fingerprint only (unparseable time); no version
    gives nothing; the `dateTime` value is the input string, not the formatted one
  - `movieFacts` returns `chapters: null` for a null `movie`, a null/absent `chapters`, `[]` or an unusable list, and
    the list as it is when usable
  - `chapterHeading`: `""` is `Main` when another chapter is named, `Clips` otherwise; a name is returned as it is

## 3. web/ — the list in the section

- [x] 3.1 Add `movie/ChapterList.tsx` and wire it into `MoviePlayer` (D4-D6): `chapters`, `asRendered` (from `age`) and `videoRef`
  props from `MovieSection`; rendered after the facts only when `file !== null` and the chapters are usable; the
  mark state fed by the video's `timeupdate` and `seeked`; the jump with the `readyState`/one-shot
  `loadedmetadata` path; `AbortError` from `play()` ignored; focus stays on the button; the layout-effect
  cleanup that moves focus to the video; the version line in the facts; the words in `labels.ts`
  (`CHAPTERS_HEADING`, `CHAPTERS_AS_RENDERED`, `CURRENT_CHAPTER`).

  Verify:
  - `npx tsc --noEmit` (app and test configs) and `npm run build` pass; `npm test` still passes
  - `grep -n "keydown\|onKeyDown\|accesskey" web/src/movie` prints nothing (no shortcut of the page's own)
  - `grep -rn "currentTime *=" web/src/movie` shows only the jump's two lines in `ChapterList.tsx` (the
    list never invents a position anywhere else)
  - `grep -rnE "start *[:=] *[a-z]+\.(duration|length)|\.reduce\(" web/src/movie/chapters.ts web/src/movie/facts.ts`
    prints nothing (no start is derived)

- [x] 3.2 Style it in `movie/movie.css` (D8): rows, the mark, the "As rendered" caption, `pointer: coarse` 44 px,
  tokens only, no `overflow` ancestor of a button, no `transition`/`animation`.

  Verify:
  - `grep -nE '#[0-9a-fA-F]{3}|oklch|rgb' web/src/movie/movie.css` prints nothing new
  - the three motion greps of `web/README.md` ("Motion") print nothing over `web/src/movie`
  - `npm run build` passes

## 4. Browser verification

- [x] 4.1 Playwright from `$SCRATCH` against the served dev library (`auto-reel serve $DEV/library --port 8311`
  with `XDG_CACHE_HOME=$SCRATCH/xdg`; `npm run build` before each pass), in Chrome 154
  (`localhost/playback-research:chrome`) and in Firefox >= 155 (check `browser.version`; the
  `localhost/pcm-audio-research:pw163` image has it), writes intercepted on `**/api/v1/jobs`, `**/api/v1/jobs/**`,
  `**/reel`, `**/reel?*` only, `main:not([hidden])` locators, `page.wait_for_timeout` only. Pass each scenario of
  `specs/web-app/spec.md` that a browser can show:
  - a list of the movie's chapters with their times; the first row marked at the start
  - activate the third chapter with the mouse before the first Play: `currentTime` within 0.1 s of its start,
    `paused === false` within 2 s, only that row marked, focus still on the button; the same by Tab to the list
    and Enter, and by Space
  - pause, drag the native timeline into another chapter: the mark follows within half a second, nothing is
    announced (no `role=status`/`alert` text changes)
  - an event with no chapter data (rendered before the gate): no "Chapters" heading, no list; the facts omit the
    version; a doctored detail (route `**/api/v1/events/<id>` fulfilled with decreasing starts) shows no list
  - the version line against the detail; "As rendered" on an outdated movie (edit the title in `$DEV` only)
  - re-render while the page is open: new player, list of the new chapters, marks reset
  - a re-read (route fulfilling a detail without chapters) while focus is on a chapter button: focus on the video
  - reduced motion emulated: the mark moves at once, `getAnimations()` is empty on the section; no horizontal
    scroll at 320, 390 and 1280 px; coarse pointer: each button at least 44 x 44 px
  Screenshots in light and dark at 1280 and 390 are taken and LOOKED at (the mark readable without colour:
  also with `forced-colors: active` emulation in Chrome). The report names every deviation and each browser's
  version.

## 5. Documentation

- [x] 5.1 Update `docs/high-level-design.md` as in D9: D-15's chapter-list sentence amended with the date and
  this change's name, §4.10's v2 item marked delivered, one D-20 line (the chapter band reuses
  `usableChapters`), the §6 GUI v2 line. Update `web/README.md`'s movie section if it lists the section's parts.

  Verify:
  - `grep -n "no chapter list" docs/high-level-design.md web/README.md openspec/specs` prints nothing except the
    archived changes' own text (the live spec was changed by this change's MODIFIED block)
  - `openspec validate movie-chapter-list --strict` passes
  - `git diff --stat` shows only `web/`, `docs/` and `openspec/changes/movie-chapter-list`
