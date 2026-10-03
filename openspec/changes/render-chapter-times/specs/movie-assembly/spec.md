## ADDED Requirements

### Requirement: Chapter times are recorded from the same measured timeline
After a render has been verified and finalized, the engine SHALL record in the render manifest the chapter
times of the movie it wrote: for each chapter, in movie order, its name, its start and end in integer
milliseconds, and the span of its title card. The times SHALL be computed from the measured durations of the
segments that were concatenated (the same values that produce the `[CHAPTER]` markers muxed into the movie),
by the same boundary arithmetic, so each recorded start and end equals the corresponding marker's START and END
in the movie's 1/1000 timebase, and the first chapter starts at 0, each next chapter starts where the previous
one ended, and the last chapter ends at the sum of the chapter durations. The title-card span SHALL start at the
chapter's start plus the measured durations of the chapter's segments before the card, and end at the chapter's
start plus those durations and the card segment's own measured duration, each rounded to milliseconds once from
the exact sum; so it lies inside its chapter and is within 1 ms of the card's measured duration. A chapter with
no title-card segment SHALL record `null`. The engine SHALL NOT use planned or nominal durations for any recorded
time. Recording SHALL NOT change the movie: the same inputs SHALL produce the same movie bytes with or without
the record.

#### Scenario: Two chapters, one trimmed
- **WHEN** a movie of two chapters is assembled where the first chapter's only clip has a cut, so its measured
  segments are 1.0 s and 0.5 s, and the second chapter's clip measures 2.0 s
- **THEN** the manifest records `[{start 0, end 1500}, {start 1500, end 3500}]` in milliseconds, and the
  movie's `[CHAPTER]` markers read back by ffprobe have the same four numbers

#### Scenario: Measured, not nominal
- **WHEN** a chapter's clip is nominally 1.0 s but its measured intermediate is 0.967 s
- **THEN** the recorded end of that chapter is 967, the same as its marker, not 1000

#### Scenario: A title card inside its chapter
- **WHEN** a chapter that begins with a 3.0 s title card followed by a 1.0 s clip is assembled as the second
  of two chapters, after a 2.0 s first chapter
- **THEN** the second chapter is recorded as start 2000, end 6000, and its title-card span as start 2000, end
  5000, and the first chapter's title-card span is `null`

#### Scenario: A title card that is not the chapter's first segment
- **WHEN** a chapter's title card was placed before its title clip, which is its second clip, and the first
  clip measures 1.0 s
- **THEN** the title-card span starts 1000 ms after the chapter's start, and ends inside the chapter

#### Scenario: Stream-copied segments are measured too
- **WHEN** every segment of the movie is copy-eligible and joined by stream copy
- **THEN** the recorded chapter times come from the measured durations of those source segments, as for a
  re-encoded set

#### Scenario: The last chapter ends where the movie ends
- **WHEN** a real two-chapter movie is rendered from small synthetic clips and probed
- **THEN** the last recorded end, in seconds, differs from the movie's probed duration by less than one frame
  period of the target frame rate

#### Scenario: A failed or skipped render records nothing
- **WHEN** a render fails verification, is skipped because the output exists, or is a dry run
- **THEN** no chapter times are written, and a previous manifest, if any, keeps its own
