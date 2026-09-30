## 1. Baseline (no gate: this change lands first)

- [x] 1.1 Confirm the starting point. This change has **no gate**. `event-edit-screen` and
  `render-progress-screen` are gated on it. Steps:
  - Confirm `openspec/changes/` holds no other active change that edits `web/src/app.css`,
    `web/src/App.tsx` or `web/src/events/*.tsx`, apart from `event-edit-screen` and
    `render-progress-screen`, which are gated on this change and build on its result. If another one
    exists, stop and report.
  - Build this agent's isolated dev library on its own database, following the per-worktree runbook with
    `N=1`:
    - `DATABASE_URL=…/arel_web_design_system`
    - `.venv/bin/python scripts/make_dev_library.py ../dev-web-design-system`
    - `auto-reel serve ../dev-web-design-system/library --port 8101`, after
      `npm ci && npm run build` in the node:22 container

    Never use port 8080, `../auto-reel-dev` or `auto-reel-media/`.
  - Record the list's summary line and the verdict of `2023-06-23 - Midsommar - Dalarna`. The spec's
    scenarios name it as "Up to date".
  - Save baseline screenshots of the list and of `2024-08-20 - Två kapitel - Tjörn`, at 1280px in light and
    dark, to `/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/web-design-system/before/`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass on the untouched tree
  - the four baseline PNGs exist
  - the summary reads "7 of 10 events need rendering · 1 needs attention", or the recorded line is used
    in 6.1 instead

## 2. web/ — stylesheets and tokens

- [x] 2.1 Add the stylesheets and page metadata (design "Stylesheet architecture", "Tokens and the support
  floor", "Theme choice and persistence"):
  - Add `src/styles/index.css`: the single `@layer reset, tokens, base, components, screens;` statement,
    then `@import`s of the four other files.
  - Add `src/styles/reset.css`, including `[hidden] { display: none !important; }`.
  - Add `src/styles/tokens.css`: `light-dark()` OKLCH tokens, the five tones, spacing, radius, shadow, type
    and motion tokens, `data-theme` overrides, and reduced-motion zeroing.
  - Add `src/styles/base.css`: typography only, no layout on `main`, `header`, `nav` or `table`.
  - Add `src/styles/components.css` with the layout classes: `.btn*`, `.panel*`, `.data-table`,
    `.segmented`, `.stats`/`.stat` and `.visually-hidden`. Tasks 3.1 and 3.2 add the classes of their
    components.
  - `main.tsx` imports `./styles/index.css` before `App`. `App.tsx` keeps importing `app.css` for now, and
    its unlayered rules keep the old screens readable until group 4.
  - `index.html`: `<meta name="color-scheme" content="light dark">`, the two media-scoped `theme-color`
    metas, the inline `<head>` theme script (key `auto-reel:theme`, inside `try/catch`), and
    `<title>auto-reel</title>`.
  - `vite.config.ts`: `AUTO_REEL_API` through `loadEnv(mode, '.', '')`, falling back to
    `http://127.0.0.1:8080`, and `build.cssTarget: ['chrome123', 'edge123', 'firefox120', 'safari17.5']`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - the built `web/dist/assets/*.css` begins with the layer order statement
  - `grep -rn 'nth-child' web/src/styles` prints nothing
  - the motion grep gate (design "Tokens and the support floor") passes over `web/src/styles`: no literal
    transition duration, no `animation` timed by a `--dur-*` token, and every `animation`/`@keyframes`
    hit inside a `prefers-reduced-motion: no-preference` block
  - `web/package.json` is byte-identical to main

## 3. web/ — shared UI and the app shell

- [x] 3.1 Add the status primitives (design "Shared primitives", "Status tones and icons"):
  - `src/ui/Icon.tsx`: the 20 `IconName`s in a `Record<IconName, ReactNode>`, paths copied from
    `lucide-static`'s `icons/*.svg`, Lucide's license notice (ISC, plus Feather's MIT) in the header
  - `src/ui/Pill.tsx` (`Tone`, `Pill`), `src/ui/Alert.tsx`, and `src/ui/Skeleton.tsx` (`SkeletonRows`,
    `LoadStatus`)
  - `.pill`, `.badge`, `.alert`, `.skeleton` and `.load-status` in `components.css`
  - `src/events/tones.ts` (`JOB_STATUS_LOOK`, `CLIP_STATUS_LOOK`); `common.tsx`'s `StalenessCell` and
    `JobCell` render `Pill`s

  Verify:
  - `tsc --noEmit` passes
  - temporarily deleting the `'grip-vertical'` path entry makes `tsc` fail at the record; restore it
  - temporarily deleting one `JOB_STATUS_LOOK` key makes `tsc` fail; restore it
- [x] 3.2 Add the overlay primitives, per design "Shared primitives":
  - `src/ui/Dialog.tsx`, with the self-initiated-close guard and the optional
    `initialFocus?: RefObject<HTMLElement | null>`: focused right after `showModal()` when given and
    connected; otherwise the first focusable child gets focus (native behavior). No `autoFocus`.
  - `src/ui/toast.ts` (`toast.success|info|error`, `dismissToast`, `pauseToasts`, `useToasts`, `Toast`;
    5 s auto-dismiss for success and info, errors sticky, at most three held)
  - `src/ui/ToastRegion.tsx`: two always-present live containers, `role="status"` and `role="alert"`
  - `.dialog` and `.toast` in `components.css`; the region's bottom offset is
    `calc(var(--toast-inset-bottom, 0px) + var(--s-4))`, and nothing in this change sets the property

  Verify:
  - `tsc --noEmit` passes
  - the exported names and signatures match the design's code blocks exactly, since C4 and C5 import them
    blind
  - `grep -n 'autoFocus' web/src/ui/Dialog.tsx` prints nothing, and
    `grep -rn -- '--toast-inset-bottom' web/src` shows only the read in `components.css`
- [x] 3.3 Add the shell:
  - `src/shell/theme.ts`, with every storage access in `try/catch`
  - `src/shell/AppShell.tsx`: the skip button, the brand mark, the primary nav with `aria-current`, the
    empty `<div className="shell-status" />`, the theme radio group and `<ToastRegion />`, plus
    `focusPageHeading`
  - `src/shell/shell.css`
  - `src/events/changes.ts`: `markEventsChanged`, `currentEventsVersion`, `useEventsVersion`
  - `App.tsx` renders the routes inside `<AppShell route={route}>`, and calls
    `focusPageHeading({ preventScroll: true })` when `route` differs from the previous route held in a
    ref (not on mount, even under StrictMode)
  - `scroll-padding-top` on `html` for the sticky header

  (design "App shell, skip control and focus", "The events-changed signal"). Verify:
  - `tsc --noEmit` and `npm run build` pass
  - on the running build the header shows on both pages
  - after opening the list, then an event, clicking Events returns to the list without a new
    `GET /api/v1/events`, checked in the `serve` access log

## 4. web/ — the two screens

- [x] 4.1 Restyle the event list (design "Tables at every width", "Status tones and icons", "The
  events-changed signal"):
  - Add `src/events/list.css`, imported by `EventList.tsx`.
  - Markup:
    - a page header with the `h1` (`tabIndex={-1}`), the summary as stat chips that keep its words ("7 of
      10 events need rendering", "1 needs attention"), "Scanned <time>", and the `LoadStatus` region
    - a toolbar with the All / Needs render segmented radio group (same `onlyStale` state) and Refresh
      (`btn btn-secondary`, `refresh` icon, `aria-disabled` + `aria-busy` while loading, never `disabled`)
    - "Needs attention" as a warning panel with an `h2`
    - one panel per year with a sticky `h2` header
    - `data-table`s with `<colgroup>` classes and explicit table roles, the clip count as "N clips", and
      `data-label="Last job"` on job cells that have a job
  - `SkeletonRows` plus the `LoadStatus` message "Scanning events…" while loading, and `Alert` on failure.
  - The events-changed effect (`[hidden, version, load]`), declared after the mount effect.

  Verify:
  - `tsc --noEmit` passes
  - no `.table-scroll` or `nth-child` remains in `EventList.tsx` or `list.css`
  - `describeProblem` in `EventList.tsx` is unchanged (`git diff` shows no edit inside it)
- [x] 4.2 Restyle the event page (design "App shell, skip control and focus", "Tables at every width"):
  - Add `src/events/detail.css`, imported by `EventDetail.tsx`.
  - The header: a back link with the `chevron-left` icon to `LIST_HREF`, the `h1` (`tabIndex={-1}`), the
    facts line, the description, the verdict and latest-job pills, the counts, the muted "Read <time>"
    (kept from `EventDetail.tsx:166`) with the `LoadStatus` region beside it, and Refresh as on the list.
    "Read <time>" and `LoadStatus` stay together, because C5 puts its "Updating…" there.
  - Chapters as panels with an `h2` (the chapter name, `Main` when named chapters exist, "Clips" when the
    default chapter is the only one), keyed by `chapter.name`, with `useId()` heading ids.
  - Clip `data-table`s with colgroup classes, explicit roles and status pills. Ignored rows are dimmed.
  - The missing-clip warning and every failure as an `Alert`; a failure with a kind keeps its
    `FAILURE_LABEL` pill in the title. The not-found action links back to the list.
  - `SkeletonRows` plus the `LoadStatus` message "Reading event…" while loading.
  - Delete `src/app.css` and its import in `App.tsx`.

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -rn "app.css\|nth-child\|table-scroll" web/src` prints nothing
  - `grep -n 'Read {' web/src/events/EventDetail.tsx` still shows the read time
  - `describeProblem` in both screens is unchanged (`git diff` shows no edit inside either function)

## 5. Docs

- [x] 5.1 Update `web/README.md`:
  - the screens paragraph ("both read-only" becomes "both only read"), plus the theme control and the
    events-changed re-read
  - the file tree: `styles/`, `ui/`, `shell/`, `events/changes.ts`, `tones.ts` and the css files; `app.css`
    removed
  - a short "Design system" section: layers, tokens, where a later change puts its CSS, the fixed primitive
    names, and the support floor, plus the rules later changes follow: the busy-control pattern, the
    motion rules with the three-command motion grep gate (run by each later change over its own
    directory), `Dialog`'s `initialFocus`, and `--toast-inset-bottom`
  - `AUTO_REEL_API` for the dev server
  - the dependency budget, unchanged

  In `docs/high-level-design.md`, add **D-10** to §7. It records that GUI v1 includes the visual system,
  overriding event-list-screen's deferral of look and feel to v2, in plain CSS under D-8, with its rules
  (layers, `light-dark()` tokens, system fonts, inline-SVG icons, native `<dialog>`, status never by color
  alone, per-browser theme choice). Add one line in §4.10 pointing to it.

  Verify: `grep -n "D-10" docs/high-level-design.md` shows the §7 entry and the §4.10 line,
  `grep -n "app.css" web/README.md` prints nothing, and
  `grep -n "aria-busy\|no-preference\|initialFocus\|toast-inset-bottom" web/README.md` shows all four
  rules.

## 6. Verification against the dev library

- [x] 6.1 Run an ad-hoc Playwright pass from the session scratchpad, **never committed**:
  - script: `/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/web-design-system/check.py`
  - container: `podman run --rm --network host --ipc host -v <scratch>:/work:Z -w /work
    mcr.microsoft.com/playwright/python:v1.49.0-noble`
  - target: the rebuilt `web/dist` served by `auto-reel serve ../dev-web-design-system/library --port 8101`
  - scope every locator to `main:not([hidden])`
  - save screenshots to `/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/web-design-system/`:
    the list, `2024-08-20 - Två kapitel - Tjörn`, `2024-09-01 - Sommarlov` and
    `2024-02-30 - Omöjligt datum`, each with `color_scheme` light and dark, at 1280px and at 390px
    (16 PNGs), plus one loading state per screen

  Look at every screenshot, then check each item:
  - **List**:
    - the same counts and words as the 1.1 baseline summary ("7 of 10 events need rendering", "1 needs
      attention"), now as stat chips
    - the header's Events link has `aria-current="page"` here, and not on any event page
    - year panels with `h2`s, newest first
    - "Needs attention" first, showing `2024-02-30 - Omöjligt datum` with its failure words and detail
    - `2024-10-05 - Trasig` reads "Failed" with an icon
    - "Needs render" hides `2023-06-23 - Midsommar - Dalarna` and keeps the attention row
  - **Två kapitel**: `Main` and `Kvällen` `h2` panels, the statuses as pills with words, and the counts
    unchanged from the baseline.
  - **Sommarlov**: an alert naming `borttagen.mp4`, and that row shows `—` for size and time.
  - **Failures**: Omöjligt datum's page shows an error `Alert` with the same failure words and detail as
    its attention row; `#/event/2024/nope` shows the not-found `Alert` with a link back to the list.
  - **Phone width**: at 390px, `document.documentElement.scrollWidth <= innerWidth` on all four pages in
    both schemes, and every fact from the 1280px screenshot is still present. At 390px, the accessibility
    snapshot of a year table (`page.accessibility.snapshot()` or `locator.aria_snapshot()`) still reports
    table, row and cell roles, in Chromium **and** in WebKit.
  - **Theme**:
    - with `color_scheme='dark'`, choose Light, then reload: light from the first screenshot, and the
      control shows Light
    - the same reload with every `/assets/*.js` request aborted still computes `color-scheme: light` on
      `<html>`: the inline `<head>` script, not the bundle, applies the choice before first paint
    - System follows the emulated scheme again
    - with an init script that makes `localStorage` throw, the list renders with no console error, and
      choosing Dark switches the page
  - **Keyboard**:
    - the first Tab shows "Skip to content", and Enter focuses the `Events` `h1` with `location.hash`
      unchanged
    - opening Två kapitel by keyboard leaves `document.activeElement` on its `h1`, and so does Back
    - busy control: hold `/api/v1/events` with `page.route`, press Enter on the focused Refresh, and
      assert `document.activeElement` is still Refresh, with `aria-busy="true"` and
      `aria-disabled="true"` and no `disabled` attribute, until the held request is released
    - a focus ring is visible on a link and a button in both schemes (screenshot), and the ring color
      against the page background, from computed styles, is at least 3:1
    - tabbing down the list, every focused link's bounding box lies below the header and its year's
      sticky `h2`
  - **Loading and motion**:
    - hold `/api/v1/events` for 2 s with `page.route`, then Refresh: placeholder rows, and the
      `role="status"` region that was already present now reads "Scanning events…"
    - under `reduced_motion='reduce'`, the computed `animation-name` of the skeleton and of the busy
      Refresh's loader is `none`; under `no-preference`, it is not `none`, and its duration is the literal
      loop duration, not a `--dur-*` value
  - **Nothing changes, nothing polls**: record `auto-reel jobs list` and a marker file before the pass;
    afterwards the jobs list is identical, `find <library> -newer <marker>` prints nothing, and every
    request the pages made was a `GET`. With the list shown and no worker running, 60 s of idling makes
    no request.
  - **Contrast**: inject axe-core from cdnjs (scratch only) and run the `wcag2a` and `wcag2aa` tags on the
    list, Två kapitel and Omöjligt datum in both schemes: zero violations. Fix tokens and re-run until clean.
  - **Back as before**: with the filter on, scroll, open an event and go Back. The filter and scroll are
    kept, and there is no new `GET /api/v1/events`.
  - **Harness for the uncalled primitives** (design "Verifying what nothing calls yet"): run Vite in the
    node:22 container (`--network host`, `-e AUTO_REEL_API=http://127.0.0.1:8101`,
    `npx vite --host 127.0.0.1 --port 5101`), then:
    - `import('/src/ui/toast.ts')`: a success toast appears in the `role="status"` container and is gone
      after about 5 s; an error toast appears in the `role="alert"` container and stays until Dismiss; a
      hovered success toast does not expire
    - toast offset: at 390px, setting `--toast-inset-bottom: 64px` on `<html>` raises the region's
      bounding box bottom by 64px; removing it restores the default
    - `import('/src/events/changes.ts')`: open the list, set the filter to Needs render, open an event,
      call `markEventsChanged()`, then press Back: exactly one new `GET /api/v1/events`, with the filter
      kept
    - mount `Dialog` inside `<StrictMode>` with the app's React, resolved from the import URLs in the
      transformed `/src/ui/Dialog.tsx`: mounted with `open` true it stays open; Escape calls `onClose`
      once; setting `open` false calls no `onClose`; focus returns to the opener. Initial focus, with two
      buttons as children ("Discard" first, "Keep" second): without `initialFocus`,
      `document.activeElement` is "Discard"; with `initialFocus` pointing at "Keep", it is "Keep". If
      this mount proves unworkable, record that `Dialog` was verified by review only.
  - **Unreachable service**: `page.route('**/api/**', abort)`, then Refresh, shows the "not reachable"
    alert.

  Verify: every item passes, the PNGs are in the verify directory, and `git status` shows no Playwright,
  harness or screenshot file in the repository.

## 7. Validation

- [x] 7.1 Run `npx tsc --noEmit` and `npm run build` in the node:22 container, and the full
  `.venv/bin/python -m pytest`, which must keep the web-mount and OpenAPI drift tests green. No Python file
  changed, so black, isort, mypy and pylint are run only to confirm they are unchanged:
  - `.venv/bin/python -m black --check auto_reel_ng tests`
  - `.venv/bin/python -m isort --check auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`

  Also run the motion grep gate (design "Tokens and the support floor") over all of `web/src`, which now
  includes `shell.css`, `list.css` and `detail.css`.

  Verify that all pass, that the motion gate's three checks hold over `web/src`, that `web/package.json` and `package-lock.json` are unchanged from main, and that
  `openspec validate web-design-system --strict` passes.
