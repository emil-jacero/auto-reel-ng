"""The FastAPI service (§4.9, phase 7c): REST + WebSocket over the existing engine.

A deliberately thin layer — every route maps to an operation the CLI already
reaches (:mod:`auto_reel_ng.cli.commands`); no scan, render, or job logic lives
here. See ``auto_reel_ng/api/app.py`` for the application factory and
``auto_reel_ng/api/settings.py`` for configuration resolution.
"""

from __future__ import annotations
