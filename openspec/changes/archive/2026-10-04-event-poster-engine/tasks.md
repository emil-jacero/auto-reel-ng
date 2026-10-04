## 1. reel/

- [x] 1.1 Parse and validate `poster` (`schema.py`, `document.py`): typed `Poster(clip, at)`, errors naming `poster.<key>`, editorial hash only when present. Test: the load, zero, negative, missing-key, unknown-key, non-finite and boolean `at` cases, and the unchanged hash of a poster-less document.
- [x] 1.2 Carry `poster` in every writer (`writer.py`, editorial write): byte-stable round trip with comments, typed write position, absent/`null` keeps, `{}` removes, key-by-key merge, validation before writing. Test: each scenario of "The poster is carried by every writer", including the untouched file on a refused write.

## 2. render/

- [x] 2.1 `render/poster.py`: `resolve_poster` (explicit / default / fallback-with-warning / `PosterFrameError` past the end, new typed error in `errors.py`) and pure `poster_args` (rotation chain, SAR, HDR tone-map, fit and pad to target, `-q:v 2`). Test: golden argument strings for plain, rotated-with-SAR and HDR clips; resolution cases with a captured warning.
- [x] 2.2 `extract_poster` through `FfmpegRuntime` and the verified JPEG check. Test (`has_ffmpeg`): a rotated clip with non-1:1 SAR yields an upright JPEG of the target size; a time with no frame raises the typed error.
- [x] 2.3 Embed the cover and extend `verify_output` (`verify.py`): ignore `attached_pic`, require exactly one mjpeg cover when expected; confirm `probe_media` and movie facts pick the real video stream. Test (`has_ffmpeg`): a covered movie verifies, a doubled or missing cover raises, facts equal the uncovered movie's.
- [x] 2.4 Atomic finalize in `orchestrator.py`: poster `.part` → verify → embed → rename poster then movie, then manifest; no poster for no played clip. Test (`has_ffmpeg`): an end-to-end render writes both files and an injected kill before the movie rename leaves neither new file nor manifest; force and re-run replace both.

## 3. staleness/ and claims

- [x] 3.1 Manifest `poster` field, the sidecar claim in `render/claims.py`, the `output` verdict for a missing sidecar (`manifest.py`, `gate.py`). Test: the field's fail-open reads, a deleted sidecar is stale with reason `output`, an old manifest stays fresh, another event's recorded poster refuses an unforced render.
- [x] 3.2 `prune-renamed` lists and deletes the sidecar with its movie (`cli/prune.py`). Test: both deleted with `--yes`, an orphan sidecar not listed, a claimed sidecar kept.
- [x] 3.3 Bump `RENDER_GRAPH_VERSION` to 11 with its history line, naming the cover and the sidecar. Test: the fingerprint of an unchanged event differs from version 10's and a poster edit changes the editorial component.

## 4. Verification and docs

- [x] 4.1 Real-browser check from the scratchpad: the covered movie plays with audio through the existing media endpoint in Chrome (`localhost/playback-research:chrome`) and Firefox (`localhost/pcm-audio-research:pw163`, confirm version first). Test: a Playwright script asserting `currentTime` advances and `audioTracks`/decoded audio where supported; no repo file.
- [x] 4.2 Update `docs/high-level-design.md`: a new D-26 entry (the poster contract: key, resolution, atomic finalize, claims, version 11), the §4.10 "event poster frames" item marked built, the §6 v2 note, and the `reel.yaml` example in §4. Test: none beyond a read-through; the doc names the same scenario cases as the specs.
- [x] 4.3 Gates: black/isort, mypy, pylint, then the full pytest (podman present, `requires_db` included). Test: the four commands pass.
