"""Typed error hierarchy for the auto-reel-ng engine.

All engine-raised exceptions derive from :class:`EngineError`, so callers can catch
the whole family with a single ``except EngineError``. The fail-loud guarantee of the
probe layer depends on these being raised rather than swallowed.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base class for every error raised by the auto-reel-ng engine."""


class FfmpegError(EngineError):
    """An ffmpeg/ffprobe binary could not be found or a command failed.

    When raised for a failed command, the message carries the exit code, the
    executed command, and the captured stderr.
    """


class FfmpegVersionError(FfmpegError):
    """The resolved ffmpeg is older than the required minimum or unparseable."""


class ProbeError(EngineError):
    """A media file could not be probed into trustworthy metadata.

    Raised for missing/empty files, files with no video stream, unparseable
    ffprobe output, or implausible values. The engine never fabricates metadata;
    it raises this instead.
    """


class AccelError(EngineError):
    """Hardware-acceleration capability detection or selection failed.

    Raised when an explicit accelerator/device override cannot be satisfied, or
    when capability detection cannot be completed at all. Note that a *missing*
    hardware path is never an error on its own: the CPU profile is always usable,
    so detection degrades to it rather than raising.
    """


class ReelError(EngineError):
    """A ``reel.yaml`` editorial document could not be parsed, validated, or applied.

    Raised for malformed YAML, an unsupported ``version``, an invalid trim span,
    a dangling chapter reference, a duplicate clip identity, an unmappable legacy
    field, or a reconcile that finds a referenced clip missing from disk. The
    engine never fabricates or silently drops editorial data; it raises this
    instead. Errors name the offending location (clip identity, chapter, field).
    """


class ReelParseError(ReelError):
    """A ``reel.yaml`` document could not be loaded or validated into the v0 model.

    Covers malformed YAML, unsupported versions, structural type errors, invalid
    trims, negative times, dangling chapter references, and duplicate identities.
    """


class ReelImportError(ReelError):
    """An auto-reel legacy document could not be faithfully imported to v0.

    Raised when a legacy field cannot be mapped into the v0 schema; the importer
    reports what it could not represent rather than dropping it silently.
    """


class ReconcileError(ReelError):
    """A disk-against-document reconcile found an inconsistency that must surface.

    Raised by apply-operations on invalid input (e.g. adding a clip to a chapter
    that does not exist, or adding a clip already referenced). MISSING clips are
    reported through the reconcile result, not raised.
    """
