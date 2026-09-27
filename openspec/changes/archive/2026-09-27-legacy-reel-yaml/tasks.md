## 1. reel/ — the per-event rule in v0

- [x] 1.1 Move `SortMethod` (adding `CUSTOM`) and `ClipOrder` (adding `custom_order`) into `reel/document.py`, and re-export them from `event/discovery.py` and `auto_reel_ng.event`. Add `sort: Optional[ClipOrder]` to `ReelDocument`. Keep `config/project.py` rejecting `custom` (design "Where the sort types live"). Verify with `mypy` and the existing `tests/test_project_config.py` and `tests/test_event_reconcile.py` (both pass unchanged).
- [x] 1.2 Add `schema._parse_sort`, plus writer emission for fresh documents (design "Parsing and writing `sort`"). Verify with `tests/test_reel_parser.py` and `tests/test_reel_writer.py`:
  - `{method: filename, reverse: true}` loads, and round-trips byte-stable
  - `{method: shuffle}`, `{reverse: 1}`, and `custom_order` without `custom` each raise `ReelParseError` naming the field
  - `{method: custom, custom_order: {a.mp4: 2}}` loads

## 2. reel/ — legacy import

- [x] 2.1 In `reel/legacy.py`, map legacy `sort` onto the v0 `sort`, reporting only an unknown method. Recognize the dated title stem (design "The dated legacy title"), and correct the "honored implicitly" docstring. Verify with `tests/test_reel_parser.py` or the existing legacy-import tests:
  - `title: "2025-01-13 - Resa till Gran Canaria"` with no date → title `Resa till Gran Canaria`, date `2025-01-13`
  - with `metadata.date: 2025-01-14` → title verbatim, date `2025-01-14`
  - `title: "2019-04-31 - X"` → verbatim, date unset
  - `sort: {method: custom, custom_order: {b.mp4: 1}, reverse: true}` → carried, with no `sort` entry in `unmapped`
  - `sort: {method: random}` → reported

## 3. event/ + cli/ — precedence and `custom`

- [x] 3.1 Add the `custom` branch to `order_clips`, and use `document.sort or order` in `cli/adoption.prepare_event` (design "Precedence", "`custom`"). Verify with `tests/test_event_reconcile.py` and `tests/test_cli_adoption.py`:
  - custom `{c.mp4: 1, a.mp4: 2}` over a–d → c, a, b, d
  - `reverse` flips it
  - a legacy `reel.yaml` (no chapters) with `sort: {method: filename}` under a `datetime` library adopts its clips in filename order, while a sibling event without a `reel.yaml` seeds in `datetime` order
  - a v0 `reel.yaml` with a chapter and `sort: filename` appends two NEW clips in filename order after the existing ones

## 4. Docs

- [x] 4.1 Update the docs. Verify by rereading them against the specs.
  - `README.md`: document the per-event `sort` in `reel.yaml` (with `custom`/`custom_order`), note that legacy `sort` and dated titles are carried by import and on load, and add one line advising that a legacy `metadata.yaml` title such as `Dans hemma - Kungälv` should have its trailing location removed before running `auto-reel import`.
  - `docs/high-level-design.md` §4.6: add the optional `sort` to the schema sketch.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`. Verify all are clean or green, apart from the known cairo `no-member` noise.
- [x] 5.2 **Only if** `findmnt -no OPTIONS /run/media/emil/MOL` starts with `ro`, run:

  ```bash
  auto-reel adopt-renders /run/media/emil/MOL/Videos/Sorted -o /run/media/emil/MOL/Videos/Completed-auto-reel --dry-run
  ```

  Verify:
  - **130 would-adopt**, including `2025-01-13 - Resa till Gran Canaria`
  - the same 3 `ERROR`s as before (the bad folder names), unless you have fixed them by then
  - 2 unrendered (Spanien, 2012 Emma & Eli)

  Otherwise record the task as deferred.
