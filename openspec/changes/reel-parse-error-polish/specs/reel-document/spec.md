## ADDED Requirements

### Requirement: Load errors name the real source and how far reading got

Every message the parse error carries for a document that cannot be loaded SHALL name the source it was read
from (the `reel.yaml` path, or the caller's stated source for text not read from a file). It SHALL NOT name
the YAML reader's internal stand-in for a string stream (`<unicode string>`): where the reader's excerpt
says which stream a line and column belong to (`in "...", line 2, column 8`), that name SHALL be the
document's own source. The excerpt's line, column and reason are otherwise unchanged. This holds for every
YAML syntax or structure error the reader reports with a position, including a repeated key.

A failure the reader reports with no position of its own SHALL, when the reader had already produced
tokens before it failed, also state the line it got as far as: a line number that is a lower bound on where
the failure is, not a claim of the exact line. When the failure happens after the whole text was read
(a document nested deeper than the engine can load), there is no such line and the message SHALL name the
source and the reason only. A document nested too deeply to load SHALL be reported as such, with the
underlying reason kept, and SHALL NOT be reported only as the bare recursion-limit message.

None of this changes which documents load or which kind of error is raised: it remains the single parse
error, and a message is never made to look as if it located something it did not.

#### Scenario: A syntax error names the document, not the stand-in
- **WHEN** the `reel.yaml` of `2024/2024-07-04 - Barbecue` reads `version: 0`, then `title: "\x"` on line 2
- **THEN** loading fails with the parse error whose message holds that `reel.yaml`'s path in the reader's
  excerpt for line 2 (in place of `<unicode string>`), still shows line 2 and the reader's reason, and does
  not contain `<unicode string>`

#### Scenario: A structure error with a position is renamed the same way
- **WHEN** a v0 document defines the same top-level key twice, or has a tab starting a line, or an unclosed
  flow sequence
- **THEN** loading fails with the parse error whose message does not contain `<unicode string>` and names
  the source in each of the reader's line-and-column excerpts

#### Scenario: A source given by the caller is used as given
- **WHEN** text is loaded with the stated source `draft-reel` and holds `title: "\x"`
- **THEN** the message names `draft-reel` in the excerpt and does not contain `<unicode string>`

#### Scenario: A position-less failure says how far reading got
- **WHEN** a v0 document's line 4 reads `  x: "\U00110000"`, a double-quoted escape past the last Unicode
  code point, and lines 1 to 3 are valid
- **THEN** loading fails with the parse error naming the file and the reader's reason, and stating that
  reading got as far as line 4

#### Scenario: A document nested too deeply is named as such
- **WHEN** a v0 document sets `title` to a flow sequence nested 250 levels deep
- **THEN** loading fails with the parse error naming the file, saying the document is nested too deeply to
  load and keeping the reader's reason, and states no line number

#### Scenario: A valid document is unaffected
- **WHEN** a v0 document with no syntax error is loaded
- **THEN** it loads exactly as before, with no re-reading and no change to its fingerprint or output
