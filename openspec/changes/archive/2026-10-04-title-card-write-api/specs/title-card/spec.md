## ADDED Requirements

### Requirement: A card image can be produced in memory for a given size
The engine SHALL provide the card renderer's output as PNG **bytes** for a title-card configuration, a card's
content and an explicit width and height, without a destination file, an ffmpeg invocation, or a target spec
derived from probed clips. The file-writing entry point a render uses SHALL produce exactly the bytes this one
produces for the same configuration, content and size, so a preview and a render cannot differ. A background
opacity of zero SHALL leave the image fully transparent where there is no text. A font family that does not
resolve, or an unavailable drawing backend, SHALL fail loud with the same typed errors as the file entry point.

#### Scenario: Bytes and file agree
- **WHEN** the same configuration and content are rendered once to bytes at 1920x1080 and once to a file at a
  1920x1080 target
- **THEN** the file's bytes equal the returned bytes

#### Scenario: A zero-opacity background is transparent
- **WHEN** a card is rendered to bytes with a background opacity of zero
- **THEN** a pixel away from the text is fully transparent and a pixel in the text is not

#### Scenario: An unresolvable family fails loud
- **WHEN** the configuration names a family fontconfig does not resolve
- **THEN** the in-memory entry point raises the same typed error naming the family as the file entry point
