"""The ``auto-reel`` headless CLI: argument parsing + engine wiring (HLD §4.11)."""

from __future__ import annotations

from .main import build_parser, main

__all__ = ["build_parser", "main"]
