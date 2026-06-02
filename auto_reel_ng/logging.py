"""Contextual logging helper carried over from auto-reel.

Provides ``ContextVar``-based thread/movie/clip tags so log lines emitted during
parallel processing identify which worker, movie, and clip they belong to. The
:class:`LoggingContext` context manager sets and restores those tags.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Optional, Union

# Context variables tracking the active processing context.
movie_context: ContextVar[Optional[str]] = ContextVar("movie_context", default=None)
clip_context: ContextVar[Optional[str]] = ContextVar("clip_context", default=None)
thread_context: ContextVar[Optional[str]] = ContextVar("thread_context", default=None)


class ContextualFormatter(logging.Formatter):
    """Formatter that prefixes records with the active movie/clip/thread tags."""

    def format(self, record: logging.LogRecord) -> str:
        """Inject the active context tags into the message, then format."""
        parts = []
        movie = movie_context.get()
        if movie:
            parts.append(f"movie={movie}")
        clip = clip_context.get()
        if clip:
            parts.append(f"clip={clip}")
        thread = thread_context.get()
        if thread:
            parts.append(f"thread={thread}")

        if parts:
            context_str = " ".join(parts)
            record.msg = f"[{context_str}] {record.getMessage()}"
            record.args = ()

        return super().format(record)


def configure_logging(level: Union[str, int] = logging.INFO) -> None:
    """Configure the root logger with the contextual formatter on stdout."""
    if isinstance(level, str):
        level = getattr(logging, level.upper())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        ContextualFormatter(
            fmt="%(asctime)s.%(msecs)03d %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(handler)


class LoggingContext:
    """Context manager that sets movie/clip/thread tags and restores them on exit."""

    def __init__(
        self,
        movie: Optional[str] = None,
        clip: Optional[str] = None,
        thread: Optional[str] = None,
    ) -> None:
        self.movie = movie
        self.clip = clip
        self.thread = thread
        self._prev_movie: Optional[str] = None
        self._prev_clip: Optional[str] = None
        self._prev_thread: Optional[str] = None

    def __enter__(self) -> "LoggingContext":
        self._prev_movie = movie_context.get()
        self._prev_clip = clip_context.get()
        self._prev_thread = thread_context.get()
        if self.movie is not None:
            movie_context.set(self.movie)
        if self.clip is not None:
            clip_context.set(self.clip)
        if self.thread is not None:
            thread_context.set(self.thread)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        movie_context.set(self._prev_movie)
        clip_context.set(self._prev_clip)
        thread_context.set(self._prev_thread)
