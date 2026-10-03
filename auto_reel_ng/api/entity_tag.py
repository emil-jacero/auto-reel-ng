"""The entity tag of a served file, from its ``stat`` (D-15).

``size`` and the nanosecond mtime, in hex: both change on every rewrite a camera, a copy or a
render makes, and neither needs the file's bytes. The media routes send the quoted form as the
``ETag`` (:attr:`~auto_reel_ng.api.media.MediaFile.etag`), and the event detail reports the
unquoted form as a proxy's ``version``, so a client can put it in the media URL as ``v``. It
lives here, below both, because ``media`` imports the events read model and the read model
cannot import ``media`` back; a test pins the two spellings together.
"""

from __future__ import annotations

import os


def entity_tag(info: os.stat_result) -> str:
    """The unquoted tag ``"{size:x}-{mtime_ns:x}"`` of a file with the stat ``info``."""
    return f"{info.st_size:x}-{info.st_mtime_ns:x}"


__all__ = ["entity_tag"]
