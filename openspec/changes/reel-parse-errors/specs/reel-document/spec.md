## MODIFIED Requirements

### Requirement: Fail-loud parse and validation

Parsing SHALL fail loudly with a clear error on malformed or invalid content and SHALL NOT fabricate or
silently drop data. Validation SHALL reject (at least) an unknown `version`, a trim with `out <= in`, a
negative time, and a `chapters` clip reference whose identity is absent from required structure. Errors SHALL
identify the offending location.

The reference-integrity checks are **disk-independent** — a referenced clip merely absent from disk is a
*reconcile* MISSING (see `event-reconcile`), not a parse error. Internally the validator SHALL reject: a clip
identity referenced more than once across all chapters (a duplicate/ambiguous reference); a `clips` property
entry keyed by an identity no chapter references (a dangling property record with nothing to attach to); and
an `ignore` entry whose identity is also referenced in a chapter (a structure/ignore contradiction).

Content that cannot be read as YAML text SHALL fail the same way. This covers:

- **An impossible typed value.** YAML reads an unquoted scalar such as `2024-02-30`, `2024-13-45` or
  `2024-02-29T25:00:00` as a date or a timestamp, and that date or time does not exist. The same holds for a
  value whose explicit tag it cannot satisfy, such as `!!int abc`, `!!bool maybe`, or `!!int` with no value.
  This SHALL fail in a v0 document and in a legacy one, wherever in the document the value appears, `look`
  included. The error SHALL name the file, the value as written, and its line.
- **Any other text the YAML reader cannot load.** An example is a double-quoted escape that names no
  Unicode character (`"\UFFFFFFFF"`). When the reader reports no position, the error SHALL name the file
  and the reader's reason.
- **Bytes that are not UTF-8 text.** The error SHALL name the file, state that it is not UTF-8 text, and give
  the offset of the first byte that cannot be decoded.

Every failure to load or validate a document's content, and every failure to read its file, SHALL be raised
as the single parse error this requirement defines, never as another kind of error. Every caller that reports
an unparseable `reel.yaml` for one event therefore reports these the same way:

- the CLI's `ERROR <event>: <reason>` line
- the events list's error row with the unparseable-`reel.yaml` failure kind
- the event detail's 502 problem body

A value is never coerced, clamped or dropped to make a document load.

#### Scenario: Invalid trim is rejected
- **WHEN** a document contains a trim with `out` less than or equal to `in`
- **THEN** loading fails with an error naming the clip and the invalid span

#### Scenario: Unknown version is rejected
- **WHEN** a document declares a `version` this engine does not support
- **THEN** loading fails with a clear unsupported-version error rather than a best-effort parse

#### Scenario: Dangling clip property entry is rejected
- **WHEN** the `clips` map holds a property entry keyed by an identity that no chapter references
- **THEN** loading fails with an error naming the dangling identity rather than silently keeping an orphaned record

#### Scenario: Duplicate clip reference is rejected
- **WHEN** the same clip identity is referenced more than once across the document's chapters
- **THEN** loading fails with an error naming the duplicated identity

#### Scenario: An impossible date is a parse error naming the value and its line
- **WHEN** the `reel.yaml` of `2024/2024-07-04 - Barbecue` reads `version: 0`, then `metadata:`, then
  `title: Barbecue`, then `date: 2024-02-30` on line 4
- **THEN** loading fails with the parse error, whose message names that `reel.yaml`, the value `2024-02-30`
  and line 4, and no other kind of error is raised

#### Scenario: An impossible date in a legacy document fails the same way
- **WHEN** a `reel.yaml` with no `version` key has `metadata:` with `date: 2024-13-45`
- **THEN** loading fails with the same parse error naming `2024-13-45` and its line, before any legacy import
  is attempted

#### Scenario: An impossible timestamp inside look fails loud
- **WHEN** a v0 document's opaque `look` map holds `generated: 2024-02-29T25:00:00`
- **THEN** loading fails with the parse error naming that value and its line, although `look` is otherwise
  not validated

#### Scenario: A value its explicit tag cannot hold fails loud
- **WHEN** a v0 document's `look` map holds `shadow: !!bool maybe`, or `size: !!int` with no value
- **THEN** loading fails with the parse error naming the file, the value as written (`maybe`, or the empty
  value), and its line, and no other kind of error is raised

#### Scenario: An escape that names no character is a parse error
- **WHEN** a v0 document sets `title: "Fest \UFFFFFFFF"`, a double-quoted escape beyond the last Unicode
  code point
- **THEN** loading fails with the parse error naming the file and the reader's reason, and no other kind
  of error is raised

#### Scenario: A real leap day and a quoted impossible date behave as before
- **WHEN** a v0 document sets `date: 2024-02-29`, or sets `date: '2024-02-30'` in quotes
- **THEN** the first loads with the date 29 February 2024, and the second fails with the existing error
  naming `metadata.date` as an invalid date

#### Scenario: A reel.yaml saved as Latin-1 is a parse error
- **WHEN** an event's `reel.yaml` holds the title `Kräftskiva` encoded as Latin-1, so its bytes are not
  valid UTF-8
- **THEN** loading fails with the parse error, whose message names that `reel.yaml`, says it is not UTF-8
  text, and gives the offset of the first bad byte

#### Scenario: One impossible date costs one event
- **WHEN** a project holds `2024-06-21 - Midsommar`, `2024-07-04 - Barbecue` and `2024-08-01 - Kräftskiva`,
  and only Barbecue's `reel.yaml` sets `date: 2024-02-30`
- **THEN** `auto-reel scan` prints one `ERROR  2024-07-04 - Barbecue:` line naming `2024-02-30`, lists the
  other two events and exits non-zero. The events list answers 200 with two summaries and one error row for
  Barbecue, whose failure kind is `unparseable_reel_yaml`.
