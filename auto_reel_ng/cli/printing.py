"""Output helpers shared by the cache-filling subcommands (``thumbs``, ``proxies``).

Every printed line is made printable first, so a file name that is not valid UTF-8 shows its
raw bytes as ``\\xNN`` instead of ending the run.
"""

from __future__ import annotations


def emit(line: str) -> None:
    """Print ``line`` made printable (see :func:`printable`)."""
    print(printable(line))


def printable(text: str) -> str:
    """``text`` with any byte of a non-UTF-8 file name shown as ``\\xNN``.

    Such names reach Python as surrogate escapes, which a UTF-8 stdout refuses.
    """
    try:
        return text.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
    except UnicodeEncodeError:  # a surrogate that no file name produced
        return text.encode("utf-8", "backslashreplace").decode("utf-8")


def os_reason(exc: OSError) -> str:
    """An ``OSError``'s cause without the path it repeats; the ERROR line names it."""
    return exc.strerror or str(exc)


def plural(count: int, noun: str) -> str:
    """``1 clip`` / ``2 clips``."""
    return f"{count} {noun}{'' if count == 1 else 's'}"


__all__ = ["emit", "os_reason", "plural", "printable"]
