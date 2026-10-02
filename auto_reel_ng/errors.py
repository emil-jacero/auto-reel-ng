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


class FfmpegTimeoutError(FfmpegError):
    """A bounded ffmpeg/ffprobe command did not exit within its time bound.

    The child process was killed. The message names the bound and the command.
    """


class FfmpegStalledError(FfmpegError):
    """A progress-streaming ffmpeg run made no progress within its stall limit.

    The child process was killed. The message names how long the output time did not
    advance, the limit, the executed command and the stderr captured so far. A distinct
    type so a caller that retries on the failure's text (the software-decode retry) can
    tell a hang from a failure: retrying a stall would only double the wait.
    """


class FfmpegCancelledError(FfmpegError):
    """A progress-streaming ffmpeg run was stopped because its cancel check reported true.

    The child process was killed. Distinct from a failed command so the caller can end the
    work as canceled rather than failed (the render layer turns it into
    :class:`RenderCancelledError`; the layers below may not import that one).
    """


class FfmpegVersionError(FfmpegError):
    """The resolved ffmpeg is older than the required minimum or unparseable."""


class ProbeError(EngineError):
    """A media file could not be probed into trustworthy metadata.

    Raised for missing/empty files, files with no video stream, unparseable
    ffprobe output, or implausible values. The engine never fabricates metadata;
    it raises this instead.
    """


class MissingClipsError(EngineError):
    """Clips an event's ``reel.yaml`` references are absent from its folder.

    Raised by the shared build path before any probe, naming every missing clip by its
    identity (its path relative to the event folder) and the fix, so the CLI line and a
    worker job's error are one text with no machine path in it.
    """


class OutputCollisionError(EngineError):
    """A claimed job's output path is also written by another event or another running job.

    Raised by the worker at claim time (D-9), before anything is written. The message is
    the one wording of the refusal, naming the shared output path and the other claimant.
    """


class ClaimedMovieError(EngineError):
    """A render would replace a movie another event's render manifest still records.

    Raised before anything is written, unless the render is forced, naming the file and the
    claiming event(s) (D-9); the one wording is
    :func:`~auto_reel_ng.render.claims.claimed_movie_message`.
    """


class AccelError(EngineError):
    """Hardware-acceleration capability detection or selection failed.

    Raised when an explicit accelerator/device override cannot be satisfied, or
    when capability detection cannot be completed at all. Note that a *missing*
    hardware path is never an error on its own: the CPU profile is always usable,
    so detection degrades to it rather than raising.
    """


class RenderError(EngineError):
    """A movie could not be rendered from its :class:`RenderPlan`.

    Raised when a segment cannot be normalized, an unknown decorator is named, a
    requested codec has no usable encoder, or a produced file fails its post-render
    verification. The engine never silently drops a clip or substitutes a
    placeholder; it raises this instead, naming the offending segment/output.
    """


class TitleCardError(RenderError):
    """A title card could not be configured or rendered.

    Raised for a malformed ``look.title_card`` value, an unknown producer key, or
    a Cairo/Pango renderer that is unavailable on the host. The engine never
    renders a card with a guessed value; it raises this instead, naming the field
    or producer at fault.
    """


class FontResolutionError(TitleCardError):
    """A configured font family did not resolve through fontconfig.

    Pango would silently substitute a different family; the engine refuses that
    and raises instead, naming the requested family and the bundled default, so an
    operator never gets a card in an unintended typeface without being told.
    """


class RenderVerificationError(RenderError):
    """A produced movie file did not match its target spec on re-probe.

    A stream-copy concat can mux at exit 0 yet produce a player-broken
    (variable-resolution/aspect) file; this is raised when the re-probe catches
    that, rather than reporting a broken render as success.
    """


class RenderCancelledError(RenderError):
    """A render was stopped by a cooperative cancel request.

    Raised when ``RenderOptions.should_cancel`` reports true, either at a segment
    boundary (job-scheduler, D-S6) or while a segment is being encoded, where ffmpeg
    is killed and the runtime's cancellation error is turned into this one. The caller
    distinguishes this from a genuine failure and transitions the job to ``canceled``
    rather than ``failed``.
    """


class AnalysisError(EngineError):
    """A clip could not be analyzed for black/white/freeze spans.

    Raised when an ffmpeg detection pass exits non-zero or a clip is undecodable.
    Consistent with the engine-wide fail-loud rule, the analysis pass never returns
    a fabricated or empty result that hides the failure; it raises this instead,
    naming the offending clip.
    """


class ThumbnailError(EngineError):
    """A clip could not give a thumbnail (D-11).

    Raised when the clip cannot be statted, its probe fails, the probe reports no
    usable duration, ffmpeg produces no frame at the requested time, or the probe or
    the extraction does not finish within its time bound. The engine
    makes exactly one attempt and never substitutes another timestamp or a
    placeholder. The message is ``<clip>: <reason>``; ``reason`` carries the cause
    without the clip's path, for a caller that names the clip itself (the CLI).
    """

    def __init__(self, clip: str, reason: str) -> None:
        super().__init__(f"{clip}: {reason}")
        self.clip = clip
        self.reason = reason


class ThumbnailCacheError(EngineError):
    """The thumbnail cache directory could not be created, read or written (D-11).

    Deliberately a sibling of :class:`ThumbnailError`, not a subclass: it is not a
    property of any one clip, so the CLI stops on it instead of reporting it
    against every clip. The message names the directory.
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


class PersistenceError(EngineError):
    """The persistence layer (connection, schema, or job store) rejected an operation."""


class IllegalJobTransitionError(PersistenceError):
    """A job was transitioned to a terminal state from a status other than ``running``.

    The job-store convention distinguishes rejection from silent no-op: an illegal
    transition raises this (the caller made a wrong assumption about job state),
    while e.g. a progress update on a non-running job is silently ignored (the
    caller's information may simply be stale).
    """


class EventMetadataError(ReelError):
    """An event's resolved metadata lacks a real date or a title, or is dated in the future.

    Raised at the project-level entry points (scan, render, enqueue, adopt-renders,
    the worker, the events reads), never by the loaders. The message names the
    event, the reason (the folder name's stated problem when the field was expected
    from it) and the fix; ``reason`` carries the message without the event name.
    """

    def __init__(self, event_name: str, reason: str) -> None:
        super().__init__(f"{event_name}: {reason}")
        self.event_name = event_name
        self.reason = reason
