## MODIFIED Requirements

### Requirement: Thumbnails are cached outside the library

A thumbnail SHALL be stored as `<key>.jpg` in the thumbnail cache directory. `<key>` SHALL be the SHA-256
hex digest over all of:

- the clip's file name, with symlinks followed, so it is the name of the file itself and not of a link to it,
  and not the directory that holds it
- its size in bytes
- its modification time in nanoseconds
- the position
- the box
- a thumbnail format version that the engine bumps whenever extraction changes its output

A requested thumbnail whose file already exists SHALL be returned as it is, without running ffprobe or
ffmpeg. A clip whose size, modification time or file name changed SHALL get a new key and therefore a new
thumbnail. A clip that is moved or copied with its size and modification time preserved, or whose library is
mounted at another path, SHALL keep the key it had, so it does not get a new thumbnail. Two different files
that have the same name, size and modification time share a key and so a thumbnail: the directory is not
part of what tells clips apart.
The file SHALL be written atomically:

1. into a uniquely named temporary file in the cache directory
2. flushed to disk
3. renamed to `<key>.jpg`

A killed or failed extraction SHALL therefore never leave a partial `<key>.jpg`. The system SHALL:

- write no thumbnail state into the library, `reel.yaml` or the database
- create the cache directory when it is absent
- evict nothing, so a thumbnail file whose key no longer occurs, such as one written under an earlier format
  version, stays in the cache directory unread

A cache directory that cannot be created, read or written SHALL be reported with a typed cache error,
naming the directory. That error SHALL be distinct from a clip's thumbnail error.

#### Scenario: A second request is served from the cache
- **WHEN** the thumbnail of `s1710002.mp4` in `2024-06-27 - Grillning med grannar` has been generated, and it
  is requested again with the same position
- **THEN** the same file is returned, and neither ffprobe nor ffmpeg runs

#### Scenario: A changed clip gets a new thumbnail
- **WHEN** a clip's modification time changes after its thumbnail was generated, and its thumbnail is
  requested again
- **THEN** a new `<key>.jpg` is generated, and the earlier file is left in place

#### Scenario: A clip linked into several events shares one thumbnail
- **WHEN** `s1710001.mp4` in `2024-06-27 - Grillning med grannar` and `s1710001.mp4` in
  `2024-08-20 - Två kapitel - Tjörn` are symlinks to the same file, and their thumbnails are requested one
  after the other
- **THEN** both requests resolve to the same `<key>.jpg`, and ffmpeg runs only for the first

#### Scenario: A library copied or remounted elsewhere keeps its thumbnails
- **WHEN** the thumbnails of the clips in `2024-06-27 - Grillning med grannar` have been generated, and the
  library is then copied with `cp -a` to another directory, or mounted at another path, so that every clip
  keeps its size and modification time
- **THEN** each clip's thumbnail is requested at the new location with the same `<key>.jpg` as before, and
  neither ffprobe nor ffmpeg runs

#### Scenario: A renamed clip gets a new thumbnail
- **WHEN** `s1710001.mp4` is renamed to `s1710009.mp4` with its size and modification time kept, and its
  thumbnail is requested
- **THEN** a new `<key>.jpg` is generated, and the earlier file is left in place

#### Scenario: A thumbnail written under an earlier format version is not read
- **WHEN** the cache directory holds `<key>.jpg` files written under the previous thumbnail format version,
  and a thumbnail is requested after the engine's version was bumped
- **THEN** the thumbnail is generated under a new key, and the earlier files are left in place and unread

#### Scenario: An interrupted extraction leaves no thumbnail
- **WHEN** the extraction process is killed before it finishes
- **THEN** no `<key>.jpg` exists for that clip, and the next request generates it

#### Scenario: Two generations of one thumbnail at once
- **WHEN** two callers, such as `auto-reel thumbs` and the service, generate the thumbnail of the same clip
  at the same time
- **THEN** both get the same `<key>.jpg`, which is a complete JPEG, and no temporary file remains

#### Scenario: Nothing is written into the library
- **WHEN** thumbnails are generated for every clip of the dev library with the default cache directory
- **THEN** no file under the project root is created or modified, and each event's `reel.yaml` is
  byte-for-byte unchanged

#### Scenario: An unwritable cache directory is its own error
- **WHEN** the cache directory is on a read-only filesystem, and a thumbnail that is not yet cached is
  requested
- **THEN** a cache error naming the directory is raised, not a thumbnail error for the clip
