## Context

See proposal.md, "Why", for the finding. The code on `main` at `6a7fe16`:

- `event/metadata.py` `load_authored_document` decides between "load the document" and "seed from the
  folder" with `reel_path.exists()`.
- `event/discovery.py` `scan_event` lists with `iterdir()` and classifies each entry with `is_dir()` (line
  134), `is_reelignored` -> `(dir / ".reelignore").is_file()` (line 145) and, in `_video_identities`,
  `is_file()` (line 333). `iterdir()` needs the read bit; every `is_*()` needs the search (`x`) bit of the
  parent. Re-checked on Python 3.14.7 with a `0600` folder holding `reel.yaml` and `a.mp4`:
  `iterdir()` lists both names, `stat()` raises `PermissionError`, `exists()` / `is_file()` answer `False`.
  At `0100`/`0300` (no read bit) `iterdir()` itself raises, which the API already maps to `unreadable_disk`
  (`tests/test_api_events_failures.py`), and `exists()` is `True`. The bug is the read-but-not-search case.
- Callers already treat `OSError` as a per-event disk failure: `events_read.py:245` and `:454` catch
  `(ReelError, OSError)` and `classify_event_failure` maps `OSError` to `unreadable_disk`. So raising
  `PermissionError` from the engine is enough for the events list and detail to turn loud.
- `load_document` already raises `ReelParseError` for a `reel.yaml` that exists but cannot be read
  (`reel/parser.py:103`). That stays as it is; it is a different case from this one.
- `is_reelignored` is public and `ingest/layouts.py:111` calls it on every event folder during the walk.

## Goals / Non-Goals

**Goals:**

- Never read "the disk refused to answer" as "there is no `reel.yaml`" or "there are no clips".
- Provide one helper the other `exists()` sites can adopt, so the rule lives in one place.
- Keep every readable event rendering byte-identically.

**Non-Goals:**

- Swapping the `exists()` calls in `editorial.py`, `events_read.py`, `commands.py` and `adoption.py`. Those
  files are changed by gated work that lands after this change (`editorial-chapter-comments`,
  `api-jobs-create-validation`, `cli-batch-isolation-and-claims`); each adopts `reel_exists` there. Editing
  them here would collide with that work.
- Making the CLI isolate an `OSError` per event (`ERROR <event>: ...`) and making the worker fail a job on
  one. `cli-batch-isolation-and-claims` and `worker-exception-backstop` own those. Until they land, an
  unsearchable event ends a CLI batch with the traceback an unreadable (`0000`) folder already produces.
- The ingest walk (`ingest/layouts.py`). A `0600` event folder is still listed by the walk, so the engine
  can report it; skipping it there would hide it again.

## Decisions

**1. `reel_exists(path: Path) -> bool` lives in `event/metadata.py`, next to `REEL_FILENAME`.** It calls
`path.stat()` and returns `False` only for `FileNotFoundError` and `NotADirectoryError`; anything else, a
`PermissionError` in particular, propagates unchanged. `stat()` follows symlinks, so a dangling symlink is
`False` and a symlinked `reel.yaml` is `True`, as with `exists()`. It takes the file's path, not the event
folder, because the call sites hold different things (`reel_path` in `editorial.py`,
`ref.event_dir / REEL_FILENAME` in `commands.py`).
Alternatives: (a) `os.access(dir, R_OK | X_OK)` as a pre-check: reads the real UID's mode bits, ignores
ACLs and capability grants, and races; asking the kernel with the operation we need is exact. (b) Put it in
`reel/`: `reel/` has no notion of an event folder and the only users are event-level; `event/metadata.py` is
where the load/seed decision already is.

**2. The helper raises the raw `OSError`, not `ReelParseError`.** The reel-document requirement turns a
failure to *read* a file into the parse error, because the file's content is the problem. Here the folder is
the problem, and the existing mapping for a folder the engine cannot list is `unreadable_disk`. Wrapping it
in `ReelParseError` would label the same `0600` event `unparseable_reel_yaml` on the events list but
`unreadable_disk` for a `0000` one. The reel-document delta states the distinction so the two requirements
do not contradict each other.

**3. `scan_event` classifies entries with a private strict `stat`, not `is_dir()` / `is_file()`.** Two
module-private helpers, `_is_dir(path)` and `_is_file(path)`, call `path.stat()` and return `False` for
`FileNotFoundError` / `NotADirectoryError` only. They are used for the chapter-subfolder test, the video
test and the `.reelignore` marker lookup inside `_is_chapter_dir`. A dangling symlink is still skipped
(`FileNotFoundError`), and a symlinked clip whose target sits in a folder the process cannot search now
raises instead of vanishing: the clip is there, the engine cannot say what it is, and an omitted clip is
what the render would then silently leave out. That consequence is deliberate and is a scenario.
Alternative: a single `os.access(event_dir, X_OK)` check at the top of `scan_event`. It misses a `0600`
chapter subfolder and the symlink case, and carries the ACL objection from decision 1.

**4. The public `is_reelignored` keeps its lenient behaviour.** The ingest walk calls it per event folder
before any event is built; if it raised, one `0600` event would fail the whole project walk (a whole-list
502) instead of costing one error row. `scan_event` does its marker lookup through the strict helper and
`is_reelignored` stays for the walk. A short docstring note says why the two differ.

**5. No `RENDER_GRAPH_VERSION` bump.** Rendered bytes for identical readable inputs do not change.

## Risks / Trade-offs

- [An interim traceback in the CLI and a stuck-until-restart job in the worker for an unsearchable event]
  -> The same failure already exists for a `0000` folder, which `scan_event` raised on before this change.
  The CLI half is closed by `cli-batch-isolation-and-claims` and the worker half by
  `worker-exception-backstop`; the engine now raises where it used to answer wrongly.
- [A project with a symlinked clip into a folder the process cannot search now fails that event] -> Intended:
  fail loud beats a render that silently drops the clip. The error names the path (the `PermissionError`
  carries it).
- [`stat()` per entry was already the cost of `is_file()`; no extra syscalls] -> None needed.
- [Running as root ignores mode bits] -> The tests skip when `os.geteuid() == 0`, as the existing
  permission tests do.
